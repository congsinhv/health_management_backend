"""
Q&A API endpoints - Main API proxy to Chat AI service.
"""

import asyncio
import json
import logging
import time
from typing import Dict, List

try:
    from typing import Annotated
except ImportError:
    # For Python < 3.9
    from typing_extensions import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse

from app.auth.dependencies import get_current_active_user
from app.middleware.rate_limit import get_rate_limiter
from app.schemas.qa import QuestionRequest, QuestionResponse, QAHealthResponse
from app.schemas.user import UserInDB
from app.core.error_context import ErrorContext
from app.core.shared.exceptions import (
    ValidationException,
    ServiceUnavailableException,
    RateLimitException,
    QAModelNotLoadedException,
    QAServiceException,
)
from app.utils.metrics import (
    StructuredLogger,
    end_sse_connection,
    increment_sse_events,
    record_sse_error,
    start_sse_connection,
)
from app.clients.chat_ai_client import get_chat_ai_client
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/ask", response_model=QuestionResponse, status_code=status.HTTP_200_OK)
async def ask_question(
    request: Request,
    question_data: QuestionRequest,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
):
    """
    Ask a health-related question and get answers (proxied to Chat AI service).

    Requires authentication. Users must be logged in to ask questions.

    - **question**: The question to ask (1-500 characters)
    - **threshold**: Minimum similarity score (0.0-1.0)
    - **top_k**: Maximum number of results to return (1-20)

    Returns:
        QuestionResponse with answers grouped by field and AI summary
    """
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "ask_question")
    ErrorContext.add_context("operation", "qa_proxy")
    ErrorContext.add_context("question_length", len(question_data.question))

    with ErrorContext(
        "ask_question",
        {
            "user_id": current_user.id,
            "threshold": question_data.threshold,
            "top_k": question_data.top_k,
            "question_preview": question_data.question[:100] + "..."
            if len(question_data.question) > 100
            else question_data.question,
        },
    ):
        # Get Chat AI client
        chat_ai_client = await get_chat_ai_client()

        if chat_ai_client is None:
            raise ServiceUnavailableException(
                "Chat AI service is not configured or available",
                details={"service": "chat_ai", "configured": bool(settings.chat_ai_service_url)}
            )

        # Proxy question to Chat AI service
        try:
            result = await chat_ai_client.ask_question(
                question=question_data.question,
                threshold=question_data.threshold,
                top_k=question_data.top_k,
            )

            ErrorContext.add_context("proxy_success", True)
            return QuestionResponse(**result)

        except Exception as e:
            ErrorContext.add_context("proxy_error", str(e))
            logger.error(f"Failed to proxy question to Chat AI service: {e}")
            raise ServiceUnavailableException(
                f"Chat AI service is temporarily unavailable: {str(e)}",
                details={"service": "chat_ai", "error": str(e)}
            )


