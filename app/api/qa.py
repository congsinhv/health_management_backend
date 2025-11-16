"""
Q&A API endpoints.
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

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.auth.dependencies import get_current_active_user
from app.middleware.rate_limit import get_rate_limiter
from app.schemas.qa import QuestionRequest, QuestionResponse, QAHealthResponse
from app.schemas.user import UserInDB
from app.utils.metrics import (
    StructuredLogger,
    end_sse_connection,
    increment_sse_events,
    record_sse_error,
    start_sse_connection,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/ask", response_model=QuestionResponse, status_code=status.HTTP_200_OK)
async def ask_question(
    request: Request,
    question_data: QuestionRequest,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
):
    """
    Ask a health-related question and get answers.

    Requires authentication. Users must be logged in to ask questions.

    - **question**: The question to ask (1-500 characters)
    - **threshold**: Minimum similarity score (0.0-1.0)
    - **top_k**: Maximum number of results to return (1-20)

    Returns:
        QuestionResponse with answers grouped by field and AI summary
    """
    try:
        # Get QA service from app state
        qa_service = request.app.state.qa_service

        if qa_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Q&A service is not available",
            )

        # Process question
        result = qa_service.ask_question(
            user_question=question_data.question,
            threshold=question_data.threshold,
            top_k=question_data.top_k,
        )

        return QuestionResponse(**result)

    except ValueError as e:
        logger.warning(f"Invalid question from user {current_user.email}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except Exception as e:
        logger.error(f"Error processing question: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
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
    Stream Q&A response with progressive events:
    1. QUESTION_RECEIVED - Immediate acknowledgment
    2. ANSWERS_FOUND - Semantic search results
    3. SUMMARY_CHUNK - Token-by-token AI summary
    4. STREAM_COMPLETE - Final event with metadata
    """

    # Rate limiting
    rate_limiter = get_rate_limiter()
    if rate_limiter:
        if not await rate_limiter.check_connection_limit(str(current_user.id)):
            StructuredLogger.log_rate_limit(str(current_user.id), "connection")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many concurrent connections",
                headers={"Retry-After": "60"},
            )

        if not await rate_limiter.check_request_rate(str(current_user.id)):
            StructuredLogger.log_rate_limit(str(current_user.id), "request_rate")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests",
                headers={"Retry-After": "60"},
            )

        await rate_limiter.register_connection(str(current_user.id))
        await rate_limiter.register_request(str(current_user.id))

    qa_service = request.app.state.qa_service
    if not qa_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Q&A service is not available",
        )

    # Start monitoring
    start_time = time.time()
    event_count = 0
    start_sse_connection()
    StructuredLogger.log_connection_start(str(current_user.id), question_data.question)

    async def event_generator():
        """Generate SSE events with disconnect detection and monitoring."""
        nonlocal event_count
        try:
            last_heartbeat = asyncio.get_event_loop().time()
            heartbeat_interval = 30  # seconds

            async for sse_event in qa_service.stream_ask_question(
                question=question_data.question,
                threshold=question_data.threshold,
                top_k=question_data.top_k,
            ):
                # Check client disconnect
                if await request.is_disconnected():
                    duration = time.time() - start_time
                    StructuredLogger.log_disconnect(str(current_user.id), duration)
                    break

                # Yield event
                yield sse_event
                event_count += 1

                # Track event type metrics
                if "event_type" in sse_event:
                    try:
                        event_type = sse_event.split('"event_type":"')[1].split('"')[0]
                        increment_sse_events(event_type)
                    except (IndexError, AttributeError):
                        pass

                # Send heartbeat if idle
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat > heartbeat_interval:
                    yield ":\n\n"  # SSE comment (keep-alive)
                    last_heartbeat = current_time

        except Exception as e:
            duration = time.time() - start_time
            StructuredLogger.log_error(str(current_user.id), str(e), "streaming_error")
            record_sse_error("streaming_error", str(current_user.id))

            error_event = {
                "event": "error",
                "data": json.dumps(
                    {"error": "Internal streaming error", "code": "internal_error"}
                ),
            }
            yield f"event: {error_event['event']}\ndata: {error_event['data']}\n\n"

        finally:
            # Cleanup and final metrics
            duration = time.time() - start_time
            end_sse_connection(duration)
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
    Check Q&A service health status.

    Public endpoint - no authentication required.

    Returns:
        Status information about the Q&A service
    """
    qa_service = request.app.state.qa_service

    if qa_service is None:
        return QAHealthResponse(
            status="unavailable",
            model_loaded=False,
            embeddings_loaded=False,
            streaming_enabled=False,
            openai_configured=False,
            message="Q&A service is not initialized",
        )

    return QAHealthResponse(
        status="healthy",
        model_loaded=qa_service.model is not None,
        embeddings_loaded=qa_service.question_embeddings is not None,
        streaming_enabled=hasattr(qa_service, "stream_ask_question"),
        openai_configured=hasattr(qa_service, "openai_client")
        and qa_service.openai_client is not None,
        message="Q&A service is operational",
    )
