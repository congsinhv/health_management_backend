"""
Tests for MessageRepository.

Tests message repository operations including CRUD operations,
branching/tree structure, pagination, and message relationships.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from typing import Dict, Any, List

from app.db.message import MessageRepository


@pytest.mark.repository
@pytest.mark.unit
class TestMessageRepository:
    """Test cases for MessageRepository."""

    @pytest.fixture
    def repo(self, mock_db_pool):
        """Create repository instance with mocked pool."""
        return MessageRepository(mock_db_pool)

    @pytest.fixture
    def sample_message_record(self):
        """Sample message record for testing."""
        return {
            "id": 1,
            "conversation_id": 100,
            "user_id": 123,
            "role": "user",
            "content": "Test message content",
            "content_cleaned": "Test message content",
            "answers": {"key": ["answer1", "answer2"]},
            "metadata": {"source": "test"},
            "parent_message_id": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "deleted_at": None,
            "version_count": 2,
            "child_count": 3,
        }

    # ========================================================================
    # CREATE MESSAGE TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_create_message_success(self, repo, mock_db_pool):
        """Test creating a message successfully."""
        # Arrange
        conversation_id = 100
        role = "user"
        content = "Test message"
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"id": 1})

        # Act
        result = await repo.create_message(
            conversation_id=conversation_id, role=role, content=content
        )

        # Assert
        assert result == 1
        mock_db_pool._mock_connection.fetchrow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_message_with_all_fields(self, repo, mock_db_pool):
        """Test creating message with all optional fields."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"id": 2})

        # Act
        result = await repo.create_message(
            conversation_id=100,
            role="assistant",
            content="Full message",
            content_cleaned="Full message cleaned",
            answers={"q1": ["a1", "a2"]},
            metadata={"key": "value"},
            parent_message_id=5,
        )

        # Assert
        assert result == 2

    @pytest.mark.asyncio
    async def test_create_message_returns_none_on_failure(self, repo, mock_db_pool):
        """Test create message returns None when insert fails."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.create_message(
            conversation_id=100, role="user", content="Test"
        )

        # Assert
        assert result is None

    # ========================================================================
    # GET MESSAGE TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_message_success(self, repo, mock_db_pool, sample_message_record):
        """Test getting a message by ID."""
        # Arrange
        message_id = 1
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            return_value=sample_message_record
        )

        # Act
        result = await repo.get_message(message_id)

        # Assert
        assert result is not None
        assert result["id"] == 1
        assert result["content"] == "Test message content"
        assert result["version_count"] == 2
        assert result["child_count"] == 3

    @pytest.mark.asyncio
    async def test_get_message_not_found(self, repo, mock_db_pool):
        """Test getting non-existent message returns None."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.get_message(9999)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_message_by_user_success(
        self, repo, mock_db_pool, sample_message_record
    ):
        """Test getting message by ID and user ID."""
        # Arrange
        message_id = 1
        user_id = 123
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            return_value=sample_message_record
        )

        # Act
        result = await repo.get_message_by_user(message_id, user_id)

        # Assert
        assert result is not None
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_get_message_by_user_wrong_user(self, repo, mock_db_pool):
        """Test getting message with wrong user ID returns None."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.get_message_by_user(1, 999)

        # Assert
        assert result is None

    # ========================================================================
    # UPDATE MESSAGE TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_update_message_success(self, repo, mock_db_pool):
        """Test updating message successfully."""
        # Arrange
        message_id = 1
        user_id = 123
        content = "Updated content"
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.update_message(message_id, user_id, content)

        # Assert
        assert result is True
        mock_db_pool._mock_connection.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_message_with_all_fields(self, repo, mock_db_pool):
        """Test updating message with all optional fields."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.update_message(
            message_id=1,
            user_id=123,
            content="New content",
            content_cleaned="New cleaned",
            answers={"new": ["answers"]},
            metadata={"updated": "metadata"},
        )

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_update_message_not_found(self, repo, mock_db_pool):
        """Test updating non-existent message returns False."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="DELETE 0")

        # Act
        result = await repo.update_message(9999, 123, "Updated")

        # Assert
        assert result is False

    # ========================================================================
    # DELETE MESSAGE TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_delete_message_success(self, repo, mock_db_pool):
        """Test soft deleting message successfully."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.delete_message(1, 123)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_message_not_found(self, repo, mock_db_pool):
        """Test deleting non-existent message returns False."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="DELETE 0")

        # Act
        result = await repo.delete_message(9999, 123)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_message_wrong_user(self, repo, mock_db_pool):
        """Test deleting message with wrong user returns False."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="DELETE 0")

        # Act
        result = await repo.delete_message(1, 999)

        # Assert
        assert result is False

    # ========================================================================
    # LIST MESSAGES TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_conversation_messages_success(self, repo, mock_db_pool):
        """Test getting conversation messages with pagination."""
        # Arrange
        conversation_id = 100
        user_id = 123
        mock_messages = [
            {"id": 1, "content": "Message 1", "version_count": 0, "child_count": 0},
            {"id": 2, "content": "Message 2", "version_count": 1, "child_count": 2},
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_messages)

        # Act
        result = await repo.get_conversation_messages(
            conversation_id, user_id, skip=0, limit=50
        )

        # Assert
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

    @pytest.mark.asyncio
    async def test_get_conversation_messages_with_custom_ordering(
        self, repo, mock_db_pool
    ):
        """Test getting messages with custom order_by field."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_conversation_messages(
            100, 123, skip=0, limit=50, order_by="updated_at"
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_get_conversation_messages_invalid_order_by(self, repo, mock_db_pool):
        """Test that invalid order_by defaults to created_at."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act - should not raise error, should use default
        result = await repo.get_conversation_messages(
            100, 123, skip=0, limit=50, order_by="invalid_field"
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_count_conversation_messages_success(self, repo, mock_db_pool):
        """Test counting conversation messages."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"count": 15})

        # Act
        result = await repo.count_conversation_messages(100, 123)

        # Assert
        assert result == 15

    @pytest.mark.asyncio
    async def test_count_conversation_messages_zero(self, repo, mock_db_pool):
        """Test count returns 0 when no messages."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"count": 0})

        # Act
        result = await repo.count_conversation_messages(100, 123)

        # Assert
        assert result == 0

    # ========================================================================
    # BRANCHING TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_create_message_branch_success(self, repo, mock_db_pool):
        """Test creating a message branch."""
        # Arrange
        parent_message_id = 5
        user_id = 123
        # First query gets conversation_id from parent
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            side_effect=[
                {"conversation_id": 100},  # Parent lookup
                {"id": 10},  # New message created
            ]
        )

        # Act
        result = await repo.create_message_branch(
            parent_message_id=parent_message_id,
            user_id=user_id,
            role="user",
            content="Branch message",
        )

        # Assert
        assert result == 10

    @pytest.mark.asyncio
    async def test_create_message_branch_parent_not_found(self, repo, mock_db_pool):
        """Test creating branch when parent doesn't exist."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            return_value=None  # Parent not found
        )

        # Act
        result = await repo.create_message_branch(
            parent_message_id=9999, user_id=123, role="user", content="Branch"
        )

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_message_children_success(self, repo, mock_db_pool):
        """Test getting child messages of a parent."""
        # Arrange
        parent_id = 5
        mock_children = [
            {"id": 10, "content": "Child 1", "parent_message_id": 5},
            {"id": 11, "content": "Child 2", "parent_message_id": 5},
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_children)

        # Act
        result = await repo.get_message_children(parent_id, 123)

        # Assert
        assert len(result) == 2
        assert result[0]["id"] == 10
        assert result[1]["id"] == 11

    @pytest.mark.asyncio
    async def test_get_message_children_no_children(self, repo, mock_db_pool):
        """Test getting children when message has none."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_message_children(5, 123)

        # Assert
        assert result == []

    # ========================================================================
    # TREE STRUCTURE TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_conversation_tree_success(self, repo, mock_db_pool):
        """Test getting conversation tree structure."""
        # Arrange
        conversation_id = 100
        mock_tree = [
            {"id": 1, "parent_message_id": None, "content": "Root"},
            {"id": 2, "parent_message_id": 1, "content": "Child 1"},
            {"id": 3, "parent_message_id": 1, "content": "Child 2"},
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_tree)

        # Act
        result = await repo.get_conversation_tree(conversation_id, 123)

        # Assert
        assert len(result) == 3
        assert result[0]["parent_message_id"] is None  # Root message

    @pytest.mark.asyncio
    async def test_get_conversation_tree_empty(self, repo, mock_db_pool):
        """Test getting tree for conversation with no messages."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_conversation_tree(100, 123)

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_get_root_messages_success(self, repo, mock_db_pool):
        """Test getting root messages (no parent)."""
        # Arrange
        mock_roots = [
            {"id": 1, "parent_message_id": None, "content": "Root 1"},
            {"id": 5, "parent_message_id": None, "content": "Root 2"},
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_roots)

        # Act
        result = await repo.get_root_messages(100, 123)

        # Assert
        assert len(result) == 2
        assert all(m["parent_message_id"] is None for m in result)

    @pytest.mark.asyncio
    async def test_get_branch_path_success(self, repo, mock_db_pool):
        """Test getting path from root to a specific message."""
        # Arrange
        message_id = 3
        mock_path = [
            {"id": 1, "level": 2, "content": "Root"},
            {"id": 2, "level": 1, "content": "Middle"},
            {"id": 3, "level": 0, "content": "Target"},
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_path)

        # Act
        result = await repo.get_branch_path(message_id, 123)

        # Assert
        assert len(result) == 3
        assert result[0]["id"] == 1  # Root
        assert result[2]["id"] == 3  # Target

    @pytest.mark.asyncio
    async def test_get_branch_path_single_message(self, repo, mock_db_pool):
        """Test getting path for a root message (no parents)."""
        # Arrange
        mock_path = [{"id": 1, "level": 0, "content": "Root only"}]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_path)

        # Act
        result = await repo.get_branch_path(1, 123)

        # Assert
        assert len(result) == 1

    # ========================================================================
    # FIRST/LAST MESSAGE TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_first_message_success(self, repo, mock_db_pool):
        """Test getting the first message in a conversation."""
        # Arrange
        mock_first = {"id": 1, "content": "First message"}
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_first)

        # Act
        result = await repo.get_first_message(100, 123)

        # Assert
        assert result is not None
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_get_first_message_no_messages(self, repo, mock_db_pool):
        """Test getting first message when conversation is empty."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.get_first_message(100, 123)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_last_message_success(self, repo, mock_db_pool):
        """Test getting the last message in a conversation."""
        # Arrange
        mock_last = {"id": 50, "content": "Last message"}
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_last)

        # Act
        result = await repo.get_last_message(100, 123)

        # Assert
        assert result is not None
        assert result["id"] == 50

    @pytest.mark.asyncio
    async def test_get_last_message_no_messages(self, repo, mock_db_pool):
        """Test getting last message when conversation is empty."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.get_last_message(100, 123)

        # Assert
        assert result is None

    # ========================================================================
    # CONVERSATION TIMESTAMP UPDATE TEST
    # ========================================================================

    @pytest.mark.asyncio
    async def test_update_conversation_timestamp_success(self, repo, mock_db_pool):
        """Test updating conversation timestamp."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.update_conversation_timestamp(100, 123)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_update_conversation_timestamp_not_found(self, repo, mock_db_pool):
        """Test updating timestamp for non-existent conversation."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="DELETE 0")

        # Act
        result = await repo.update_conversation_timestamp(9999, 123)

        # Assert
        assert result is False

    # ========================================================================
    # CURSOR PAGINATION TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_messages_cursor_forward(self, repo, mock_db_pool):
        """Test cursor-based pagination going forward."""
        # Arrange
        mock_messages = [
            {"id": 1, "created_at": datetime.now(timezone.utc)},
            {"id": 2, "created_at": datetime.now(timezone.utc)},
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_messages)

        # Act
        results, next_cursor, has_more = await repo.get_messages_cursor(
            conversation_id=100, user_id=123, cursor=None, limit=50
        )

        # Assert
        assert len(results) == 2
        assert has_more is False
        assert next_cursor is None

    @pytest.mark.asyncio
    async def test_get_messages_cursor_has_more(self, repo, mock_db_pool):
        """Test cursor pagination detects more results."""
        # Arrange - Return limit + 1 to indicate more results
        now = datetime.now(timezone.utc)
        mock_messages = [
            {"id": i, "created_at": now.isoformat()} for i in range(1, 52)
        ]  # 51 items when limit is 50
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_messages)

        # Act
        results, next_cursor, has_more = await repo.get_messages_cursor(
            conversation_id=100, user_id=123, cursor=None, limit=50
        )

        # Assert
        assert len(results) == 50  # Extra item removed
        assert has_more is True
        assert next_cursor is not None

    @pytest.mark.asyncio
    async def test_get_messages_cursor_invalid_cursor(self, repo, mock_db_pool):
        """Test invalid cursor raises ValueError."""
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid cursor format"):
            await repo.get_messages_cursor(
                conversation_id=100,
                user_id=123,
                cursor="invalid-cursor",
                limit=50,
            )

    @pytest.mark.asyncio
    async def test_get_messages_cursor_invalid_order_by(self, repo, mock_db_pool):
        """Test that invalid order_by defaults to created_at."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act - should not raise error
        results, next_cursor, has_more = await repo.get_messages_cursor(
            conversation_id=100,
            user_id=123,
            cursor=None,
            limit=50,
            order_by="invalid_field",
        )

        # Assert
        assert results == []
        assert has_more is False
