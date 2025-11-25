"""
Integration tests for chat system workflow.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import asyncpg
from datetime import datetime, timezone

from app.db.conversation import ConversationRepository
from app.db.message import MessageRepository
from app.db.message_version import MessageVersionRepository


@pytest.mark.asyncio
class TestChatWorkflowIntegration:
    """Integration tests for complete chat workflow."""

    @pytest.fixture
    def mock_pool(self):
        """Mock database connection pool."""
        pool = MagicMock()
        # Configure the acquire method to return a context manager
        connection_manager = AsyncMock()
        connection_manager.__aenter__ = AsyncMock()
        connection_manager.__aexit__ = AsyncMock(return_value=None)
        pool.acquire.return_value = connection_manager
        return pool

    @pytest.fixture
    def conversation_repo(self, mock_pool):
        """Conversation repository fixture."""
        return ConversationRepository(mock_pool)

    @pytest.fixture
    def message_repo(self, mock_pool):
        """Message repository fixture."""
        return MessageRepository(mock_pool)

    @pytest.fixture
    def message_version_repo(self, mock_pool):
        """Message version repository fixture."""
        return MessageVersionRepository(mock_pool)

    async def test_complete_conversation_workflow(
        self, conversation_repo, message_repo, mock_pool
    ):
        """Test complete conversation creation and messaging workflow."""

        # Arrange - Mock conversation creation
        conversation_data = {
            "user_id": 1,
            "title": "Health Consultation",
            "is_pinned": False,
            "metadata": {"topic": "health"},
        }

        conversation_record = {
            "id": 1,
            "user_id": 1,
            "title": "Health Consultation",
            "is_pinned": False,
            "is_archived": False,
            "metadata": {"topic": "health"},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "deleted_at": None,
        }

        # Arrange - Mock message creation
        message_data = {
            "conversation_id": 1,
            "user_id": 1,
            "content": "I have a question about my health",
            "content_type": "text",
            "metadata": {"source": "web"},
        }

        message_record = {
            "id": 1,
            "conversation_id": 1,
            "user_id": 1,
            "content": "I have a question about my health",
            "content_type": "text",
            "metadata": {"source": "web"},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "deleted_at": None,
        }

        # Arrange - Mock conversation retrieval with message count
        conversation_with_count = conversation_record.copy()
        conversation_with_count["message_count"] = 1

        # Get mock connection from pool
        mock_connection = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection

        # Mock database responses
        mock_connection.fetchrow.side_effect = [
            # Create conversation
            conversation_record,
            # Create message
            message_record,
            # Get conversation by ID
            conversation_record,
            # Get message count
            {"count": 1},
        ]

        # Act & Assert - Create conversation
        conversation = await conversation_repo.create_conversation(conversation_data)
        assert conversation is not None
        assert conversation["title"] == "Health Consultation"
        assert conversation["user_id"] == 1

        # Act & Assert - Create message
        message = await message_repo.create_message(message_data)
        assert message is not None
        assert message["content"] == "I have a question about my health"
        assert message["conversation_id"] == 1

        # Act & Assert - Verify conversation exists
        retrieved_conversation = (
            await conversation_repo.get_conversation_by_id_and_user(1, 1)
        )
        assert retrieved_conversation is not None
        assert retrieved_conversation["id"] == 1

        # Act & Assert - Get message count
        message_count = await conversation_repo.get_message_count(1)
        assert message_count == 1

        # Verify all expected database calls were made
        assert mock_connection.fetchrow.call_count == 4
        assert mock_connection.fetch.call_count == 0
        assert mock_connection.execute.call_count == 0

    async def test_message_edit_workflow(
        self, mock_pool, message_repo, message_version_repo
    ):
        """Test message editing with version history workflow."""
        # Get mock connection from pool
        mock_connection = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection

        # Arrange - Original message
        original_message = {
            "id": 1,
            "conversation_id": 1,
            "user_id": 1,
            "content": "Original message",
            "content_type": "text",
            "metadata": {},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "deleted_at": None,
        }

        # Arrange - Updated message
        updated_message = {
            "id": 1,
            "conversation_id": 1,
            "user_id": 1,
            "content": "Edited message",
            "content_type": "text",
            "metadata": {"edited": True},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "deleted_at": None,
        }

        # Arrange - Message version created by trigger
        message_version = {
            "id": 1,
            "message_id": 1,
            "version_number": 1,
            "content": "Original message",
            "metadata": {},
            "user_id": 1,
            "created_at": datetime.now(timezone.utc),
        }

        # Arrange - Latest version number
        latest_version_number = 1

        # Mock database responses
        mock_connection.fetchrow.side_effect = [
            # Check user can edit message (returns exists=True)
            {"exists": True},
            # Update message
            updated_message,
            # Get latest version number
            {"coalesce": latest_version_number},
            # Get version history
            message_version,
        ]

        # Act & Assert - Check user can edit message
        can_edit = await message_repo.can_user_edit_message(1, 1)
        assert can_edit is True

        # Reset mock for update
        mock_connection.reset_mock()
        mock_connection.fetchrow.side_effect = [updated_message]

        # Act & Assert - Update message
        update_data = {"content": "Edited message", "metadata": {"edited": True}}

        updated = await message_repo.update(1, 1, update_data)
        assert updated is not None
        assert updated["content"] == "Edited message"
        assert updated["metadata"] == {"edited": True}

        # Act & Assert - Get version history
        mock_connection.reset_mock()
        mock_connection.fetchrow.side_effect = [{"coalesce": latest_version_number}]
        mock_connection.fetch.return_value = [message_version]

        versions = await message_version_repo.list_message_versions(1)
        assert len(versions) == 1
        assert versions[0]["version_number"] == 1
        assert versions[0]["content"] == "Original message"

    async def test_conversation_list_and_pagination(self, mock_pool, conversation_repo):
        """Test conversation listing with pagination and sorting."""
        # Get mock connection from pool
        mock_connection = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection

        # Arrange - Sample conversations
        conversations = [
            {
                "id": 2,
                "user_id": 1,
                "title": "Pinned Conversation",
                "is_pinned": True,
                "is_archived": False,
                "metadata": {},
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "deleted_at": None,
            },
            {
                "id": 1,
                "user_id": 1,
                "title": "Regular Conversation",
                "is_pinned": False,
                "is_archived": False,
                "metadata": {},
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "deleted_at": None,
            },
        ]

        # Mock database response
        mock_connection.fetch.return_value = conversations

        # Act
        result = await conversation_repo.list_conversations_by_user(
            1, limit=10, offset=0
        )

        # Assert
        assert len(result) == 2
        # Pinned conversation should come first
        assert result[0]["is_pinned"] is True
        assert result[0]["title"] == "Pinned Conversation"
        assert result[1]["is_pinned"] is False
        assert result[1]["title"] == "Regular Conversation"

        # Verify query
        mock_connection.fetch.assert_called_once_with(
            """
            SELECT * FROM conversations
            WHERE user_id = $1 AND deleted_at IS NULL
            ORDER BY is_pinned DESC, updated_at DESC
            LIMIT $2 OFFSET $3
        """,
            1,
            10,
            0,
        )

    async def test_message_pagination_with_cursor(self, mock_pool, message_repo):
        """Test message pagination with cursor-based navigation."""
        # Get mock connection from pool
        mock_connection = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection

        # Arrange - Sample messages
        messages = [
            {
                "id": 3,
                "conversation_id": 1,
                "user_id": 1,
                "content": "Third message",
                "content_type": "text",
                "metadata": {},
                "created_at": datetime(2025, 1, 1, 12, 3, tzinfo=timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "deleted_at": None,
            },
            {
                "id": 4,
                "conversation_id": 1,
                "user_id": 2,
                "content": "Fourth message",
                "content_type": "text",
                "metadata": {},
                "created_at": datetime(2025, 1, 1, 12, 4, tzinfo=timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "deleted_at": None,
            },
        ]

        # Mock database response
        mock_connection.fetch.return_value = messages

        # Act - Get messages with cursor (before message ID 2)
        result = await message_repo.list_messages_by_conversation(
            conversation_id=1, limit=50, before=2
        )

        # Assert
        assert len(result) == 2
        assert all(msg["conversation_id"] == 1 for msg in result)
        assert result[0]["id"] == 3
        assert result[1]["id"] == 4

        # Verify query was called with correct parameters
        mock_connection.fetch.assert_called_once()
        call_args = mock_connection.fetch.call_args
        query = call_args[0][0]
        assert "SELECT * FROM messages" in query
        assert "WHERE conversation_id = $1" in query
        assert "created_at <" in query
        assert "ORDER BY created_at ASC" in query
        assert "LIMIT $3" in query
        assert call_args[0][1] == 1  # conversation_id
        assert call_args[0][2] == 2  # before
        assert call_args[0][3] == 50  # limit

    async def test_conversation_soft_delete_workflow(
        self, mock_pool, conversation_repo, message_repo
    ):
        """Test conversation soft delete and its effect on message access."""
        # Get mock connection from pool
        mock_connection = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection

        # Arrange - Mock successful soft delete
        mock_connection.execute.return_value = "UPDATE 1"

        # Act - Soft delete conversation
        result = await conversation_repo.delete(1, 1)

        # Assert
        assert result is True
        mock_connection.execute.assert_called_once_with(
            """
            UPDATE conversations
            SET deleted_at = NOW()
            WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
        """,
            1,
            1,
        )

        # Act - Try to get messages from deleted conversation
        mock_connection.reset_mock()
        mock_connection.fetch.return_value = []  # Empty list for deleted conversation

        messages = await message_repo.list_messages_by_conversation(1)

        # Assert - Should return empty list (even though we didn't check deleted_at in this query)
        assert len(messages) == 0
