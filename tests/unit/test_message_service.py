"""
Tests for MessageService.

Tests message business logic including CRUD operations, tree operations,
branching, and integration with versioning and caching.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.services.message import MessageService
from app.schemas.message import MessageDetail, MessageListResponse, MessageTreeNode


@pytest.mark.service
@pytest.mark.unit
class TestMessageService:
    """Test cases for MessageService."""

    @pytest.fixture
    def service(
        self, mock_db_pool, mock_qa_service, mock_message_repo, mock_version_repo
    ):
        """Create service instance with mocked dependencies."""
        service = MessageService(mock_db_pool, mock_qa_service)
        # Replace real repositories with mocked ones
        service.message_repo = mock_message_repo
        service.version_repo = mock_version_repo
        return service

    @pytest.fixture
    def mock_message_data(self, test_user_id):
        """Mock message data from database."""
        return {
            "id": 1,
            "conversation_id": 1,
            "role": "user",
            "content": "Test message",
            "content_cleaned": "Test message",
            "answers": None,
            "parent_id": None,
            "is_deleted": False,
            "metadata": {},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    # ========================================================================
    # ADD MESSAGE TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_add_message_success(self, service, test_user_id, mock_message_data):
        """Test adding message successfully."""
        # Arrange
        service.message_repo.verify_conversation_ownership = AsyncMock(
            return_value=True
        )
        service.message_repo.create_message = AsyncMock(return_value=1)
        service.message_repo.update_conversation_timestamp = AsyncMock()
        service.message_repo.get_message_by_user = AsyncMock(
            return_value=mock_message_data
        )

        # Act
        result = await service.add_message(
            conversation_id=1,
            user_id=test_user_id,
            content="Test message",
            role="user",
        )

        # Assert
        assert isinstance(result, MessageDetail)
        assert result.content == "Test message"
        service.message_repo.verify_conversation_ownership.assert_called_once_with(
            1, test_user_id
        )
        service.message_repo.create_message.assert_called_once()
        service.message_repo.update_conversation_timestamp.assert_called_once_with(
            1, test_user_id
        )

    @pytest.mark.asyncio
    async def test_add_message_with_parent(
        self, service, test_user_id, mock_message_data
    ):
        """Test adding message with parent (branching)."""
        # Arrange
        service.message_repo.verify_conversation_ownership = AsyncMock(
            return_value=True
        )
        service.message_repo.create_message = AsyncMock(return_value=2)
        service.message_repo.update_conversation_timestamp = AsyncMock()
        service.message_repo.get_message_by_user = AsyncMock(
            return_value=mock_message_data
        )

        # Act
        result = await service.add_message(
            conversation_id=1,
            user_id=test_user_id,
            content="Reply message",
            role="assistant",
            parent_message_id=1,
        )

        # Assert
        assert isinstance(result, MessageDetail)
        service.message_repo.create_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_message_invalid_role(self, service, test_user_id):
        """Test adding message with invalid role."""
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid message role"):
            await service.add_message(
                conversation_id=1,
                user_id=test_user_id,
                content="Test",
                role="invalid",
            )

    @pytest.mark.asyncio
    async def test_add_message_content_too_long(self, service, test_user_id):
        """Test adding message with content exceeding max length."""
        # Arrange
        long_content = "x" * 5001

        # Act & Assert
        with pytest.raises(ValueError, match="Message content too long"):
            await service.add_message(
                conversation_id=1,
                user_id=test_user_id,
                content=long_content,
                role="user",
            )

    @pytest.mark.asyncio
    async def test_add_message_creation_failure(self, service, test_user_id):
        """Test handling message creation failure."""
        # Arrange
        service.message_repo.verify_conversation_ownership = AsyncMock(
            return_value=True
        )
        service.message_repo.create_message = AsyncMock(return_value=1)
        service.message_repo.update_conversation_timestamp = AsyncMock()
        service.message_repo.get_message_by_user = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="Failed to create message"):
            await service.add_message(
                conversation_id=1,
                user_id=test_user_id,
                content="Test",
                role="user",
            )

    # ========================================================================
    # GET MESSAGE TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_message_success(self, service, test_user_id, mock_message_data):
        """Test getting message successfully."""
        # Arrange
        service.message_repo.get_message_by_user = AsyncMock(
            return_value=mock_message_data
        )

        # Act
        result = await service.get_message(1, test_user_id)

        # Assert
        assert isinstance(result, MessageDetail)
        assert result.id == 1
        service.message_repo.get_message_by_user.assert_called_once_with(
            1, test_user_id
        )

    @pytest.mark.asyncio
    async def test_get_message_not_found(self, service, test_user_id):
        """Test getting non-existent message."""
        # Arrange
        service.message_repo.get_message_by_user = AsyncMock(return_value=None)

        # Act
        result = await service.get_message(999, test_user_id)

        # Assert
        assert result is None

    # ========================================================================
    # UPDATE MESSAGE TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_update_message_success(
        self, service, test_user_id, mock_message_data
    ):
        """Test updating message successfully."""
        # Arrange
        updated_data = mock_message_data.copy()
        updated_data["content"] = "Updated content"

        service.message_repo.get_message_by_user = AsyncMock(
            return_value=mock_message_data
        )
        service.message_repo.update_message = AsyncMock(return_value=True)
        service.version_repo.create_version = AsyncMock(return_value=1)

        # Mock second call after update
        service.message_repo.get_message_by_user = AsyncMock(
            side_effect=[mock_message_data, updated_data]
        )

        # Act
        result = await service.update_message(
            message_id=1,
            user_id=test_user_id,
            content="Updated content",
        )

        # Assert
        assert isinstance(result, MessageDetail)
        service.message_repo.update_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_message_not_found(self, service, test_user_id):
        """Test updating non-existent message."""
        # Arrange
        service.message_repo.get_message_by_user = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="Message not found"):
            await service.update_message(
                message_id=999,
                user_id=test_user_id,
                content="Updated content",
            )

    @pytest.mark.asyncio
    async def test_update_message_with_versioning(
        self, service, test_user_id, mock_message_data
    ):
        """Test updating message with versioning enabled."""
        # Arrange
        updated_data = mock_message_data.copy()
        updated_data["content"] = "Updated content"

        service.message_repo.get_message_by_user = AsyncMock(
            side_effect=[mock_message_data, updated_data]
        )
        service.message_repo.update_message = AsyncMock(return_value=True)
        service.version_repo.get_latest_version_number = AsyncMock(return_value=0)
        service.version_repo.create_version = AsyncMock(return_value=1)

        # Act
        result = await service.update_message(
            message_id=1,
            user_id=test_user_id,
            content="Updated content",
            create_version=True,
        )

        # Assert
        assert isinstance(result, MessageDetail)
        service.version_repo.create_version.assert_called_once()

    # ========================================================================
    # DELETE MESSAGE TESTS
    # ========================================================================

    @pytest.mark.asyncio
    @patch("app.services.message.conversation_cache")
    async def test_delete_message_success(
        self, mock_cache, service, test_user_id, mock_message_data
    ):
        """Test deleting message successfully."""
        # Arrange
        service.message_repo.get_message_by_user = AsyncMock(
            return_value=mock_message_data
        )
        service.message_repo.delete_message = AsyncMock(return_value=True)

        # Act
        result = await service.delete_message(1, test_user_id)

        # Assert
        assert result is True
        service.message_repo.delete_message.assert_called_once_with(1, test_user_id)

    @pytest.mark.asyncio
    async def test_delete_message_not_found(self, service, test_user_id):
        """Test deleting non-existent message."""
        # Arrange
        service.message_repo.get_message_by_user = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="Message not found"):
            await service.delete_message(999, test_user_id)

    # ========================================================================
    # LIST MESSAGES TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_list_messages_success(self, service, test_user_id):
        """Test listing messages successfully."""
        # Arrange
        mock_messages = [
            {
                "id": i,
                "conversation_id": 1,
                "role": "user",
                "content": f"Message {i}",
                "content_cleaned": f"Message {i}",
                "answers": None,
                "parent_id": None,
                "is_deleted": False,
                "metadata": {},
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            for i in range(1, 6)
        ]

        service.message_repo.get_conversation_messages = AsyncMock(
            return_value=mock_messages
        )
        service.message_repo.count_conversation_messages = AsyncMock(return_value=5)

        # Act
        result = await service.list_messages(
            conversation_id=1,
            user_id=test_user_id,
            page=1,
            page_size=20,
        )

        # Assert
        assert isinstance(result, MessageListResponse)
        assert result.total == 5
        assert len(result.messages) == 5

    @pytest.mark.asyncio
    async def test_list_messages_pagination(self, service, test_user_id):
        """Test message list pagination."""
        # Arrange
        service.message_repo.get_conversation_messages = AsyncMock(return_value=[])
        service.message_repo.count_conversation_messages = AsyncMock(return_value=50)

        # Act
        result = await service.list_messages(
            conversation_id=1,
            user_id=test_user_id,
            page=2,
            page_size=10,
        )

        # Assert
        assert result.page == 2
        assert result.page_size == 10
        assert result.total == 50
        assert result.total_pages == 5

    @pytest.mark.asyncio
    async def test_list_messages_empty(self, service, test_user_id):
        """Test listing when conversation has no messages."""
        # Arrange
        service.message_repo.get_conversation_messages = AsyncMock(return_value=[])
        service.message_repo.count_conversation_messages = AsyncMock(return_value=0)

        # Act
        result = await service.list_messages(
            conversation_id=1,
            user_id=test_user_id,
        )

        # Assert
        assert result.total == 0
        assert len(result.messages) == 0

    # ========================================================================
    # CREATE BRANCH TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_create_branch_success(
        self, service, test_user_id, mock_message_data
    ):
        """Test creating message branch successfully."""
        # Arrange
        # First call: check parent exists
        # Second call: get created branch message
        new_message = mock_message_data.copy()
        new_message["id"] = 2
        new_message["parent_id"] = 1

        service.message_repo.get_message_by_user = AsyncMock(
            side_effect=[mock_message_data, new_message]
        )
        service.message_repo.create_message_branch = AsyncMock(return_value=2)
        service.message_repo.update_conversation_timestamp = AsyncMock()

        # Act
        result = await service.create_branch(
            parent_message_id=1,
            user_id=test_user_id,
            role="assistant",
            content="Branch message",
        )

        # Assert
        assert isinstance(result, MessageDetail)
        service.message_repo.create_message_branch.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_branch_parent_not_found(self, service, test_user_id):
        """Test creating branch with non-existent parent."""
        # Arrange
        service.message_repo.get_message_by_user = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="Parent message not found"):
            await service.create_branch(
                parent_message_id=999,
                user_id=test_user_id,
                content="Branch message",
                role="assistant",
            )

    # ========================================================================
    # CONVERSATION TREE TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_conversation_tree_success(self, service, test_user_id):
        """Test getting conversation tree successfully."""
        # Arrange
        mock_messages = [
            {
                "id": 1,
                "conversation_id": 1,
                "role": "user",
                "content": "Root",
                "parent_message_id": None,
                "children": [],
                "created_at": datetime.now(timezone.utc),
            },
            {
                "id": 2,
                "conversation_id": 1,
                "role": "assistant",
                "content": "Child 1",
                "parent_message_id": 1,
                "children": [],
                "created_at": datetime.now(timezone.utc),
            },
        ]

        service.message_repo.get_conversation_tree = AsyncMock(
            return_value=mock_messages
        )

        # Act
        result = await service.get_conversation_tree(1, test_user_id)

        # Assert
        assert isinstance(result, MessageTreeNode)
        assert result.id == 1
        assert len(result.children) == 1
        assert result.children[0].id == 2

    @pytest.mark.asyncio
    async def test_get_conversation_tree_empty(self, service, test_user_id):
        """Test getting tree for conversation with no messages."""
        # Arrange
        service.message_repo.get_conversation_tree = AsyncMock(return_value=[])

        # Act & Assert
        with pytest.raises(ValueError, match="Conversation not found or no messages"):
            await service.get_conversation_tree(1, test_user_id)

    # ========================================================================
    # MESSAGE PATH TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_message_path_success(self, service, test_user_id):
        """Test getting message path successfully."""
        # Arrange
        mock_path = [
            {
                "id": 1,
                "conversation_id": 1,
                "role": "user",
                "content": "Root",
                "content_cleaned": "Root",
                "answers": None,
                "parent_id": None,
                "is_deleted": False,
                "metadata": {},
                "child_count": 1,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
            {
                "id": 2,
                "conversation_id": 1,
                "role": "assistant",
                "content": "Child",
                "content_cleaned": "Child",
                "answers": None,
                "parent_id": 1,
                "is_deleted": False,
                "metadata": {},
                "child_count": 0,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        ]

        service.message_repo.get_branch_path = AsyncMock(return_value=mock_path)

        # Act
        result = await service.get_message_path(2, test_user_id)

        # Assert
        assert result is not None
        assert len(result.path) == 2
        assert result.total_length == 2
        assert 1 in result.branch_points  # Message 1 has child_count > 0
        service.message_repo.get_branch_path.assert_called_once_with(2, test_user_id)

    @pytest.mark.asyncio
    async def test_get_message_path_not_found(self, service, test_user_id):
        """Test getting path for non-existent message."""
        # Arrange
        service.message_repo.get_branch_path = AsyncMock(return_value=[])

        # Act
        result = await service.get_message_path(999, test_user_id)

        # Assert
        assert result.total_length == 0
        assert len(result.path) == 0

    # ========================================================================
    # MESSAGE CHILDREN TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_message_children_success(self, service, test_user_id):
        """Test getting message children successfully."""
        # Arrange
        mock_children = [
            {
                "id": 2,
                "conversation_id": 1,
                "role": "assistant",
                "content": "Child 1",
                "parent_id": 1,
                "is_deleted": False,
                "metadata": {},
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
            {
                "id": 3,
                "conversation_id": 1,
                "role": "assistant",
                "content": "Child 2",
                "parent_id": 1,
                "is_deleted": False,
                "metadata": {},
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        ]

        service.message_repo.get_message_children = AsyncMock(
            return_value=mock_children
        )

        # Act
        result = await service.get_message_children(1, test_user_id)

        # Assert
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(m, MessageDetail) for m in result)

    @pytest.mark.asyncio
    async def test_get_message_children_no_children(self, service, test_user_id):
        """Test getting children for message with no children."""
        # Arrange
        service.message_repo.get_message_children = AsyncMock(return_value=[])

        # Act
        result = await service.get_message_children(1, test_user_id)

        # Assert
        assert isinstance(result, list)
        assert len(result) == 0

    # ========================================================================
    # EDGE CASE TESTS
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.edge_case
    async def test_add_message_with_special_characters(
        self, service, test_user_id, mock_message_data
    ):
        """Test adding message with special characters."""
        # Arrange
        special_content = "Test 中文 émojis 🎉 <script>alert('xss')</script>"
        service.message_repo.verify_conversation_ownership = AsyncMock(
            return_value=True
        )
        service.message_repo.create_message = AsyncMock(return_value=1)
        service.message_repo.update_conversation_timestamp = AsyncMock()
        service.message_repo.get_message_by_user = AsyncMock(
            return_value=mock_message_data
        )

        # Act
        result = await service.add_message(
            conversation_id=1,
            user_id=test_user_id,
            content=special_content,
            role="user",
        )

        # Assert
        assert isinstance(result, MessageDetail)

    @pytest.mark.asyncio
    @pytest.mark.edge_case
    async def test_add_message_max_length(
        self, service, test_user_id, mock_message_data
    ):
        """Test adding message at maximum allowed length."""
        # Arrange
        max_content = "x" * 5000
        service.message_repo.verify_conversation_ownership = AsyncMock(
            return_value=True
        )
        service.message_repo.create_message = AsyncMock(return_value=1)
        service.message_repo.update_conversation_timestamp = AsyncMock()
        service.message_repo.get_message_by_user = AsyncMock(
            return_value=mock_message_data
        )

        # Act
        result = await service.add_message(
            conversation_id=1,
            user_id=test_user_id,
            content=max_content,
            role="user",
        )

        # Assert
        assert isinstance(result, MessageDetail)

    @pytest.mark.asyncio
    async def test_service_handles_repository_exceptions(self, service, test_user_id):
        """Test that service properly handles repository exceptions."""
        # Arrange
        service.message_repo.get_message_by_user = AsyncMock(
            side_effect=Exception("Database error")
        )

        # Act & Assert
        with pytest.raises(Exception, match="Database error"):
            await service.get_message(1, test_user_id)
