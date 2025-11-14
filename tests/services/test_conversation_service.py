"""
Tests for ConversationService.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
import asyncpg
from datetime import datetime, timezone

from app.services.conversation import ConversationService
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationPinRequest,
)


@pytest.fixture
def mock_db_pool():
    """Mock database connection pool."""
    pool = MagicMock()
    return pool


@pytest.fixture
def mock_conversation_repo():
    """Mock conversation repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_message_repo():
    """Mock message repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def conversation_service(mock_db_pool, mock_conversation_repo, mock_message_repo):
    """Create ConversationService with mocked dependencies."""
    service = ConversationService(mock_db_pool)
    service.conversation_repo = mock_conversation_repo
    service.message_repo = mock_message_repo
    return service


@pytest.fixture
def sample_conversation_record():
    """Sample conversation record from database."""
    return {
        "id": 1,
        "user_id": 1,
        "title": "Test Conversation",
        "is_pinned": False,
        "is_archived": False,
        "metadata": {"theme": "health"},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


class TestConversationService:
    """Test cases for ConversationService."""

    @pytest.mark.asyncio
    async def test_create_conversation_success(
        self, conversation_service, mock_conversation_repo, sample_conversation_record
    ):
        """Test successful conversation creation."""
        # Arrange
        user_id = 1
        conversation_data = ConversationCreate(
            user_id=user_id,
            title="Test Conversation",
            is_pinned=False,
            metadata={"theme": "health"},
        )

        mock_conversation_repo.create.return_value = sample_conversation_record

        # Act
        result = await conversation_service.create_conversation(
            user_id, conversation_data
        )

        # Assert
        assert result is not None
        assert result.id == 1
        assert result.user_id == 1
        assert result.title == "Test Conversation"
        assert result.is_pinned is False
        mock_conversation_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_conversation_user_mismatch(
        self, conversation_service, mock_conversation_repo
    ):
        """Test conversation creation with user ID mismatch."""
        # Arrange
        user_id = 1
        conversation_data = ConversationCreate(user_id=2)  # Different user_id

        # Act & Assert
        with pytest.raises(ValueError, match="User ID mismatch"):
            await conversation_service.create_conversation(user_id, conversation_data)

        mock_conversation_repo.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_conversation_database_error(
        self, conversation_service, mock_conversation_repo
    ):
        """Test conversation creation with database error."""
        # Arrange
        user_id = 1
        conversation_data = ConversationCreate(user_id=user_id)
        mock_conversation_repo.create.return_value = None

        # Act & Assert
        with pytest.raises(RuntimeError, match="Failed to create conversation"):
            await conversation_service.create_conversation(user_id, conversation_data)

    @pytest.mark.asyncio
    async def test_get_conversation_by_id_success(
        self, conversation_service, mock_conversation_repo, sample_conversation_record
    ):
        """Test successful conversation retrieval by ID."""
        # Arrange
        conversation_id = 1
        user_id = 1
        mock_conversation_repo.get_by_id.return_value = sample_conversation_record

        # Act
        result = await conversation_service.get_conversation_by_id(
            conversation_id, user_id
        )

        # Assert
        assert result is not None
        assert result.id == conversation_id
        assert result.user_id == user_id
        mock_conversation_repo.get_by_id.assert_called_once_with(
            conversation_id, user_id
        )

    @pytest.mark.asyncio
    async def test_get_conversation_by_id_not_found(
        self, conversation_service, mock_conversation_repo
    ):
        """Test conversation retrieval when not found."""
        # Arrange
        conversation_id = 999
        user_id = 1
        mock_conversation_repo.get_by_id.return_value = None

        # Act
        result = await conversation_service.get_conversation_by_id(
            conversation_id, user_id
        )

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_list_user_conversations_success(
        self, conversation_service, mock_conversation_repo, sample_conversation_record
    ):
        """Test successful conversation listing."""
        # Arrange
        user_id = 1
        limit = 10
        offset = 0
        records = [sample_conversation_record]
        mock_conversation_repo.list_by_user.return_value = records
        mock_conversation_repo.count_conversations_by_user.return_value = 1

        # Act
        result = await conversation_service.list_user_conversations(
            user_id, limit, offset
        )

        # Assert
        assert result is not None
        assert len(result.conversations) == 1
        assert result.total_count == 1
        assert result.has_more is False
        mock_conversation_repo.list_by_user.assert_called_once_with(
            user_id, limit, offset
        )
        mock_conversation_repo.count_conversations_by_user.assert_called_once_with(
            user_id
        )

    @pytest.mark.asyncio
    async def test_update_conversation_success(
        self, conversation_service, mock_conversation_repo, sample_conversation_record
    ):
        """Test successful conversation update."""
        # Arrange
        conversation_id = 1
        user_id = 1
        update_data = ConversationUpdate(title="Updated Title")
        updated_record = sample_conversation_record.copy()
        updated_record["title"] = "Updated Title"

        mock_conversation_repo.get_by_id.return_value = sample_conversation_record
        mock_conversation_repo.update.return_value = updated_record

        # Act
        result = await conversation_service.update_conversation(
            conversation_id, user_id, update_data
        )

        # Assert
        assert result is not None
        assert result.title == "Updated Title"
        mock_conversation_repo.get_by_id.assert_called_once_with(
            conversation_id, user_id
        )
        mock_conversation_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_conversation_not_found(
        self, conversation_service, mock_conversation_repo
    ):
        """Test conversation update when conversation not found."""
        # Arrange
        conversation_id = 999
        user_id = 1
        update_data = ConversationUpdate(title="Updated Title")
        mock_conversation_repo.get_by_id.return_value = None

        # Act
        result = await conversation_service.update_conversation(
            conversation_id, user_id, update_data
        )

        # Assert
        assert result is None
        mock_conversation_repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_pin_conversation_success(
        self, conversation_service, mock_conversation_repo, sample_conversation_record
    ):
        """Test successful conversation pinning."""
        # Arrange
        conversation_id = 1
        user_id = 1
        pin_request = ConversationPinRequest(is_pinned=True)
        pinned_record = sample_conversation_record.copy()
        pinned_record["is_pinned"] = True

        mock_conversation_repo.pin_conversation.return_value = pinned_record

        # Act
        result = await conversation_service.pin_conversation(
            conversation_id, user_id, pin_request
        )

        # Assert
        assert result is not None
        assert result.is_pinned is True
        mock_conversation_repo.pin_conversation.assert_called_once_with(
            conversation_id, user_id, True
        )

    @pytest.mark.asyncio
    async def test_delete_conversation_success(
        self, conversation_service, mock_conversation_repo, sample_conversation_record
    ):
        """Test successful conversation deletion."""
        # Arrange
        conversation_id = 1
        user_id = 1
        mock_conversation_repo.get_by_id.return_value = sample_conversation_record
        mock_conversation_repo.delete.return_value = True

        # Act
        result = await conversation_service.delete_conversation(
            conversation_id, user_id
        )

        # Assert
        assert result is True
        mock_conversation_repo.get_by_id.assert_called_once_with(
            conversation_id, user_id
        )
        mock_conversation_repo.delete.assert_called_once_with(conversation_id, user_id)

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(
        self, conversation_service, mock_conversation_repo
    ):
        """Test conversation deletion when conversation not found."""
        # Arrange
        conversation_id = 999
        user_id = 1
        mock_conversation_repo.get_by_id.return_value = None

        # Act
        result = await conversation_service.delete_conversation(
            conversation_id, user_id
        )

        # Assert
        assert result is False
        mock_conversation_repo.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_conversation_message_count_success(
        self, conversation_service, mock_conversation_repo, mock_message_repo
    ):
        """Test successful message count retrieval."""
        # Arrange
        conversation_id = 1
        user_id = 1
        expected_count = 5
        sample_conversation_record = {"id": conversation_id, "user_id": user_id}

        mock_conversation_repo.get_by_id.return_value = sample_conversation_record
        mock_conversation_repo.get_message_count.return_value = expected_count

        # Act
        result = await conversation_service.get_conversation_message_count(
            conversation_id, user_id
        )

        # Assert
        assert result == expected_count
        mock_conversation_repo.get_by_id.assert_called_once_with(
            conversation_id, user_id
        )
        mock_conversation_repo.get_message_count.assert_called_once_with(
            conversation_id
        )

    @pytest.mark.asyncio
    async def test_get_conversation_message_count_not_found(
        self, conversation_service, mock_conversation_repo
    ):
        """Test message count retrieval when conversation not found."""
        # Arrange
        conversation_id = 999
        user_id = 1
        mock_conversation_repo.get_by_id.return_value = None

        # Act
        result = await conversation_service.get_conversation_message_count(
            conversation_id, user_id
        )

        # Assert
        assert result is None
        mock_conversation_repo.get_message_count.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_pinned_conversations_success(
        self, conversation_service, mock_conversation_repo, sample_conversation_record
    ):
        """Test successful pinned conversations retrieval."""
        # Arrange
        user_id = 1
        limit = 10
        pinned_record = sample_conversation_record.copy()
        pinned_record["is_pinned"] = True
        records = [pinned_record]

        mock_conversation_repo.list_by_user.return_value = records

        # Act
        result = await conversation_service.get_pinned_conversations(user_id, limit)

        # Assert
        assert len(result) == 1
        assert result[0].is_pinned is True
        mock_conversation_repo.list_by_user.assert_called_once_with(user_id, limit, 0)

    @pytest.mark.asyncio
    async def test_update_conversation_title_success(
        self, conversation_service, mock_conversation_repo, sample_conversation_record
    ):
        """Test successful conversation title update."""
        # Arrange
        conversation_id = 1
        user_id = 1
        new_title = "New Title"
        updated_record = sample_conversation_record.copy()
        updated_record["title"] = new_title

        mock_conversation_repo.get_by_id.return_value = sample_conversation_record
        mock_conversation_repo.update.return_value = updated_record

        # Act
        result = await conversation_service.update_conversation_title(
            conversation_id, user_id, new_title
        )

        # Assert
        assert result is not None
        assert result.title == new_title
        mock_conversation_repo.update.assert_called_once()
