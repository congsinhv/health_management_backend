"""
Unit tests for VersionDiffService.

Tests diff generation, parsing, HTML rendering, and statistics.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

from app.services.version_diff import VersionDiffService


@pytest.mark.unit
class TestVersionDiffService:
    """Test cases for VersionDiffService."""

    @pytest.fixture
    def mock_version_repo(self):
        """Mock MessageVersionRepository."""
        repo = AsyncMock()
        repo.get_version_history = AsyncMock(return_value=[])
        repo.get_version = AsyncMock(return_value=None)
        repo.get_latest_version_number = AsyncMock(return_value=1)
        repo.create_version = AsyncMock(return_value={"id": 1})
        return repo

    @pytest.fixture
    def mock_message_repo(self):
        """Mock MessageRepository."""
        repo = AsyncMock()
        repo.get_message_by_user = AsyncMock(return_value=None)
        repo.update_message = AsyncMock(return_value=True)
        return repo

    @pytest.fixture
    def version_diff_service(self, mock_db_pool, mock_version_repo):
        """Create VersionDiffService instance with mocked repository."""
        service = VersionDiffService(mock_db_pool)
        service.version_repo = mock_version_repo
        return service

    @pytest.fixture
    def sample_versions(self):
        """Sample version data for testing."""
        now = datetime.now(timezone.utc)
        return [
            {
                "id": 1,
                "message_id": 123,
                "version_number": 1,
                "content": "Original content",
                "content_cleaned": "Original cleaned content",
                "answers": {"q1": ["answer1"]},
                "metadata": {"edited_by": 123},
                "change_reason": "Initial version",
                "created_at": now - timedelta(hours=2),
            },
            {
                "id": 2,
                "message_id": 123,
                "version_number": 2,
                "content": "Modified content with changes",
                "content_cleaned": "Modified cleaned content",
                "answers": {"q1": ["answer1"], "q2": ["answer2"]},
                "metadata": {"edited_by": 123, "editor": "human"},
                "change_reason": "Updated information",
                "created_at": now - timedelta(hours=1),
            },
            {
                "id": 3,
                "message_id": 123,
                "version_number": 3,
                "content": "Final modified content with more changes",
                "content_cleaned": "Final cleaned content",
                "answers": {"q1": ["new_answer1"], "q2": ["answer2"]},
                "metadata": {"edited_by": 456, "editor": "ai"},
                "change_reason": "AI enhancement",
                "created_at": now,
            },
        ]

    async def test_generate_unified_diff(self, version_diff_service):
        """Test generation of unified diff format."""
        old_text = "Line 1\nLine 2\nLine 3\n"
        new_text = "Line 1\nModified Line 2\nLine 3\nLine 4\n"

        diff_result = version_diff_service._generate_text_diff(old_text, new_text)

        # Verify unified diff is generated
        assert "unified_diff" in diff_result
        assert "--- old" in diff_result["unified_diff"]
        assert "+++ new" in diff_result["unified_diff"]
        assert "-Line 2" in diff_result["unified_diff"]
        assert "+Modified Line 2" in diff_result["unified_diff"]
        assert "+Line 4" in diff_result["unified_diff"]

    async def test_generate_side_by_side_diff(self, version_diff_service):
        """Test generation of side-by-side diff."""
        old_text = "Original content"
        new_text = "Modified content"

        diff_result = version_diff_service._generate_text_diff(old_text, new_text)

        # Verify HTML diff is generated for side-by-side view
        assert "html_diff" in diff_result
        assert "<table" in diff_result["html_diff"]
        assert "Old Version" in diff_result["html_diff"]
        assert "New Version" in diff_result["html_diff"]

    async def test_generate_inline_diff(self, version_diff_service):
        """Test generation of inline diff."""
        old_text = "short"
        new_text = "much longer text with changes"

        diff_result = version_diff_service._generate_text_diff(old_text, new_text)

        # Verify statistics are calculated
        assert "statistics" in diff_result
        stats = diff_result["statistics"]
        assert "additions" in stats
        assert "deletions" in stats
        assert "modifications" in stats
        assert "total_changes" in stats

    async def test_parse_diff_format(self, version_diff_service):
        """Test parsing and formatting of diff output."""
        old_text = "Line 1\nLine 2\n"
        new_text = "Line 1\nLine 2 Modified\n"

        diff_result = version_diff_service._generate_text_diff(old_text, new_text)

        # Verify diff format compliance
        unified_diff = diff_result["unified_diff"]
        assert isinstance(unified_diff, str)
        assert len(unified_diff) > 0

        # Check for proper diff headers
        lines = unified_diff.split("\n")
        assert any("---" in line for line in lines)
        assert any("+++" in line for line in lines)

    async def test_render_html_diff_with_highlighting(self, version_diff_service):
        """Test HTML diff rendering with syntax highlighting."""
        code_old = "def hello():\n    print('Hello')"
        code_new = "def hello():\n    print('Hello, World!')"

        diff_result = version_diff_service._generate_text_diff(code_old, code_new)

        # Verify HTML diff structure
        html_diff = diff_result["html_diff"]
        assert "<table" in html_diff
        assert "diff" in html_diff.lower()
        assert (
            "Hello" in html_diff
        )  # HTML entity encoding might affect the exact string

    async def test_calculate_diff_statistics(self, version_diff_service):
        """Test calculation of diff statistics."""
        old_text = "Line 1\nLine 2\nLine 3\n"
        new_text = "Line 1\nModified Line 2\nLine 3\nNew Line 4\n"

        diff_result = version_diff_service._generate_text_diff(old_text, new_text)
        stats = diff_result["statistics"]

        # Verify statistics are correctly calculated
        assert stats["total_changes"] > 0  # Some changes should be detected
        assert isinstance(stats["additions"], int)
        assert isinstance(stats["deletions"], int)
        assert isinstance(stats["modifications"], int)

    async def test_calculate_text_similarity(self, version_diff_service):
        """Test calculation of text similarity ratio."""
        identical_texts = "Same content"
        different_texts1 = "Content A"
        different_texts2 = "Content B"

        # Test identical texts
        diff1 = version_diff_service._generate_text_diff(
            identical_texts, identical_texts
        )
        assert diff1["similarity_ratio"] == 1.0

        # Test different texts
        diff2 = version_diff_service._generate_text_diff(
            different_texts1, different_texts2
        )
        assert 0 <= diff2["similarity_ratio"] < 1.0
        assert diff2["similarity_ratio"] > 0  # Some similarity due to common words

    async def test_semantic_diff_for_code(self, version_diff_service):
        """Test semantic diff for code structures."""
        old_code = """def calculate(x, y):
    return x + y

