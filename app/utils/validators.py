"""
Common validation utilities for health management application.
DRY - Centralized validation logic to prevent duplication across services.
"""

import re
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ValidationError(ValueError):
    """Custom validation error for better error handling."""

    pass


def validate_pin(pin: str) -> str:
    """
    Validate conversation pin format.

    Args:
        pin: Pin string to validate

    Returns:
        Normalized pin string

    Raises:
        ValidationError: If pin format is invalid
    """
    if not pin:
        raise ValidationError("Pin cannot be empty")

    # Remove whitespace and convert to uppercase
    normalized_pin = pin.strip().upper()

    # Validate pin format (4-6 alphanumeric characters)
    if not re.match(r"^[A-Z0-9]{4,6}$", normalized_pin):
        raise ValidationError("Pin must be 4-6 alphanumeric characters")

    return normalized_pin


def validate_tags(tags: List[str]) -> List[str]:
    """
    Validate and normalize conversation tags.

    Args:
        tags: List of tag strings to validate

    Returns:
        Normalized list of tags

    Raises:
        ValidationError: If tags format is invalid
    """
    if not isinstance(tags, list):
        raise ValidationError("Tags must be a list")

    if len(tags) > 10:
        raise ValidationError("Maximum 10 tags allowed")

    normalized_tags = []
    for tag in tags:
        if not isinstance(tag, str):
            raise ValidationError(f"Tag must be string, got {type(tag)}")

        # Remove whitespace, convert to lowercase, limit length
        normalized_tag = tag.strip().lower()

        if not normalized_tag:
            continue  # Skip empty tags

        if len(normalized_tag) > 20:
            raise ValidationError(f"Tag '{tag}' too long (max 20 characters)")

        # Validate tag format (alphanumeric, spaces, hyphens, underscores)
        if not re.match(r"^[a-z0-9\s\-_]+$", normalized_tag):
            raise ValidationError(f"Tag '{tag}' contains invalid characters")

        if normalized_tag not in normalized_tags:
            normalized_tags.append(normalized_tag)

    return normalized_tags


def validate_date_range(
    date_from: Optional[str], date_to: Optional[str]
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Validate and parse date range strings.

    Args:
        date_from: Start date string (ISO format)
        date_to: End date string (ISO format)

    Returns:
        Tuple of parsed datetime objects

    Raises:
        ValidationError: If date format is invalid or range is invalid
    """
    parsed_from = None
    parsed_to = None

    if date_from:
        try:
            parsed_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
        except ValueError:
            raise ValidationError(f"Invalid date_from format: {date_from}")

    if date_to:
        try:
            parsed_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        except ValueError:
            raise ValidationError(f"Invalid date_to format: {date_to}")

    # Validate date range logic
    if parsed_from and parsed_to and parsed_from > parsed_to:
        raise ValidationError("date_from cannot be after date_to")

    return parsed_from, parsed_to


def validate_message_content(content: str) -> str:
    """
    Validate message content.

    Args:
        content: Message content to validate

    Returns:
        Normalized content

    Raises:
        ValidationError: If content is invalid
    """
    if not isinstance(content, str):
        raise ValidationError("Content must be a string")

    content = content.strip()

    if not content:
        raise ValidationError("Content cannot be empty")

    if len(content) > 5000:
        raise ValidationError("Content too long (max 5000 characters)")

    return content


def validate_message_role(role: str) -> str:
    """
    Validate message role.

    Args:
        role: Message role to validate

    Returns:
        Normalized role

    Raises:
        ValidationError: If role is invalid
    """
    valid_roles = ["user", "assistant", "system"]

    if not isinstance(role, str):
        raise ValidationError("Role must be a string")

    normalized_role = role.strip().lower()

    if normalized_role not in valid_roles:
        raise ValidationError(f"Invalid role: {role}. Must be one of {valid_roles}")

    return normalized_role


def validate_sort_field(
    sort_field: str, allowed_fields: List[str], default_field: str = "updated_at"
) -> str:
    """
    Validate sort field against allowed values.

    Args:
        sort_field: Sort field to validate
        allowed_fields: List of allowed field names
        default_field: Default field if invalid

    Returns:
        Validated sort field
    """
    if not isinstance(sort_field, str):
        return default_field

    normalized_field = sort_field.strip().lower()

    if normalized_field not in allowed_fields:
        logger.warning(
            f"Invalid sort field: {sort_field}, using default: {default_field}"
        )
        return default_field

    return normalized_field


def validate_sort_order(sort_order: str, default_order: str = "desc") -> str:
    """
    Validate sort order.

    Args:
        sort_order: Sort order to validate
        default_order: Default order if invalid

    Returns:
        Validated sort order
    """
    if not isinstance(sort_order, str):
        return default_order

    normalized_order = sort_order.strip().lower()

    if normalized_order not in ["asc", "desc"]:
        logger.warning(
            f"Invalid sort order: {sort_order}, using default: {default_order}"
        )
        return default_order

    return normalized_order


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe file storage.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    # Remove path separators and special characters
    sanitized = re.sub(r'[<>:"/\\|?*]', "", filename)

    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip(". ")

    # Limit length
    if len(sanitized) > 255:
        name, ext = sanitized.rsplit(".", 1) if "." in sanitized else (sanitized, "")
        sanitized = name[: 255 - len(ext) - 1] + "." + ext if ext else name[:255]

    return sanitized or "untitled"


def validate_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize metadata dictionary.

    Args:
        metadata: Metadata dictionary to validate

    Returns:
        Validated metadata dictionary

    Raises:
        ValidationError: If metadata is invalid
    """
    if not isinstance(metadata, dict):
        raise ValidationError("Metadata must be a dictionary")

    if len(metadata) > 50:
        raise ValidationError("Metadata cannot have more than 50 key-value pairs")

    validated_metadata = {}

    for key, value in metadata.items():
        if not isinstance(key, str):
            raise ValidationError("Metadata keys must be strings")

        # Validate key format
        key = key.strip().lower()
        if not re.match(r"^[a-z0-9_]+$", key):
            raise ValidationError(f"Invalid metadata key: {key}")

        if len(key) > 30:
            raise ValidationError(f"Metadata key too long: {key}")

        # Validate value
        if isinstance(value, (str, int, float, bool)) or value is None:
            validated_metadata[key] = value
        else:
            # Convert complex objects to string representation
            validated_metadata[key] = str(value)

    return validated_metadata


# Common validation error messages
VALIDATION_ERRORS = {
    "required_field": "This field is required",
    "invalid_email": "Invalid email address",
    "invalid_password": "Password must be at least 8 characters",
    "invalid_date": "Invalid date format",
    "invalid_range": "Invalid date range",
    "too_long": "Value too long",
    "invalid_format": "Invalid format",
    "not_found": "Resource not found",
    "access_denied": "Access denied",
    "duplicate": "Duplicate entry",
}


def get_validation_error(error_key: str, **kwargs) -> str:
    """
    Get standardized validation error message.

    Args:
        error_key: Error key from VALIDATION_ERRORS
        **kwargs: Additional formatting arguments

    Returns:
        Formatted error message
    """
    message = VALIDATION_ERRORS.get(error_key, "Validation error")

    try:
        return message.format(**kwargs)
    except (KeyError, ValueError):
        return message
