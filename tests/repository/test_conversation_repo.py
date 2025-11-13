"""
Tests for ConversationRepository.

Tests conversation repository operations including CRUD operations,
search functionality, pagination, tags management, and statistics.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from typing import Dict, Any, List

from app.db.conversation import ConversationRepository


@pytest.mark.repository
@pytest.mark.unit
class TestConversationRepository:
    """Test cases for ConversationRepository."""

    @pytest.fixture
    def repo(self, mock_db_pool):
        """Create repository instance with mocked pool."""
        return ConversationRepository(mock_db_pool)

    @pytest.fixture
    def sample_conversation_record(self):
        """Sample conversation record for testing."""
        return {
            "id": 1,
            "user_id": 123,
            "title": "Test Conversation",
            "question": "What is this?",
            "answer": "A test",
            "is_pinned": False,
            "tags": ["test", "example"],
            "metadata": {"key": "value"},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "deleted_at": None,
            "message_count": 5,
            "last_message_at": datetime.now(timezone.utc),
        }

    # ========================================================================
    # CREATE CONVERSATION TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_create_conversation_success(self, repo, mock_db_pool):
        """Test creating a conversation successfully."""
        # Arrange
        user_id = 123
        title = "Test Conversation"
        question = "What is this?"
        tags = ["test", "example"]
        metadata = {"key": "value"}

        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"id": 1})

        # Act
        result = await repo.create_conversation(
            user_id=user_id,
            title=title,
            question=question,
            tags=tags,
            metadata=metadata,
        )

        # Assert
        assert result == 1
        mock_db_pool._mock_connection.fetchrow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_conversation_minimal_data(self, repo, mock_db_pool):
        """Test creating conversation with minimal required data."""
        # Arrange
        user_id = 123
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"id": 2})

        # Act
        result = await repo.create_conversation(user_id=user_id)

        # Assert
        assert result == 2
        mock_db_pool._mock_connection.fetchrow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_conversation_returns_none_on_failure(
        self, repo, mock_db_pool
    ):
        """Test create conversation returns None when insert fails."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.create_conversation(user_id=123)

        # Assert
        assert result is None

    # ========================================================================
    # GET CONVERSATION TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_conversation_success(
        self, repo, mock_db_pool, sample_conversation_record
    ):
        """Test getting a conversation by ID."""
        # Arrange
        conversation_id = 1
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            return_value=sample_conversation_record
        )

        # Act
        result = await repo.get_conversation(conversation_id)

        # Assert
        assert result is not None
        assert result["id"] == 1
        assert result["title"] == "Test Conversation"
        assert result["message_count"] == 5

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, repo, mock_db_pool):
        """Test getting non-existent conversation returns None."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.get_conversation(9999)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_conversation_by_user_success(
        self, repo, mock_db_pool, sample_conversation_record
    ):
        """Test getting conversation by ID and user ID."""
        # Arrange
        conversation_id = 1
        user_id = 123
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            return_value=sample_conversation_record
        )

        # Act
        result = await repo.get_conversation_by_user(conversation_id, user_id)

        # Assert
        assert result is not None
        assert result["id"] == 1
        assert result["user_id"] == 123

    @pytest.mark.asyncio
    async def test_get_conversation_by_user_wrong_user(self, repo, mock_db_pool):
        """Test getting conversation with wrong user ID returns None."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.get_conversation_by_user(1, 999)

        # Assert
        assert result is None

    # ========================================================================
    # UPDATE CONVERSATION TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_update_conversation_success(self, repo, mock_db_pool):
        """Test updating conversation successfully."""
        # Arrange
        conversation_id = 1
        user_id = 123
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.update_conversation(
            conversation_id, user_id, title="Updated Title", is_pinned=True
        )

        # Assert
        assert result is True
        mock_db_pool._mock_connection.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_conversation_no_valid_fields(self, repo, mock_db_pool):
        """Test update with no valid fields returns False."""
        # Arrange - no execute should be called
        # Act
        result = await repo.update_conversation(1, 123, invalid_field="value")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_update_conversation_not_found(self, repo, mock_db_pool):
        """Test updating non-existent conversation returns False."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="DELETE 0")

        # Act
        result = await repo.update_conversation(9999, 123, title="Updated")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_update_conversation_tags(self, repo, mock_db_pool):
        """Test updating conversation tags."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.update_conversation(1, 123, tags=["new", "tags", "list"])

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_update_conversation_metadata(self, repo, mock_db_pool):
        """Test updating conversation metadata."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.update_conversation(
            1, 123, metadata={"updated": "metadata"}
        )

        # Assert
        assert result is True

    # ========================================================================
    # DELETE CONVERSATION TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_delete_conversation_success(self, repo, mock_db_pool):
        """Test soft deleting conversation successfully."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.delete_conversation(1, 123)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, repo, mock_db_pool):
        """Test deleting non-existent conversation returns False."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="DELETE 0")

        # Act
        result = await repo.delete_conversation(9999, 123)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_conversation_wrong_user(self, repo, mock_db_pool):
        """Test deleting conversation with wrong user returns False."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="DELETE 0")

        # Act
        result = await repo.delete_conversation(1, 999)

        # Assert
        assert result is False

    # ========================================================================
    # LIST CONVERSATIONS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_user_conversations_success(self, repo, mock_db_pool):
        """Test getting user conversations with pagination."""
        # Arrange
        user_id = 123
        mock_conversations = [
            {
                "id": 1,
                "title": "Conv 1",
                "message_count": 5,
                "last_message_at": datetime.now(timezone.utc),
                "last_message_preview": "Last message",
            },
            {
                "id": 2,
                "title": "Conv 2",
                "message_count": 3,
                "last_message_at": datetime.now(timezone.utc),
                "last_message_preview": "Another message",
            },
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_conversations)

        # Act
        result = await repo.get_user_conversations(user_id, skip=0, limit=20)

        # Assert
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

    @pytest.mark.asyncio
    async def test_get_user_conversations_with_sorting(self, repo, mock_db_pool):
        """Test getting conversations with custom sorting."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_user_conversations(
            123, skip=0, limit=10, sort_by="created_at", sort_order="asc"
        )

        # Assert
        assert result == []
        mock_db_pool._mock_connection.fetch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_user_conversations_exclude_pinned(self, repo, mock_db_pool):
        """Test getting conversations excluding pinned ones."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_user_conversations(
            123, skip=0, limit=20, include_pinned=False
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_get_user_conversations_invalid_sort_field(self, repo, mock_db_pool):
        """Test that invalid sort field defaults to updated_at."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act - should not raise error, should use default
        result = await repo.get_user_conversations(
            123, skip=0, limit=20, sort_by="invalid_field"
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_get_user_conversations_invalid_sort_order(self, repo, mock_db_pool):
        """Test that invalid sort order defaults to desc."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_user_conversations(
            123, skip=0, limit=20, sort_order="invalid"
        )

        # Assert
        assert result == []

    # ========================================================================
    # COUNT CONVERSATIONS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_count_user_conversations_success(self, repo, mock_db_pool):
        """Test counting user conversations."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"count": 42})

        # Act
        result = await repo.count_user_conversations(123)

        # Assert
        assert result == 42

    @pytest.mark.asyncio
    async def test_count_user_conversations_zero(self, repo, mock_db_pool):
        """Test count returns 0 when no conversations."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"count": 0})

        # Act
        result = await repo.count_user_conversations(123)

        # Assert
        assert result == 0

    @pytest.mark.asyncio
    async def test_count_user_conversations_exclude_pinned(self, repo, mock_db_pool):
        """Test counting conversations excluding pinned."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"count": 10})

        # Act
        result = await repo.count_user_conversations(123, include_pinned=False)

        # Assert
        assert result == 10

    @pytest.mark.asyncio
    async def test_count_total_conversations(self, repo, mock_db_pool):
        """Test counting total conversations."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"count": 15})

        # Act
        result = await repo.count_total_conversations(123)

        # Assert
        assert result == 15

    # ========================================================================
    # PIN CONVERSATION TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_pin_conversation_success(self, repo, mock_db_pool):
        """Test pinning a conversation."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.pin_conversation(1, 123, is_pinned=True)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_unpin_conversation_success(self, repo, mock_db_pool):
        """Test unpinning a conversation."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.pin_conversation(1, 123, is_pinned=False)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_pin_conversation_not_found(self, repo, mock_db_pool):
        """Test pinning non-existent conversation returns False."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="DELETE 0")

        # Act
        result = await repo.pin_conversation(9999, 123, is_pinned=True)

        # Assert
        assert result is False

    # ========================================================================
    # UPDATE TAGS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_update_tags_success(self, repo, mock_db_pool):
        """Test updating conversation tags."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.update_tags(1, 123, ["tag1", "tag2", "tag3"])

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_update_tags_empty_list(self, repo, mock_db_pool):
        """Test updating tags with empty list."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.update_tags(1, 123, [])

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_update_tags_not_found(self, repo, mock_db_pool):
        """Test updating tags for non-existent conversation."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="DELETE 0")

        # Act
        result = await repo.update_tags(9999, 123, ["tag"])

        # Assert
        assert result is False

    # ========================================================================
    # SEARCH TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_search_conversations_success(self, repo, mock_db_pool):
        """Test searching conversations."""
        # Arrange
        mock_results = [
            {
                "id": 1,
                "title": "Test Conversation",
                "message_count": 5,
                "rank": 0.9,
                "title_highlight": "<mark>Test</mark> Conversation",
            }
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_results)

        # Act
        result = await repo.search_conversations(123, "test", skip=0, limit=20)

        # Assert
        assert len(result) == 1
        assert result[0]["rank"] == 0.9

    @pytest.mark.asyncio
    async def test_search_conversations_no_results(self, repo, mock_db_pool):
        """Test search with no matching results."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.search_conversations(123, "nonexistent", skip=0, limit=20)

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_full_text_search_success(self, repo, mock_db_pool):
        """Test full-text search with filters."""
        # Arrange
        mock_results = [
            {
                "id": 1,
                "title": "Test",
                "rank": 0.9,
                "title_highlight": "<mark>Test</mark>",
            }
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_results)
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"total": 1})

        # Act
        results, total = await repo.full_text_search(123, "test", skip=0, limit=20)

        # Assert
        assert len(results) == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_full_text_search_with_tag_filter(self, repo, mock_db_pool):
        """Test full-text search with tag filters."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"total": 0})
        filters = {"tags": ["important", "urgent"]}

        # Act
        results, total = await repo.full_text_search(
            123, "test", skip=0, limit=20, filters=filters
        )

        # Assert
        assert results == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_full_text_search_with_date_filters(self, repo, mock_db_pool):
        """Test full-text search with date range filters."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"total": 0})
        filters = {
            "date_from": datetime(2024, 1, 1),
            "date_to": datetime(2024, 12, 31),
        }

        # Act
        results, total = await repo.full_text_search(
            123, "test", skip=0, limit=20, filters=filters
        )

        # Assert
        assert results == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_full_text_search_pinned_only(self, repo, mock_db_pool):
        """Test full-text search for pinned conversations only."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"total": 0})
        filters = {"pinned_only": True}

        # Act
        results, total = await repo.full_text_search(
            123, "test", skip=0, limit=20, filters=filters
        )

        # Assert
        assert results == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_count_search_results(self, repo, mock_db_pool):
        """Test counting search results."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"count": 5})

        # Act
        result = await repo.count_search_results(123, "test query")

        # Assert
        assert result == 5

    # ========================================================================
    # SEARCH HELPERS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_search_suggestions(self, repo, mock_db_pool):
        """Test getting search suggestions."""
        # Arrange
        mock_suggestions = [
            {"suggestion": "Test Conversation 1"},
            {"suggestion": "Test Conversation 2"},
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_suggestions)

        # Act
        result = await repo.get_search_suggestions(123, "test", limit=5)

        # Assert
        assert len(result) == 2
        assert "Test Conversation 1" in result
        assert "Test Conversation 2" in result

    @pytest.mark.asyncio
    async def test_get_popular_search_terms(self, repo, mock_db_pool):
        """Test getting popular search terms."""
        # Arrange
        mock_terms = [
            {"term": "health", "rank": 0.9},
            {"term": "fitness", "rank": 0.8},
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_terms)

        # Act
        result = await repo.get_popular_search_terms(123, limit=10)

        # Assert
        assert len(result) == 2
        assert result[0]["term"] == "health"
        assert result[1]["term"] == "fitness"

    @pytest.mark.asyncio
    async def test_refresh_search_index(self, repo, mock_db_pool):
        """Test refreshing materialized view."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(
            return_value="REFRESH MATERIALIZED VIEW"
        )

        # Act
        await repo.refresh_search_index()

        # Assert
        mock_db_pool._mock_connection.execute.assert_awaited_once()

    # ========================================================================
    # USER TAGS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_user_tags_success(self, repo, mock_db_pool):
        """Test getting all user tags."""
        # Arrange
        mock_tags = [{"tag": "health"}, {"tag": "fitness"}, {"tag": "nutrition"}]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_tags)

        # Act
        result = await repo.get_user_tags(123)

        # Assert
        assert len(result) == 3
        assert "health" in result
        assert "fitness" in result
        assert "nutrition" in result

    @pytest.mark.asyncio
    async def test_get_user_tags_empty(self, repo, mock_db_pool):
        """Test getting user tags when none exist."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_user_tags(123)

        # Assert
        assert result == []

    # ========================================================================
    # PINNED CONVERSATIONS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_pinned_conversations(self, repo, mock_db_pool):
        """Test getting pinned conversations."""
        # Arrange
        mock_pinned = [
            {"id": 1, "is_pinned": True, "title": "Pinned 1"},
            {"id": 2, "is_pinned": True, "title": "Pinned 2"},
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_pinned)

        # Act
        result = await repo.get_pinned_conversations(123)

        # Assert
        assert len(result) == 2
        assert all(r["is_pinned"] for r in result)

    @pytest.mark.asyncio
    async def test_get_pinned_conversations_none(self, repo, mock_db_pool):
        """Test getting pinned conversations when none exist."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_pinned_conversations(123)

        # Assert
        assert result == []

    # ========================================================================
    # MESSAGE PREVIEW TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_conversation_with_message_preview(self, repo, mock_db_pool):
        """Test getting conversation with last message preview."""
        # Arrange
        mock_conv = {
            "id": 1,
            "title": "Test",
            "message_count": 5,
            "last_message_preview": "Last message content",
        }
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_conv)

        # Act
        result = await repo.get_conversation_with_message_preview(1, 123)

        # Assert
        assert result is not None
        assert result["last_message_preview"] == "Last message content"

    # ========================================================================
    # CURSOR PAGINATION TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_conversations_cursor_forward(self, repo, mock_db_pool):
        """Test cursor-based pagination going forward."""
        # Arrange
        mock_convs = [
            {"id": 1, "updated_at": datetime.now(timezone.utc)},
            {"id": 2, "updated_at": datetime.now(timezone.utc)},
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_convs)

        # Act
        results, next_cursor, has_more = await repo.get_conversations_cursor(
            user_id=123, cursor=None, limit=20, direction="forward"
        )

        # Assert
        assert len(results) == 2
        assert has_more is False  # No extra item, so no more
        assert next_cursor is None

    @pytest.mark.asyncio
    async def test_get_conversations_cursor_has_more(self, repo, mock_db_pool):
        """Test cursor pagination detects more results."""
        # Arrange - Return limit + 1 to indicate more results
        now = datetime.now(timezone.utc)
        mock_convs = [
            {"id": i, "updated_at": now.isoformat()} for i in range(1, 22)
        ]  # 21 items when limit is 20
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_convs)

        # Act
        results, next_cursor, has_more = await repo.get_conversations_cursor(
            user_id=123, cursor=None, limit=20
        )

        # Assert
        assert len(results) == 20  # Extra item removed
        assert has_more is True
        assert next_cursor is not None

    @pytest.mark.asyncio
    async def test_get_conversations_cursor_invalid_cursor(self, repo, mock_db_pool):
        """Test invalid cursor raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid cursor format"):
            await repo.get_conversations_cursor(
                user_id=123, cursor="invalid-cursor", limit=20
            )
