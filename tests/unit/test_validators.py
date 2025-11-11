"""
Tests for app/utils/validators.py validation utilities.
"""

import pytest
from app.utils.validators import (
    ValidationError,
    validate_pin,
    validate_tags,
    validate_date_range,
    validate_message_content,
    validate_message_role,
    validate_sort_field,
    validate_sort_order,
    sanitize_filename,
    validate_metadata,
    get_validation_error,
)


class TestValidatePin:
    """Tests for validate_pin function."""

    def test_valid_pin(self):
        """Test validating correct pin formats."""
        assert validate_pin("ABC1") == "ABC1"
        assert validate_pin("XYZ123") == "XYZ123"
        assert validate_pin("  abc1  ") == "ABC1"  # Normalization

    def test_invalid_pin_empty(self):
        """Test validation fails for empty pin."""
        with pytest.raises(ValidationError):
            validate_pin("")
        with pytest.raises(ValidationError):
            validate_pin("   ")

    def test_invalid_pin_length(self):
        """Test validation fails for incorrect length."""
        with pytest.raises(ValidationError, match="4-6 alphanumeric"):
            validate_pin("ABC")  # Too short
        with pytest.raises(ValidationError, match="4-6 alphanumeric"):
            validate_pin("ABCDEFG")  # Too long

    def test_invalid_pin_characters(self):
        """Test validation fails for invalid characters."""
        with pytest.raises(ValidationError, match="4-6 alphanumeric"):
            validate_pin("ABC-1")  # Hyphen
        with pytest.raises(ValidationError, match="4-6 alphanumeric"):
            validate_pin("ABC 1")  # Space


class TestValidateTags:
    """Tests for validate_tags function."""

    def test_valid_tags(self):
        """Test validating correct tag formats."""
        assert validate_tags(["health", "fitness"]) == ["health", "fitness"]
        assert validate_tags(["Medical Info", "Tips"]) == ["medical info", "tips"]

    def test_empty_tags_list(self):
        """Test validating empty tags list."""
        assert validate_tags([]) == []

    def test_tags_normalization(self):
        """Test tag normalization (lowercase, trim)."""
        result = validate_tags(["  Health  ", "FITNESS", "Wellness"])
        assert result == ["health", "fitness", "wellness"]

    def test_tags_deduplication(self):
        """Test duplicate tags are removed."""
        result = validate_tags(["health", "fitness", "health"])
        assert result == ["health", "fitness"]

    def test_invalid_tags_not_list(self):
        """Test validation fails if tags is not a list."""
        with pytest.raises(ValidationError, match="Tags must be a list"):
            validate_tags("not-a-list")

    def test_invalid_tags_too_many(self):
        """Test validation fails for more than 10 tags."""
        tags = [f"tag{i}" for i in range(11)]
        with pytest.raises(ValidationError, match="Maximum 10 tags"):
            validate_tags(tags)

    def test_invalid_tag_type(self):
        """Test validation fails for non-string tag."""
        with pytest.raises(ValidationError, match="Tag must be string"):
            validate_tags(["health", 123])

    def test_invalid_tag_too_long(self):
        """Test validation fails for tag exceeding 20 characters."""
        with pytest.raises(ValidationError, match="too long"):
            validate_tags(["a" * 21])

    def test_invalid_tag_characters(self):
        """Test validation fails for invalid characters."""
        with pytest.raises(ValidationError, match="invalid characters"):
            validate_tags(["health@wellness"])


class TestValidateDateRange:
    """Tests for validate_date_range function."""

    def test_valid_date_range(self):
        """Test validating correct date range."""
        date_from, date_to = validate_date_range(
            "2024-01-01T00:00:00Z", "2024-12-31T23:59:59Z"
        )
        assert date_from is not None
        assert date_to is not None
        assert date_from < date_to

    def test_none_dates(self):
        """Test handling None dates."""
        date_from, date_to = validate_date_range(None, None)
        assert date_from is None
        assert date_to is None

    def test_invalid_date_format(self):
        """Test validation fails for invalid date format."""
        with pytest.raises(ValidationError, match="Invalid date_from format"):
            validate_date_range("not-a-date", None)

    def test_invalid_date_range_order(self):
        """Test validation fails when start date is after end date."""
        with pytest.raises(ValidationError, match="date_from cannot be after date_to"):
            validate_date_range("2024-12-31T00:00:00Z", "2024-01-01T00:00:00Z")


class TestValidateMessageContent:
    """Tests for validate_message_content function."""

    def test_valid_content(self):
        """Test validating correct message content."""
        assert validate_message_content("Hello, world!") == "Hello, world!"
        assert validate_message_content("  Trimmed  ") == "Trimmed"

    def test_invalid_content_not_string(self):
        """Test validation fails for non-string content."""
        with pytest.raises(ValidationError, match="Content must be a string"):
            validate_message_content(123)

    def test_invalid_content_empty(self):
        """Test validation fails for empty content."""
        with pytest.raises(ValidationError, match="Content cannot be empty"):
            validate_message_content("")
        with pytest.raises(ValidationError, match="Content cannot be empty"):
            validate_message_content("   ")

    def test_invalid_content_too_long(self):
        """Test validation fails for content exceeding 5000 characters."""
        with pytest.raises(ValidationError, match="Content too long"):
            validate_message_content("a" * 5001)


