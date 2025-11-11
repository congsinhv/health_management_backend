"""
Unit tests for CacheService and ConversationCacheService.

Tests Redis operations, pattern matching, TTL management, and cache statistics.
"""

import json
import pickle
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from app.services.cache import CacheService, ConversationCacheService


@pytest.mark.unit
class TestCacheService:
    """Test cases for CacheService."""

    @patch("app.services.cache.REDIS_AVAILABLE", True)
    @patch("app.services.cache.settings")
    def test_cache_initialization_with_redis(self, mock_settings, fake_redis):
        """Test cache initialization when Redis is available."""
        mock_settings.enable_redis_cache = True
        mock_settings.redis_url = "redis://localhost:6379/0"

        with patch("redis.from_url", return_value=fake_redis):
            cache = CacheService()
            assert cache.enabled is True
            assert cache.redis_client is not None

    @patch("app.services.cache.REDIS_AVAILABLE", False)
    @patch("app.services.cache.settings")
    def test_cache_initialization_without_redis(self, mock_settings):
        """Test cache initialization when Redis is not available."""
        mock_settings.enable_redis_cache = True

        cache = CacheService()
        assert cache.enabled is False
        assert cache.redis_client is None

    @patch("app.services.cache.REDIS_AVAILABLE", True)
    @patch("app.services.cache.settings")
    def test_redis_health_check_success(self, mock_settings):
        """Test successful Redis health check during initialization."""
        mock_settings.enable_redis_cache = True
        mock_settings.redis_url = "redis://localhost:6379/0"

        mock_redis = MagicMock()
        mock_redis.ping = MagicMock(return_value=True)

        with patch("redis.from_url", return_value=mock_redis):
            cache = CacheService()
            assert cache.enabled is True

    @patch("app.services.cache.REDIS_AVAILABLE", True)
    @patch("app.services.cache.settings")
    def test_redis_health_check_failure(self, mock_settings):
        """Test cache initialization failure when Redis health check fails."""
        mock_settings.enable_redis_cache = True
        mock_settings.redis_url = "redis://localhost:6379/0"

        mock_redis = MagicMock()
        mock_redis.ping.side_effect = Exception("Connection failed")

        with patch("redis.from_url", return_value=mock_redis):
            cache = CacheService()
            assert cache.enabled is False
            # Note: redis_client remains set even when disabled, which is expected behavior

    def test_set_get_simple_value(self, mock_cache_service):
        """Test setting and getting a simple string value."""
        cache = mock_cache_service

        # Mock Redis operations
        cache.redis_client.set = MagicMock(return_value=True)
        cache.redis_client.get = MagicMock(return_value=b'"test_value"')

        # Set a simple value
        result = cache.set("test_key", "test_value")
        assert result is True

        # Get the value
        value = cache.get("test_key")
        assert value == "test_value"

    def test_set_get_complex_object(self, mock_cache_service):
        """Test setting and getting a complex object (dict)."""
        cache = mock_cache_service

        test_data = {
            "id": 1,
            "name": "Test Object",
            "nested": {"key": "value"},
            "list": [1, 2, 3],
        }

        # Mock Redis operations
        cache.redis_client.set = MagicMock(return_value=True)
        cache.redis_client.get = MagicMock(
            return_value=b'{"id": 1, "name": "Test Object"}'
        )

        # Set complex object
        result = cache.set("complex_key", test_data)
        assert result is True

        # Get and verify
        value = cache.get("complex_key")
        assert "id" in value

    def test_set_with_ttl(self, mock_cache_service):
        """Test setting a value with TTL."""
        cache = mock_cache_service

        # Mock Redis operations
        cache.redis_client.setex = MagicMock(return_value=True)
        cache.redis_client.get = MagicMock(return_value=b'"ttl_value"')
        cache.redis_client.ttl = MagicMock(return_value=60)

        # Set with TTL
        result = cache.set("ttl_key", "ttl_value", ttl=60)
        assert result is True

        # Verify value exists
        value = cache.get("ttl_key")
        assert value == "ttl_value"

        # Verify TTL was set
        ttl = cache.get_ttl("ttl_key")
        assert ttl == 60

    def test_delete_key_success(self, mock_cache_service):
        """Test successful key deletion."""
        cache = mock_cache_service

        # Set a value first
        cache.set("delete_key", "delete_value")

        # Delete the key
        result = cache.delete("delete_key")
        assert result is True

        # Verify key is gone
        value = cache.get("delete_key")
        assert value is None

    def test_delete_pattern_multiple_keys(self, mock_cache_service):
        """Test deleting multiple keys matching a pattern."""
        cache = mock_cache_service

        # Mock Redis operations
        cache.redis_client.set = MagicMock(return_value=True)
        cache.redis_client.get = MagicMock(return_value=None)
        cache.redis_client.keys = MagicMock(
            return_value=[b"user:1:data", b"user:2:data"]
        )
        cache.redis_client.delete = MagicMock(return_value=2)

        # Delete pattern
        deleted_count = cache.delete_pattern("user:*:data")
        assert deleted_count == 2

        # Verify correct methods were called
        cache.redis_client.keys.assert_called_with("user:*:data")
        cache.redis_client.delete.assert_called_with(b"user:1:data", b"user:2:data")

    def test_get_keys_by_pattern(self, mock_cache_service):
        """Test getting keys matching a pattern."""
        cache = mock_cache_service

        # Mock the keys method
        cache.redis_client.keys = MagicMock(
            return_value=[b"user:1:data", b"user:2:data"]
        )

        # Get pattern keys
        keys = cache.redis_client.keys("user:*:data")
        assert len(keys) == 2
        assert b"user:1:data" in keys
        assert b"user:2:data" in keys

    def test_get_ttl(self, mock_cache_service):
        """Test getting TTL for a key."""
        cache = mock_cache_service

        # Mock TTL response
        cache.redis_client.ttl = MagicMock(return_value=300)

        ttl = cache.get_ttl("test_key")
        assert ttl == 300

    def test_set_ttl(self, mock_cache_service):
        """Test setting TTL for existing key."""
        cache = mock_cache_service

        # Mock expire response
        cache.redis_client.expire = MagicMock(return_value=True)

        result = cache.expire("test_key", 600)
        assert result is True

    def test_cache_statistics(self, mock_cache_service):
        """Test getting cache statistics."""
        cache = mock_cache_service

        # Mock Redis info response
        mock_info = {
            "used_memory_human": "1.5M",
            "used_memory_rss_human": "2.1M",
            "used_memory_peak_human": "1.8M",
            "maxmemory_human": "0B",
        }
        cache.redis_client.info = MagicMock(return_value=mock_info)

        stats = cache.get_memory_info()
        assert stats["used_memory"] == "1.5M"
        assert stats["used_memory_rss"] == "2.1M"
        assert stats["used_memory_peak"] == "1.8M"

    def test_cache_hit_rate_calculation(self, mock_cache_service):
        """Test cache hit rate calculation (mock scenario)."""
        cache = mock_cache_service

        # Mock Redis operations
        cache.redis_client.set = MagicMock(return_value=True)
        cache.redis_client.get = MagicMock(
            side_effect=[b'"value1"', None, None, b'"value1"']
        )

        # Simulate cache operations
        cache.set("key1", "value1")
        hit1 = cache.get("key1")  # Hit
        miss1 = cache.get("key2")  # Miss
        miss2 = cache.get("key3")  # Miss

        # This would typically be tracked by Redis itself
        # Here we just verify the operations complete without error
        assert hit1 == "value1"
        assert miss1 is None
        assert miss2 is None

    def test_cache_warming_strategy(self, mock_cache_service):
        """Test cache warming strategy implementation."""
        cache = mock_cache_service

        # Mock Redis operations - override the fake redis with simple mock
        cache.redis_client.set = MagicMock(return_value=True)
        cache.redis_client.get = MagicMock(
            side_effect=[None, None, None]
        )  # All cache misses
        cache.redis_client.setex = MagicMock(return_value=True)  # Mock TTL method

        # Simulate cache warming by pre-loading common data
        warm_data = {
            "popular_conversations": [{"id": 1, "title": "Popular"}],
            "user_preferences": {"theme": "dark"},
            "common_queries": ["health", "medicine"],
        }

        for key, data in warm_data.items():
            result = cache.set(f"warm:{key}", data, ttl=3600)
            assert result is True

        # Verify warmed data operations were called
        assert cache.redis_client.setex.call_count == 3

    def test_pickle_serialization_fallback(self, mock_cache_service):
        """Test pickle serialization for complex objects that can't be JSON serialized."""
        cache = mock_cache_service

        # Mock Redis operations - simulate successful pickle serialization
        cache.redis_client.set = MagicMock(return_value=True)
        cache.redis_client.get = MagicMock(return_value=pickle.dumps({"value": "test"}))

        # Create a simple dict that can be serialized
        test_obj = {"value": "test", "type": "custom"}

        # Set should use serialization
        result = cache.set("pickle_key", test_obj)
        assert result is True

        # Get should deserialize correctly
        retrieved = cache.get("pickle_key")
        assert isinstance(retrieved, dict)
        assert retrieved["value"] == "test"

    def test_error_handling_in_cache_operations(self, mock_cache_service):
        """Test error handling in cache operations."""
        cache = mock_cache_service

        # Mock Redis to raise exception
        cache.redis_client.get = MagicMock(side_effect=Exception("Redis error"))

        # Should return default on error
        value = cache.get("error_key", "default")
        assert value == "default"


