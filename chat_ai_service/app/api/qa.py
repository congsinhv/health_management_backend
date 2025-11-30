"""
Q&A API endpoints for standalone Chat AI microservice.
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

from fastapi import APIRouter, Depends, Request, status, FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from app.schemas.qa import QuestionRequest, QuestionResponse, QAHealthResponse
from app.core.shared.exceptions import (
    ValidationException,
    ServiceUnavailableException,
    RateLimitException,
    QAModelNotLoadedException,
    QAServiceException,
    AIServiceException,
    OpenAIException,
)
from app.core.error_context import ErrorContext
from app.services.qa import QAService
from app.config import settings

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


def create_qa_app() -> FastAPI:
    """Create FastAPI application for QA microservice."""
    app = FastAPI(
        title="VHealth Chat AI Service",
        description="Microservice for health-related Q&A with AI summarization",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(router, prefix="/api/v1/qa")

    # Initialize QA service on startup
    @app.on_event("startup")
    async def startup_event():
        """Initialize QA service on startup."""
        try:
            from app.services.qa import create_qa_service

            app.state.qa_service = create_qa_service(settings)

            # Initialize the service
            await app.state.qa_service.initialize()
            logger.info("QA service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize QA service: {e}")
            app.state.qa_service = None

    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown."""
        if hasattr(app.state, "qa_service") and app.state.qa_service:
            try:
                if hasattr(app.state.qa_service, "ai_summarizer"):
                    await app.state.qa_service.ai_summarizer.close()
                logger.info("QA service cleanup completed")
            except Exception as e:
                logger.error(f"Error during QA service cleanup: {e}")

    return app


@router.post("/ask", response_model=QuestionResponse, status_code=status.HTTP_200_OK)
async def ask_question(
    request: Request,
    question_data: QuestionRequest,
):
    """
    Ask a health-related question and get answers.

    This endpoint is designed for service-to-service communication
    with authentication handled at the service level.

    - **question**: The question to ask (1-500 characters)
    - **threshold**: Minimum similarity score (0.0-1.0)
    - **top_k**: Maximum number of results to return (1-20)

    Returns:
        QuestionResponse with answers grouped by field and AI summary
    """
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "ask_question")
    ErrorContext.add_context("operation", "qa_inference")
    ErrorContext.add_context("question_length", len(question_data.question))

    with ErrorContext.operation(
        "ask_question",
        {
            "threshold": question_data.threshold,
            "top_k": question_data.top_k,
            "question_preview": question_data.question[:100] + "..."
            if len(question_data.question) > 100
            else question_data.question,
        },
    ):
        # Get QA service from app state
        qa_service = request.app.state.qa_service

        if qa_service is None:
            raise ServiceUnavailableException("Q&A service is not available")

        # Validate input
        if not question_data.question or not question_data.question.strip():
            raise ValidationException("Question cannot be empty")

        # Process question using non-streaming method (convert from streaming)
        result = await _process_question_non_streaming(
            qa_service,
            question_data.question,
            question_data.threshold,
            question_data.top_k,
        )

        return QuestionResponse(**result)


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
):
    """
    Stream Q&A response with progressive events:
    1. QUESTION_RECEIVED - Immediate acknowledgment
    2. ANSWERS_FOUND - Semantic search results
    3. SUMMARY_CHUNK - Token-by-token AI summary
    4. STREAM_COMPLETE - Final event with metadata
    """
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "ask_question_stream")
    ErrorContext.add_context("operation", "qa_streaming")
    ErrorContext.add_context("question_length", len(question_data.question))

    qa_service = request.app.state.qa_service
    if not qa_service:
        raise ServiceUnavailableException("Q&A service is not available")

    # Validate input
    if not question_data.question or not question_data.question.strip():
        raise ValidationException("Question cannot be empty")

    # Start monitoring
    start_time = time.time()
    event_count = 0
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

            async for sse_event in qa_service.ask_question_stream(
                question=question_data.question,
                threshold=question_data.threshold,
                top_k=question_data.top_k,
            ):
                # Check client disconnect
                if await request.is_disconnected():
                    duration = time.time() - start_time
                    ErrorContext.add_context("client_disconnected", True)
                    ErrorContext.add_context("stream_duration", duration)
                    break

                # Format as proper SSE event
                if isinstance(sse_event, str):
                    # Simple text chunk
                    yield f'event: summary_chunk\ndata: {{"chunk": {json.dumps(sse_event)}, "token_count": 1}}\n\n'
                    event_count += 1
                else:
                    # Event object
                    yield f"event: summary_chunk\ndata: {json.dumps(sse_event)}\n\n"
                    event_count += 1

                # Send heartbeat if idle
                current_time = asyncio.get_event_loop().time()
                if current_time - last_heartbeat > heartbeat_interval:
                    yield ":\n\n"  # SSE comment (keep-alive)
                    last_heartbeat = current_time

        except Exception as e:
            duration = time.time() - start_time
            ErrorContext.add_context("stream_error", str(e))
            ErrorContext.add_context("stream_duration", duration)
            logger.error(f"Streaming error: {e}")

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
            ErrorContext.add_context("stream_completed", True)
            ErrorContext.add_context("stream_duration", duration)
            ErrorContext.add_context("event_count", event_count)

            # Send final event
            complete_event = {
                "event": "stream_complete",
                "data": json.dumps(
                    {
                        "total_tokens": event_count,
                        "duration": duration,
                        "question": question_data.question,
                    }
                ),
            }
            yield f"event: {complete_event['event']}\ndata: {complete_event['data']}\n\n"

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
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "qa_health_check")
    ErrorContext.add_context("operation", "health_check")

    with ErrorContext.operation("qa_health_check"):
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

        health_info = qa_service.get_health_check()

        return QAHealthResponse(
            status=health_info.get("status", "unknown"),
            model_loaded=health_info.get("components", {}).get("model_loaded", False),
            embeddings_loaded=health_info.get("components", {}).get(
                "embeddings_ready", False
            ),
            streaming_enabled=True,  # Always true in this service
            openai_configured=health_info.get("components", {}).get(
                "ai_available", False
            ),
            message="Q&A service is operational"
            if health_info.get("status") == "healthy"
            else "Q&A service issues detected",
        )