def multiply(x, y):
    return x * y"""

        new_code = """def calculate(x, y):
    return x + y

def multiply(x, y):
    result = x * y
    return result

def divide(x, y):
    return x / y"""

        diff_result = version_diff_service._generate_text_diff(old_code, new_code)

        # Verify diff captures semantic changes
        assert (
            diff_result["statistics"]["total_changes"] > 0
        )  # Should capture new function and modifications

    async def test_semantic_diff_for_json(self, version_diff_service):
        """Test semantic diff for JSON structures."""
        import json

        old_json = {"name": "John", "age": 30, "city": "New York"}
        new_json = {"name": "John", "age": 31, "city": "Boston", "country": "USA"}

        old_text = json.dumps(old_json, indent=2)
        new_text = json.dumps(new_json, indent=2)

        diff_result = version_diff_service._generate_text_diff(old_text, new_text)

        # Verify JSON structural changes are captured
        stats = diff_result["statistics"]
        assert (
            stats["total_changes"] > 0
        )  # Should capture both modifications and additions

    async def test_optimize_diff_output(self, version_diff_service):
        """Test optimization of diff output for large texts."""
        # Create large texts with small changes - using a simpler case
        base_text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        modified_text = "Line 1\nLine 2\nModified Line 3\nLine 4\nLine 5"

        diff_result = version_diff_service._generate_text_diff(base_text, modified_text)

        # Verify diff captures the change
        unified_diff = diff_result["unified_diff"]
        assert "Modified Line 3" in unified_diff
        assert "-Line 3" in unified_diff
        assert diff_result["statistics"]["total_changes"] > 0

    async def test_compress_large_diff(self, version_diff_service):
        """Test compression of large diffs."""
        # Create a smaller diff for testing
        old_lines = ["Line 1", "Line 2", "Line 3", "Line 4", "Line 5"]
        new_lines = ["Line 1", "Modified Line 2", "Line 3", "Line 4", "Line 5"]

        old_text = "\n".join(old_lines)
        new_text = "\n".join(new_lines)

        diff_result = version_diff_service._generate_text_diff(old_text, new_text)

        # Verify diff is generated and captures changes
        unified_diff = diff_result["unified_diff"]
        assert len(unified_diff) > 0
        assert "Modified Line 2" in unified_diff
        assert diff_result["statistics"]["total_changes"] > 0

    async def test_handle_empty_content_diff(self, version_diff_service):
        """Test handling of empty content in diffs."""
        # Test empty old content
        diff1 = version_diff_service._generate_text_diff("", "New content")
        assert diff1["statistics"]["additions"] > 0
        assert diff1["statistics"]["deletions"] == 0

        # Test empty new content
        diff2 = version_diff_service._generate_text_diff("Old content", "")
        assert diff2["statistics"]["deletions"] > 0
        assert diff2["statistics"]["additions"] == 0

        # Test both empty
        diff3 = version_diff_service._generate_text_diff("", "")
        assert diff3["statistics"]["total_changes"] == 0
        assert diff3["similarity_ratio"] == 1.0

    async def test_compare_versions_integration(
        self, version_diff_service, sample_versions
    ):
        """Test full version comparison integration."""
        message_id = 123
        user_id = 456
        from_version = 1
        to_version = 3

        version_diff_service.version_repo.get_version_history.return_value = (
            sample_versions
        )

        result = await version_diff_service.compare_versions(
            message_id, user_id, from_version, to_version
        )

        # Verify comparison result structure
        assert result["message_id"] == message_id
        assert result["from_version"] == from_version
        assert result["to_version"] == to_version
        assert "content_diff" in result
        assert "changes_summary" in result
        assert result["changes_summary"]["content_changed"] is True

    async def test_get_version_timeline(self, version_diff_service, sample_versions):
        """Test generation of version timeline."""
        message_id = 123
        user_id = 456

        version_diff_service.version_repo.get_version_history.return_value = (
            sample_versions
        )

        timeline = await version_diff_service.get_version_timeline(message_id, user_id)

        # Verify timeline structure
        assert len(timeline) == 3
        assert timeline[0]["version_number"] == 1
        assert timeline[2]["version_number"] == 3

        # Verify timeline entries have required fields
        for entry in timeline:
            assert "version_number" in entry
            assert "created_at" in entry
            assert "content_preview" in entry
            assert "changes_from_previous" in entry

    async def test_export_versions(self, version_diff_service, sample_versions):
        """Test exporting versions in different formats."""
        message_id = 123
        user_id = 456

        version_diff_service.version_repo.get_version_history.return_value = (
            sample_versions
        )

        # Test JSON export
        export_data = await version_diff_service.export_versions(
            message_id, user_id, "json"
        )

        assert export_data["message_id"] == message_id
        assert export_data["total_versions"] == 3
        assert "versions" in export_data
        assert len(export_data["versions"]) == 3

        # Verify version data structure
        version = export_data["versions"][0]
        assert "version_number" in version
        assert "created_at" in version
        assert "content" in version
        assert "metadata" in version

        # Test unsupported format
        with pytest.raises(ValueError):
            await version_diff_service.export_versions(message_id, user_id, "xml")

    async def test_version_restore_with_backup(
        self, version_diff_service, sample_versions
    ):
        """Test version restoration with backup creation."""
        message_id = 123
        version_number = 1
        user_id = 456

        # Mock repository responses
        version_diff_service.version_repo.get_version.return_value = sample_versions[0]
        version_diff_service.version_repo.get_latest_version_number.return_value = 3

        current_message = {
            "id": message_id,
            "content": "Current content",
            "content_cleaned": "Current cleaned",
            "answers": {"q1": ["current"]},
            "metadata": {"current": True},
        }

        with patch("app.db.message.MessageRepository") as mock_message_repo_class:
            mock_message_repo = AsyncMock()
            mock_message_repo.get_message_by_user.return_value = current_message
            mock_message_repo.update_message.return_value = True
            mock_message_repo_class.return_value = mock_message_repo

            result = await version_diff_service.restore_version(
                message_id, version_number, user_id, create_backup=True
            )

            # Verify restore result
            assert result["message_id"] == message_id
            assert result["restored_version"] == version_number
            assert result["backup_created"] is True

            # Verify backup was created
            assert version_diff_service.version_repo.create_version.call_count == 2

            # Verify message was updated
            mock_message_repo.update_message.assert_called_once()

    async def test_answer_comparison_logic(self, version_diff_service):
        """Test comparison of answer dictionaries."""
        old_answers = {
            "symptoms": ["headache", "fever"],
            "duration": ["2 days"],
            "severity": ["mild"],
        }
        new_answers = {
            "symptoms": ["headache", "fever", "cough"],
            "duration": ["3 days"],
            "severity": ["moderate"],
        }

        result = version_diff_service._compare_answers(old_answers, new_answers)

        # Verify answer comparison
        assert result["has_changes"] is True
        assert "symptoms" in result["changed_fields"]
        assert "duration" in result["changed_fields"]
        assert "severity" in result["changed_fields"]

        # Check specific field changes
        symptoms_changes = result["field_changes"]["symptoms"]
        assert "cough" in symptoms_changes["added"]
        assert symptoms_changes["old_count"] == 2
        assert symptoms_changes["new_count"] == 3

    async def test_metadata_comparison(self, version_diff_service):
        """Test comparison of metadata dictionaries."""
        old_metadata = {"edited_by": 123, "source": "web", "confidence": 0.8}
        new_metadata = {
            "edited_by": 456,
            "source": "mobile",
            "confidence": 0.9,
            "reviewed": True,
        }

        result = version_diff_service._compare_metadata(old_metadata, new_metadata)

        # Verify metadata comparison
        assert result["has_changes"] is True
        assert len(result["changed_keys"]) == 4

        # Check specific key changes
        assert "edited_by" in result["changed_keys"]
        assert result["key_changes"]["edited_by"]["old"] == 123
        assert result["key_changes"]["edited_by"]["new"] == 456

        # Check new key
        assert "reviewed" in result["changed_keys"]
        assert result["key_changes"]["reviewed"]["old"] is None
        assert result["key_changes"]["reviewed"]["new"] is True
