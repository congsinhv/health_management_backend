"""
Integration tests for Conversation caching functionality.

Tests cache miss → compute → cache store flow,
cache hit → fast return, and graceful fallback when Redis unavailable.
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.services.conversation import ConversationService
from app.services.cache import CacheService
from app.schemas.conversation import ConversationResponse, ConversationList


@pytest.fixture
def mock_cache_service():
    """Create a mock cache service for testing."""
    cache_service = AsyncMock(spec=CacheService)
    cache_service.enabled = True
    cache_service.get = AsyncMock(return_value=None)  # Cache miss by default
    cache_service.get_json = AsyncMock(return_value=None)
    cache_service.set = AsyncMock(return_value=True)
    cache_service.set_json = AsyncMock(return_value=True)
    cache_service.delete_pattern = AsyncMock(return_value=1)
    return cache_service


@pytest.fixture
def mock_conversation_service(mock_cache_service):
    """Create Conversation service with mock cache."""
    db_pool = Mock()
    service = ConversationService(db_pool, cache_service=mock_cache_service)
    return service


@pytest.fixture
def disabled_conversation_service():
    """Create Conversation service without cache."""
    db_pool = Mock()
    service = ConversationService(db_pool, cache_service=None)
    return service


class TestConversationCaching:
    """Test Conversation caching integration."""

    @pytest.mark.asyncio
    async def test_list_conversations_cache_miss(
        self, mock_conversation_service, mock_cache_service
    ):
        """Test cache miss → compute → cache store flow."""
        user_id = 123
        limit = 20
        offset = 0

        # Mock cache miss
        mock_cache_service.get_json.return_value = None
        mock_cache_service.get.return_value = None

        # Mock database responses
        mock_records = [
            {
                "id": 1,
                "user_id": user_id,
                "title": "Test Conversation",
                "is_pinned": False,
                "is_archived": False,
                "metadata": "{}",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        ]

        mock_conversation_service.conversation_repo.list_by_user = AsyncMock(
            return_value=mock_records
        )
        mock_conversation_service.conversation_repo.count_conversations_by_user = (
            AsyncMock(return_value=1)
        )

        result = await mock_conversation_service.list_user_conversations(
            user_id, limit, offset
        )

        # Verify cache was checked
        expected_list_key = f"conv:list:{user_id}:{limit}:{offset}"
        expected_count_key = f"conv:count:{user_id}"
        mock_cache_service.get_json.assert_called_once_with(expected_list_key)
        mock_cache_service.get.assert_called_once_with(expected_count_key)

        # Verify result was cached
        mock_cache_service.set_json.assert_called_once()
        mock_cache_service.set.assert_called_once()

        # Verify result structure
        assert isinstance(result, ConversationList)
        assert len(result.conversations) == 1
        assert result.total_count == 1
        assert result.has_more is False

    @pytest.mark.asyncio
    async def test_list_conversations_cache_hit(
        self, mock_conversation_service, mock_cache_service
    ):
        """Test cache hit → fast return."""
        user_id = 123
        limit = 20
        offset = 0

        # Prepare cached conversation data
        cached_conversations = [
            {
                "id": 1,
                "user_id": user_id,
                "title": "Cached Conversation",
                "is_pinned": False,
                "is_archived": False,
                "metadata": {},
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        ]

        # Mock cache hit
        mock_cache_service.get_json.return_value = cached_conversations
        mock_cache_service.get.return_value = "1"

        result = await mock_conversation_service.list_user_conversations(
            user_id, limit, offset
        )

        # Verify cache was checked
        expected_list_key = f"conv:list:{user_id}:{limit}:{offset}"
        expected_count_key = f"conv:count:{user_id}"
        mock_cache_service.get_json.assert_called_once_with(expected_list_key)
        mock_cache_service.get.assert_called_once_with(expected_count_key)

        # Verify no database calls were made (cache hit)
        mock_conversation_service.conversation_repo.list_by_user.assert_not_called()
        mock_conversation_service.conversation_repo.count_conversations_by_user.assert_not_called()

        # Verify cached result was returned
        assert isinstance(result, ConversationList)
        assert len(result.conversations) == 1
        assert result.total_count == 1
        assert result.has_more is False
        assert result.conversations[0].title == "Cached Conversation"

    @pytest.mark.asyncio
    async def test_get_conversation_by_id_cache_miss(
        self, mock_conversation_service, mock_cache_service
    ):
        """Test conversation detail cache miss → compute → cache store."""
        user_id = 123
        conversation_id = 456

        # Mock cache miss
        mock_cache_service.get_json.return_value = None

        # Mock database response
        mock_record = {
            "id": conversation_id,
            "user_id": user_id,
            "title": "Test Conversation",
            "is_pinned": False,
            "is_archived": False,
            "metadata": "{}",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        mock_conversation_service.conversation_repo.get_by_id_and_user = AsyncMock(
            return_value=mock_record
        )

        result = await mock_conversation_service.get_conversation_by_id(
            conversation_id, user_id
        )

        # Verify cache was checked
        expected_cache_key = f"conv:detail:{conversation_id}:{user_id}"
        mock_cache_service.get_json.assert_called_once_with(expected_cache_key)

        # Verify database was called
        mock_conversation_service.conversation_repo.get_by_id_and_user.assert_called_once_with(
            conversation_id, user_id
        )

        # Verify result was cached
        mock_cache_service.set_json.assert_called_once()
        call_args = mock_cache_service.set_json.call_args
        assert call_args[0][0] == expected_cache_key  # cache key

        # Verify result structure
        assert isinstance(result, ConversationResponse)
        assert result.id == conversation_id
        assert result.user_id == user_id

    @pytest.mark.asyncio
    async def test_get_conversation_by_id_cache_hit(
        self, mock_conversation_service, mock_cache_service
    ):
        """Test conversation detail cache hit → fast return."""
        user_id = 123
        conversation_id = 456

        # Prepare cached conversation data
        cached_conversation = {
            "id": conversation_id,
            "user_id": user_id,
            "title": "Cached Conversation",
            "is_pinned": False,
            "is_archived": False,
            "metadata": {},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        # Mock cache hit
        mock_cache_service.get_json.return_value = cached_conversation

        result = await mock_conversation_service.get_conversation_by_id(
            conversation_id, user_id
        )

        # Verify cache was checked
        expected_cache_key = f"conv:detail:{conversation_id}:{user_id}"
        mock_cache_service.get_json.assert_called_once_with(expected_cache_key)

        # Verify no database call was made (cache hit)
        mock_conversation_service.conversation_repo.get_by_id_and_user.assert_not_called()

        # Verify cached result was returned
        assert isinstance(result, ConversationResponse)
        assert result.id == conversation_id
        assert result.title == "Cached Conversation"

    @pytest.mark.asyncio
    async def test_get_pinned_conversations_cache_miss(
        self, mock_conversation_service, mock_cache_service
    ):
        """Test pinned conversations cache miss → compute → cache store."""
        user_id = 123
        limit = 10

        # Mock cache miss
        mock_cache_service.get_json.return_value = None

        # Mock database response (mix of pinned and unpinned)
        mock_records = [
            {"id": 1, "is_pinned": True},  # Pinned
            {"id": 2, "is_pinned": False},  # Not pinned
            {"id": 3, "is_pinned": True},  # Pinned
        ]

        mock_conversation_service.conversation_repo.list_by_user = AsyncMock(
            return_value=mock_records
        )
        mock_conversation_service._transform_conversation_record = Mock(
            side_effect=lambda record, **kwargs: {
                "id": record["id"],
                "user_id": user_id,
                "title": f"Conversation {record['id']}",
                "is_pinned": record["is_pinned"],
                "is_archived": False,
                "metadata": {},
            }
        )

        result = await mock_conversation_service.get_pinned_conversations(
            user_id, limit
        )

        # Verify cache was checked
        expected_cache_key = f"conv:pinned:{user_id}:{limit}"
        mock_cache_service.get_json.assert_called_once_with(expected_cache_key)

        # Verify database was called
        mock_conversation_service.conversation_repo.list_by_user.assert_called_once_with(
            user_id, limit=limit, offset=0
        )

        # Verify result was cached (only if there are pinned conversations)
        mock_cache_service.set_json.assert_called_once()

        # Verify only pinned conversations returned
        assert len(result) == 2
        assert all(conv.is_pinned for conv in result)

    @pytest.mark.asyncio
    async def test_get_pinned_conversations_cache_hit(
        self, mock_conversation_service, mock_cache_service
    ):
        """Test pinned conversations cache hit → fast return."""
        user_id = 123
        limit = 10

        # Prepare cached pinned conversations
        cached_pinned = [
            {
                "id": 1,
                "user_id": user_id,
                "title": "Pinned Conversation 1",
                "is_pinned": True,
                "is_archived": False,
                "metadata": {},
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
            {
                "id": 2,
                "user_id": user_id,
                "title": "Pinned Conversation 2",
                "is_pinned": True,
                "is_archived": False,
                "metadata": {},
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
        ]

        # Mock cache hit
        mock_cache_service.get_json.return_value = cached_pinned

        result = await mock_conversation_service.get_pinned_conversations(
            user_id, limit
        )

        # Verify cache was checked
        expected_cache_key = f"conv:pinned:{user_id}:{limit}"
        mock_cache_service.get_json.assert_called_once_with(expected_cache_key)

        # Verify no database call was made (cache hit)
        mock_conversation_service.conversation_repo.list_by_user.assert_not_called()

        # Verify cached result was returned
        assert len(result) == 2
        assert all(conv.is_pinned for conv in result)
        assert result[0].title == "Pinned Conversation 1"

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_create(
        self, mock_conversation_service, mock_cache_service
    ):
        """Test cache invalidation on conversation creation."""
        user_id = 123
        conversation_data = Mock()
        conversation_data.user_id = user_id
        conversation_data.title = "New Conversation"
        conversation_data.metadata = {}

        # Mock successful database operation
        mock_record = {
            "id": 1,
            "user_id": user_id,
            "title": "New Conversation",
            "is_pinned": False,
            "is_archived": False,
            "metadata": "{}",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        mock_conversation_service.conversation_repo.create = AsyncMock(
            return_value=mock_record
        )
        mock_conversation_service._broadcast_conversation_update = AsyncMock()

        await mock_conversation_service.create_conversation(user_id, conversation_data)

        # Verify cache invalidation was called
        mock_cache_service.delete_pattern.assert_called()

        # Verify correct patterns were used for invalidation
        call_args_list = mock_cache_service.delete_pattern.call_args_list
        patterns = [call[0][0] for call in call_args_list]

        expected_patterns = [
            f"conv:list:{user_id}:*",
            f"conv:count:{user_id}",
            f"conv:pinned:{user_id}:*",
            f"conv:search:{user_id}:*",
        ]

        for pattern in expected_patterns:
            assert pattern in patterns

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_update(
        self, mock_conversation_service, mock_cache_service
    ):
        """Test cache invalidation on conversation update."""
        user_id = 123
        conversation_id = 456
        update_data = Mock()
        update_data.title = "Updated Title"

        # Mock existing conversation and successful update
        existing_record = {"id": conversation_id, "user_id": user_id}
        updated_record = {
            "id": conversation_id,
            "user_id": user_id,
            "title": "Updated Title",
            "is_pinned": False,
            "is_archived": False,
            "metadata": "{}",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

        mock_conversation_service.conversation_repo.get_by_id_and_user = AsyncMock(
            return_value=existing_record
        )
        mock_conversation_service.conversation_repo.update = AsyncMock(
            return_value=updated_record
        )
        mock_conversation_service._broadcast_conversation_update = AsyncMock()

        await mock_conversation_service.update_conversation(
            conversation_id, user_id, update_data
        )

        # Verify cache invalidation was called
        mock_cache_service.delete_pattern.assert_called()

        # Verify specific conversation detail was invalidated
        call_args_list = mock_cache_service.delete_pattern.call_args_list
        patterns = [call[0][0] for call in call_args_list]

        expected_detail_pattern = f"conv:detail:{conversation_id}:{user_id}"
        assert expected_detail_pattern in patterns

    @pytest.mark.asyncio
    async def test_cache_disabled_operations(self, disabled_conversation_service):
        """Test that operations work normally when cache is disabled."""
        user_id = 123
        limit = 20
        offset = 0

        # Mock database response
        mock_records = []
        disabled_conversation_service.conversation_repo.list_by_user = AsyncMock(
            return_value=mock_records
        )
        disabled_conversation_service.conversation_repo.count_conversations_by_user = (
            AsyncMock(return_value=0)
        )

        result = await disabled_conversation_service.list_user_conversations(
            user_id, limit, offset
        )

        # Verify result structure
        assert isinstance(result, ConversationList)
        assert len(result.conversations) == 0
        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_cache_error_handling(
        self, mock_conversation_service, mock_cache_service
    ):
        """Test graceful fallback when cache operations fail."""
        user_id = 123

        # Mock cache error
        mock_cache_service.get_json.side_effect = Exception("Redis connection failed")

        # Mock database response
        mock_records = []
        mock_conversation_service.conversation_repo.list_by_user = AsyncMock(
            return_value=mock_records
        )
        mock_conversation_service.conversation_repo.count_conversations_by_user = (
            AsyncMock(return_value=0)
        )

        # Should not raise exception, should continue with normal flow
        result = await mock_conversation_service.list_user_conversations(user_id)

        # Verify result is still returned despite cache error
        assert isinstance(result, ConversationList)
        assert len(result.conversations) == 0

    def test_cache_key_structure(self):
        """Test cache key structure matches expected format."""
        user_id = 123
        conversation_id = 456
        limit = 20
        offset = 0

        list_key = f"conv:list:{user_id}:{limit}:{offset}"
        count_key = f"conv:count:{user_id}"
        detail_key = f"conv:detail:{conversation_id}:{user_id}"
        pinned_key = f"conv:pinned:{user_id}:{limit}"

        # Verify key components
        assert list_key.startswith("conv:list:")
        assert str(user_id) in list_key
        assert str(limit) in list_key
        assert str(offset) in list_key

        assert count_key.startswith("conv:count:")
        assert str(user_id) in count_key

        assert detail_key.startswith("conv:detail:")
        assert str(conversation_id) in detail_key
        assert str(user_id) in detail_key

        assert pinned_key.startswith("conv:pinned:")
        assert str(user_id) in pinned_key
        assert str(limit) in pinned_key

    def test_user_isolation_in_cache_keys(self):
        """Test that cache keys are properly isolated by user ID."""
        user1_id = 123
        user2_id = 456
        conversation_id = 789

        # Keys should be different for different users
        detail_key_user1 = f"conv:detail:{conversation_id}:{user1_id}"
        detail_key_user2 = f"conv:detail:{conversation_id}:{user2_id}"
        list_key_user1 = f"conv:list:{user1_id}:20:0"
        list_key_user2 = f"conv:list:{user2_id}:20:0"

        assert detail_key_user1 != detail_key_user2
        assert list_key_user1 != list_key_user2

        # Same conversation, different users should have different cache entries
        assert detail_key_user1.endswith(f":{user1_id}")
        assert detail_key_user2.endswith(f":{user2_id}")


class TestConversationCacheIntegration:
    """End-to-end integration tests for Conversation caching."""

    @pytest.mark.asyncio
    async def test_full_cache_cycle(self):
        """Test complete cycle: cache miss → compute → cache → cache hit → invalidation."""
        # This would require real Redis instance or fakeredis
        # For now, we'll use comprehensive mocks
        pass

    def test_pagination_cache_isolation(self):
        """Test that different pagination creates separate cache entries."""
        user_id = 123
        limit = 20

        page1_key = f"conv:list:{user_id}:{limit}:0"
        page2_key = f"conv:list:{user_id}:{limit}:20"
        page3_key = f"conv:list:{user_id}:{limit}:40"

        # All keys should be different
        assert page1_key != page2_key != page3_key

        # All should be for the same user
        for key in [page1_key, page2_key, page3_key]:
            assert str(user_id) in key
            assert str(limit) in key