@router.get("/status", status_code=status.HTTP_200_OK)
async def qa_service_status(request: Request):
    """
    Get detailed Q&A service status for monitoring.

    Returns comprehensive status information about all service components.

    Returns:
        Detailed status information
    """
    qa_service = request.app.state.qa_service

    if qa_service is None:
        return {
            "service": "chat_ai_service",
            "status": "unavailable",
            "message": "Q&A service is not initialized",
            "timestamp": time.time(),
        }

    return {
        "service": "chat_ai_service",
        **qa_service.get_service_status(),
        "timestamp": time.time(),
    }


async def _process_question_non_streaming(
    qa_service: QAService, question: str, threshold: float, top_k: int
) -> Dict[str, any]:
    """Process question using streaming API and collect results."""
    try:
        # Collect all streaming chunks
        chunks = []
        answers_found = False
        final_summary = ""

        async for chunk in qa_service.ask_question_stream(question, threshold, top_k):
            if isinstance(chunk, str):
                if chunk.startswith("Sorry") or chunk.startswith("Xin lỗi"):
                    return {
                        "question": question,
                        "answers": {},
                        "summary": chunk,
                    }
                chunks.append(chunk)
                answers_found = True

        if not answers_found:
            return {
                "question": question,
                "answers": {},
                "summary": "Tôi không tìm thấy thông tin phù hợp cho câu hỏi của bạn.",
            }

        # Combine all chunks into final summary
        final_summary = "".join(chunks)

        # For now, return empty answers dict as the streaming API focuses on summary
        # In a full implementation, we'd extract the answers from the search results
        return {
            "question": question,
            "answers": {"health": [final_summary]},  # Simplified for streaming
            "summary": final_summary,
        }

    except Exception as e:
        logger.error(f"Error processing question: {e}")
        return {
            "question": question,
            "answers": {},
            "summary": "Xin lỗi, đã xảy ra lỗi khi xử lý câu hỏi của bạn.",
        }
