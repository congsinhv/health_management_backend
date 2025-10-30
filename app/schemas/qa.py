"""
Pydantic schemas for Q&A endpoints.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class QuestionRequest(BaseModel):
    """Request model for asking questions."""

    question: str = Field(
        ..., min_length=1, max_length=500, description="User question"
    )
    threshold: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Similarity threshold"
    )
    top_k: Optional[int] = Field(None, ge=1, le=20, description="Number of top results")


class QuestionResponse(BaseModel):
    """Response model for question answers."""

    question: str
    answers: Dict[str, List[str]]
    summary: str
    conversation_id: Optional[int] = None


class ConversationBase(BaseModel):
    """Base conversation model."""

    question: str
    summary: str
    threshold: float
    top_k: int


class ConversationListItem(ConversationBase):
    """Conversation list item model."""

    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetail(ConversationBase):
    """Detailed conversation model."""

    id: int
    user_id: Optional[int]
    question_cleaned: Optional[str]
    answers: Dict[str, List[str]]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationListResponse(BaseModel):
    """Response model for conversation list."""

    conversations: List[ConversationListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class QAHealthResponse(BaseModel):
    """Response model for Q&A health check."""

    status: str
    message: str
    model_loaded: Optional[bool] = None
    data_loaded: Optional[bool] = None
