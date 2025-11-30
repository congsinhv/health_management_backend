"""
Service-to-service HTTP client with IAM authentication.

Provides HTTP client for secure communication between VHealth microservices
using Google Cloud IAM identity tokens for authentication.

Usage:
    from app.core.shared.http_client import ServiceClient

    client = ServiceClient(base_url="https://qa-service-v45ti4rlpa-uc.a.run.app")

    # Make POST request
    response = await client.post("/ask_question", {"question": "What is diabetes?"})

    # Make GET request
    response = await client.get("/health_check")
"""

import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any, Union
from datetime import datetime, timedelta

try:
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token
    from google.auth.exceptions import DefaultCredentialsError
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    GOOGLE_AUTH_AVAILABLE = False

logger = logging.getLogger(__name__)


class ServiceClient:
    """HTTP client for service-to-service communication with IAM auth."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 0.5
    ):
        """
        Initialize service client.

        Args:
            base_url: Base URL of the target service
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            retry_delay: Delay between retries in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._session: Optional[aiohttp.ClientSession] = None
        self._token_cache: Dict[str, Dict[str, Any]] = {}
        self._token_cache_ttl = timedelta(minutes=5)  # Cache tokens for 5 minutes

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    @property
    def session(self) -> Optional[aiohttp.ClientSession]:
        """Get the current session (for streaming use)."""
        return self._session

    async def _get_iam_token(self, audience: Optional[str] = None) -> str:
        """
        Get IAM identity token for service-to-service auth.

        For Cloud Run services, this uses the Compute Metadata Server.
        Falls back to no auth if Google auth is not available.
        """
        if not GOOGLE_AUTH_AVAILABLE:
            logger.warning("Google Auth not available, using no-auth mode")
            return "no-auth"

        cache_key = audience or self.base_url
        now = datetime.utcnow()

        # Check cache
        if cache_key in self._token_cache:
            cached = self._token_cache[cache_key]
            if now < cached["expires_at"]:
                return cached["token"]

        try:
            # For Cloud Run: Use Compute Metadata Server
            request = Request()
            target_audience = audience or self.base_url
            token = id_token.fetch_id_token(request, target_audience)

            # Cache the token
            self._token_cache[cache_key] = {
                "token": token,
                "expires_at": now + self._token_cache_ttl
            }

            return token

        except DefaultCredentialsError:
            logger.warning("Default credentials not found, using no-auth mode")
            return "no-auth"
        except Exception as e:
            logger.error(f"Failed to get IAM token: {e}")
            return "no-auth"

    async def _make_request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic and IAM authentication.
        """
        session = await self._get_session()
        url = f"{self.base_url}{path}"

        # Prepare headers with IAM token
        req_headers = headers or {}
        token = await self._get_iam_token()

        if token != "no-auth":
            req_headers["Authorization"] = f"Bearer {token}"

        if json:
            req_headers["Content-Type"] = "application/json"

        try:
            async with session.request(
                method,
                url,
                json=json,
                params=params,
                headers=req_headers
            ) as response:
                response.raise_for_status()

                # Handle different content types
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    return await response.json()
                else:
                    # Return text response as dict
                    return {"data": await response.text()}

        except aiohttp.ClientError as e:
            logger.warning(f"Request failed (attempt {retry_count + 1}): {e}")

            # Retry logic for transient errors
            if (retry_count < self.max_retries and
                isinstance(e, (aiohttp.ClientConnectionError,
                              aiohttp.ClientPayloadError))):
                await asyncio.sleep(self.retry_delay * (2 ** retry_count))  # Exponential backoff
                return await self._make_request(
                    method, path, json, params, headers, retry_count + 1
                )

            # Re-raise for other errors or after max retries
            raise

    async def post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """POST request with IAM auth."""
        return await self._make_request("POST", path, json=json, headers=headers)

    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """GET request with IAM auth."""
        return await self._make_request("GET", path, params=params, headers=headers)

    async def put(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """PUT request with IAM auth."""
        return await self._make_request("PUT", path, json=json, headers=headers)

    async def delete(
        self,
        path: str,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """DELETE request with IAM auth."""
        return await self._make_request("DELETE", path, headers=headers)

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the target service."""
        try:
            return await self.get("/health_check")
        except Exception as e:
            logger.error(f"Health check failed for {self.base_url}: {e}")
            return {
                "status": "unhealthy",
                "service": self.base_url,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def close(self):
        """Close HTTP session and cleanup."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._token_cache.clear()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


class ServiceClientPool:
    """Pool of service clients for efficient connection reuse."""

    def __init__(self):
        self._clients: Dict[str, ServiceClient] = {}

    async def get_client(
        self,
        service_name: str,
        base_url: str,
        **kwargs
    ) -> ServiceClient:
        """Get or create a service client for the given service."""
        if service_name not in self._clients:
            self._clients[service_name] = ServiceClient(base_url, **kwargs)
        return self._clients[service_name]

    async def close_all(self):
        """Close all service clients in the pool."""
        close_tasks = []
        for client in self._clients.values():
            close_tasks.append(client.close())

        if close_tasks:
            await asyncio.gather(*close_tasks, return_exceptions=True)
        self._clients.clear()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_all()


# Global client pool instance
_client_pool = ServiceClientPool()


def get_service_client_pool() -> ServiceClientPool:
    """Get the global service client pool."""
    return _client_pool


async def cleanup_service_clients():
    """Cleanup all service clients. Call this on application shutdown."""
    await _client_pool.close_all()