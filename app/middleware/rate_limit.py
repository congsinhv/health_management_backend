"""
Rate limiting middleware for SSE streaming endpoints.
"""

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class SSERateLimiter:
    """Rate limiter for SSE streaming endpoints."""

    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize rate limiter.

        Args:
            redis_url: Optional Redis URL for distributed rate limiting
        """
        self.redis_client = None
        if redis_url:
            try:
                import redis.asyncio as redis

                self.redis_client = redis.from_url(redis_url)
                logger.info("Redis rate limiting enabled")
            except ImportError:
                logger.warning(
                    "Redis not available, falling back to local rate limiting"
                )

        self.local_connections = defaultdict(list)
        self.local_requests = defaultdict(list)

        self.MAX_CONNECTIONS_PER_USER = 3
        self.MAX_REQUESTS_PER_MINUTE = 60
        self.CLEANUP_INTERVAL = timedelta(minutes=5)

    async def check_connection_limit(self, user_id: str) -> bool:
        """Check if user can open new SSE connection."""
        if self.redis_client:
            return await self._check_redis_connection_limit(user_id)
        else:
            return self._check_local_connection_limit(user_id)

    async def _check_redis_connection_limit(self, user_id: str) -> bool:
        """Check connection limit using Redis."""
        try:
            key = f"sse:connections:{user_id}"
            count = await self.redis_client.get(key)
            return int(count or 0) < self.MAX_CONNECTIONS_PER_USER
        except Exception as e:
            logger.error(f"Redis error checking connection limit: {e}")
            # Fall back to local checking
            return self._check_local_connection_limit(user_id)

    def _check_local_connection_limit(self, user_id: str) -> bool:
        """Check connection limit using local storage."""
        now = datetime.utcnow()
        self._cleanup_stale_connections(user_id, now)
        return len(self.local_connections[user_id]) < self.MAX_CONNECTIONS_PER_USER

    async def cleanup_all_stale_data(self):
        """Clean up all stale connection and request data."""
        now = datetime.utcnow()

        # Clean up stale connections for all users
        stale_users = []
        for user_id in self.local_connections:
            self._cleanup_stale_connections(user_id, now)
            if not self.local_connections[user_id]:
                stale_users.append(user_id)

        for user_id in stale_users:
            del self.local_connections[user_id]

        # Clean up stale requests for all users
        stale_request_users = []
        minute_ago = now - timedelta(minutes=1)

        for user_id in self.local_requests:
            self.local_requests[user_id] = [
                req_time
                for req_time in self.local_requests[user_id]
                if req_time > minute_ago
            ]
            if not self.local_requests[user_id]:
                stale_request_users.append(user_id)

        for user_id in stale_request_users:
            del self.local_requests[user_id]

    async def register_connection(self, user_id: str):
        """Register new SSE connection."""
        if self.redis_client:
            await self._register_redis_connection(user_id)
        else:
            self._register_local_connection(user_id)

    async def _register_redis_connection(self, user_id: str):
        """Register connection in Redis."""
        try:
            key = f"sse:connections:{user_id}"
            await self.redis_client.incr(key)
            await self.redis_client.expire(key, 3600)  # 1 hour TTL
        except Exception as e:
            logger.error(f"Redis error registering connection: {e}")
            # Fall back to local registration
            self._register_local_connection(user_id)

    def _register_local_connection(self, user_id: str):
        """Register connection locally."""
        self.local_connections[user_id].append(datetime.utcnow())

    async def unregister_connection(self, user_id: str):
        """Unregister SSE connection on close."""
        if self.redis_client:
            await self._unregister_redis_connection(user_id)
        else:
            self._unregister_local_connection(user_id)

    async def _unregister_redis_connection(self, user_id: str):
        """Unregister connection from Redis."""
        try:
            key = f"sse:connections:{user_id}"
            await self.redis_client.decr(key)
        except Exception as e:
            logger.error(f"Redis error unregistering connection: {e}")
            # Fall back to local unregistration
            self._unregister_local_connection(user_id)

    def _unregister_local_connection(self, user_id: str):
        """Unregister connection locally."""
        if self.local_connections[user_id]:
            self.local_connections[user_id].pop()

    def _cleanup_stale_connections(self, user_id: str, now: datetime):
        """Remove stale connection records."""
        self.local_connections[user_id] = [
            conn_time
            for conn_time in self.local_connections[user_id]
            if now - conn_time < self.CLEANUP_INTERVAL
        ]

    async def check_request_rate(self, user_id: str) -> bool:
        """Check if user has exceeded request rate limit."""
        if self.redis_client:
            return await self._check_redis_request_rate(user_id)
        else:
            return self._check_local_request_rate(user_id)

    async def _check_redis_request_rate(self, user_id: str) -> bool:
        """Check request rate using Redis."""
        try:
            key = f"sse:requests:{user_id}"
            count = await self.redis_client.get(key)
            return int(count or 0) < self.MAX_REQUESTS_PER_MINUTE
        except Exception as e:
            logger.error(f"Redis error checking request rate: {e}")
            return self._check_local_request_rate(user_id)

    def _check_local_request_rate(self, user_id: str) -> bool:
        """Check request rate locally."""
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)

        # Clean old requests
        self.local_requests[user_id] = [
            req_time
            for req_time in self.local_requests[user_id]
            if req_time > minute_ago
        ]

        return len(self.local_requests[user_id]) < self.MAX_REQUESTS_PER_MINUTE

    async def register_request(self, user_id: str):
        """Register a new request."""
        if self.redis_client:
            await self._register_redis_request(user_id)
        else:
            self._register_local_request(user_id)

    async def _register_redis_request(self, user_id: str):
        """Register request in Redis."""
        try:
            key = f"sse:requests:{user_id}"
            await self.redis_client.incr(key)
            await self.redis_client.expire(key, 60)  # 1 minute TTL
        except Exception as e:
            logger.error(f"Redis error registering request: {e}")
            self._register_local_request(user_id)

    def _register_local_request(self, user_id: str):
        """Register request locally."""
        self.local_requests[user_id].append(datetime.utcnow())


# Global rate limiter instance
rate_limiter: Optional[SSERateLimiter] = None


def get_rate_limiter() -> Optional[SSERateLimiter]:
    """Get the global rate limiter instance."""
    return rate_limiter


def init_rate_limiter(redis_url: Optional[str] = None) -> SSERateLimiter:
    """Initialize the global rate limiter."""
    global rate_limiter
    rate_limiter = SSERateLimiter(redis_url=redis_url)
    return rate_limiter
