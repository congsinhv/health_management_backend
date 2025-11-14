"""
Tests for ConversationRepository.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest_asyncio

from app.db.conversation import ConversationRepository


@pytest.fixture
def mock_pool():
    """Mock database connection pool."""
    pool = MagicMock()
    # Configure the acquire method to return a context manager
    connection_manager = AsyncMock()
    connection_manager.__aenter__ = AsyncMock()
    connection_manager.__aexit__ = AsyncMock(return_value=None)
    pool.acquire.return_value = connection_manager
    return pool


@pytest.fixture
def conversation_repo(mock_pool):
    """Create ConversationRepository instance with mock pool."""
    return ConversationRepository(mock_pool)


@pytest_asyncio.fixture
async def mock_connection():
    """Mock database connection."""
    connection = AsyncMock()
    return connection


def create_mock_record(**kwargs):
    """Create a mock record that behaves like asyncpg.Record."""
    record = MagicMock()
    for key, value in kwargs.items():
        setattr(record, key, value)
    # Make it behave like a dictionary
    record.__getitem__ = lambda self, key: getattr(self, key)
    return record


class TestConversationRepository:
    """Test cases for ConversationRepository."""

    @pytest.mark.asyncio
    async def test_create_conversation_success(
        self, conversation_repo, mock_pool, mock_connection
    ):
        """Test successful conversation creation."""
        # Arrange
        conversation_data = {
            "user_id": 1,
            "title": "Test Conversation",
            "is_pinned": True,
            "metadata": {"theme": "health"},
        }

        expected_record = create_mock_record(
            id=1,
            user_id=1,
            title="Test Conversation",
            is_pinned=True,
            is_archived=False,
            metadata={"theme": "health"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=None,
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = expected_record

        # Act
        result = await conversation_repo.create(conversation_data)

        # Assert
        assert result is not None
        assert result["user_id"] == 1
        assert result["title"] == "Test Conversation"
        assert result["is_pinned"] is True
        mock_connection.fetchrow.assert_called_once()

        # Verify query parameters
        call_args = mock_connection.fetchrow.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert "INSERT INTO conversations" in query
        assert "VALUES ($1, $2, $3, $4)" in query
        assert params[0] == "Test Conversation"  # title
        assert params[1] == 1  # user_id
        assert params[2] is True  # is_pinned
        assert params[3] == {"theme": "health"}  # metadata

    @pytest.mark.asyncio
    async def test_create_conversation_minimal_data(
        self, conversation_repo, mock_pool, mock_connection
    ):
        """Test conversation creation with minimal required data."""
        # Arrange
        conversation_data = {
            "user_id": 1,
        }

        expected_record = create_mock_record(
            id=1,
            user_id=1,
            title=None,
            is_pinned=False,
            is_archived=False,
            metadata={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=None,
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = expected_record

        # Act
        result = await conversation_repo.create(conversation_data)

        # Assert
        assert result is not None
        assert result["title"] is None
        assert result["is_pinned"] is False
        assert result["metadata"] == {}

    @pytest.mark.asyncio
    async def test_get_by_id_success(
        self, conversation_repo, mock_pool, mock_connection
    ):
        """Test successful conversation retrieval by ID."""
        # Arrange
        conversation_id = 1
        user_id = 1

        expected_record = create_mock_record(
            id=conversation_id,
            user_id=user_id,
            title="Test Conversation",
            is_pinned=False,
            is_archived=False,
            metadata={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=None,
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = expected_record

        # Act
        result = await conversation_repo.get_by_id_and_user(conversation_id, user_id)

        # Assert
        assert result is not None
        assert result["id"] == conversation_id
        assert result["user_id"] == user_id
        mock_connection.fetchrow.assert_called_once_with(
            """
            SELECT * FROM conversations
            WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
        """,
            conversation_id,
            user_id,
        )

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(
        self, conversation_repo, mock_pool, mock_connection
    ):
        """Test conversation retrieval when not found."""
        # Arrange
        conversation_id = 999
        user_id = 1

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = None

        # Act
        result = await conversation_repo.get_by_id_and_user(conversation_id, user_id)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_list_by_user_success(
        self, conversation_repo, mock_pool, mock_connection
    ):
        """Test successful conversation listing for user."""
        # Arrange
        user_id = 1
        limit = 10
        offset = 0

        expected_records = [
            create_mock_record(
                id=1,
                user_id=user_id,
                title="Pinned Conversation",
                is_pinned=True,
                is_archived=False,
                metadata={},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                deleted_at=None,
            ),
            create_mock_record(
                id=2,
                user_id=user_id,
                title="Regular Conversation",
                is_pinned=False,
                is_archived=False,
                metadata={},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                deleted_at=None,
            ),
        ]

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetch.return_value = expected_records

        # Act
        result = await conversation_repo.list_by_user(user_id, limit, offset)

        # Assert
        assert len(result) == 2
        assert (
            result[0]["is_pinned"] is True
        )  # Should be first (pinned conversations first)
        assert result[1]["is_pinned"] is False
        mock_connection.fetch.assert_called_once_with(
            """
            SELECT * FROM conversations
            WHERE user_id = $1 AND deleted_at IS NULL
            ORDER BY is_pinned DESC, updated_at DESC
            LIMIT $2 OFFSET $3
        """,
            user_id,
            limit,
            offset,
        )

    @pytest.mark.asyncio
    async def test_update_conversation_success(
        self, conversation_repo, mock_pool, mock_connection
    ):
        """Test successful conversation update."""
        # Arrange
        conversation_id = 1
        user_id = 1
        update_data = {
            "title": "Updated Conversation",
            "is_pinned": True,
            "metadata": {"updated": True},
        }

        expected_record = create_mock_record(
            id=conversation_id,
            user_id=user_id,
            title="Updated Conversation",
            is_pinned=True,
            is_archived=False,
            metadata={"updated": True},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=None,
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = expected_record

        # Act
        result = await conversation_repo.update(conversation_id, user_id, update_data)

        # Assert
        assert result is not None
        assert result["title"] == "Updated Conversation"
        assert result["is_pinned"] is True
        assert result["metadata"] == {"updated": True}
        mock_connection.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_conversation_empty_data(
        self, conversation_repo, mock_pool, mock_connection
    ):
        """Test conversation update with empty data (should return existing conversation)."""
        # Arrange
        conversation_id = 1
        user_id = 1
        update_data = {}

        expected_record = create_mock_record(
            id=conversation_id,
            user_id=user_id,
            title="Existing Conversation",
            is_pinned=False,
            is_archived=False,
            metadata={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=None,
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        # First call for get_by_id
        mock_connection.fetchrow.side_effect = [expected_record, expected_record]

        # Act
        result = await conversation_repo.update(conversation_id, user_id, update_data)

        # Assert
        assert result is not None
        assert result["title"] == "Existing Conversation"

    @pytest.mark.asyncio
    async def test_delete_conversation_success(
        self, conversation_repo, mock_pool, mock_connection
    ):
        """Test successful conversation soft delete."""
        # Arrange
        conversation_id = 1
        user_id = 1

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.execute.return_value = "UPDATE 1"

        # Act
        result = await conversation_repo.delete(conversation_id, user_id)

        # Assert
        assert result is True
        mock_connection.execute.assert_called_once_with(
            """
            UPDATE conversations
            SET deleted_at = NOW()
            WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
        """,
            conversation_id,
            user_id,
        )

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(
        self, conversation_repo, mock_pool, mock_connection
    ):
        """Test conversation soft delete when conversation not found."""
        # Arrange
        conversation_id = 999
        user_id = 1

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.execute.return_value = "UPDATE 0"

        # Act
        result = await conversation_repo.delete(conversation_id, user_id)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_get_message_count_success(
        self, conversation_repo, mock_pool, mock_connection
    ):
        """Test successful message count retrieval."""
        # Arrange
        conversation_id = 1
        expected_count = 5

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = create_mock_record(count=expected_count)

        # Act
        result = await conversation_repo.get_message_count(conversation_id)

        # Assert
        assert result == expected_count
        mock_connection.fetchrow.assert_called_once_with(
            """
            SELECT COUNT(*) FROM messages
            WHERE conversation_id = $1 AND deleted_at IS NULL
        """,
            conversation_id,
        )

    @pytest.mark.asyncio
    async def test_get_message_count_zero(
        self, conversation_repo, mock_pool, mock_connection
    ):
        """Test message count retrieval when no messages exist."""
        # Arrange
        conversation_id = 1

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = None

        # Act
        result = await conversation_repo.get_message_count(conversation_id)

        # Assert
        assert result == 0

    @pytest.mark.asyncio
    async def test_pin_conversation_success(
        self, conversation_repo, mock_pool, mock_connection
    ):
        """Test successful conversation pinning."""
        # Arrange
        conversation_id = 1
        user_id = 1
        is_pinned = True

        expected_record = create_mock_record(
            id=conversation_id,
            user_id=user_id,
            title="Test Conversation",
            is_pinned=is_pinned,
            is_archived=False,
            metadata={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=None,
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = expected_record

        # Act
        result = await conversation_repo.pin_conversation(
            conversation_id, user_id, is_pinned
        )

        # Assert
        assert result is not None
        assert result["is_pinned"] is is_pinned
        mock_connection.fetchrow.assert_called_once_with(
            """
            UPDATE conversations
            SET is_pinned = $1, updated_at = NOW()
            WHERE id = $2 AND user_id = $3 AND deleted_at IS NULL
            RETURNING *
        """,
            is_pinned,
            conversation_id,
            user_id,
        )

    @pytest.mark.asyncio
    async def test_count_conversations_by_user_success(
        self, conversation_repo, mock_pool, mock_connection
    ):
        """Test successful conversation count for user."""
        # Arrange
        user_id = 1
        expected_count = 3

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = create_mock_record(count=expected_count)

        # Act
        result = await conversation_repo.count_conversations_by_user(user_id)

        # Assert
        assert result == expected_count
        mock_connection.fetchrow.assert_called_once_with(
            """
            SELECT COUNT(*) FROM conversations
            WHERE user_id = $1 AND deleted_at IS NULL
        """,
            user_id,
        )
