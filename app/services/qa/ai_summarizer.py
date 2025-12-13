"""
AI summarizer for Q&A service using OpenAI API.
from app.exceptions import (
    QAServiceException,
    QAModelNotLoadedException,
    QADatasetException,
    QAModelException,
    AIServiceException,
    OpenAIException,
    ModelNotLoadedException,
    DataProcessingException,
    ServiceUnavailableException,
    DatabaseException,
)
from app.core.error_context import ErrorContext

This module handles AI-powered summarization of Q&A answers
with proper streaming, error handling, and cost optimization.
"""

import logging
from typing import List, Dict, Optional, Iterator
import asyncio

try:
    from openai import OpenAI, AsyncOpenAI
    from openai.types import ChatCompletionChunk
except ImportError:
    OpenAI = None
    AsyncOpenAI = None
    ChatCompletionChunk = None

from app.core.qa_constants import OPENAI_TEMPERATURE
from app.config import settings, logger as app_logger

logger = logging.getLogger(__name__)


class AISummarizer:
    """AI-powered answer summarization using OpenAI API."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize AI summarizer.

        Args:
            api_key: OpenAI API key (defaults to settings)
            model: OpenAI model to use
        """
        if OpenAI is None:
            raise ImportError(
                "OpenAI package is required. Install with: pip install openai"
            )

        self.api_key = api_key or settings.openai_api_key
        self.model = model
        self.temperature = OPENAI_TEMPERATURE
        self.max_tokens = 150  # Concise summaries
        self.client = None
        self.async_client = None

        if self.api_key:
            self._initialize_clients()

    def _initialize_clients(self) -> None:
        """Initialize OpenAI clients with retry configuration."""
        try:
            # Configure retry with exponential backoff for rate limits (429)
            # max_retries: 3 attempts with exponential backoff
            # timeout: 60s per request
            self.client = OpenAI(
                api_key=self.api_key,
                max_retries=3,
                timeout=60.0,
            )
            self.async_client = AsyncOpenAI(
                api_key=self.api_key,
                max_retries=3,
                timeout=60.0,
            )
            logger.info("OpenAI clients initialized successfully with retry configuration")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI clients: {e}")

    def is_available(self) -> bool:
        """Check if OpenAI service is available."""
        return self.client is not None and self.async_client is not None

    async def generate_summary_stream(
        self, question: str, answers: List[Dict[str, any]]
    ) -> Iterator[str]:
        """
        Generate streaming summary for Q&A answers.

        Args:
            question: The user's question
            answers: List of answer dictionaries

        Yields:
            Streamed summary chunks
        """
        if not self.is_available():
            yield "Sorry, AI summarization is currently unavailable."
            return

        try:
            # Prepare answers text
            answers_text = self._format_answers_for_summary(answers)

            # Create prompt
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that summarizes Vietnamese Q&A answers. "
                        "Provide concise, accurate summaries in Vietnamese. "
                        "Focus on the most relevant medical information."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Câu hỏi: {question}\n\n"
                        f"Câu trả lời:\n{answers_text}\n\n"
                        "Hãy tóm tắt các câu trả lời trên thành một câu trả lời ngắn gọn, "
                        "chính xác và hữu ích cho người dùng bằng tiếng Việt."
                    ),
                },
            ]

            # Stream response
            stream = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            yield "Xin lỗi, không thể tạo tóm tắt tại thời điểm này."

    async def generate_summary(
        self, question: str, answers: List[Dict[str, any]]
    ) -> str:
        """
        Generate complete summary for Q&A answers.

        Args:
            question: The user's question
            answers: List of answer dictionaries

        Returns:
            Complete summary text
        """
        if not self.is_available():
            return "Sorry, AI summarization is currently unavailable."

        try:
            # Collect streaming chunks
            chunks = []
            async for chunk in self.generate_summary_stream(question, answers):
                chunks.append(chunk)

            return "".join(chunks)

        except Exception as e:
            logger.error(f"Error generating complete summary: {e}")
            return "Xin lỗi, không thể tạo tóm tắt tại thời điểm này."

    def _format_answers_for_summary(self, answers: List[Dict[str, any]]) -> str:
        """
        Format answers for AI summarization.

        Args:
            answers: List of answer dictionaries

        Returns:
            Formatted text for AI processing
        """
        formatted_answers = []

        for i, answer in enumerate(answers, 1):
            # Extract relevant fields
            answer_text = answer.get("answer", "")
            field = answer.get("field", "unknown")
            score = answer.get("score", 0.0)

            if answer_text:
                formatted_answers.append(
                    f"{i}. [Lĩnh vực: {field}, Điểm tương đồng: {score:.2f}]\n"
                    f"{answer_text}\n"
                )

        return "\n".join(formatted_answers)

    async def validate_answer_quality(
        self, question: str, answer: str
    ) -> Dict[str, any]:
        """
        Validate and rate answer quality.

        Args:
            question: The original question
            answer: The answer to validate

        Returns:
            Quality assessment results
        """
        if not self.is_available():
            return {
                "available": False,
                "quality_score": 0.0,
                "feedback": "AI validation unavailable",
            }

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an expert evaluator of Vietnamese medical Q&A answers. "
                        "Rate the quality of answers based on accuracy, completeness, "
                        "relevance, and clarity. Provide a score from 0-10 and brief feedback."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Câu hỏi: {question}\n\n"
                        f"Câu trả lời: {answer}\n\n"
                        "Vui lòng đánh giá chất lượng câu trả lời và cho điểm từ 0-10."
                    ),
                },
            ]

            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,  # Lower temperature for evaluation
                max_tokens=200,
            )

            evaluation = response.choices[0].message.content
            return {"available": True, "evaluation": evaluation, "feedback": evaluation}

        except Exception as e:
            logger.error(f"Error validating answer quality: {e}")
            return {
                "available": False,
                "quality_score": 0.0,
                "feedback": f"Validation error: {str(e)}",
            }

    def get_model_info(self) -> Dict[str, any]:
        """Get information about the AI model configuration."""
        return {
            "available": self.is_available(),
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "api_configured": bool(self.api_key),
        }