class TestValidateMessageRole:
    """Tests for validate_message_role function."""

    def test_valid_roles(self):
        """Test validating correct message roles."""
        assert validate_message_role("user") == "user"
        assert validate_message_role("assistant") == "assistant"
        assert validate_message_role("system") == "system"
        assert validate_message_role("  USER  ") == "user"  # Normalization

    def test_invalid_role_not_string(self):
        """Test validation fails for non-string role."""
        with pytest.raises(ValidationError, match="Role must be a string"):
            validate_message_role(123)

    def test_invalid_role_value(self):
        """Test validation fails for invalid role value."""
        with pytest.raises(ValidationError, match="Invalid role"):
            validate_message_role("admin")


class TestValidateSortField:
    """Tests for validate_sort_field function."""

    def test_valid_sort_field(self):
        """Test validating correct sort field."""
        allowed = ["created_at", "updated_at", "title"]
        assert validate_sort_field("created_at", allowed) == "created_at"
        assert validate_sort_field("  TITLE  ", allowed) == "title"

    def test_invalid_sort_field_returns_default(self):
        """Test invalid sort field returns default."""
        allowed = ["created_at", "updated_at"]
        assert validate_sort_field("invalid", allowed) == "updated_at"
        assert validate_sort_field("invalid", allowed, "created_at") == "created_at"

    def test_non_string_returns_default(self):
        """Test non-string sort field returns default."""
        allowed = ["created_at"]
        assert validate_sort_field(123, allowed) == "updated_at"


class TestValidateSortOrder:
    """Tests for validate_sort_order function."""

    def test_valid_sort_order(self):
        """Test validating correct sort order."""
        assert validate_sort_order("asc") == "asc"
        assert validate_sort_order("desc") == "desc"
        assert validate_sort_order("  ASC  ") == "asc"

    def test_invalid_sort_order_returns_default(self):
        """Test invalid sort order returns default."""
        assert validate_sort_order("invalid") == "desc"
        assert validate_sort_order("invalid", "asc") == "asc"

    def test_non_string_returns_default(self):
        """Test non-string sort order returns default."""
        assert validate_sort_order(123) == "desc"


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_sanitize_normal_filename(self):
        """Test sanitizing normal filename."""
        assert sanitize_filename("document.pdf") == "document.pdf"

    def test_sanitize_removes_special_chars(self):
        """Test sanitizing removes special characters."""
        assert sanitize_filename('file<>:"/\\|?*.txt') == "file.txt"

    def test_sanitize_removes_leading_trailing(self):
        """Test sanitizing removes leading/trailing dots and spaces."""
        assert sanitize_filename("  ..file.txt..  ") == "file.txt"

    def test_sanitize_limits_length(self):
        """Test sanitizing limits filename length."""
        long_name = "a" * 300 + ".txt"
        result = sanitize_filename(long_name)
        assert len(result) <= 255

    def test_sanitize_empty_returns_untitled(self):
        """Test empty filename returns 'untitled'."""
        assert sanitize_filename("") == "untitled"
        assert sanitize_filename("....") == "untitled"


class TestValidateMetadata:
    """Tests for validate_metadata function."""

    def test_valid_metadata(self):
        """Test validating correct metadata."""
        metadata = {"key1": "value1", "key2": 123, "key3": True}
        result = validate_metadata(metadata)
        assert result == {"key1": "value1", "key2": 123, "key3": True}

    def test_empty_metadata(self):
        """Test validating empty metadata."""
        assert validate_metadata({}) == {}

    def test_metadata_key_normalization(self):
        """Test metadata key normalization."""
        metadata = {"  KEY_1  ": "value"}
        result = validate_metadata(metadata)
        assert "key_1" in result

    def test_invalid_metadata_not_dict(self):
        """Test validation fails if metadata is not a dictionary."""
        with pytest.raises(ValidationError, match="Metadata must be a dictionary"):
            validate_metadata("not-a-dict")

    def test_invalid_metadata_too_many_keys(self):
        """Test validation fails for more than 50 keys."""
        metadata = {f"key{i}": f"value{i}" for i in range(51)}
        with pytest.raises(ValidationError, match="cannot have more than 50"):
            validate_metadata(metadata)

    def test_invalid_metadata_key_not_string(self):
        """Test validation fails for non-string key."""
        with pytest.raises(ValidationError, match="Metadata keys must be strings"):
            validate_metadata({123: "value"})

    def test_invalid_metadata_key_format(self):
        """Test validation fails for invalid key format."""
        with pytest.raises(ValidationError, match="Invalid metadata key"):
            validate_metadata({"invalid-key": "value"})

    def test_invalid_metadata_key_too_long(self):
        """Test validation fails for key exceeding 30 characters."""
        with pytest.raises(ValidationError, match="Metadata key too long"):
            validate_metadata({"a" * 31: "value"})

    def test_metadata_complex_value_converted_to_string(self):
        """Test complex values are converted to strings."""
        metadata = {"key": {"nested": "dict"}}
        result = validate_metadata(metadata)
        assert isinstance(result["key"], str)


class TestGetValidationError:
    """Tests for get_validation_error function."""

    def test_get_validation_error_known_key(self):
        """Test getting known validation error message."""
        assert get_validation_error("required_field") == "This field is required"
        assert get_validation_error("invalid_email") == "Invalid email address"

    def test_get_validation_error_unknown_key(self):
        """Test getting unknown validation error returns default."""
        assert get_validation_error("unknown_key") == "Validation error"

    def test_get_validation_error_with_formatting(self):
        """Test error message formatting (if template supports it)."""
        # Current implementation doesn't have format placeholders,
        # but test that it doesn't crash with kwargs
        result = get_validation_error("required_field", field="email")
        assert "required" in result.lower()
