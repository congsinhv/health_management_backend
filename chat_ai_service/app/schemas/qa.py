"""
Q&A schemas for API requests/responses and SSE events.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# Request/Response Schemas (extracted from qa.py)
class QuestionRequest(BaseModel):
    """Request model for asking questions."""

    question: str = Field(
        ..., min_length=1, max_length=500, description="User question"
    )
    threshold: float = Field(
        default=0.55, ge=0.0, le=1.0, description="Similarity threshold"
    )
    top_k: int = Field(default=7, ge=1, le=20, description="Number of top results")


class QuestionResponse(BaseModel):
    """Response model for question answers."""

    question: str
    answers: Dict[str, List[str]]
    summary: str


# SSE Event Base Schema
class SSEEvent(BaseModel):
    """Base schema for Server-Sent Events."""

    event_type: str
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Specific Event Types
class QuestionReceivedEvent(SSEEvent):
    """Event when question is received."""

    event_type: Literal["question_received"] = "question_received"
    data: Dict[str, str] = Field(..., description="Question data")


class AnswersFoundEvent(SSEEvent):
    """Event when answers are found from semantic search."""

    event_type: Literal["answers_found"] = "answers_found"
    data: Dict[str, Any] = Field(..., description="Answers data with count")


class SummaryChunkEvent(SSEEvent):
    """Event for each chunk of AI summary streaming."""

    event_type: Literal["summary_chunk"] = "summary_chunk"
    data: Dict[str, Any] = Field(..., description="Summary chunk with token count")


class StreamCompleteEvent(SSEEvent):
    """Event when streaming is complete."""

    event_type: Literal["stream_complete"] = "stream_complete"
    data: Dict[str, Any] = Field(..., description="Completion metadata")


class StreamErrorEvent(SSEEvent):
    """Event for streaming errors."""

    event_type: Literal["error"] = "error"
    data: Dict[str, str] = Field(..., description="Error details")


# Health Check Response Schema
class QAHealthResponse(BaseModel):
    """Response model for Q&A health check."""

    status: str
    model_loaded: bool = False
    embeddings_loaded: bool = False
    streaming_enabled: bool = False
    openai_configured: bool = False
    message: str
