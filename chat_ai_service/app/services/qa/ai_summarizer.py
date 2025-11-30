"""
AI summarizer for Q&A service using service client for OpenAI communication.
from app.core.shared.exceptions import (
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
with proper streaming, error handling, and service communication.
"""

import logging
from typing import List, Dict, Optional, Iterator
import asyncio

from app.core.shared.http_client import ServiceClient
from app.core.qa_constants import OPENAI_TEMPERATURE
from app.config import settings

logger = logging.getLogger(__name__)


class AISummarizer:
    """AI-powered answer summarization using service client for OpenAI API."""

    def __init__(self,
                 api_key: Optional[str] = None,
                 model: str = "gpt-4o-mini",
                 service_url: Optional[str] = None):
        """
        Initialize AI summarizer.

        Args:
            api_key: OpenAI API key (defaults to settings)
            model: OpenAI model to use
            service_url: URL for OpenAI service (if using service-to-service communication)
        """
        self.api_key = api_key or settings.openai_api_key
        self.model = model
        self.temperature = OPENAI_TEMPERATURE
        self.max_tokens = 150  # Concise summaries
        self.service_url = service_url or getattr(settings, 'openai_service_url', None)
        self.service_client = None
        self.direct_client = None

        if self.service_url:
            logger.info(f"Using service client for OpenAI: {self.service_url}")
            self.service_client = ServiceClient(base_url=self.service_url)
        elif self.api_key:
            logger.info("Using direct OpenAI client")
            self._initialize_direct_client()

    def _initialize_direct_client(self) -> None:
        """Initialize direct OpenAI client."""
        try:
            from openai import OpenAI, AsyncOpenAI
            self.direct_client = OpenAI(api_key=self.api_key)
            self.async_client = AsyncOpenAI(api_key=self.api_key)
            logger.info("Direct OpenAI clients initialized successfully")
        except ImportError:
            logger.error("OpenAI package not available for direct client")
            self.direct_client = None
            self.async_client = None
        except Exception as e:
            logger.error(f"Failed to initialize direct OpenAI client: {e}")
            self.direct_client = None
            self.async_client = None

    def is_available(self) -> bool:
        """Check if AI summarization service is available."""
        return bool(self.service_client or (self.async_client and self.api_key))

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

            if self.service_client:
                # Use service client for OpenAI communication
                async for chunk in self._stream_with_service_client(question, answers_text):
                    yield chunk
            else:
                # Use direct OpenAI client
                async for chunk in self._stream_with_direct_client(question, answers_text):
                    yield chunk

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            yield "Xin lỗi, không thể tạo tóm tắt tại thời điểm này."

    async def _stream_with_service_client(
        self, question: str, answers_text: str
    ) -> Iterator[str]:
        """Generate summary using service client for OpenAI communication."""
        try:
            # Prepare request payload
            payload = {
                "model": self.model,
                "messages": [
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
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "stream": True,
            }

            # Make streaming request through service client
            async with self.service_client._get_session() as session:
                url = f"{self.service_client.base_url}/chat/completions"

                # Set up headers
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}" if self.api_key else "no-auth"
                }

                async with session.post(url, json=payload, headers=headers) as response:
                    response.raise_for_status()

                    # Process streaming response
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            data = line[6:]  # Remove 'data: ' prefix
                            if data == '[DONE]':
                                break
                            try:
                                import json
                                chunk = json.loads(data)
                                if chunk.get("choices"):
                                    delta = chunk["choices"][0].get("delta", {})
                                    if delta.get("content"):
                                        yield delta["content"]
                            except json.JSONDecodeError:
                                continue

        except Exception as e:
            logger.error(f"Service client streaming error: {e}")
            raise

    async def _stream_with_direct_client(
        self, question: str, answers_text: str
    ) -> Iterator[str]:
        """Generate summary using direct OpenAI client."""
        try:
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
            logger.error(f"Direct client streaming error: {e}")
            raise

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
            if self.service_client:
                # Use service client for validation
                payload = {
                    "model": self.model,
                    "messages": [
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
                    ],
                    "temperature": 0.3,  # Lower temperature for evaluation
                    "max_tokens": 200,
                }

                response = await self.service_client.post("/chat/completions", json=payload)
                evaluation = response.get("choices", [{}])[0].get("message", {}).get("content", "")
                return {"available": True, "evaluation": evaluation, "feedback": evaluation}
            else:
                # Use direct client for validation
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
            "service_url": self.service_url,
            "using_service_client": bool(self.service_client),
            "using_direct_client": bool(self.direct_client),
        }

    async def close(self):
        """Cleanup resources."""
        if self.service_client:
            await self.service_client.close()