@router.post(
    "/ask-stream",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask health question with streaming response",
    description="Stream AI-generated answer progressively via Server-Sent Events",
)
async def ask_question_stream(
    request: Request,
    question_data: QuestionRequest,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
):
    """
    Stream Q&A response with progressive events (proxied to Chat AI service):
    1. QUESTION_RECEIVED - Immediate acknowledgment
    2. ANSWERS_FOUND - Semantic search results
    3. SUMMARY_CHUNK - Token-by-token AI summary
    4. STREAM_COMPLETE - Final event with metadata
    """
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "ask_question_stream")
    ErrorContext.add_context("operation", "qa_proxy_streaming")
    ErrorContext.add_context("question_length", len(question_data.question))

    # Rate limiting
    rate_limiter = get_rate_limiter()
    if rate_limiter:
        if not await rate_limiter.check_connection_limit(str(current_user.id)):
            StructuredLogger.log_rate_limit(str(current_user.id), "connection")
            raise RateLimitException("Too many concurrent connections")

        if not await rate_limiter.check_request_rate(str(current_user.id)):
            StructuredLogger.log_rate_limit(str(current_user.id), "request_rate")
            raise RateLimitException("Too many requests")

        await rate_limiter.register_connection(str(current_user.id))
        await rate_limiter.register_request(str(current_user.id))

    # Get Chat AI client
    chat_ai_client = await get_chat_ai_client()

    if chat_ai_client is None:
        raise ServiceUnavailableException(
            "Chat AI service is not configured or available",
            details={"service": "chat_ai", "configured": bool(settings.chat_ai_service_url)}
        )

    # Start monitoring
    start_time = time.time()
    event_count = 0
    start_sse_connection()
    StructuredLogger.log_connection_start(str(current_user.id), question_data.question)

    ErrorContext.add_context("streaming", True)
    ErrorContext.add_context(
        "question_preview",
        question_data.question[:100] + "..."
        if len(question_data.question) > 100
        else question_data.question,
    )

    async def event_generator():
        """Generate SSE events with disconnect detection and monitoring."""
        nonlocal event_count
        try:
            last_heartbeat = asyncio.get_event_loop().time()
            heartbeat_interval = 30  # seconds

            async for sse_event in chat_ai_client.stream_ask_question(
                question=question_data.question,
                threshold=question_data.threshold,
                top_k=question_data.top_k,
            ):
                # Check client disconnect
                if await request.is_disconnected():
                    duration = time.time() - start_time
                    ErrorContext.add_context("client_disconnected", True)
                    ErrorContext.add_context("stream_duration", duration)
                    StructuredLogger.log_disconnect(str(current_user.id), duration)
                    break

                # Yield event from Chat AI service
                yield sse_event
                event_count += 1

                # Track event type metrics
                if "event_type" in sse_event:
                    try:
                        event_type = sse_event.split('"event_type":"')[1].split('"')[0]
                        increment_sse_events(event_type)
                        ErrorContext.add_context("last_event_type", event_type)
                    except (IndexError, AttributeError):
                        pass

                # Send heartbeat if idle
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat > heartbeat_interval:
                    yield ":\n\n"  # SSE comment (keep-alive)
                    last_heartbeat = current_time

            ErrorContext.add_context("proxy_success", True)

        except Exception as e:
            duration = time.time() - start_time
            ErrorContext.add_context("stream_error", str(e))
            ErrorContext.add_context("stream_duration", duration)
            ErrorContext.add_context("proxy_error", str(e))
            StructuredLogger.log_error(str(current_user.id), str(e), "streaming_error")
            record_sse_error("streaming_error", str(current_user.id))

            error_event = {
                "event": "error",
                "data": json.dumps(
                    {"error": "Chat AI service streaming error", "code": "service_unavailable"}
                ),
            }
            yield f"event: {error_event['event']}\ndata: {error_event['data']}\n\n"

        finally:
            # Cleanup and final metrics
            duration = time.time() - start_time
            end_sse_connection(duration)
            ErrorContext.add_context("stream_completed", True)
            ErrorContext.add_context("stream_duration", duration)
            ErrorContext.add_context("event_count", event_count)
            StructuredLogger.log_connection_end(
                str(current_user.id), duration, event_count
            )

            if rate_limiter:
                await rate_limiter.unregister_connection(str(current_user.id))

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",  # Disable Nginx buffering
        "Connection": "keep-alive",
    }

    return StreamingResponse(
        event_generator(), media_type="text/event-stream", headers=headers
    )


@router.get("/health", response_model=QAHealthResponse, status_code=status.HTTP_200_OK)
async def qa_health_check(request: Request):
    """
    Check Q&A service health status (proxied to Chat AI service).

    Public endpoint - no authentication required.

    Returns:
        Status information about the Q&A service
    """
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "qa_health_check")
    ErrorContext.add_context("operation", "health_check_proxy")

    with ErrorContext("qa_health_check"):
        # Get Chat AI client
        chat_ai_client = await get_chat_ai_client()

        if chat_ai_client is None:
            return QAHealthResponse(
                status="unavailable",
                model_loaded=False,
                embeddings_loaded=False,
                streaming_enabled=False,
                openai_configured=False,
                message="Chat AI service is not configured",
            )

        # Proxy health check to Chat AI service
        try:
            health_response = await chat_ai_client.health_check()

            # Map health check response to QAHealthResponse
            return QAHealthResponse(
                status=health_response.get("status", "unknown"),
                model_loaded=health_response.get("model_loaded", False),
                embeddings_loaded=health_response.get("embeddings_loaded", False),
                streaming_enabled=health_response.get("streaming_enabled", False),
                openai_configured=health_response.get("openai_configured", False),
                message=health_response.get("message", "Health check completed"),
            )

        except Exception as e:
            ErrorContext.add_context("health_check_error", str(e))
            logger.error(f"Failed to proxy health check to Chat AI service: {e}")
            return QAHealthResponse(
                status="unhealthy",
                model_loaded=False,
                embeddings_loaded=False,
                streaming_enabled=False,
                openai_configured=False,
                message=f"Chat AI service health check failed: {str(e)}",
            )
