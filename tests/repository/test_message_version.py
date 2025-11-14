"""
Tests for MessageVersionRepository.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest_asyncio

from app.db.message_version import MessageVersionRepository


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
def message_version_repo(mock_pool):
    """Create MessageVersionRepository instance with mock pool."""
    return MessageVersionRepository(mock_pool)


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


class TestMessageVersionRepository:
    """Test cases for MessageVersionRepository."""

    @pytest.mark.asyncio
    async def test_create_version_success(
        self, message_version_repo, mock_pool, mock_connection
    ):
        """Test successful message version creation."""
        # Arrange
        version_data = {
            "message_id": 1,
            "version_number": 2,
            "content": "Edited message content",
            "user_id": 1,
            "metadata": {"edited": True},
        }

        expected_record = create_mock_record(
            id=5,
            message_id=1,
            version_number=2,
            content="Edited message content",
            metadata={"edited": True},
            user_id=1,
            created_at=datetime.now(timezone.utc),
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = expected_record

        # Act
        result = await message_version_repo.create(version_data)

        # Assert
        assert result is not None
        assert result["message_id"] == 1
        assert result["version_number"] == 2
        assert result["content"] == "Edited message content"
        assert result["user_id"] == 1
        assert result["metadata"] == {"edited": True}

        # Verify query parameters
        call_args = mock_connection.fetchrow.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert "INSERT INTO message_versions" in query
        assert "VALUES ($1, $2, $3, $4, $5)" in query
        assert params[0] == 1  # message_id
        assert params[1] == 2  # version_number
        assert params[2] == "Edited message content"  # content
        assert params[3] == {"edited": True}  # metadata
        assert params[4] == 1  # user_id

    @pytest.mark.asyncio
    async def test_create_version_minimal_data(
        self, message_version_repo, mock_pool, mock_connection
    ):
        """Test version creation with minimal required data."""
        # Arrange
        version_data = {
            "message_id": 1,
            "version_number": 1,
            "content": "Initial message",
            "user_id": 1,
        }

        expected_record = create_mock_record(
            id=1,
            message_id=1,
            version_number=1,
            content="Initial message",
            metadata={},  # Default value
            user_id=1,
            created_at=datetime.now(timezone.utc),
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = expected_record

        # Act
        result = await message_version_repo.create(version_data)

        # Assert
        assert result is not None
        assert result["metadata"] == {}  # Default value

    @pytest.mark.asyncio
    async def test_list_by_message_success(
        self, message_version_repo, mock_pool, mock_connection
    ):
        """Test successful version listing for a message."""
        # Arrange
        message_id = 1

        expected_records = [
            create_mock_record(
                id=5,
                message_id=message_id,
                version_number=3,
                content="Third version",
                metadata={},
                user_id=1,
                created_at=datetime.now(timezone.utc),
            ),
            create_mock_record(
                id=3,
                message_id=message_id,
                version_number=2,
                content="Second version",
                metadata={},
                user_id=1,
                created_at=datetime.now(timezone.utc),
            ),
            create_mock_record(
                id=1,
                message_id=message_id,
                version_number=1,
                content="First version",
                metadata={},
                user_id=1,
                created_at=datetime.now(timezone.utc),
            ),
        ]

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetch.return_value = expected_records

        # Act
        result = await message_version_repo.list_by_message(message_id)

        # Assert
        assert len(result) == 3
        # Should be ordered by version_number DESC
        assert result[0]["version_number"] == 3
        assert result[1]["version_number"] == 2
        assert result[2]["version_number"] == 1
        mock_connection.fetch.assert_called_once_with(
            """
            SELECT * FROM message_versions
            WHERE message_id = $1
            ORDER BY version_number DESC
        """,
            message_id,
        )

    @pytest.mark.asyncio
    async def test_get_latest_version_number_success(
        self, message_version_repo, mock_pool, mock_connection
    ):
        """Test successful latest version number retrieval."""
        # Arrange
        message_id = 1
        expected_version = 5

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = create_mock_record(
            coalesce=expected_version
        )

        # Act
        result = await message_version_repo.get_latest_version_number(message_id)

        # Assert
        assert result == expected_version
        mock_connection.fetchrow.assert_called_once_with(
            """
            SELECT COALESCE(MAX(version_number), 0)
            FROM message_versions
            WHERE message_id = $1
        """,
            message_id,
        )

    @pytest.mark.asyncio
    async def test_get_latest_version_number_no_versions(
        self, message_version_repo, mock_pool, mock_connection
    ):
        """Test latest version number when no versions exist."""
        # Arrange
        message_id = 1

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = None

        # Act
        result = await message_version_repo.get_latest_version_number(message_id)

        # Assert
        assert result == 0

    @pytest.mark.asyncio
    async def test_get_by_version_success(
        self, message_version_repo, mock_pool, mock_connection
    ):
        """Test successful specific version retrieval."""
        # Arrange
        message_id = 1
        version_number = 2

        expected_record = create_mock_record(
            id=3,
            message_id=message_id,
            version_number=version_number,
            content="Version 2 content",
            metadata={},
            user_id=1,
            created_at=datetime.now(timezone.utc),
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = expected_record

        # Act
        result = await message_version_repo.get_by_version(message_id, version_number)

        # Assert
        assert result is not None
        assert result["message_id"] == message_id
        assert result["version_number"] == version_number
        assert result["content"] == "Version 2 content"
        mock_connection.fetchrow.assert_called_once_with(
            """
            SELECT * FROM message_versions
            WHERE message_id = $1 AND version_number = $2
        """,
            message_id,
            version_number,
        )

    @pytest.mark.asyncio
    async def test_get_by_version_not_found(
        self, message_version_repo, mock_pool, mock_connection
    ):
        """Test specific version retrieval when version not found."""
        # Arrange
        message_id = 1
        version_number = 999

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = None

        # Act
        result = await message_version_repo.get_by_version(message_id, version_number)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_count_versions_success(
        self, message_version_repo, mock_pool, mock_connection
    ):
        """Test successful version count for a message."""
        # Arrange
        message_id = 1
        expected_count = 3

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = create_mock_record(count=expected_count)

        # Act
        result = await message_version_repo.count_versions(message_id)

        # Assert
        assert result == expected_count
        mock_connection.fetchrow.assert_called_once_with(
            """
            SELECT COUNT(*) FROM message_versions
            WHERE message_id = $1
        """,
            message_id,
        )

    @pytest.mark.asyncio
    async def test_get_versions_by_user_success(
        self, message_version_repo, mock_pool, mock_connection
    ):
        """Test successful version listing filtered by user."""
        # Arrange
        message_id = 1
        user_id = 1

        expected_records = [
            create_mock_record(
                id=5,
                message_id=message_id,
                version_number=2,
                content="User edited version",
                metadata={},
                user_id=user_id,
                created_at=datetime.now(timezone.utc),
            )
        ]

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetch.return_value = expected_records

        # Act
        result = await message_version_repo.get_versions_by_user(message_id, user_id)

        # Assert
        assert len(result) == 1
        assert result[0]["user_id"] == user_id
        assert result[0]["version_number"] == 2
        mock_connection.fetch.assert_called_once_with(
            """
            SELECT * FROM message_versions
            WHERE message_id = $1 AND user_id = $2
            ORDER BY version_number DESC
        """,
            message_id,
            user_id,
        )

    @pytest.mark.asyncio
    async def test_get_latest_version_success(
        self, message_version_repo, mock_pool, mock_connection
    ):
        """Test successful latest version retrieval."""
        # Arrange
        message_id = 1

        expected_record = create_mock_record(
            id=5,
            message_id=message_id,
            version_number=3,
            content="Latest version",
            metadata={},
            user_id=1,
            created_at=datetime.now(timezone.utc),
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = expected_record

        # Act
        result = await message_version_repo.get_latest_version(message_id)

        # Assert
        assert result is not None
        assert result["version_number"] == 3
        assert result["content"] == "Latest version"
        mock_connection.fetchrow.assert_called_once_with(
            """
            SELECT * FROM message_versions
            WHERE message_id = $1
            ORDER BY version_number DESC
            LIMIT 1
        """,
            message_id,
        )

    @pytest.mark.asyncio
    async def test_restore_version_success(
        self, message_version_repo, mock_pool, mock_connection
    ):
        """Test successful version restoration."""
        # Arrange
        message_id = 1
        version_number = 2
        user_id = 1

        # Mock the version to restore
        version_to_restore = create_mock_record(
            id=3,
            message_id=message_id,
            version_number=version_number,
            content="Restored content",
            metadata={"restored": True},
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
        )

        # Mock the updated message after restoration
        restored_message = create_mock_record(
            id=message_id,
            conversation_id=1,
            user_id=user_id,
            content="Restored content",
            metadata={"restored": True},
            content_type="text",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            deleted_at=None,
        )

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        # Mock get_by_version call and update call
        mock_connection.fetchrow.side_effect = [version_to_restore, restored_message]

        # Act
        result = await message_version_repo.restore_version(
            message_id, version_number, user_id
        )

        # Assert
        assert result is not None
        assert result["content"] == "Restored content"
        assert result["metadata"] == {"restored": True}

        # Verify both calls were made
        assert mock_connection.fetchrow.call_count == 2

    @pytest.mark.asyncio
    async def test_restore_version_not_found(
        self, message_version_repo, mock_pool, mock_connection
    ):
        """Test version restoration when version not found."""
        # Arrange
        message_id = 1
        version_number = 999
        user_id = 1

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = None

        # Act
        result = await message_version_repo.restore_version(
            message_id, version_number, user_id
        )

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_versions_for_message_success(
        self, message_version_repo, mock_pool, mock_connection
    ):
        """Test successful deletion of all versions for a message."""
        # Arrange
        message_id = 1

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.execute.return_value = "DELETE 3"

        # Act
        result = await message_version_repo.delete_versions_for_message(message_id)

        # Assert
        assert result is True
        mock_connection.execute.assert_called_once_with(
            """
            DELETE FROM message_versions
            WHERE message_id = $1
        """,
            message_id,
        )

    @pytest.mark.asyncio
    async def test_get_version_history_summary_success(
        self, message_version_repo, mock_pool, mock_connection
    ):
        """Test successful version history summary retrieval."""
        # Arrange
        message_id = 1
        limit = 10

        expected_records = [
            create_mock_record(
                id=5,
                message_id=message_id,
                version_number=2,
                content="Edited version",
                metadata={},
                user_id=1,
                created_at=datetime.now(timezone.utc),
                editor_email="user@example.com",
                first_name="John",
                last_name="Doe",
            )
        ]

        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetch.return_value = expected_records

        # Act
        result = await message_version_repo.get_version_history_summary(
            message_id, limit
        )

        # Assert
        assert len(result) == 1
        assert result[0]["version_number"] == 2
        assert result[0]["editor_email"] == "user@example.com"
        assert result[0]["first_name"] == "John"
        assert result[0]["last_name"] == "Doe"
        mock_connection.fetch.assert_called_once_with(
            """
            SELECT mv.*, u.email as editor_email, up.first_name, up.last_name
            FROM message_versions mv
            LEFT JOIN users u ON mv.user_id = u.id
            LEFT JOIN user_profiles up ON mv.user_id = up.user_id
            WHERE mv.message_id = $1
            ORDER BY mv.version_number DESC
            LIMIT $2
        """,
            message_id,
            limit,
        )
