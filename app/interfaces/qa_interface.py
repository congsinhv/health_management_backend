"""
Q&A service interface contract.

Defines the abstract interface for Vietnamese health question answering service.
Implements the contract that all Q&A service implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.shared.schemas import BaseResponse, ServiceRequest


class QARequest(ServiceRequest):
    """Q&A request model."""

    question: str = Field(..., min_length=1, max_length=1000, description="Health question in Vietnamese")
    user_id: Optional[int] = Field(None, description="User ID for personalization")
    conversation_id: Optional[int] = Field(None, description="Conversation ID for context")
    context: Optional[str] = Field(None, description="Additional context for the question")
    threshold: Optional[float] = Field(0.55, ge=0.0, le=1.0, description="Similarity threshold for answers")


class QAAnswer(BaseModel):
    """Individual Q&A answer model."""

    answer: str = Field(..., description="Answer text in Vietnamese")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    source: str = Field(..., description="Source of the answer")
    similarity: float = Field(..., ge=0.0, le=1.0, description="Similarity score with question")


class QAResponse(BaseResponse):
    """Q&A response model."""

    question: str = Field(..., description="Original question")
    answers: list[QAAnswer] = Field(..., description="List of matching answers")
    summary: Optional[str] = Field(None, description="AI-generated summary")
    processing_time_ms: Optional[int] = Field(None, description="Processing time in milliseconds")
    cache_hit: bool = Field(False, description="Whether response came from cache")


class QAStreamChunk(BaseModel):
    """Q&A streaming response chunk."""

    chunk: str = Field(..., description="Text chunk for streaming")
    type: str = Field(..., description="Chunk type: 'summary' or 'partial'")
    finished: bool = Field(False, description="Whether streaming is complete")
    final_response: Optional[QAResponse] = Field(None, description="Final complete response")


class QAHealthCheck(BaseResponse):
    """Q&A service health check model."""

    service: str = Field("qa", description="Service name")
    model_loaded: bool = Field(..., description="Whether SBERT model is loaded")
    database_connected: bool = Field(..., description="Whether QA database is connected")
    openai_available: bool = Field(..., description="Whether OpenAI API is available")
    cache_status: str = Field(..., description="Cache service status")
    total_questions: Optional[int] = Field(None, description="Total questions in dataset")


class IQAService(ABC):
    """Q&A service interface."""

    @abstractmethod
    async def ask_question(self, request: QARequest) -> QAResponse:
        """
        Ask a health question and get answers.

        Args:
            request: Q&A request with question and metadata

        Returns:
            QAResponse with matching answers and optional AI summary

        Raises:
            QAModelNotLoadedException: If SBERT model is not loaded
            QADatasetException: If QA dataset has errors
            AIServiceException: If AI summarization fails
        """
        pass

    @abstractmethod
    async def ask_question_stream(
        self, request: QARequest
    ) -> AsyncIterator[QAStreamChunk]:
        """
        Ask a health question with streaming response.

        Args:
            request: Q&A request with question and metadata

        Yields:
            QAStreamChunk with partial responses

        Raises:
            QAModelNotLoadedException: If SBERT model is not loaded
            QADatasetException: If QA dataset has errors
            AIServiceException: If AI summarization fails
        """
        pass

    @abstractmethod
    async def health_check(self) -> QAHealthCheck:
        """
        Check the health of the Q&A service.

        Returns:
            QAHealthCheck with service status and component details
        """
        pass

    @abstractmethod
    async def get_answer_count(self) -> int:
        """
        Get total number of answers in the QA dataset.

        Returns:
            Total answer count

        Raises:
            DatabaseException: If database query fails
        """
        pass

    @abstractmethod
    async def add_answer(
        self,
        question: str,
        answer: str,
        source: str,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a new Q&A pair to the dataset.

        Args:
            question: Health question in Vietnamese
            answer: Answer in Vietnamese
            source: Source of the answer
            category: Optional category for the Q&A pair

        Returns:
            Dict with added answer ID and metadata

        Raises:
            ValidationException: If question or answer is invalid
            DatabaseException: If database insert fails
        """
        pass

    @abstractmethod
    async def delete_answer(self, answer_id: int) -> bool:
        """
        Delete a Q&A answer from the dataset.

        Args:
            answer_id: ID of answer to delete

        Returns:
            True if deleted, False if not found

        Raises:
            DatabaseException: If database delete fails
        """
        pass

    @abstractmethod
    async def search_answers(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.55
    ) -> list[Dict[str, Any]]:
        """
        Search for answers matching a query.

        Args:
            query: Search query
            limit: Maximum number of results
            threshold: Similarity threshold

        Returns:
            List of matching answers with metadata

        Raises:
            QAModelNotLoadedException: If SBERT model is not loaded
            DatabaseException: If database query fails
        """
        pass

    @abstractmethod
    async def get_conversation_context(
        self,
        conversation_id: int,
        user_id: int
    ) -> list[Dict[str, Any]]:
        """
        Get conversation context for better answers.

        Args:
            conversation_id: Conversation ID
            user_id: User ID for validation

        Returns:
            List of previous Q&A pairs in conversation

        Raises:
            ValidationException: If conversation not found
            AuthorizationException: If user doesn't own conversation
            DatabaseException: If database query fails
        """
        pass