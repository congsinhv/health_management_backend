"""
Tests for the branching conversation service.
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
from app.services.branching import BranchingService
from app.schemas.message import MessageDetail


@pytest.mark.unit
@pytest.mark.service
class TestBranchingService:
    """Tests for BranchingService."""

    @pytest.fixture
    def service(self, mock_db_pool, mock_message_repo):
        """Create branching service with mocked dependencies."""
        service = BranchingService(mock_db_pool)
        service.message_repo = mock_message_repo
        return service

    @pytest.mark.asyncio
    async def test_create_branch_point_success(
        self, service, mock_message_repo, test_user_id
    ):
        """Test creating a branch point successfully."""
        # Arrange
        parent_message_id = 1
        branch_name = "Test Branch"

        parent_message = {
            "id": parent_message_id,
            "conversation_id": 1,
            "role": "user",
            "content": "Parent message content",
            "created_at": datetime.now(timezone.utc),
        }

        existing_children = [
            {"id": 2, "role": "assistant", "content": "Child 1"},
            {"id": 3, "role": "assistant", "content": "Child 2"},
        ]

        mock_message_repo.get_message_by_user = AsyncMock(return_value=parent_message)
        mock_message_repo.get_message_children = AsyncMock(
            return_value=existing_children
        )

        # Act
        result = await service.create_branch_point(
            parent_message_id, test_user_id, branch_name
        )

        # Assert
        assert result["branch_point_id"] == parent_message_id
        assert result["branch_name"] == branch_name
        assert result["branch_order"] == 2  # 2 existing children
        assert result["parent_conversation_id"] == 1
        assert "created_at" in result

        mock_message_repo.get_message_by_user.assert_called_once_with(
            parent_message_id, test_user_id
        )
        mock_message_repo.get_message_children.assert_called_once_with(
            parent_message_id, test_user_id
        )

    @pytest.mark.asyncio
    async def test_create_branch_point_auto_generates_name(
        self, service, mock_message_repo, test_user_id
    ):
        """Test creating a branch point with auto-generated name."""
        # Arrange
        parent_message_id = 1

        parent_message = {
            "id": parent_message_id,
            "conversation_id": 1,
            "role": "user",
            "content": "Parent message content",
            "created_at": datetime.now(timezone.utc),
        }

        mock_message_repo.get_message_by_user = AsyncMock(return_value=parent_message)
        mock_message_repo.get_message_children = AsyncMock(return_value=[])

        # Act
        result = await service.create_branch_point(parent_message_id, test_user_id)

        # Assert
        assert result["branch_name"] == "Branch from user message"
        assert result["branch_order"] == 0

    @pytest.mark.asyncio
    async def test_create_branch_point_parent_not_found(
        self, service, mock_message_repo, test_user_id
    ):
        """Test creating a branch point when parent message doesn't exist."""
        # Arrange
        parent_message_id = 999
        mock_message_repo.get_message_by_user = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="Parent message not found"):
            await service.create_branch_point(parent_message_id, test_user_id)

    @pytest.mark.asyncio
    async def test_get_conversation_branches_success(
        self, service, mock_message_repo, test_user_id
    ):
        """Test getting all branches in a conversation."""
        # Arrange
        conversation_id = 1

        # Mock conversation tree with branch points
        tree_messages = [
            {
                "id": 1,
                "role": "user",
                "content": "Root message",
                "parent_message_id": None,
                "created_at": datetime.now(timezone.utc),
            },
            {
                "id": 2,
                "role": "assistant",
                "content": "Branch 1",
                "parent_message_id": 1,
                "created_at": datetime.now(timezone.utc),
            },
            {
                "id": 3,
                "role": "assistant",
                "content": "Branch 2",
                "parent_message_id": 1,
                "created_at": datetime.now(timezone.utc),
            },
            {
                "id": 4,
                "role": "user",
                "content": "Child of branch 1",
                "parent_message_id": 2,
                "created_at": datetime.now(timezone.utc),
            },
        ]

        mock_message_repo.get_conversation_tree = AsyncMock(return_value=tree_messages)

        # Act
        result = await service.get_conversation_branches(conversation_id, test_user_id)

        # Assert
        assert len(result) == 1
        branch_point = result[0]
        assert branch_point["branch_point_id"] == 1
        assert branch_point["branch_point_role"] == "user"
        assert branch_point["num_branches"] == 2
        assert len(branch_point["branches"]) == 2
        assert branch_point["branches"][0]["branch_order"] == 0
        assert branch_point["branches"][1]["branch_order"] == 1

    @pytest.mark.asyncio
    async def test_get_conversation_branches_no_branches(
        self, service, mock_message_repo, test_user_id
    ):
        """Test getting branches when there are no branch points."""
        # Arrange
        conversation_id = 1

        tree_messages = [
            {
                "id": 1,
                "role": "user",
                "content": "Root",
                "parent_message_id": None,
                "created_at": datetime.now(timezone.utc),
            },
            {
                "id": 2,
                "role": "assistant",
                "content": "Child",
                "parent_message_id": 1,
                "created_at": datetime.now(timezone.utc),
            },
        ]

        mock_message_repo.get_conversation_tree = AsyncMock(return_value=tree_messages)

        # Act
        result = await service.get_conversation_branches(conversation_id, test_user_id)

        # Assert
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_branch_path_success(
        self, service, mock_message_repo, test_user_id
    ):
        """Test getting the complete path from root to a message."""
        # Arrange
        message_id = 3

        path_messages = [
            {
                "id": 1,
                "conversation_id": 1,
                "role": "user",
                "content": "Root message",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "metadata": {},
            },
            {
                "id": 2,
                "conversation_id": 1,
                "role": "assistant",
                "content": "Response",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "metadata": {},
            },
            {
                "id": 3,
                "conversation_id": 1,
                "role": "user",
                "content": "Follow-up",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "metadata": {},
            },
        ]

        mock_message_repo.get_branch_path = AsyncMock(return_value=path_messages)

        # Act
        result = await service.get_branch_path(message_id, test_user_id)

        # Assert
        assert len(result) == 3
        assert all(isinstance(msg, MessageDetail) for msg in result)
        assert result[0].id == 1
        assert result[1].id == 2
        assert result[2].id == 3

    @pytest.mark.asyncio
    async def test_merge_branches_replace_strategy_success(
        self, service, mock_message_repo, test_user_id
    ):
        """Test merging branches with replace strategy."""
        # Arrange
        source_id = 1
        target_id = 2

        source_msg = {
            "id": source_id,
            "conversation_id": 1,
            "role": "user",
            "content": "Source content",
            "content_cleaned": "Source cleaned",
            "answers": {"answer": "value"},
            "metadata": {"key": "value"},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        target_msg = {
            "id": target_id,
            "conversation_id": 1,
            "role": "user",
            "content": "Target content",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        merged_msg = {
            "id": target_id,
            "conversation_id": 1,
            "role": "user",
            "content": "Source content",
            "content_cleaned": "Source cleaned",
            "answers": {"answer": "value"},
            "metadata": {"key": "value"},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        mock_message_repo.get_message_by_user = AsyncMock(
            side_effect=[source_msg, target_msg, merged_msg]
        )
        mock_message_repo.update_message = AsyncMock(return_value=True)

        # Act
        result = await service.merge_branches(
            source_id, target_id, test_user_id, "replace"
        )

        # Assert
        assert isinstance(result, MessageDetail)
        assert result.id == target_id
        assert result.content == "Source content"
        assert result.content_cleaned == "Source cleaned"
        assert result.answers == {"answer": "value"}

    @pytest.mark.asyncio
    async def test_merge_branches_different_conversations(
        self, service, mock_message_repo, test_user_id
    ):
        """Test merging branches from different conversations."""
        # Arrange
        source_id = 1
        target_id = 2

        source_msg = {
            "id": source_id,
            "conversation_id": 1,
            "role": "user",
            "content": "Source",
            "created_at": datetime.now(timezone.utc),
        }

        target_msg = {
            "id": target_id,
            "conversation_id": 2,  # Different conversation
            "role": "user",
            "content": "Target",
            "created_at": datetime.now(timezone.utc),
        }

        mock_message_repo.get_message_by_user = AsyncMock(
            side_effect=[source_msg, target_msg]
        )

        # Act & Assert
        with pytest.raises(
            ValueError, match="Messages must be in the same conversation"
        ):
            await service.merge_branches(source_id, target_id, test_user_id)

    @pytest.mark.asyncio
    async def test_merge_branches_message_not_found(
        self, service, mock_message_repo, test_user_id
    ):
        """Test merging when one message is not found."""
        # Arrange
        source_id = 1
        target_id = 2

        mock_message_repo.get_message_by_user = AsyncMock(side_effect=[None, None])

        # Act & Assert
        with pytest.raises(ValueError, match="One or both messages not found"):
            await service.merge_branches(source_id, target_id, test_user_id)

    @pytest.mark.asyncio
    async def test_merge_branches_unsupported_strategy(
        self, service, mock_message_repo, test_user_id
    ):
        """Test merging with unsupported merge strategy."""
        # Arrange
        source_id = 1
        target_id = 2

        source_msg = {
            "id": source_id,
            "conversation_id": 1,
            "role": "user",
            "content": "Source",
            "created_at": datetime.now(timezone.utc),
        }

        target_msg = {
            "id": target_id,
            "conversation_id": 1,
            "role": "user",
            "content": "Target",
            "created_at": datetime.now(timezone.utc),
        }

        mock_message_repo.get_message_by_user = AsyncMock(
            side_effect=[source_msg, target_msg]
        )

        # Act & Assert
        with pytest.raises(
            ValueError, match="Merge strategy 'unsupported' not implemented"
        ):
            await service.merge_branches(
                source_id, target_id, test_user_id, "unsupported"
            )

    @pytest.mark.asyncio
    async def test_delete_branch_cascade_success(
        self, service, mock_message_repo, test_user_id
    ):
        """Test deleting a branch with cascade."""
        # Arrange
        message_id = 1

        # Mock the message to get conversation_id
        message = {
            "id": message_id,
            "conversation_id": 1,
            "role": "user",
            "content": "Message to delete",
        }
        mock_message_repo.get_message_by_user = AsyncMock(return_value=message)

        # Mock descendants
        descendants = [{"id": 2, "content": "Child 1"}, {"id": 3, "content": "Child 2"}]

        service._get_all_descendants = AsyncMock(return_value=descendants)
        mock_message_repo.delete_message = AsyncMock(return_value=True)

        # Act
        result = await service.delete_branch(message_id, test_user_id, cascade=True)

        # Assert
        assert result is True
        # Should delete children first (in reverse order), then the parent
        assert mock_message_repo.delete_message.call_count == 3
        # Verify order of deletion
        calls = mock_message_repo.delete_message.call_args_list
        assert calls[0][0] == (3, test_user_id)  # Child 2
        assert calls[1][0] == (2, test_user_id)  # Child 1
        assert calls[2][0] == (1, test_user_id)  # Parent

    @pytest.mark.asyncio
    async def test_delete_branch_no_cascade(
        self, service, mock_message_repo, test_user_id
    ):
        """Test deleting a branch without cascade."""
        # Arrange
        message_id = 1

        # Mock the message to get conversation_id
        message = {
            "id": message_id,
            "conversation_id": 1,
            "role": "user",
            "content": "Message to delete",
        }
        mock_message_repo.get_message_by_user = AsyncMock(return_value=message)
        mock_message_repo.delete_message = AsyncMock(return_value=True)

        # Act
        result = await service.delete_branch(message_id, test_user_id, cascade=False)

        # Assert
        assert result is True
        mock_message_repo.delete_message.assert_called_once_with(
            message_id, test_user_id
        )

    @pytest.mark.asyncio
    async def test_get_branch_statistics_success(
        self, service, mock_message_repo, test_user_id
    ):
        """Test getting branch statistics for a conversation."""
        # Arrange
        conversation_id = 1

        messages = [
            {"id": 1, "parent_message_id": None},  # Root
            {"id": 2, "parent_message_id": 1},  # Child 1
            {"id": 3, "parent_message_id": 1},  # Child 2 (branch point)
            {"id": 4, "parent_message_id": 2},  # Grandchild 1
            {"id": 5, "parent_message_id": 3},  # Grandchild 2
            {"id": 6, "parent_message_id": 3},  # Grandchild 3
        ]

        mock_message_repo.get_conversation_tree = AsyncMock(return_value=messages)

        # Act
        result = await service.get_branch_statistics(conversation_id, test_user_id)

        # Assert
        assert result["total_messages"] == 6
        assert result["max_depth"] == 2
        assert result["branch_points"] == 1  # Message 1 has 2 children
        assert result["max_branches_from_point"] == 2
        assert (
            result["branch_distribution"]["no_branches"] == 1
        )  # Message 2 has 1 child
        assert (
            result["branch_distribution"]["two_branches"] == 1
        )  # Message 1 has 2 children

    @pytest.mark.asyncio
    async def test_get_branch_statistics_empty_conversation(
        self, service, mock_message_repo, test_user_id
    ):
        """Test getting statistics for empty conversation."""
        # Arrange
        conversation_id = 1

        mock_message_repo.get_conversation_tree = AsyncMock(return_value=[])

        # Act
        result = await service.get_branch_statistics(conversation_id, test_user_id)

        # Assert
        assert result["total_messages"] == 0
        assert result["max_depth"] == 0
        assert result["branch_points"] == 0
        assert result["max_branches_from_point"] == 0

    @pytest.mark.asyncio
    async def test_visualize_tree_success(
        self, service, mock_message_repo, test_user_id
    ):
        """Test visualizing conversation tree."""
        # Arrange
        conversation_id = 1
        max_depth = 3

        messages = [
            {
                "id": 1,
                "role": "user",
                "content": "Root message content here",
                "parent_message_id": None,
                "created_at": datetime.now(timezone.utc),
            },
            {
                "id": 2,
                "role": "assistant",
                "content": "Branch 1 content here",
                "parent_message_id": 1,
                "created_at": datetime.now(timezone.utc),
            },
            {
                "id": 3,
                "role": "assistant",
                "content": "Branch 2 content here",
                "parent_message_id": 1,
                "created_at": datetime.now(timezone.utc),
            },
        ]

        mock_message_repo.get_conversation_tree = AsyncMock(return_value=messages)

        # Act
        result = await service.visualize_tree(conversation_id, test_user_id, max_depth)

        # Assert
        assert result["conversation_id"] == conversation_id
        assert result["total_messages"] == 3
        assert result["max_depth"] == max_depth
        assert len(result["tree"]) == 1  # One root

        root = result["tree"][0]
        assert root["id"] == 1
        assert root["depth"] == 0
        assert len(root["children"]) == 2

        # Check children
        child1 = root["children"][0]
        child2 = root["children"][1]
        assert child1["id"] == 2
        assert child2["id"] == 3
        assert child1["depth"] == 1
        assert child2["depth"] == 1

    @pytest.mark.asyncio
    async def test_visualize_tree_max_depth_limit(
        self, service, mock_message_repo, test_user_id
    ):
        """Test tree visualization respects max depth limit."""
        # Arrange
        conversation_id = 1
        max_depth = 1

        messages = [
            {
                "id": 1,
                "role": "user",
                "content": "Root",
                "parent_message_id": None,
                "created_at": datetime.now(timezone.utc),
            },
            {
                "id": 2,
                "role": "assistant",
                "content": "Child",
                "parent_message_id": 1,
                "created_at": datetime.now(timezone.utc),
            },
            {
                "id": 3,
                "role": "user",
                "content": "Grandchild",
                "parent_message_id": 2,
                "created_at": datetime.now(timezone.utc),
            },
        ]

        mock_message_repo.get_conversation_tree = AsyncMock(return_value=messages)

        # Act
        result = await service.visualize_tree(conversation_id, test_user_id, max_depth)

        # Assert
        root = result["tree"][0]
        assert root["depth"] == 0
        assert len(root["children"]) == 1
        # Grandchild should not be included due to depth limit
        assert len(root["children"][0]["children"]) == 0

    @pytest.mark.asyncio
    async def test_get_all_descendants_success(self, service, test_user_id):
        """Test getting all descendants of a message."""
        # Arrange
        message_id = 1

        descendants = [
            {"id": 2, "content": "Child 1"},
            {"id": 3, "content": "Grandchild 1"},
            {"id": 4, "content": "Child 2"},
        ]

        service.message_repo.fetch_many = AsyncMock(return_value=descendants)

        # Act
        result = await service._get_all_descendants(message_id, test_user_id)

        # Assert
        assert len(result) == 3
        assert result[0]["id"] == 2
        assert result[1]["id"] == 3
        assert result[2]["id"] == 4

    def test_get_ancestors_success(self, service):
        """Test getting ancestors of a message."""
        # Arrange
        message_id = 4

        messages = [
            {"id": 1, "parent_message_id": None},
            {"id": 2, "parent_message_id": 1},
            {"id": 3, "parent_message_id": 2},
            {"id": 4, "parent_message_id": 3},
        ]

        # Act
        result = service._get_ancestors(message_id, messages)

        # Assert
        assert result == [3, 2, 1]

    def test_get_ancestors_root_message(self, service):
        """Test getting ancestors of a root message."""
        # Arrange
        message_id = 1

        messages = [
            {"id": 1, "parent_message_id": None},
            {"id": 2, "parent_message_id": 1},
        ]

        # Act
        result = service._get_ancestors(message_id, messages)

        # Assert
        assert result == []

    def test_get_ancestors_message_not_found(self, service):
        """Test getting ancestors when message is not in list."""
        # Arrange
        message_id = 999

        messages = [
            {"id": 1, "parent_message_id": None},
            {"id": 2, "parent_message_id": 1},
        ]

        # Act
        result = service._get_ancestors(message_id, messages)

        # Assert
        assert result == []
