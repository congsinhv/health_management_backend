"""
Tests for the message version service.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from app.services.message_version import MessageVersionService
from app.schemas.message import (
    MessageVersionDetail,
    MessageVersionListResponse,
    MessageVersionCompareResponse,
    MessageVersionRollbackResponse,
)


@pytest.mark.unit
@pytest.mark.service
class TestMessageVersionService:
    """Tests for MessageVersionService."""

    @pytest.fixture
    def service(self, mock_db_pool, mock_message_repo, mock_version_repo):
        """Create version service with mocked dependencies."""
        service = MessageVersionService(mock_db_pool, mock_message_repo)
        service.version_repo = mock_version_repo
        return service

    @pytest.mark.asyncio
    async def test_create_version_success(
        self, service, mock_message_repo, mock_version_repo, test_user_id
    ):
        """Test creating a new version successfully."""
        # Arrange
        message_id = 1
        content = "New version content"
        content_cleaned = "Cleaned content"
        answers = {"answer": ["response"]}
        metadata = {"key": "value"}

        message = {
            "id": message_id,
            "content": "Original content",
            "created_at": datetime.now(timezone.utc),
        }

        mock_message_repo.get_message_by_user = AsyncMock(return_value=message)
        mock_version_repo.get_latest_version_number = AsyncMock(return_value=2)
        mock_version_repo.create_version = AsyncMock(return_value=123)

        # Act
        result = await service.create_version(
            message_id, test_user_id, content, content_cleaned, answers, metadata
        )

        # Assert
        assert result == 123
        mock_message_repo.get_message_by_user.assert_called_once_with(
            message_id, test_user_id
        )
        mock_version_repo.get_latest_version_number.assert_called_once_with(
            message_id, test_user_id
        )
        mock_version_repo.create_version.assert_called_once_with(
            message_id=message_id,
            version_number=3,  # latest + 1
            content=content,
            content_cleaned=content_cleaned,
            answers=answers,
            metadata=metadata,
        )

    @pytest.mark.asyncio
    async def test_create_version_message_not_found(
        self, service, mock_message_repo, test_user_id
    ):
        """Test creating a version when message doesn't exist."""
        # Arrange
        message_id = 999
        mock_message_repo.get_message_by_user = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="Message not found"):
            await service.create_version(message_id, test_user_id, "content")

    @pytest.mark.asyncio
    async def test_create_version_triggers_cleanup(
        self, service, mock_message_repo, mock_version_repo, test_user_id
    ):
        """Test creating version triggers cleanup when limit exceeded."""
        # Arrange
        message_id = 1
        content = "New version content"

        message = {
            "id": message_id,
            "content": "Original",
            "created_at": datetime.now(timezone.utc),
        }
        mock_message_repo.get_message_by_user = AsyncMock(return_value=message)
        mock_version_repo.get_latest_version_number = AsyncMock(
            return_value=50
        )  # At limit
        mock_version_repo.create_version = AsyncMock(return_value=123)
        mock_version_repo.cleanup_old_versions = AsyncMock(return_value=10)

        # Mock settings to have lower limit for testing
        with patch("app.config.settings.message_version_limit", 50):
            # Act
            result = await service.create_version(message_id, test_user_id, content)

        # Assert
        assert result == 123
        mock_version_repo.cleanup_old_versions.assert_called_once_with(
            test_user_id, message_id, 40
        )

    @pytest.mark.asyncio
    async def test_get_versions_success(self, service, mock_version_repo, test_user_id):
        """Test getting all versions of a message."""
        # Arrange
        message_id = 1

        version_records = [
            {
                "id": 1,
                "message_id": message_id,
                "version_number": 1,
                "content": "Version 1",
                "content_cleaned": "Cleaned 1",
                "answers": {"answer": ["response1"]},
                "metadata": {"key": "value1"},
                "created_at": datetime.now(timezone.utc),
            },
            {
                "id": 2,
                "message_id": message_id,
                "version_number": 2,
                "content": "Version 2",
                "content_cleaned": "Cleaned 2",
                "answers": {"answer": ["response2"]},
                "metadata": {"key": "value2"},
                "created_at": datetime.now(timezone.utc),
            },
        ]

        mock_version_repo.get_message_versions = AsyncMock(return_value=version_records)
        mock_version_repo.get_latest_version_number = AsyncMock(return_value=2)

        # Act
        result = await service.get_versions(message_id, test_user_id)

        # Assert
        assert isinstance(result, MessageVersionListResponse)
        assert len(result.versions) == 2
        assert result.total == 2
        assert result.current_version == 2
        assert all(isinstance(v, MessageVersionDetail) for v in result.versions)
        assert result.versions[0].version_number == 1
        assert result.versions[1].version_number == 2

    @pytest.mark.asyncio
    async def test_get_version_success(self, service, mock_version_repo, test_user_id):
        """Test getting a specific version of a message."""
        # Arrange
        message_id = 1
        version_number = 2

        version_record = {
            "id": 2,
            "message_id": message_id,
            "version_number": version_number,
            "content": "Version 2 content",
            "content_cleaned": "Cleaned content",
            "answers": {"answer": ["response"]},
            "metadata": {"key": "value"},
            "created_at": datetime.now(timezone.utc),
        }

        mock_version_repo.get_version = AsyncMock(return_value=version_record)

        # Act
        result = await service.get_version(message_id, version_number, test_user_id)

        # Assert
        assert isinstance(result, MessageVersionDetail)
        assert result.id == 2
        assert result.message_id == message_id
        assert result.version_number == version_number
        assert result.content == "Version 2 content"

    @pytest.mark.asyncio
    async def test_get_version_not_found(
        self, service, mock_version_repo, test_user_id
    ):
        """Test getting a version that doesn't exist."""
        # Arrange
        message_id = 1
        version_number = 999

        mock_version_repo.get_version = AsyncMock(return_value=None)

        # Act
        result = await service.get_version(message_id, version_number, test_user_id)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_rollback_to_version_with_backup(
        self, service, mock_message_repo, mock_version_repo, test_user_id
    ):
        """Test rolling back to a version with backup creation."""
        # Arrange
        message_id = 1
        version_number = 2

        current_message = {
            "id": message_id,
            "content": "Current content",
            "content_cleaned": "Current cleaned",
            "answers": {"current": ["answer"]},
            "metadata": {"current": "metadata"},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "conversation_id": 1,
            "role": "user",
        }

        target_version = {
            "id": 2,
            "message_id": message_id,
            "version_number": version_number,
            "content": "Target content",
            "created_at": datetime.now(timezone.utc),
        }

        updated_message = {
            "id": message_id,
            "content": "Target content",
            "content_cleaned": "Target cleaned",
            "answers": {"target": ["answer"]},
            "metadata": {"target": "metadata"},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "conversation_id": 1,
            "role": "user",
        }

        mock_message_repo.get_message_by_user = AsyncMock(
            side_effect=[current_message, updated_message]
        )
        mock_version_repo.get_version = AsyncMock(return_value=target_version)
        mock_version_repo.get_latest_version_number = AsyncMock(return_value=3)
        mock_version_repo.create_version = AsyncMock(return_value=456)
        mock_version_repo.rollback_to_version = AsyncMock(return_value=True)

        # Act
        result = await service.rollback_to_version(
            message_id, version_number, test_user_id, create_backup_version=True
        )

        # Assert
        assert isinstance(result, MessageVersionRollbackResponse)
        assert result.rollback_version == version_number
        assert result.backup_version_created == 456
        assert result.rolled_back_message.content == "Target content"

        # Verify backup was created
        mock_version_repo.create_version.assert_called_once()
        backup_call = mock_version_repo.create_version.call_args[1]
        assert backup_call["message_id"] == message_id
        assert backup_call["version_number"] == 4
        assert backup_call["content"] == "Current content"
        assert backup_call["metadata"]["rollback_backup"] is True

    @pytest.mark.asyncio
    async def test_rollback_to_version_no_backup(
        self, service, mock_message_repo, mock_version_repo, test_user_id
    ):
        """Test rolling back to a version without backup creation."""
        # Arrange
        message_id = 1
        version_number = 2

        current_message = {
            "id": message_id,
            "content": "Current content",
            "created_at": datetime.now(timezone.utc),
            "conversation_id": 1,
            "role": "user",
        }

        target_version = {
            "id": 2,
            "message_id": message_id,
            "version_number": version_number,
            "content": "Target content",
            "created_at": datetime.now(timezone.utc),
        }

        updated_message = {
            "id": message_id,
            "content": "Target content",
            "created_at": datetime.now(timezone.utc),
            "conversation_id": 1,
            "role": "user",
        }

        mock_message_repo.get_message_by_user = AsyncMock(
            side_effect=[current_message, updated_message]
        )
        mock_version_repo.get_version = AsyncMock(return_value=target_version)
        mock_version_repo.rollback_to_version = AsyncMock(return_value=True)

        # Act
        result = await service.rollback_to_version(
            message_id, version_number, test_user_id, create_backup_version=False
        )

        # Assert
        assert isinstance(result, MessageVersionRollbackResponse)
        assert result.rollback_version == version_number
        assert result.backup_version_created is None
        assert result.rolled_back_message.content == "Target content"

        # Verify no backup was created
        mock_version_repo.create_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_rollback_to_version_message_not_found(
        self, service, mock_message_repo, test_user_id
    ):
        """Test rollback when message doesn't exist."""
        # Arrange
        message_id = 999
        version_number = 1

        mock_message_repo.get_message_by_user = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="Message not found"):
            await service.rollback_to_version(message_id, version_number, test_user_id)

    @pytest.mark.asyncio
    async def test_rollback_to_version_not_found(
        self, service, mock_message_repo, mock_version_repo, test_user_id
    ):
        """Test rollback when target version doesn't exist."""
        # Arrange
        message_id = 1
        version_number = 999

        current_message = {
            "id": message_id,
            "content": "Current",
            "created_at": datetime.now(timezone.utc),
        }
        mock_message_repo.get_message_by_user = AsyncMock(return_value=current_message)
        mock_version_repo.get_version = AsyncMock(return_value=None)

        # Act & Assert
        with pytest.raises(ValueError, match="Version not found"):
            await service.rollback_to_version(message_id, version_number, test_user_id)

    @pytest.mark.asyncio
    async def test_compare_versions_success(
        self, service, mock_version_repo, test_user_id
    ):
        """Test comparing two versions successfully."""
        # Arrange
        message_id = 1
        version1 = 1
        version2 = 2

        comparison_data = {
            "content_v1": "Version 1 content\nLine 2",
            "content_v2": "Version 2 content\nModified line 2\nLine 3",
        }

        version1_record = {
            "id": 1,
            "message_id": message_id,
            "version_number": version1,
            "content": "Version 1 content",
            "created_at": datetime.now(timezone.utc),
        }

        version2_record = {
            "id": 2,
            "message_id": message_id,
            "version_number": version2,
            "content": "Version 2 content",
            "created_at": datetime.now(timezone.utc),
        }

        mock_version_repo.compare_versions = AsyncMock(return_value=comparison_data)
        mock_version_repo.get_version = AsyncMock(
            side_effect=[version1_record, version2_record]
        )

        # Act
        result = await service.compare_versions(
            message_id, version1, version2, test_user_id
        )

        # Assert
        assert isinstance(result, MessageVersionCompareResponse)
        assert result.version1.version_number == version1
        assert result.version2.version_number == version2
        assert "diff" in result.differences
        assert "added_lines" in result.differences
        assert "removed_lines" in result.differences
        assert "total_changes" in result.differences
        assert "similarity" in result.differences

    @pytest.mark.asyncio
    async def test_compare_versions_one_not_found(
        self, service, mock_version_repo, test_user_id
    ):
        """Test comparing when one version doesn't exist."""
        # Arrange
        message_id = 1
        version1 = 1
        version2 = 999

        comparison_data = {"content_v1": "Content 1", "content_v2": "Content 2"}

        version1_record = {
            "id": 1,
            "message_id": message_id,
            "version_number": version1,
            "content": "Version 1 content",
            "created_at": datetime.now(timezone.utc),
        }

        mock_version_repo.compare_versions = AsyncMock(return_value=comparison_data)
        mock_version_repo.get_version = AsyncMock(side_effect=[version1_record, None])

        # Act & Assert
        with pytest.raises(ValueError, match="One or both versions not found"):
            await service.compare_versions(message_id, version1, version2, test_user_id)

    @pytest.mark.asyncio
    async def test_cleanup_old_versions_success(
        self, service, mock_version_repo, test_user_id
    ):
        """Test cleaning up old versions successfully."""
        # Arrange
        message_id = 1
        keep_latest = 10
        cleaned_count = 5

        mock_version_repo.cleanup_old_versions = AsyncMock(return_value=cleaned_count)

        # Act
        result = await service.cleanup_old_versions(
            test_user_id, message_id, keep_latest
        )

        # Assert
        assert result == cleaned_count
        mock_version_repo.cleanup_old_versions.assert_called_once_with(
            test_user_id, message_id, keep_latest
        )

    @pytest.mark.asyncio
    async def test_get_version_summary_success(
        self, service, mock_version_repo, test_user_id
    ):
        """Test getting version summary successfully."""
        # Arrange
        message_id = 1

        summary_data = {
            "total_versions": 5,
            "first_version": 1,
            "latest_version": 5,
            "first_created": datetime.now(timezone.utc),
            "latest_created": datetime.now(timezone.utc),
        }

        mock_version_repo.get_version_summary = AsyncMock(return_value=summary_data)

        # Act
        result = await service.get_version_summary(message_id, test_user_id)

        # Assert
        assert result["total_versions"] == 5
        assert result["first_version"] == 1
        assert result["latest_version"] == 5
        assert "first_created" in result
        assert "latest_created" in result

    @pytest.mark.asyncio
    async def test_get_version_summary_not_found(
        self, service, mock_version_repo, test_user_id
    ):
        """Test getting version summary when no versions exist."""
        # Arrange
        message_id = 999

        mock_version_repo.get_version_summary = AsyncMock(return_value=None)

        # Act
        result = await service.get_version_summary(message_id, test_user_id)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_versions_after_success(
        self, service, mock_version_repo, test_user_id
    ):
        """Test deleting versions after a specific version."""
        # Arrange
        message_id = 1
        version_number = 3

        mock_version_repo.delete_versions_after = AsyncMock(return_value=True)

        # Act
        result = await service.delete_versions_after(
            message_id, version_number, test_user_id
        )

        # Assert
        assert result is True
        mock_version_repo.delete_versions_after.assert_called_once_with(
            message_id, version_number, test_user_id
        )

    @pytest.mark.asyncio
    async def test_bulk_cleanup_versions_success(
        self, service, mock_version_repo, test_user_id
    ):
        """Test bulk cleanup of versions for all messages."""
        # Arrange
        keep_latest = 10
        messages_to_clean = [{"message_id": 1}, {"message_id": 2}, {"message_id": 3}]

        mock_version_repo.get_all_message_versions_for_cleanup = AsyncMock(
            return_value=messages_to_clean
        )
        mock_version_repo.cleanup_old_versions = AsyncMock(return_value=5)

        # Act
        result = await service.bulk_cleanup_versions(test_user_id, keep_latest)

        # Assert
        assert result["total_messages_processed"] == 3
        assert result["total_versions_cleaned"] == 15  # 5 * 3 messages
        assert len(result["errors"]) == 0
        assert mock_version_repo.cleanup_old_versions.call_count == 3

    @pytest.mark.asyncio
    async def test_bulk_cleanup_versions_with_errors(
        self, service, mock_version_repo, test_user_id
    ):
        """Test bulk cleanup with some errors."""
        # Arrange
        keep_latest = 10
        messages_to_clean = [{"message_id": 1}, {"message_id": 2}]

        mock_version_repo.get_all_message_versions_for_cleanup = AsyncMock(
            return_value=messages_to_clean
        )
        mock_version_repo.cleanup_old_versions = AsyncMock(
            side_effect=[5, Exception("DB Error")]
        )

        # Act
        result = await service.bulk_cleanup_versions(test_user_id, keep_latest)

        # Assert
        assert result["total_messages_processed"] == 2
        assert result["total_versions_cleaned"] == 5
        assert len(result["errors"]) == 1
        assert result["errors"][0]["message_id"] == 2
        assert "DB Error" in result["errors"][0]["error"]

    def test_convert_to_version_detail(self, service):
        """Test converting database record to MessageVersionDetail."""
        # Arrange
        record = {
            "id": 1,
            "message_id": 10,
            "version_number": 3,
            "content": "Test content",
            "content_cleaned": "Cleaned content",
            "answers": {"answer": ["response"]},
            "metadata": {"key": "value"},
            "created_at": datetime.now(timezone.utc),
        }

        # Act
        result = service._convert_to_version_detail(record)

        # Assert
        assert isinstance(result, MessageVersionDetail)
        assert result.id == 1
        assert result.message_id == 10
        assert result.version_number == 3
        assert result.content == "Test content"
        assert result.content_cleaned == "Cleaned content"
        assert result.answers == {"answer": ["response"]}
        assert result.metadata == {"key": "value"}

    def test_convert_to_message_detail(self, service):
        """Test converting database record to MessageDetail."""
        # Arrange
        record = {
            "id": 1,
            "conversation_id": 10,
            "role": "user",
            "content": "Test content",
            "content_cleaned": "Cleaned content",
            "answers": {"answer": ["response"]},
            "parent_message_id": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "deleted_at": None,
            "metadata": {"key": "value"},
        }

        # Act
        result = service._convert_to_message_detail(record)

        # Assert
        from app.schemas.message import MessageDetail

        assert isinstance(result, MessageDetail)
        assert result.id == 1
        assert result.conversation_id == 10
        assert result.role == "user"
        assert result.content == "Test content"

    def test_calculate_differences_success(self, service):
        """Test calculating differences between two content strings."""
        # Arrange
        content1 = "Line 1\nLine 2\nLine 3"
        content2 = "Line 1\nModified Line 2\nLine 3\nLine 4"

        # Act
        result = service._calculate_differences(content1, content2)

        # Assert
        assert "diff" in result
        assert "added_lines" in result
        assert "removed_lines" in result
        assert "modified_lines" in result
        assert "total_changes" in result
        assert "similarity" in result
        assert result["added_lines"] >= 1  # Line 4 was added
        assert result["total_changes"] > 0

    def test_calculate_differences_error_handling(self, service):
        """Test error handling in difference calculation."""
        # Arrange
        content1 = "Content 1"
        content2 = None  # This will cause an error

        # Act
        result = service._calculate_differences(content1, content2)

        # Assert
        assert result["diff"] == ""
        assert result["added_lines"] == 0
        assert result["removed_lines"] == 0
        assert result["modified_lines"] == 0
        assert result["total_changes"] == 0
        assert result["similarity"] == 0.0
        assert "error" in result

    def test_calculate_similarity_success(self, service):
        """Test calculating similarity between two content strings."""
        # Arrange
        content1 = "Hello world"
        content2 = "Hello world"

        # Act
        result = service._calculate_similarity(content1, content2)

        # Assert
        assert result == 1.0  # Perfect match

    def test_calculate_similarity_different(self, service):
        """Test calculating similarity between different content strings."""
        # Arrange
        content1 = "Hello world"
        content2 = "Goodbye world"

        # Act
        result = service._calculate_similarity(content1, content2)

        # Assert
        assert 0.0 < result < 1.0  # Partial match

    def test_calculate_similarity_error_handling(self, service):
        """Test error handling in similarity calculation."""
        # Arrange
        content1 = "Content 1"
        content2 = None

        # Act
        result = service._calculate_similarity(content1, content2)

        # Assert
        assert result == 0.0
