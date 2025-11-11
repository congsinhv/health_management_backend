"""
Redis caching service for performance optimization.
"""

import json
import logging
from typing import Optional, Any, Union, List, TypeVar, Generic, Dict
import pickle
from datetime import datetime, timedelta

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from app.config import settings

logger = logging.getLogger(__name__)

# Generic type for cache values
T = TypeVar("T")


class TypedCache(Generic[T]):
    """Typed cache interface for better type safety."""

    def __init__(self, cache_service: "CacheService", key_prefix: str):
        self.cache_service = cache_service
        self.key_prefix = key_prefix

    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """Get typed value from cache."""
        full_key = f"{self.key_prefix}:{key}"
        return self.cache_service.get(full_key, default)

    def set(self, key: str, value: T, ttl: Optional[int] = None) -> bool:
        """Set typed value in cache."""
        full_key = f"{self.key_prefix}:{key}"
        return self.cache_service.set(full_key, value, ttl)

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        full_key = f"{self.key_prefix}:{key}"
        return self.cache_service.delete(full_key)


class CacheService:
    """Redis-based caching service with fallback to no-op."""

    def __init__(self):
        self.redis_client = None
        self.enabled = settings.enable_redis_cache and REDIS_AVAILABLE

        if self.enabled:
            try:
                self.redis_client = redis.from_url(
                    settings.redis_url,
                    decode_responses=False,  # Handle bytes manually for pickle support
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                # Test connection
                self.redis_client.ping()
                logger.info("Redis cache service initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Redis: {e}")
                self.enabled = False
        else:
            if not REDIS_AVAILABLE:
                logger.warning("Redis not installed - caching disabled")
            else:
                logger.info("Redis caching disabled in settings")

    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """
        Get typed value from cache.

        Args:
            key: Cache key
            default: Default value if key not found

        Returns:
            Cached value or default
        """
        if not self.enabled or not self.redis_client:
            return default

        try:
            value = self.redis_client.get(key)
            if value is None:
                return default

            # Try to deserialize as JSON first, then pickle
            try:
                return json.loads(value.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                try:
                    return pickle.loads(value)
                except (pickle.PickleError, TypeError):
                    return value.decode("utf-8") if isinstance(value, bytes) else value
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return default

    def set(self, key: str, value: T, ttl: Optional[int] = None) -> bool:
        """
        Set typed value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache (typed)
            ttl: Time to live in seconds

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False

        try:
            # Serialize value based on type
            if isinstance(value, (dict, list, tuple)) or value is None:
                # JSON-serializable types
                serialized = json.dumps(value, default=str)
            elif isinstance(value, (str, int, float, bool)):
                # Simple types - JSON serialize for consistency
                serialized = json.dumps(value)
            else:
                # Complex objects - use pickle
                try:
                    serialized = pickle.dumps(value)
                except (pickle.PickleError, TypeError):
                    # Fallback to string representation
                    serialized = str(value).encode("utf-8")

            # Set with TTL
            if ttl:
                return self.redis_client.setex(key, ttl, serialized)
            else:
                return self.redis_client.set(key, serialized)
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if not self.enabled or not self.redis_client:
            return False

        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern."""
        if not self.enabled or not self.redis_client:
            return 0

        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error for pattern {pattern}: {e}")
            return 0

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.enabled or not self.redis_client:
            return False

        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

    def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for existing key."""
        if not self.enabled or not self.redis_client:
            return False

        try:
            return self.redis_client.expire(key, ttl)
        except Exception as e:
            logger.error(f"Cache expire error for key {key}: {e}")
            return False

    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment numeric value."""
        if not self.enabled or not self.redis_client:
            return None

        try:
            return self.redis_client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return None

    def get_ttl(self, key: str) -> int:
        """Get TTL for key."""
        if not self.enabled or not self.redis_client:
            return -1

        try:
            return self.redis_client.ttl(key)
        except Exception as e:
            logger.error(f"Cache TTL error for key {key}: {e}")
            return -1

    def get_memory_info(self) -> dict:
        """Get Redis memory information."""
        if not self.enabled or not self.redis_client:
            return {"error": "Redis not available"}

        try:
            info = self.redis_client.info("memory")
            return {
                "used_memory": info.get("used_memory_human"),
                "used_memory_rss": info.get("used_memory_rss_human"),
                "used_memory_peak": info.get("used_memory_peak_human"),
                "maxmemory": info.get("maxmemory_human"),
            }
        except Exception as e:
            logger.error(f"Error getting Redis memory info: {e}")
            return {"error": str(e)}

    def flush_db(self) -> bool:
        """Flush all keys from current database (use with caution)."""
        if not self.enabled or not self.redis_client:
            return False

        try:
            return self.redis_client.flushdb()
        except Exception as e:
            logger.error(f"Error flushing Redis database: {e}")
            return False

    def create_typed_cache(self, key_prefix: str) -> TypedCache[T]:
        """
        Create a typed cache instance for better type safety.

        Args:
            key_prefix: Prefix for cache keys

        Returns:
            Typed cache instance
        """
        return TypedCache(self, key_prefix)

    def get_string_cache(self, key_prefix: str) -> TypedCache[str]:
        """Create a typed cache for string values."""
        return self.create_typed_cache(key_prefix)

    def get_dict_cache(self, key_prefix: str) -> TypedCache[Dict]:
        """Create a typed cache for dictionary values."""
        return self.create_typed_cache(key_prefix)

    def get_list_cache(self, key_prefix: str) -> TypedCache[List]:
        """Create a typed cache for list values."""
        return self.create_typed_cache(key_prefix)

    def get_int_cache(self, key_prefix: str) -> TypedCache[int]:
        """Create a typed cache for integer values."""
        return self.create_typed_cache(key_prefix)


class ConversationCacheService:
    """High-level caching service for conversations."""

    def __init__(self, cache_service: CacheService):
        self.cache = cache_service

    def get_conversation(self, user_id: int, conversation_id: int) -> Optional[dict]:
        """Get cached conversation."""
        key = f"conversation:{user_id}:{conversation_id}"
        return self.cache.get(key)

    def set_conversation(
        self, user_id: int, conversation_id: int, data: dict, ttl: Optional[int] = None
    ) -> bool:
        """Cache conversation."""
        key = f"conversation:{user_id}:{conversation_id}"
        ttl = ttl or settings.cache_conversation_detail_ttl
        return self.cache.set(key, data, ttl)

    def delete_conversation(self, user_id: int, conversation_id: int) -> bool:
        """Delete cached conversation."""
        key = f"conversation:{user_id}:{conversation_id}"
        return self.cache.delete(key)

    def get_conversation_list(
        self, user_id: int, page: int, page_size: int, filters: dict = None
    ) -> Optional[dict]:
        """Get cached conversation list."""
        filter_hash = hash(str(sorted(filters.items()))) if filters else ""
        key = f"conversation_list:{user_id}:{page}:{page_size}:{filter_hash}"
        return self.cache.get(key)

    def set_conversation_list(
        self,
        user_id: int,
        page: int,
        page_size: int,
        data: dict,
        filters: dict = None,
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache conversation list."""
        filter_hash = hash(str(sorted(filters.items()))) if filters else ""
        key = f"conversation_list:{user_id}:{page}:{page_size}:{filter_hash}"
        ttl = ttl or settings.cache_conversation_list_ttl
        return self.cache.set(key, data, ttl)

    def get_search_results(
        self, user_id: int, query_hash: str, page: int, page_size: int
    ) -> Optional[dict]:
        """Get cached search results."""
        key = f"search:{user_id}:{query_hash}:{page}:{page_size}"
        return self.cache.get(key)

    def set_search_results(
        self,
        user_id: int,
        query_hash: str,
        page: int,
        page_size: int,
        data: dict,
        ttl: Optional[int] = None,
    ) -> bool:
        """Cache search results."""
        key = f"search:{user_id}:{query_hash}:{page}:{page_size}"
        ttl = ttl or settings.cache_search_results_ttl
        return self.cache.set(key, data, ttl)

    def get_user_tags(self, user_id: int) -> Optional[List[str]]:
        """Get cached user tags."""
        key = f"user_tags:{user_id}"
        return self.cache.get(key)

    def set_user_tags(self, user_id: int, tags: List[str], ttl: int = 3600) -> bool:
        """Cache user tags."""
        key = f"user_tags:{user_id}"
        return self.cache.set(key, tags, ttl)

    def invalidate_user_cache(self, user_id: int) -> int:
        """Invalidate all cache entries for a user."""
        patterns = [
            f"conversation:{user_id}:*",
            f"conversation_list:{user_id}:*",
            f"search:{user_id}:*",
            f"user_tags:{user_id}",
        ]

        total_deleted = 0
        for pattern in patterns:
            total_deleted += self.cache.delete_pattern(pattern)

        return total_deleted

    def get_pinned_conversations(self, user_id: int) -> Optional[List[dict]]:
        """Get cached pinned conversations."""
        key = f"pinned_conversations:{user_id}"
        return self.cache.get(key)

    def set_pinned_conversations(
        self, user_id: int, conversations: List[dict], ttl: int = 600
    ) -> bool:
        """Cache pinned conversations."""
        key = f"pinned_conversations:{user_id}"
        return self.cache.set(key, conversations, ttl)

    def get_message(self, conversation_id: int, message_id: int) -> Optional[dict]:
        """Get cached message."""
        key = f"message:{conversation_id}:{message_id}"
        return self.cache.get(key)

    def set_message(
        self, conversation_id: int, message_id: int, data: dict, ttl: int = 1800
    ) -> bool:
        """Cache message."""
        key = f"message:{conversation_id}:{message_id}"
        return self.cache.set(key, data, ttl)

    def get_message_list(
        self, conversation_id: int, page: int, page_size: int
    ) -> Optional[dict]:
        """Get cached message list."""
        key = f"message_list:{conversation_id}:{page}:{page_size}"
        return self.cache.get(key)

    def set_message_list(
        self,
        conversation_id: int,
        page: int,
        page_size: int,
        data: dict,
        ttl: int = 600,
    ) -> bool:
        """Cache message list."""
        key = f"message_list:{conversation_id}:{page}:{page_size}"
        return self.cache.set(key, data, ttl)

    def invalidate_conversation_cache(self, conversation_id: int) -> int:
        """Invalidate all cache entries for a conversation."""
        patterns = [f"message:{conversation_id}:*", f"message_list:{conversation_id}:*"]

        total_deleted = 0
        for pattern in patterns:
            total_deleted += self.cache.delete_pattern(pattern)

        return total_deleted


# Global cache service instance
cache_service = CacheService()
conversation_cache = ConversationCacheService(cache_service)
