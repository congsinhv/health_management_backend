"""
Tests for MessageVersionRepository.

Tests message version repository operations including version creation,
retrieval, rollback, comparison, and cleanup.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from typing import Dict, Any, List

from app.db.message_version import MessageVersionRepository


@pytest.mark.repository
@pytest.mark.unit
class TestMessageVersionRepository:
    """Test cases for MessageVersionRepository."""

    @pytest.fixture
    def repo(self, mock_db_pool):
        """Create repository instance with mocked pool."""
        return MessageVersionRepository(mock_db_pool)

    @pytest.fixture
    def sample_version_record(self):
        """Sample version record for testing."""
        return {
            "id": 1,
            "message_id": 100,
            "version_number": 1,
            "content": "Version 1 content",
            "content_cleaned": "Version 1 content cleaned",
            "answers": {"key": ["answer1"]},
            "metadata": {"source": "test"},
            "created_at": datetime.now(timezone.utc),
        }

    # ========================================================================
    # CREATE VERSION TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_create_version_success(self, repo, mock_db_pool):
        """Test creating a version successfully."""
        # Arrange
        message_id = 100
        version_number = 1
        content = "Test version content"
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"id": 1})

        # Act
        result = await repo.create_version(
            message_id=message_id, version_number=version_number, content=content
        )

        # Assert
        assert result == 1
        mock_db_pool._mock_connection.fetchrow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_version_with_all_fields(self, repo, mock_db_pool):
        """Test creating version with all optional fields."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"id": 2})

        # Act
        result = await repo.create_version(
            message_id=100,
            version_number=2,
            content="Full version",
            content_cleaned="Full version cleaned",
            answers={"q1": ["a1", "a2"]},
            metadata={"key": "value"},
        )

        # Assert
        assert result == 2

    @pytest.mark.asyncio
    async def test_create_version_returns_none_on_failure(self, repo, mock_db_pool):
        """Test create version returns None when insert fails."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.create_version(
            message_id=100, version_number=1, content="Test"
        )

        # Assert
        assert result is None

    # ========================================================================
    # GET VERSIONS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_message_versions_success(self, repo, mock_db_pool):
        """Test getting all versions of a message."""
        # Arrange
        message_id = 100
        user_id = 123
        mock_versions = [
            {"id": 3, "version_number": 3, "content": "Version 3"},
            {"id": 2, "version_number": 2, "content": "Version 2"},
            {"id": 1, "version_number": 1, "content": "Version 1"},
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_versions)

        # Act
        result = await repo.get_message_versions(message_id, user_id)

        # Assert
        assert len(result) == 3
        assert result[0]["version_number"] == 3  # Ordered DESC

    @pytest.mark.asyncio
    async def test_get_message_versions_empty(self, repo, mock_db_pool):
        """Test getting versions when message has none."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_message_versions(100, 123)

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_get_version_success(self, repo, mock_db_pool, sample_version_record):
        """Test getting a specific version."""
        # Arrange
        message_id = 100
        version_number = 1
        user_id = 123
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            return_value=sample_version_record
        )

        # Act
        result = await repo.get_version(message_id, version_number, user_id)

        # Assert
        assert result is not None
        assert result["version_number"] == 1
        assert result["content"] == "Version 1 content"

    @pytest.mark.asyncio
    async def test_get_version_not_found(self, repo, mock_db_pool):
        """Test getting non-existent version returns None."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.get_version(100, 9999, 123)

        # Assert
        assert result is None

    # ========================================================================
    # LATEST VERSION NUMBER TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_latest_version_number_success(self, repo, mock_db_pool):
        """Test getting latest version number."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            return_value={"latest_version": 5}
        )

        # Act
        result = await repo.get_latest_version_number(100, 123)

        # Assert
        assert result == 5

    @pytest.mark.asyncio
    async def test_get_latest_version_number_no_versions(self, repo, mock_db_pool):
        """Test getting latest version when no versions exist."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            return_value={"latest_version": 0}
        )

        # Act
        result = await repo.get_latest_version_number(100, 123)

        # Assert
        assert result == 0

    @pytest.mark.asyncio
    async def test_get_latest_version_number_returns_zero_on_none(
        self, repo, mock_db_pool
    ):
        """Test getting latest version returns 0 when query returns None."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.get_latest_version_number(100, 123)

        # Assert
        assert result == 0

    # ========================================================================
    # ROLLBACK VERSION TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_rollback_to_version_success(self, repo, mock_db_pool):
        """Test rolling back to a specific version."""
        # Arrange
        message_id = 100
        version_number = 3
        user_id = 123

        # Mock sequence: get version, get latest version number, create version, update message
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            side_effect=[
                {  # Version to rollback to
                    "content": "Old content",
                    "content_cleaned": "Old cleaned",
                    "answers": {"key": ["old"]},
                    "metadata": {"old": "meta"},
                },
                {"latest_version": 5},  # Latest version number
                {"id": 6},  # New version created
            ]
        )
        mock_db_pool._mock_connection.execute = AsyncMock(
            return_value="UPDATE 1"  # Message update
        )

        # Act
        result = await repo.rollback_to_version(message_id, version_number, user_id)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_rollback_to_version_not_found(self, repo, mock_db_pool):
        """Test rollback when version doesn't exist."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            return_value=None  # Version not found
        )

        # Act
        result = await repo.rollback_to_version(100, 999, 123)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_rollback_to_version_update_fails(self, repo, mock_db_pool):
        """Test rollback when message update fails."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            side_effect=[
                {
                    "content": "Old",
                    "content_cleaned": None,
                    "answers": None,
                    "metadata": None,
                },
                {"latest_version": 2},
                {"id": 3},
            ]
        )
        mock_db_pool._mock_connection.execute = AsyncMock(
            return_value="DELETE 0"  # Update failed
        )

        # Act
        result = await repo.rollback_to_version(100, 1, 123)

        # Assert
        assert result is False

    # ========================================================================
    # COMPARE VERSIONS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_compare_versions_success(self, repo, mock_db_pool):
        """Test comparing two versions."""
        # Arrange
        mock_comparison = {
            "content_v1": "Version 1 content",
            "content_v2": "Version 2 content",
            "created_at_v1": datetime.now(timezone.utc),
            "created_at_v2": datetime.now(timezone.utc),
        }
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_comparison)

        # Act
        result = await repo.compare_versions(100, 1, 2, 123)

        # Assert
        assert result is not None
        assert result["content_v1"] == "Version 1 content"
        assert result["content_v2"] == "Version 2 content"

    @pytest.mark.asyncio
    async def test_compare_versions_one_not_found(self, repo, mock_db_pool):
        """Test comparing when one version doesn't exist."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.compare_versions(100, 1, 999, 123)

        # Assert
        assert result is None

    # ========================================================================
    # VERSION WITH METADATA TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_version_with_metadata_success(self, repo, mock_db_pool):
        """Test getting version with additional metadata."""
        # Arrange
        mock_version = {
            "id": 1,
            "version_number": 2,
            "content": "Test",
            "conversation_id": 50,
            "role": "user",
            "user_id": 123,
            "versions_after": 3,
        }
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_version)

        # Act
        result = await repo.get_version_with_metadata(100, 2, 123)

        # Assert
        assert result is not None
        assert result["versions_after"] == 3
        assert result["conversation_id"] == 50

    @pytest.mark.asyncio
    async def test_get_version_with_metadata_not_found(self, repo, mock_db_pool):
        """Test getting version with metadata when not found."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.get_version_with_metadata(100, 999, 123)

        # Assert
        assert result is None

    # ========================================================================
    # DELETE VERSIONS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_delete_versions_after_success(self, repo, mock_db_pool):
        """Test deleting versions after a specific version."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="DELETE 3")

        # Act
        result = await repo.delete_versions_after(100, 2, 123)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_versions_after_none_found(self, repo, mock_db_pool):
        """Test deleting versions when none exist after specified version."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="DELETE 0")

        # Act
        result = await repo.delete_versions_after(100, 10, 123)

        # Assert
        assert result is True  # DELETE is in result even if 0 rows

    @pytest.mark.asyncio
    async def test_delete_versions_after_fails(self, repo, mock_db_pool):
        """Test delete versions when operation fails."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 0")

        # Act
        result = await repo.delete_versions_after(100, 2, 123)

        # Assert
        assert result is False  # No DELETE in result

    # ========================================================================
    # CLEANUP TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_all_message_versions_for_cleanup(self, repo, mock_db_pool):
        """Test getting versions that exceed the limit."""
        # Arrange
        mock_versions = [
            {
                "message_id": 100,
                "version_number": 10,
                "total_versions": 60,
                "position_from_latest": 51,
            },
            {
                "message_id": 100,
                "version_number": 9,
                "total_versions": 60,
                "position_from_latest": 52,
            },
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_versions)

        # Act
        result = await repo.get_all_message_versions_for_cleanup(
            123, limit_per_message=50
        )

        # Assert
        assert len(result) == 2
        assert result[0]["total_versions"] == 60

    @pytest.mark.asyncio
    async def test_get_all_message_versions_for_cleanup_empty(self, repo, mock_db_pool):
        """Test cleanup list when no messages exceed limit."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_all_message_versions_for_cleanup(
            123, limit_per_message=50
        )

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_cleanup_old_versions_success(self, repo, mock_db_pool):
        """Test cleaning up old versions."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="DELETE 10")

        # Act
        result = await repo.cleanup_old_versions(123, 100, keep_latest=50)

        # Assert
        assert result == 10

    @pytest.mark.asyncio
    async def test_cleanup_old_versions_none_deleted(self, repo, mock_db_pool):
        """Test cleanup when no versions are deleted."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="DELETE 0")

        # Act
        result = await repo.cleanup_old_versions(123, 100, keep_latest=50)

        # Assert
        assert result == 0

    @pytest.mark.asyncio
    async def test_cleanup_old_versions_no_delete_in_result(self, repo, mock_db_pool):
        """Test cleanup when result doesn't contain DELETE."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 0")

        # Act
        result = await repo.cleanup_old_versions(123, 100, keep_latest=50)

        # Assert
        assert result == 0

    # ========================================================================
    # VERSION SUMMARY TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_version_summary_success(self, repo, mock_db_pool):
        """Test getting version summary."""
        # Arrange
        mock_summary = {
            "total_versions": 5,
            "first_version": 1,
            "latest_version": 5,
            "first_created": datetime.now(timezone.utc),
            "latest_created": datetime.now(timezone.utc),
        }
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_summary)

        # Act
        result = await repo.get_version_summary(100, 123)

        # Assert
        assert result is not None
        assert result["total_versions"] == 5
        assert result["first_version"] == 1
        assert result["latest_version"] == 5

    @pytest.mark.asyncio
    async def test_get_version_summary_no_versions(self, repo, mock_db_pool):
        """Test getting summary when no versions exist."""
        # Arrange
        mock_summary = {
            "total_versions": 0,
            "first_version": None,
            "latest_version": None,
            "first_created": None,
            "latest_created": None,
        }
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_summary)

        # Act
        result = await repo.get_version_summary(100, 123)

        # Assert
        assert result is not None
        assert result["total_versions"] == 0

    @pytest.mark.asyncio
    async def test_get_version_summary_message_not_found(self, repo, mock_db_pool):
        """Test getting summary for non-existent message."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.get_version_summary(9999, 123)

        # Assert
        assert result is None
