"""
Chat AI Service client for Main API proxy implementation.

Provides HTTP client for secure communication with Chat AI service
using Google Cloud IAM identity tokens for authentication.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, AsyncGenerator
import json

from app.core.shared.http_client import ServiceClient
from app.core.shared.exceptions import ServiceUnavailableException, ValidationException
from app.config import settings

logger = logging.getLogger(__name__)


class ChatAIClient:
    """HTTP client for Chat AI service communication."""

    def __init__(self, base_url: str, timeout: int = 60):
        """
        Initialize Chat AI client.

        Args:
            base_url: Base URL of the Chat AI service
            timeout: Request timeout in seconds (longer for streaming)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = None

    async def _get_client(self) -> ServiceClient:
        """Get or create ServiceClient instance."""
        if self._client is None:
            self._client = ServiceClient(
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=3,
                retry_delay=0.5,
            )
        return self._client

    async def ask_question(
        self, question: str, threshold: float = 0.55, top_k: int = 7
    ) -> Dict[str, Any]:
        """
        Ask a question via Chat AI service.

        Args:
            question: The health-related question to ask
            threshold: Minimum similarity threshold for answers
            top_k: Maximum number of results to return

        Returns:
            QuestionResponse dictionary with answers and AI summary
        """
        try:
            client = await self._get_client()

            # Prepare request payload
            payload = {"question": question, "threshold": threshold, "top_k": top_k}

            logger.info(f"Proxying question to Chat AI service: {question[:100]}...")
            response = await client.post("/api/v1/qa/ask", json=payload)

            logger.info("Received response from Chat AI service")
            return response

        except Exception as e:
            logger.error(f"Failed to proxy question to Chat AI service: {e}")
            raise ServiceUnavailableException(
                f"Chat AI service is temporarily unavailable: {str(e)}",
                details={"service": "chat_ai", "error": str(e)},
            )

    async def stream_ask_question(
        self, question: str, threshold: float = 0.55, top_k: int = 7
    ) -> AsyncGenerator[str, None]:
        """
        Stream question response via Chat AI service.

        Args:
            question: The health-related question to ask
            threshold: Minimum similarity threshold for answers
            top_k: Maximum number of results to return

        Yields:
            SSE event strings from Chat AI service
        """
        try:
            client = await self._get_client()

            # Prepare request payload
            payload = {"question": question, "threshold": threshold, "top_k": top_k}

            logger.info(
                f"Proxying streaming question to Chat AI service: {question[:100]}..."
            )

            # Get the underlying session for streaming
            session = await client._get_session()
            url = f"{client.base_url}/api/v1/qa/ask-stream"

            # Get IAM token for authentication
            token = await client._get_iam_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            }

            async with session.post(url, json=payload, headers=headers) as response:
                response.raise_for_status()

                # Stream response chunks line by line for SSE
                async for line in response.content:
                    if line:
                        yield line.decode("utf-8")

            logger.info("Completed streaming response from Chat AI service")

        except Exception as e:
            logger.error(f"Failed to stream question from Chat AI service: {e}")
            # Yield error event for streaming clients
            error_event = {
                "event": "error",
                "data": json.dumps(
                    {
                        "error": "Chat AI service is temporarily unavailable",
                        "code": "service_unavailable",
                    }
                ),
            }
            yield f"event: {error_event['event']}\ndata: {error_event['data']}\n\n"

    async def health_check(self) -> Dict[str, Any]:
        """
        Check Chat AI service health.

        Returns:
            Health check response from Chat AI service
        """
        try:
            client = await self._get_client()
            response = await client.health_check()
            return response

        except Exception as e:
            logger.error(f"Chat AI service health check failed: {e}")
            return {
                "status": "unhealthy",
                "service": "chat_ai",
                "error": str(e),
                "message": "Chat AI service is not responding",
            }

    async def close(self):
        """Close client and cleanup resources."""
        if self._client:
            await self._client.close()
            self._client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Global client instance
_chat_ai_client: Optional[ChatAIClient] = None


async def get_chat_ai_client() -> Optional[ChatAIClient]:
    """
    Get the global Chat AI client instance.

    Returns:
        ChatAIClient instance if service URL is configured, None otherwise
    """
    global _chat_ai_client

    if not settings.chat_ai_service_url:
        logger.warning(
            "CHAT_AI_SERVICE_URL not configured, Chat AI client not available"
        )
        return None

    if _chat_ai_client is None:
        _chat_ai_client = ChatAIClient(settings.chat_ai_service_url)

    return _chat_ai_client


async def cleanup_chat_ai_client():
    """Cleanup the global Chat AI client. Call this on application shutdown."""
    global _chat_ai_client

    if _chat_ai_client:
        await _chat_ai_client.close()
        _chat_ai_client = None
