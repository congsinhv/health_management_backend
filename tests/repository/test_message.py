"""
Tests for MessageRepository.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest_asyncio

from app.db.message import MessageRepository


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
def message_repo(mock_pool):
    """Create MessageRepository instance with mock pool."""
    return MessageRepository(mock_pool)


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


class TestMessageRepository:
    """Test cases for MessageRepository."""

    @pytest.mark.asyncio
    async def test_create_message_success(
        self, message_repo, mock_pool, mock_connection
    ):
        """Test successful message creation."""
        # Arrange
        message_data = {
            "conversation_id": 1,
            "user_id": 1,
            "content": "Hello, this is a test message",
            "content_type": "text",
            "metadata": {"source": "web"},
        }

        expected_record = create_mock_record(
            id=1,
            conversation_id=1,
            user_id=1,
            content="Hello, this is a test message",
            content_type="text",
            metadata={"source": "web"},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=None,
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = expected_record

        # Act
        result = await message_repo.create(message_data)

        # Assert
        assert result is not None
        assert result["conversation_id"] == 1
        assert result["user_id"] == 1
        assert result["content"] == "Hello, this is a test message"
        assert result["content_type"] == "text"
        assert result["metadata"] == {"source": "web"}

        # Verify query parameters
        call_args = mock_connection.fetchrow.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert "INSERT INTO messages" in query
        assert "VALUES ($1, $2, $3, $4, $5)" in query
        assert params[0] == 1  # conversation_id
        assert params[1] == 1  # user_id
        assert params[2] == "Hello, this is a test message"  # content
        assert params[3] == "text"  # content_type
        assert params[4] == {"source": "web"}  # metadata

    @pytest.mark.asyncio
    async def test_create_message_minimal_data(
        self, message_repo, mock_pool, mock_connection
    ):
        """Test message creation with minimal required data."""
        # Arrange
        message_data = {
            "conversation_id": 1,
            "user_id": 1,
            "content": "Minimal message",
        }

        expected_record = create_mock_record(
            id=1,
            conversation_id=1,
            user_id=1,
            content="Minimal message",
            content_type="text",  # Default value
            metadata={},  # Default value
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=None,
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = expected_record

        # Act
        result = await message_repo.create(message_data)

        # Assert
        assert result is not None
        assert result["content_type"] == "text"  # Default value
        assert result["metadata"] == {}  # Default value

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, message_repo, mock_pool, mock_connection):
        """Test successful message retrieval by ID."""
        # Arrange
        message_id = 1
        conversation_id = 1

        expected_record = create_mock_record(
            id=message_id,
            conversation_id=conversation_id,
            user_id=1,
            content="Test message",
            content_type="text",
            metadata={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=None,
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = expected_record

        # Act
        result = await message_repo.get_by_id(message_id, conversation_id)

        # Assert
        assert result is not None
        assert result["id"] == message_id
        assert result["conversation_id"] == conversation_id
        mock_connection.fetchrow.assert_called_once_with(
            """
            SELECT * FROM messages
            WHERE id = $1 AND conversation_id = $2 AND deleted_at IS NULL
        """,
            message_id,
            conversation_id,
        )

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, message_repo, mock_pool, mock_connection):
        """Test message retrieval when not found."""
        # Arrange
        message_id = 999
        conversation_id = 1

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = None

        # Act
        result = await message_repo.get_by_id(message_id, conversation_id)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_list_by_conversation_success(
        self, message_repo, mock_pool, mock_connection
    ):
        """Test successful message listing for conversation."""
        # Arrange
        conversation_id = 1
        limit = 50
        before = None

        expected_records = [
            create_mock_record(
                id=1,
                conversation_id=conversation_id,
                user_id=1,
                content="First message",
                content_type="text",
                metadata={},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                deleted_at=None,
            ),
            create_mock_record(
                id=2,
                conversation_id=conversation_id,
                user_id=2,
                content="Second message",
                content_type="text",
                metadata={},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                deleted_at=None,
            ),
        ]

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetch.return_value = expected_records

        # Act
        result = await message_repo.list_by_conversation(conversation_id, limit, before)

        # Assert
        assert len(result) == 2
        assert result[0]["content"] == "First message"
        assert result[1]["content"] == "Second message"
        mock_connection.fetch.assert_called_once_with(
            """
                SELECT * FROM messages
                WHERE conversation_id = $1 AND deleted_at IS NULL
                ORDER BY created_at ASC
                LIMIT $2
            """,
            conversation_id,
            limit,
        )

    @pytest.mark.asyncio
    async def test_list_by_conversation_with_cursor(
        self, message_repo, mock_pool, mock_connection
    ):
        """Test message listing with cursor pagination."""
        # Arrange
        conversation_id = 1
        limit = 50
        before = 5

        expected_records = [
            create_mock_record(
                id=6,
                conversation_id=conversation_id,
                user_id=1,
                content="Message after cursor",
                content_type="text",
                metadata={},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                deleted_at=None,
            )
        ]

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetch.return_value = expected_records

        # Act
        result = await message_repo.list_by_conversation(conversation_id, limit, before)

        # Assert
        assert len(result) == 1
        assert result[0]["id"] == 6
        mock_connection.fetch.assert_called_once_with(
            """
                SELECT * FROM messages
                WHERE conversation_id = $1 AND created_at < (
                    SELECT created_at FROM messages WHERE id = $2
                ) AND deleted_at IS NULL
                ORDER BY created_at ASC
                LIMIT $3
            """,
            conversation_id,
            before,
            limit,
        )

    @pytest.mark.asyncio
    async def test_update_message_success(
        self, message_repo, mock_pool, mock_connection
    ):
        """Test successful message update."""
        # Arrange
        message_id = 1
        conversation_id = 1
        update_data = {
            "content": "Updated message content",
            "metadata": {"edited": True},
        }

        expected_record = create_mock_record(
            id=message_id,
            conversation_id=conversation_id,
            user_id=1,
            content="Updated message content",
            content_type="text",
            metadata={"edited": True},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=None,
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = expected_record

        # Act
        result = await message_repo.update(message_id, conversation_id, update_data)

        # Assert
        assert result is not None
        assert result["content"] == "Updated message content"
        assert result["metadata"] == {"edited": True}
        mock_connection.fetchrow.assert_called_once_with(
            """
            UPDATE messages
            SET content = $1, metadata = $2, updated_at = NOW()
            WHERE id = $3 AND conversation_id = $4 AND deleted_at IS NULL
            RETURNING *
        """,
            update_data["content"],
            update_data["metadata"],
            message_id,
            conversation_id,
        )

    @pytest.mark.asyncio
    async def test_delete_message_success(
        self, message_repo, mock_pool, mock_connection
    ):
        """Test successful message soft delete."""
        # Arrange
        message_id = 1
        conversation_id = 1

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.execute.return_value = "UPDATE 1"

        # Act
        result = await message_repo.delete(message_id, conversation_id)

        # Assert
        assert result is True
        mock_connection.execute.assert_called_once_with(
            """
            UPDATE messages
            SET deleted_at = NOW()
            WHERE id = $1 AND conversation_id = $2 AND deleted_at IS NULL
        """,
            message_id,
            conversation_id,
        )

    @pytest.mark.asyncio
    async def test_delete_message_not_found(
        self, message_repo, mock_pool, mock_connection
    ):
        """Test message soft delete when message not found."""
        # Arrange
        message_id = 999
        conversation_id = 1

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.execute.return_value = "UPDATE 0"

        # Act
        result = await message_repo.delete(message_id, conversation_id)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_get_conversation_latest_message_success(
        self, message_repo, mock_pool, mock_connection
    ):
        """Test successful latest message retrieval."""
        # Arrange
        conversation_id = 1

        expected_record = create_mock_record(
            id=5,
            conversation_id=conversation_id,
            user_id=1,
            content="Latest message",
            content_type="text",
            metadata={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=None,
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = expected_record

        # Act
        result = await message_repo.get_conversation_latest_message(conversation_id)

        # Assert
        assert result is not None
        assert result["id"] == 5
        assert result["content"] == "Latest message"
        mock_connection.fetchrow.assert_called_once_with(
            """
            SELECT * FROM messages
            WHERE conversation_id = $1 AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
        """,
            conversation_id,
        )

    @pytest.mark.asyncio
    async def test_count_by_conversation_success(
        self, message_repo, mock_pool, mock_connection
    ):
        """Test successful message count for conversation."""
        # Arrange
        conversation_id = 1
        expected_count = 10

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = create_mock_record(count=expected_count)

        # Act
        result = await message_repo.count_by_conversation(conversation_id)

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
    async def test_can_user_edit_message_true(
        self, message_repo, mock_pool, mock_connection
    ):
        """Test user can edit message verification - positive case."""
        # Arrange
        message_id = 1
        user_id = 1

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = create_mock_record(exists=True)

        # Act
        result = await message_repo.can_user_edit_message(message_id, user_id)

        # Assert
        assert result is True
        mock_connection.fetchrow.assert_called_once_with(
            """
            SELECT EXISTS (
                SELECT 1 FROM messages
                WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
            )
        """,
            message_id,
            user_id,
        )

    @pytest.mark.asyncio
    async def test_can_user_edit_message_false(
        self, message_repo, mock_pool, mock_connection
    ):
        """Test user can edit message verification - negative case."""
        # Arrange
        message_id = 1
        user_id = 2  # Different user

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = create_mock_record(exists=False)

        # Act
        result = await message_repo.can_user_edit_message(message_id, user_id)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_get_user_messages_in_conversation_success(
        self, message_repo, mock_pool, mock_connection
    ):
        """Test successful user messages retrieval in conversation."""
        # Arrange
        conversation_id = 1
        user_id = 1

        expected_records = [
            create_mock_record(
                id=1,
                conversation_id=conversation_id,
                user_id=user_id,
                content="User message 1",
                content_type="text",
                metadata={},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                deleted_at=None,
            ),
            create_mock_record(
                id=3,
                conversation_id=conversation_id,
                user_id=user_id,
                content="User message 2",
                content_type="text",
                metadata={},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                deleted_at=None,
            ),
        ]

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetch.return_value = expected_records

        # Act
        result = await message_repo.get_user_messages_in_conversation(
            conversation_id, user_id
        )

        # Assert
        assert len(result) == 2
        assert all(msg["user_id"] == user_id for msg in result)
        mock_connection.fetch.assert_called_once_with(
            """
            SELECT * FROM messages
            WHERE conversation_id = $1 AND user_id = $2 AND deleted_at IS NULL
            ORDER BY created_at ASC
        """,
            conversation_id,
            user_id,
        )