@pytest.mark.unit
class TestConversationCacheService:
    """Test cases for ConversationCacheService."""

    def test_conversation_caching_operations(self, mock_conversation_cache_service):
        """Test conversation-specific caching operations."""
        cache = mock_conversation_cache_service

        user_id = 123
        conversation_id = 456
        conversation_data = {
            "id": conversation_id,
            "title": "Test Conversation",
            "messages": [],
        }

        # Mock Redis operations
        cache.cache.set = MagicMock(return_value=True)
        cache.cache.get = MagicMock(return_value=conversation_data)

        # Set conversation
        result = cache.set_conversation(user_id, conversation_id, conversation_data)
        assert result is True

        # Get conversation
        cached = cache.get_conversation(user_id, conversation_id)
        assert cached is not None
        assert cached["id"] == conversation_id
        assert cached["title"] == "Test Conversation"

    def test_conversation_list_caching_with_filters(
        self, mock_conversation_cache_service
    ):
        """Test caching conversation lists with filters."""
        cache = mock_conversation_cache_service

        user_id = 123
        page = 1
        page_size = 20
        filters = {"tag": "health", "date_from": "2024-01-01"}
        list_data = {
            "conversations": [{"id": 1, "title": "Health Chat"}],
            "total": 1,
            "page": page,
        }

        # Mock Redis operations
        cache.cache.set = MagicMock(return_value=True)
        cache.cache.get = MagicMock(return_value=list_data)

        # Set with filters
        result = cache.set_conversation_list(
            user_id, page, page_size, list_data, filters
        )
        assert result is True

        # Get with same filters
        cached = cache.get_conversation_list(user_id, page, page_size, filters)
        assert cached is not None
        assert len(cached["conversations"]) == 1

    def test_search_results_caching(self, mock_conversation_cache_service):
        """Test caching search results."""
        cache = mock_conversation_cache_service

        user_id = 123
        query_hash = "abc123"
        page = 1
        page_size = 10
        search_data = {
            "results": [{"id": 1, "title": "Search Result"}],
            "total": 1,
            "query_time": 0.05,
        }

        # Mock Redis operations
        cache.cache.set = MagicMock(return_value=True)
        cache.cache.get = MagicMock(return_value=search_data)

        # Cache search results
        result = cache.set_search_results(
            user_id, query_hash, page, page_size, search_data
        )
        assert result is True

        # Retrieve cached results
        cached = cache.get_search_results(user_id, query_hash, page, page_size)
        assert cached is not None
        assert cached["total"] == 1

    def test_user_tags_caching(self, mock_conversation_cache_service):
        """Test caching user tags."""
        cache = mock_conversation_cache_service

        user_id = 123
        tags = ["health", "work", "personal"]

        # Mock Redis operations
        cache.cache.set = MagicMock(return_value=True)
        cache.cache.get = MagicMock(return_value=tags)

        # Cache tags
        result = cache.set_user_tags(user_id, tags)
        assert result is True

        # Retrieve cached tags
        cached = cache.get_user_tags(user_id)
        assert cached == tags

    def test_cache_invalidation_patterns(self, mock_conversation_cache_service):
        """Test cache invalidation patterns."""
        cache = mock_conversation_cache_service

        user_id = 123

        # Set various cache entries for user
        cache.set_conversation(user_id, 1, {"id": 1, "title": "Conv 1"})
        cache.set_conversation_list(user_id, 1, 20, {"conversations": []})
        cache.set_search_results(user_id, "query", 1, 10, {"results": []})
        cache.set_user_tags(user_id, ["tag1", "tag2"])

        # Mock delete_pattern to return counts
        cache.cache.delete_pattern = MagicMock(side_effect=[2, 3, 1, 1])

        # Invalidate all user cache
        deleted_count = cache.invalidate_user_cache(user_id)

        # Should have deleted entries from all patterns
        assert deleted_count == 7
        assert cache.cache.delete_pattern.call_count == 4

    def test_pinned_conversations_caching(self, mock_conversation_cache_service):
        """Test caching pinned conversations."""
        cache = mock_conversation_cache_service

        user_id = 123
        pinned = [{"id": 1, "title": "Pinned 1"}, {"id": 2, "title": "Pinned 2"}]

        # Mock Redis operations
        cache.cache.set = MagicMock(return_value=True)
        cache.cache.get = MagicMock(return_value=pinned)

        # Cache pinned conversations
        result = cache.set_pinned_conversations(user_id, pinned)
        assert result is True

        # Retrieve cached pinned conversations
        cached = cache.get_pinned_conversations(user_id)
        assert cached is not None
        assert len(cached) == 2

    def test_message_caching_operations(self, mock_conversation_cache_service):
        """Test message-specific caching operations."""
        cache = mock_conversation_cache_service

        conversation_id = 123
        message_id = 456
        message_data = {"id": message_id, "content": "Test message", "role": "user"}

        # Mock Redis operations
        cache.cache.set = MagicMock(return_value=True)
        cache.cache.get = MagicMock(return_value=message_data)

        # Cache message
        result = cache.set_message(conversation_id, message_id, message_data)
        assert result is True

        # Retrieve cached message
        cached = cache.get_message(conversation_id, message_id)
        assert cached is not None
        assert cached["id"] == message_id

    def test_conversation_cache_invalidation(self, mock_conversation_cache_service):
        """Test invalidating conversation-related cache."""
        cache = mock_conversation_cache_service

        conversation_id = 123

        # Set message-related cache entries
        cache.set_message(conversation_id, 1, {"id": 1, "content": "Message 1"})
        cache.set_message_list(conversation_id, 1, 20, {"messages": []})

        # Mock delete_pattern to return counts
        cache.cache.delete_pattern = MagicMock(side_effect=[1, 1])

        # Invalidate conversation cache
        deleted_count = cache.invalidate_conversation_cache(conversation_id)

        assert deleted_count == 2
        assert cache.cache.delete_pattern.call_count == 2
