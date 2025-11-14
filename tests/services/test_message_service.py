"""
Tests for MessageService.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import asyncpg
from datetime import datetime, timezone

from app.services.message import MessageService
from app.schemas.message import (
    MessageCreate,
    MessageEditRequest,
    MessageRestoreRequest,
)


@pytest.fixture
def mock_db_pool():
    """Mock database connection pool."""
    pool = MagicMock()
    return pool


@pytest.fixture
def mock_message_repo():
    """Mock message repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_conversation_repo():
    """Mock conversation repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_version_repo():
    """Mock message version repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def message_service(mock_db_pool, mock_message_repo, mock_conversation_repo):
    """Create MessageService with mocked dependencies."""
    service = MessageService(mock_db_pool)
    service.message_repo = mock_message_repo
    service.conversation_repo = mock_conversation_repo
    service.version_repo = mock_version_repo
    return service


@pytest.fixture
def sample_message_record():
    """Sample message record from database."""
    return {
        "id": 1,
        "conversation_id": 1,
        "user_id": 1,
        "content": "Hello, this is a test message",
        "content_type": "text",
        "metadata": {"source": "user_input"},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_conversation_record():
    """Sample conversation record from database."""
    return {
        "id": 1,
        "user_id": 1,
        "title": "Test Conversation",
        "is_pinned": False,
        "is_archived": False,
        "metadata": {},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_version_record():
    """Sample message version record from database."""
    return {
        "id": 1,
        "message_id": 1,
        "version_number": 1,
        "content": "Original message content",
        "metadata": {},
        "user_id": 1,
        "created_at": datetime.now(timezone.utc),
    }


class TestMessageService:
    """Test cases for MessageService."""

    @pytest.mark.asyncio
    async def test_create_message_success(
        self,
        message_service,
        mock_conversation_repo,
        mock_message_repo,
        sample_conversation_record,
        sample_message_record,
    ):
        """Test successful message creation."""
        # Arrange
        user_id = 1
        conversation_id = 1
        message_data = MessageCreate(
            conversation_id=conversation_id,
            user_id=user_id,
            content="Hello, this is a test message",
            content_type="text",
        )

        mock_conversation_repo.get_by_id.return_value = sample_conversation_record
        mock_message_repo.create.return_value = sample_message_record

        # Act
        result = await message_service.create_message(
            user_id, conversation_id, message_data
        )

        # Assert
        assert result is not None
        assert result.id == 1
        assert result.conversation_id == conversation_id
        assert result.user_id == user_id
        assert result.content == "Hello, this is a test message"
        mock_conversation_repo.get_by_id.assert_called_once_with(
            conversation_id, user_id
        )
        mock_message_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_message_conversation_not_found(
        self, message_service, mock_conversation_repo
    ):
        """Test message creation with conversation not found."""
        # Arrange
        user_id = 1
        conversation_id = 999
        message_data = MessageCreate(
            conversation_id=conversation_id,
            user_id=user_id,
            content="Hello, this is a test message",
        )

        mock_conversation_repo.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Conversation not found or access denied"):
            await message_service.create_message(user_id, conversation_id, message_data)

        mock_message_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_message_database_error(
        self,
        message_service,
        mock_conversation_repo,
        mock_message_repo,
        sample_conversation_record,
    ):
        """Test message creation with database error."""
        # Arrange
        user_id = 1
        conversation_id = 1
        message_data = MessageCreate(
            conversation_id=conversation_id,
            user_id=user_id,
            content="Hello, this is a test message",
        )

        mock_conversation_repo.get_by_id.return_value = sample_conversation_record
        mock_message_repo.create.return_value = None

        # Act & Assert
        with pytest.raises(RuntimeError, match="Failed to create message"):
            await message_service.create_message(user_id, conversation_id, message_data)

    @pytest.mark.asyncio
    async def test_get_message_by_id_success(
        self,
        message_service,
        mock_conversation_repo,
        mock_message_repo,
        sample_conversation_record,
        sample_message_record,
    ):
        """Test successful message retrieval by ID."""
        # Arrange
        message_id = 1
        conversation_id = 1
        user_id = 1

        mock_conversation_repo.get_by_id.return_value = sample_conversation_record
        mock_message_repo.get_by_id.return_value = sample_message_record

        # Act
        result = await message_service.get_message_by_id(
            message_id, conversation_id, user_id
        )

        # Assert
        assert result is not None
        assert result.id == message_id
        assert result.conversation_id == conversation_id
        assert result.user_id == user_id
        mock_conversation_repo.get_by_id.assert_called_once_with(
            conversation_id, user_id
        )
        mock_message_repo.get_by_id.assert_called_once_with(message_id, conversation_id)

    @pytest.mark.asyncio
    async def test_get_message_by_id_conversation_not_found(
        self, message_service, mock_conversation_repo
    ):
        """Test message retrieval when conversation not found."""
        # Arrange
        message_id = 1
        conversation_id = 999
        user_id = 1

        mock_conversation_repo.get_by_id.return_value = None

        # Act
        result = await message_service.get_message_by_id(
            message_id, conversation_id, user_id
        )

        # Assert
        assert result is None
        mock_message_repo.get_by_id.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_conversation_messages_success(
        self,
        message_service,
        mock_conversation_repo,
        mock_message_repo,
        sample_conversation_record,
        sample_message_record,
    ):
        """Test successful conversation message listing."""
        # Arrange
        conversation_id = 1
        user_id = 1
        limit = 50
        before = None
        records = [sample_message_record]

        mock_conversation_repo.get_by_id.return_value = sample_conversation_record
        mock_message_repo.list_by_conversation.return_value = records

        # Act
        result = await message_service.list_conversation_messages(
            conversation_id, user_id, limit, before
        )

        # Assert
        assert result is not None
        assert len(result.messages) == 1
        assert result.has_more is True  # len(messages) == limit
        mock_conversation_repo.get_by_id.assert_called_once_with(
            conversation_id, user_id
        )
        mock_message_repo.list_by_conversation.assert_called_once_with(
            conversation_id, limit, before
        )

    @pytest.mark.asyncio
    async def test_list_conversation_messages_access_denied(
        self, message_service, mock_conversation_repo
    ):
        """Test conversation message listing with access denied."""
        # Arrange
        conversation_id = 1
        user_id = 1
        limit = 50

        mock_conversation_repo.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="Conversation not found or access denied"):
            await message_service.list_conversation_messages(
                conversation_id, user_id, limit
            )

        mock_message_repo.list_by_conversation.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_message_success(
        self,
        message_service,
        mock_conversation_repo,
        mock_message_repo,
        sample_conversation_record,
        sample_message_record,
    ):
        """Test successful message update."""
        # Arrange
        message_id = 1
        conversation_id = 1
        user_id = 1
        update_data = MessageEditRequest(content="Updated message content")
        updated_record = sample_message_record.copy()
        updated_record["content"] = "Updated message content"

        mock_conversation_repo.get_by_id.return_value = sample_conversation_record
        mock_message_repo.can_user_edit_message.return_value = True
        mock_message_repo.update.return_value = updated_record

        # Act
        result = await message_service.update_message(
            message_id, conversation_id, user_id, update_data
        )

        # Assert
        assert result is not None
        assert result.content == "Updated message content"
        mock_conversation_repo.get_by_id.assert_called_once_with(
            conversation_id, user_id
        )
        mock_message_repo.can_user_edit_message.assert_called_once_with(
            message_id, user_id
        )
        mock_message_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_message_access_denied(
        self, message_service, mock_message_repo
    ):
        """Test message update with access denied."""
        # Arrange
        message_id = 1
        conversation_id = 1
        user_id = 1
        update_data = MessageEditRequest(content="Updated message content")

        mock_message_repo.can_user_edit_message.return_value = False

        # Act & Assert
        with pytest.raises(ValueError, match="Cannot edit message: access denied"):
            await message_service.update_message(
                message_id, conversation_id, user_id, update_data
            )

        mock_message_repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_message_success(
        self,
        message_service,
        mock_conversation_repo,
        mock_message_repo,
        sample_conversation_record,
    ):
        """Test successful message deletion."""
        # Arrange
        message_id = 1
        conversation_id = 1
        user_id = 1

        mock_conversation_repo.get_by_id.return_value = sample_conversation_record
        mock_message_repo.can_user_edit_message.return_value = True
        mock_message_repo.delete.return_value = True

        # Act
        result = await message_service.delete_message(
            message_id, conversation_id, user_id
        )

        # Assert
        assert result is True
        mock_conversation_repo.get_by_id.assert_called_once_with(
            conversation_id, user_id
        )
        mock_message_repo.can_user_edit_message.assert_called_once_with(
            message_id, user_id
        )
        mock_message_repo.delete.assert_called_once_with(message_id, conversation_id)

    @pytest.mark.asyncio
    async def test_get_message_version_history_success(
        self,
        message_service,
        mock_conversation_repo,
        mock_message_repo,
        mock_version_repo,
        sample_conversation_record,
        sample_message_record,
        sample_version_record,
    ):
        """Test successful message version history retrieval."""
        # Arrange
        message_id = 1
        conversation_id = 1
        user_id = 1
        version_records = [sample_version_record]

        mock_conversation_repo.get_by_id.return_value = sample_conversation_record
        mock_message_repo.get_by_id.return_value = sample_message_record
        mock_version_repo.list_by_message.return_value = version_records

        # Act
        result = await message_service.get_message_version_history(
            message_id, conversation_id, user_id
        )

        # Assert
        assert result is not None
        assert len(result.versions) == 1
        assert result.total_count == 1
        assert result.versions[0].version_number == 1

    @pytest.mark.asyncio
    async def test_restore_message_to_version_success(
        self,
        message_service,
        mock_conversation_repo,
        mock_message_repo,
        mock_version_repo,
        sample_conversation_record,
        sample_message_record,
        sample_version_record,
    ):
        """Test successful message restoration to previous version."""
        # Arrange
        message_id = 1
        conversation_id = 1
        user_id = 1
        restore_request = MessageRestoreRequest(version_number=1)
        restored_record = sample_message_record.copy()
        restored_record["content"] = sample_version_record["content"]

        mock_conversation_repo.get_by_id.return_value = sample_conversation_record
        mock_message_repo.can_user_edit_message.return_value = True
        mock_version_repo.get_by_message_and_version.return_value = (
            sample_version_record
        )
        mock_message_repo.update.return_value = restored_record

        # Act
        result = await message_service.restore_message_to_version(
            message_id, conversation_id, user_id, restore_request
        )

        # Assert
        assert result is not None
        assert result.content == sample_version_record["content"]
        mock_version_repo.get_by_message_and_version.assert_called_once_with(
            message_id, 1
        )

    @pytest.mark.asyncio
    async def test_get_latest_message_success(
        self,
        message_service,
        mock_conversation_repo,
        mock_message_repo,
        sample_conversation_record,
        sample_message_record,
    ):
        """Test successful latest message retrieval."""
        # Arrange
        conversation_id = 1
        user_id = 1

        mock_conversation_repo.get_by_id.return_value = sample_conversation_record
        mock_message_repo.get_conversation_latest_message.return_value = (
            sample_message_record
        )

        # Act
        result = await message_service.get_latest_message(conversation_id, user_id)

        # Assert
        assert result is not None
        assert result.id == sample_message_record["id"]
        mock_conversation_repo.get_by_id.assert_called_once_with(
            conversation_id, user_id
        )
        mock_message_repo.get_conversation_latest_message.assert_called_once_with(
            conversation_id
        )

    @pytest.mark.asyncio
    async def test_count_messages_in_conversation_success(
        self,
        message_service,
        mock_conversation_repo,
        mock_message_repo,
        sample_conversation_record,
    ):
        """Test successful message counting in conversation."""
        # Arrange
        conversation_id = 1
        user_id = 1
        expected_count = 5

        mock_conversation_repo.get_by_id.return_value = sample_conversation_record
        mock_message_repo.count_by_conversation.return_value = expected_count

        # Act
        result = await message_service.count_messages_in_conversation(
            conversation_id, user_id
        )

        # Assert
        assert result == expected_count
        mock_conversation_repo.get_by_id.assert_called_once_with(
            conversation_id, user_id
        )
        mock_message_repo.count_by_conversation.assert_called_once_with(conversation_id)

    @pytest.mark.asyncio
    async def test_count_messages_in_conversation_not_found(
        self, message_service, mock_conversation_repo
    ):
        """Test message counting when conversation not found."""
        # Arrange
        conversation_id = 999
        user_id = 1

        mock_conversation_repo.get_by_id.return_value = None

        # Act
        result = await message_service.count_messages_in_conversation(
            conversation_id, user_id
        )

        # Assert
        assert result is None
        mock_message_repo.count_by_conversation.assert_not_called()
