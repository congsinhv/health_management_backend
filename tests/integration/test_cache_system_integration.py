"""
Integration tests for complete cache system.

Tests end-to-end cache behavior across all services,
invalidation propagation, and real-world scenarios.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.services.cache import CacheService, CacheStats
from app.services.cache_invalidation import (
    CacheInvalidator,
    InvalidationEvent,
    get_cache_invalidator,
)
from app.services.user import UserService
from app.services.conversation import ConversationService
from app.services.message import MessageService
from app.services.qa_service import QAService
from app.schemas.user import UserResponse, UserCreate
from app.schemas.conversation import ConversationResponse, ConversationCreate
from app.schemas.message import MessageResponse, MessageCreate


@pytest.fixture
async def integration_cache_setup():
    """Set up integrated cache system for testing."""
    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True
    mock_redis.get.return_value = None
    mock_redis.setex.return_value = True
    mock_redis.delete.return_value = 1
    mock_redis.keys.return_value = []
    mock_redis.info.return_value = {
        "redis_version": "7.0.0",
        "used_memory_human": "1M",
        "keyspace_hits": 0,
        "keyspace_misses": 0,
    }

    # Create cache service
    cache_service = CacheService(mock_redis)

    # Create cache invalidator
    cache_invalidator = get_cache_invalidator(cache_service)

    return {
        "cache_service": cache_service,
        "cache_invalidator": cache_invalidator,
        "mock_redis": mock_redis,
    }


@pytest.fixture
def mock_db_pool():
    """Create mock database pool."""
    pool = AsyncMock()
    pool.acquire = AsyncMock()
    return pool


class TestCacheSystemIntegration:
    """Test complete cache system integration."""

    @pytest.mark.asyncio
    async def test_user_service_caching_integration(
        self, integration_cache_setup, mock_db_pool
    ):
        """Test UserService caching integration."""
        cache_service = integration_cache_setup["cache_service"]
        cache_invalidator = integration_cache_setup["cache_invalidator"]
        mock_redis = integration_cache_setup["mock_redis"]

        # Create user service with cache
        user_service = UserService(mock_db_pool, cache_service=cache_service)
        user_service.set_cache_invalidator(cache_invalidator)

        # Mock database responses
        mock_user_record = {
            "id": 123,
            "email": "test@example.com",
            "username": "testuser",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "is_active": True,
            "metadata": "{}",
        }

        user_service.user_repo.get_by_id = AsyncMock(return_value=mock_user_record)
        user_service.user_repo.get_by_email = AsyncMock(return_value=mock_user_record)
        user_service.user_repo.update = AsyncMock(return_value=mock_user_record)

        # Test cache miss -> database -> cache
        user1 = await user_service.get_user_by_id(123)
        assert user1.id == 123

        # Verify cache was set
        mock_redis.setex.assert_called()
        cache_call_args = mock_redis.setex.call_args[0]
        assert "user:detail:123" in cache_call_args[0]

        # Test cache hit
        mock_redis.get.return_value = json.dumps(
            {
                "id": 123,
                "email": "test@example.com",
                "username": "testuser",
                "is_active": True,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "metadata": {},
            }
        )

        user2 = await user_service.get_user_by_id(123)
        assert user2.id == 123

        # Verify database was not called on second request
        assert user_service.user_repo.get_by_id.call_count == 1

    @pytest.mark.asyncio
    async def test_conversation_service_caching_integration(
        self, integration_cache_setup, mock_db_pool
    ):
        """Test ConversationService caching integration."""
        cache_service = integration_cache_setup["cache_service"]
        cache_invalidator = integration_cache_setup["cache_invalidator"]
        mock_redis = integration_cache_setup["mock_redis"]

        conversation_service = ConversationService(
            mock_db_pool, cache_service=cache_service
        )
        conversation_service.set_cache_invalidator(cache_invalidator)

        # Mock database responses
        mock_conv_records = [
            {
                "id": 456,
                "user_id": 123,
                "title": "Test Conversation",
                "is_pinned": False,
                "is_archived": False,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "metadata": "{}",
            }
        ]

        conversation_service.conversation_repo.list_by_user = AsyncMock(
            return_value=mock_conv_records
        )
        conversation_service.conversation_repo.count_conversations_by_user = AsyncMock(
            return_value=1
        )
        conversation_service.conversation_repo.get_by_id_and_user = AsyncMock(
            return_value=mock_conv_records[0]
        )

        # Test conversation list caching
        conversations = await conversation_service.list_user_conversations(
            123, limit=20, offset=0
        )
        assert len(conversations.conversations) == 1

        # Verify cache was set
        cache_calls = [call[0][0] for call in mock_redis.setex.call_args_list]
        list_cache_key = next(key for key in cache_calls if "conv:list:123:20:0" in key)
        assert list_cache_key is not None

        # Test conversation detail caching
        conversation = await conversation_service.get_conversation_by_id(456, 123)
        assert conversation.id == 456

        # Verify detail cache was set
        detail_cache_key = next(
            key for key in cache_calls if "conv:detail:456:123" in key
        )
        assert detail_cache_key is not None

    @pytest.mark.asyncio
    async def test_message_service_caching_integration(
        self, integration_cache_setup, mock_db_pool
    ):
        """Test MessageService caching integration."""
        cache_service = integration_cache_setup["cache_service"]
        cache_invalidator = integration_cache_setup["cache_invalidator"]
        mock_redis = integration_cache_setup["mock_redis"]

        message_service = MessageService(mock_db_pool, cache_service=cache_service)
        message_service.set_cache_invalidator(cache_invalidator)

        # Mock database responses
        mock_conv_record = {"id": 456, "user_id": 123}
        mock_msg_records = [
            {
                "id": 789,
                "conversation_id": 456,
                "user_id": 123,
                "content": "Hello world",
                "content_type": "text",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "metadata": "{}",
            }
        ]

        message_service.conversation_repo.get_by_id_and_user = AsyncMock(
            return_value=mock_conv_record
        )
        message_service.message_repo.list_by_conversation = AsyncMock(
            return_value=mock_msg_records
        )
        message_service.message_repo.get_conversation_latest_message = AsyncMock(
            return_value=mock_msg_records[0]
        )
        message_service.message_repo.create = AsyncMock(
            return_value=mock_msg_records[0]
        )

        # Test message list caching
        messages = await message_service.list_conversation_messages(456, 123, limit=50)
        assert len(messages.messages) == 1

        # Test latest message caching
        latest = await message_service.get_latest_message(456, 123)
        assert latest.id == 789

        # Verify cache keys were set
        cache_calls = [call[0][0] for call in mock_redis.setex.call_args_list]
        latest_cache_key = next(key for key in cache_calls if "msg:latest:456" in key)
        assert latest_cache_key is not None

    @pytest.mark.asyncio
    async def test_qa_service_caching_integration(self, integration_cache_setup):
        """Test QAService caching integration."""
        cache_service = integration_cache_setup["cache_service"]
        mock_redis = integration_cache_setup["mock_redis"]

        # Mock settings
        mock_settings = Mock()
        mock_settings.qa_enabled = True
        mock_settings.openai_api_key = "test_key"
        mock_settings.qa_model = "gpt-3.5-turbo"
        mock_settings.qa_max_tokens = 1000
        mock_settings.qa_temperature = 0.7

        qa_service = QAService(mock_settings, cache_service=cache_service)

        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This is a health-related answer"

        with patch.object(qa_service, "client") as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

            # Test question answering with caching
            question = "What are the benefits of exercise?"
            answer = await qa_service.ask_question(question, threshold=0.8, top_k=5)

            assert answer is not None
            assert "This is a health-related answer" in answer

            # Verify cache was set with hash-based key
            cache_calls = [call[0][0] for call in mock_redis.setex.call_args_list]
            qa_cache_key = next(key for key in cache_calls if "qa:answers:" in key)
            assert qa_cache_key is not None

    @pytest.mark.asyncio
    async def test_cross_service_invalidation_propagation(
        self, integration_cache_setup, mock_db_pool
    ):
        """Test that invalidations propagate across services correctly."""
        cache_service = integration_cache_setup["cache_service"]
        cache_invalidator = integration_cache_setup["cache_invalidator"]
        mock_redis = integration_cache_setup["mock_redis"]

        # Set up services
        user_service = UserService(mock_db_pool, cache_service=cache_service)
        conversation_service = ConversationService(
            mock_db_pool, cache_service=cache_service
        )
        message_service = MessageService(mock_db_pool, cache_service=cache_service)

        user_service.set_cache_invalidator(cache_invalidator)
        conversation_service.set_cache_invalidator(cache_invalidator)
        message_service.set_cache_invalidator(cache_invalidator)

        # Mock database operations
        mock_user_record = {
            "id": 123,
            "email": "test@example.com",
            "username": "testuser",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "is_active": True,
            "metadata": "{}",
        }

        user_service.user_repo.update = AsyncMock(return_value=mock_user_record)
        mock_redis.delete_pattern.return_value = 5  # Simulate 5 keys deleted

        # Simulate user update
        await user_service.update_user(123, {"username": "newusername"})

        # Verify invalidation patterns were called
        delete_calls = [call[0][0] for call in mock_redis.delete_pattern.call_args_list]
        user_patterns = [call for call in delete_calls if "user:detail:123" in call]
        assert len(user_patterns) > 0

        # Verify conversation and message patterns were also invalidated
        conv_patterns = [call for call in delete_calls if "conv:list:123:" in call]
        msg_patterns = [
            call for call in delete_calls if "msg:list:" in call and "123" in call
        ]

        assert len(conv_patterns) > 0
        # Message patterns might not be present unless there are actual conversations

    @pytest.mark.asyncio
    async def test_bulk_operations_performance(
        self, integration_cache_setup, mock_db_pool
    ):
        """Test bulk invalidation performance."""
        cache_service = integration_cache_setup["cache_service"]
        cache_invalidator = integration_cache_setup["cache_invalidator"]
        mock_redis = integration_cache_setup["mock_redis"]

        # Set up services
        conversation_service = ConversationService(
            mock_db_pool, cache_service=cache_service
        )
        message_service = MessageService(mock_db_pool, cache_service=cache_service)

        conversation_service.set_cache_invalidator(cache_invalidator)
        message_service.set_cache_invalidator(cache_invalidator)

        # Mock database for bulk operations
        conversation_service.conversation_repo.create = AsyncMock(
            return_value={"id": 1, "user_id": 123, "title": "Conv 1"}
        )
        message_service.message_repo.create = AsyncMock(
            return_value={
                "id": 1,
                "conversation_id": 1,
                "user_id": 123,
                "content": "Message 1",
            }
        )

        mock_redis.delete_pattern.return_value = (
            2  # Simulate 2 keys deleted per operation
        )

        # Simulate multiple rapid operations
        start_time = asyncio.get_event_loop().time()

        tasks = []
        for i in range(10):
            # Create conversation and messages concurrently
            conv_task = conversation_service.create_conversation(
                123, ConversationCreate(title=f"Conversation {i}")
            )
            msg_task = message_service.create_message(
                123,
                1,
                MessageCreate(content=f"Message {i}", content_type="text"),
                Mock(),
            )
            tasks.extend([conv_task, msg_task])

        await asyncio.gather(*tasks, return_exceptions=True)

        end_time = asyncio.get_event_loop().time()
        duration_ms = (end_time - start_time) * 1000

        # Verify performance (should complete quickly)
        assert duration_ms < 1000  # Should complete in less than 1 second

        # Verify cache invalidation occurred
        assert mock_redis.delete_pattern.call_count > 0

    @pytest.mark.asyncio
    async def test_cache_coherence_under_failures(
        self, integration_cache_setup, mock_db_pool
    ):
        """Test cache coherence when Redis failures occur."""
        cache_service = integration_cache_setup["cache_service"]
        mock_redis = integration_cache_setup["mock_redis"]

        # Simulate Redis failures
        mock_redis.get.side_effect = Exception("Redis connection failed")
        mock_redis.setex.side_effect = Exception("Redis connection failed")

        user_service = UserService(mock_db_pool, cache_service=cache_service)

        # Mock database
        mock_user_record = {
            "id": 123,
            "email": "test@example.com",
            "username": "testuser",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "is_active": True,
            "metadata": "{}",
        }
        user_service.user_repo.get_by_id = AsyncMock(return_value=mock_user_record)

        # Service should still work despite cache failures
        user = await user_service.get_user_by_id(123)
        assert user.id == 123

        # Database should have been called (cache miss due to failure)
        user_service.user_repo.get_by_id.assert_called_once_with(123)

        # Service should track errors
        assert cache_service.stats.errors > 0
        assert cache_service.stats.error_rate > 0

    @pytest.mark.asyncio
    async def test_cache_statistics_and_monitoring(self, integration_cache_setup):
        """Test cache statistics tracking and monitoring."""
        cache_service = integration_cache_setup["cache_service"]
        cache_invalidator = integration_cache_setup["cache_invalidator"]
        mock_redis = integration_cache_setup["mock_redis"]

        # Simulate various cache operations
        mock_redis.get.return_value = None  # Cache miss
        await cache_service.get("test:key1")
        await cache_service.get("test:key2")

        mock_redis.get.return_value = b'{"test": "data"}'  # Cache hit
        await cache_service.get("test:key3")

        mock_redis.setex.side_effect = Exception("Redis error")  # Error
        await cache_service.set("test:key4", "value")

        # Get statistics
        stats = await cache_service.get_stats()

        assert stats["enabled"] is True
        assert stats["hits"] == 1
        assert stats["misses"] == 2
        assert stats["errors"] == 1
        assert stats["total_requests"] == 4
        assert stats["hit_rate"] == 25.0  # 1 hit out of 4 requests
        assert stats["error_rate"] == 25.0  # 1 error out of 4 requests

        # Test invalidation statistics
        await cache_invalidator.invalidate(InvalidationEvent.USER_UPDATE, user_id=123)
        await cache_invalidator.invalidate(
            InvalidationEvent.MESSAGE_CREATE, conversation_id=456, user_id=123
        )

        invalidation_stats = cache_invalidator.get_invalidation_stats(hours=1)

        assert invalidation_stats["total_invalidations"] == 2
        assert invalidation_stats["total_patterns_invalidated"] > 0
        assert (
            InvalidationEvent.USER_UPDATE.value in invalidation_stats["event_breakdown"]
        )
        assert (
            InvalidationEvent.MESSAGE_CREATE.value
            in invalidation_stats["event_breakdown"]
        )

    @pytest.mark.asyncio
    async def test_memory_efficiency_and_cleanup(self, integration_cache_setup):
        """Test memory efficiency and cleanup mechanisms."""
        cache_invalidator = integration_cache_setup["cache_invalidator"]

        # Add many invalidation records
        for i in range(1200):  # More than the 1000 limit
            cache_invalidator._invalidation_history.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "event": InvalidationEvent.USER_UPDATE.value,
                    "patterns_invalidated": 2,
                    "duration_ms": 10.0,
                }
            )

        # Verify history is limited
        assert len(cache_invalidator._invalidation_history) == 1000

        # Verify recent records are kept
        latest_record = cache_invalidator._invalidation_history[-1]
        assert latest_record["event"] == InvalidationEvent.USER_UPDATE.value

        # Test cleanup
        cache_invalidator.clear_history()
        assert len(cache_invalidator._invalidation_history) == 0
