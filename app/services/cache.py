"""
Redis caching service for Health Management API.

Provides high-performance caching with graceful fallback when Redis is unavailable.
Implements cache-aside pattern with TTL support, JSON serialization, and numpy embedding cache.
"""

import json
import logging
from typing import Optional, Any, Dict, List
from datetime import datetime
from dataclasses import dataclass

import redis.asyncio as redis
from redis.asyncio import Redis
from redis.exceptions import ConnectionError, TimeoutError, RedisError
import msgpack
import msgpack_numpy as m
import numpy as np

from app.config import settings

from app.exceptions import (
    CacheException,
    CacheUnavailableException,
    CacheTimeoutException,
    ServiceUnavailableException,
    DataProcessingException,
)
from app.core.error_context import ErrorContext

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """Cache statistics for monitoring."""

    hits: int = 0
    misses: int = 0
    errors: int = 0
    total_requests: int = 0
    hit_rate: float = 0.0
    error_rate: float = 0.0

    def calculate_rates(self) -> None:
        """Calculate hit and error rates."""
        if self.total_requests > 0:
            self.hit_rate = (self.hits / self.total_requests) * 100
            self.error_rate = (self.errors / self.total_requests) * 100


class CacheService:
    """
    Redis cache service with graceful fallback.

    Provides async cache operations with comprehensive error handling.
    Falls back to pass-through mode when Redis is unavailable.
    """

    def __init__(self, redis_client: Optional[Redis] = None):
        """
        Initialize cache service.

        Args:
            redis_client: Optional Redis client instance. If None, cache operates in pass-through mode.
        """
        self.redis_client = redis_client
        self.enabled = redis_client is not None
        self.stats = CacheStats()

        logger.info(
            f"CacheService initialized - enabled: {self.enabled}, "
            f"redis_url: {'***' if settings.redis_url else None}"
        )

    async def get(self, key: str) -> Optional[str]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/error
        """
        if not self.enabled:
            self.stats.misses += 1
            self.stats.total_requests += 1
            self.stats.calculate_rates()
            return None

        try:
            value = await self.redis_client.get(key)
            if value is not None:
                self.stats.hits += 1
                logger.debug(f"Cache hit for key: {key}")
                return value.decode("utf-8") if isinstance(value, bytes) else value
            else:
                self.stats.misses += 1
                logger.debug(f"Cache miss for key: {key}")
                return None

        except (ConnectionError, TimeoutError, RedisError) as e:
            self.stats.errors += 1
            logger.warning(f"Cache get error for key {key}: {type(e).__name__}: {e}")
            return None
        finally:
            self.stats.total_requests += 1
            self.stats.calculate_rates()

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: 300s)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return True  # Pass-through mode, consider it successful

        try:
            if ttl is None:
                ttl = 300  # Default 5 minutes TTL

            result = await self.redis_client.setex(key, ttl, value)
            logger.debug(f"Cache set for key: {key}, TTL: {ttl}s")
            return bool(result)

        except (ConnectionError, TimeoutError, RedisError) as e:
            self.stats.errors += 1
            logger.warning(f"Cache set error for key {key}: {type(e).__name__}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted successfully or key didn't exist, False on error
        """
        if not self.enabled:
            return True

        try:
            result = await self.redis_client.delete(key)
            logger.debug(f"Cache delete for key: {key}")
            return (
                True  # Redis returns number of deleted keys, 0 means key didn't exist
            )

        except (ConnectionError, TimeoutError, RedisError) as e:
            self.stats.errors += 1
            logger.warning(f"Cache delete error for key {key}: {type(e).__name__}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete keys matching pattern.

        Args:
            pattern: Redis pattern (e.g., "user:*", "conversation:123:*")

        Returns:
            Number of deleted keys, 0 on error or if no keys match
        """
        if not self.enabled:
            return 0

        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                result = await self.redis_client.delete(*keys)
                logger.debug(f"Cache delete pattern: {pattern}, deleted {result} keys")
                return result
            return 0

        except (ConnectionError, TimeoutError, RedisError) as e:
            self.stats.errors += 1
            logger.warning(
                f"Cache delete pattern error for {pattern}: {type(e).__name__}: {e}"
            )
            return 0

    async def clear_all(self) -> bool:
        """
        Clear all keys in current database.

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return True

        try:
            await self.redis_client.flushdb()
            logger.warning("Cache cleared - all keys deleted")
            return True

        except (ConnectionError, TimeoutError, RedisError) as e:
            self.stats.errors += 1
            logger.warning(f"Cache clear error: {type(e).__name__}: {e}")
            return False

    async def ping(self) -> bool:
        """
        Check Redis connectivity.

        Returns:
            True if Redis is responsive, False otherwise
        """
        if not self.enabled:
            return False

        try:
            result = await self.redis_client.ping()
            logger.debug(f"Redis ping result: {result}")
            return bool(result)

        except (ConnectionError, TimeoutError, RedisError) as e:
            self.stats.errors += 1
            logger.warning(f"Redis ping error: {type(e).__name__}: {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        self.stats.calculate_rates()

        stats_data = {
            "enabled": self.enabled,
            "hits": self.stats.hits,
            "misses": self.stats.misses,
            "errors": self.stats.errors,
            "total_requests": self.stats.total_requests,
            "hit_rate": round(self.stats.hit_rate, 2),
            "error_rate": round(self.stats.error_rate, 2),
        }

        # Get Redis info if available
        if self.enabled:
            try:
                info = await self.redis_client.info()
                stats_data.update(
                    {
                        "redis_version": info.get("redis_version"),
                        "used_memory": info.get("used_memory_human"),
                        "connected_clients": info.get("connected_clients"),
                        "total_commands_processed": info.get(
                            "total_commands_processed"
                        ),
                    }
                )
            except (ConnectionError, TimeoutError, RedisError) as e:
                logger.warning(f"Failed to get Redis info: {type(e).__name__}: {e}")

        return stats_data

    def build_key(
        self,
        namespace: str,
        entity_type: str,
        entity_id: str,
        field: Optional[str] = None,
    ) -> str:
        """
        Build standardized cache key.

        Args:
            namespace: Application namespace (e.g., "app")
            entity_type: Type of entity (e.g., "conversation", "user")
            entity_id: Entity identifier
            field: Optional field name

        Returns:
            Formatted cache key
        """
        if field:
            return f"{namespace}:{entity_type}:{entity_id}:{field}"
        return f"{namespace}:{entity_type}:{entity_id}"

    async def get_json(self, key: str) -> Optional[Any]:
        """
        Get JSON value from cache and deserialize.

        Args:
            key: Cache key

        Returns:
            Deserialized Python object or None
        """
        cached_value = await self.get(key)
        if cached_value is None:
            return None

        try:
            return json.loads(cached_value)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to decode JSON for key {key}: {e}")
            await self.delete(key)  # Remove corrupted cache entry
            return None

    async def set_json(self, key: str, obj: Any, ttl: Optional[int] = None) -> bool:
        """
        Serialize object to JSON and store in cache.

        Args:
            key: Cache key
            obj: Python object to cache
            ttl: Time to live in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            json_value = json.dumps(obj, ensure_ascii=False, default=str)
            return await self.set(key, json_value, ttl)
        except (TypeError, ValueError) as e:
            logger.warning(f"Failed to serialize JSON for key {key}: {e}")
            return False

    async def get_embedding(self, key: str) -> Optional[np.ndarray]:
        """
        Get cached embedding from Redis with msgpack deserialization.

        Args:
            key: Cache key

        Returns:
            Numpy array embedding or None if not found/error
        """
        if not self.enabled:
            self.stats.misses += 1
            self.stats.total_requests += 1
            self.stats.calculate_rates()
            return None

        try:
            cached = await self.redis_client.get(key)
            if cached:
                # Deserialize msgpack-encoded numpy array
                embedding = msgpack.unpackb(cached, object_hook=m.decode)
                self.stats.hits += 1
                logger.debug(f"Embedding cache HIT: {key} ({len(cached)} bytes)")
                return embedding
            else:
                self.stats.misses += 1
                logger.debug(f"Embedding cache MISS: {key}")
                return None

        except (ConnectionError, TimeoutError, RedisError) as e:
            self.stats.errors += 1
            logger.warning(
                f"Embedding cache get error for {key}: {type(e).__name__}: {e}"
            )
            return None
        except Exception as e:
            self.stats.errors += 1
            logger.warning(
                f"Embedding deserialization error for {key}: {type(e).__name__}: {e}"
            )
            return None
        finally:
            self.stats.total_requests += 1
            self.stats.calculate_rates()

    async def set_embedding(
        self, key: str, embedding: np.ndarray, ttl: Optional[int] = None
    ) -> bool:
        """
        Cache embedding in Redis with msgpack serialization.

        Args:
            key: Cache key
            embedding: Numpy array (typically 768-dim SBERT vector)
            ttl: Time to live in seconds (default: 86400 = 24h)

        Returns:
            True if cached successfully, False otherwise
        """
        if not self.enabled:
            return True  # Pass-through mode, consider it successful

        try:
            if ttl is None:
                ttl = settings.cache_ttl_qa_embedding

            # Serialize numpy array with msgpack
            serialized = msgpack.packb(embedding, default=m.encode)

            # Store in Redis
            result = await self.redis_client.setex(key, ttl, serialized)
            logger.debug(
                f"Embedding cached: {key} ({len(serialized)} bytes, TTL: {ttl}s)"
            )
            return bool(result)

        except (ConnectionError, TimeoutError, RedisError) as e:
            self.stats.errors += 1
            logger.warning(
                f"Embedding cache set error for {key}: {type(e).__name__}: {e}"
            )
            return False
        except Exception as e:
            self.stats.errors += 1
            logger.warning(
                f"Embedding serialization error for {key}: {type(e).__name__}: {e}"
            )
            return False


async def create_cache_service() -> CacheService:
    """
    Create and initialize CacheService with Redis connection.

    Returns:
        Initialized CacheService instance
    """
    redis_client = None

    if settings.enable_redis_cache and settings.redis_url:
        try:
            logger.info(f"Connecting to Redis at: {settings.redis_host}")
        logger.debug(f"Redis URL: {settings.redis_url}")
        logger.debug(f"Redis password present: {'Yes' if settings.redis_password else 'No'}")

            # Create Redis client with authentication for GCP Memorystore
            connection_kwargs = {
                "max_connections": settings.redis_max_connections,
                "retry_on_timeout": True,
                "socket_connect_timeout": settings.redis_connection_timeout,
                "socket_timeout": settings.redis_connection_timeout,
                "health_check_interval": 30,  # Check connection every 30 seconds
                "encoding": "utf-8",
                "decode_responses": True,
            }

            # Add SSL options if enabled (redis-py 5.0+ compatible)
            if settings.redis_ssl and not settings.redis_ssl_cert_verify:
                import ssl
                # Create SSL context for GCP Memorystore
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                connection_kwargs["ssl"] = ssl_context
            elif settings.redis_ssl:
                import ssl
                # Create SSL context for normal SSL with verification
                connection_kwargs["ssl"] = True

            # GCP Memorystore uses password-only authentication
            # Don't use URL, pass parameters directly to avoid parsing issues
            redis_client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,  # Use auth string as password
                **connection_kwargs,
            )

            # Test connection
            await redis_client.ping()
            logger.info("Redis connection established successfully")

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.error(f"Failed to connect to Redis: {type(e).__name__}: {e}")
            redis_client = None
        except Exception as e:
            logger.error(
                f"Unexpected error connecting to Redis: {type(e).__name__}: {e}"
            )
            redis_client = None

    return CacheService(redis_client)
