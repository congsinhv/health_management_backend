"""
Date utility functions for health management application.
DRY - Centralized date parsing and manipulation logic.
"""

import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)


# Common date formats we accept
DATE_FORMATS = [
    "%Y-%m-%d",  # 2023-12-31
    "%Y-%m-%d %H:%M:%S",  # 2023-12-31 23:59:59
    "%Y-%m-%dT%H:%M:%S",  # 2023-12-31T23:59:59
    "%Y-%m-%dT%H:%M:%SZ",  # 2023-12-31T23:59:59Z
    "%Y-%m-%dT%H:%M:%S.%fZ",  # 2023-12-31T23:59:59.123456Z
    "%Y-%m-%dT%H:%M:%S.%f",  # 2023-12-31T23:59:59.123456
    "%Y-%m-%dT%H:%M:%S%z",  # 2023-12-31T23:59:59+0000
    "%Y-%m-%dT%H:%M:%S.%f%z",  # 2023-12-31T23:59:59.123456+0000
]


def parse_iso_datetime(date_string: str) -> datetime:
    """
    Parse ISO 8601 datetime string with multiple format support.

    Args:
        date_string: Date string to parse

    Returns:
        datetime object with timezone awareness

    Raises:
        ValueError: If date_string cannot be parsed
    """
    if not date_string:
        raise ValueError("Date string cannot be empty")

    # Handle Z timezone indicator
    if date_string.endswith("Z"):
        date_string = date_string[:-1] + "+00:00"

    # Try each format
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(date_string, fmt)
            # Add timezone if missing
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue

    # Try ISO format parsing as fallback
    try:
        return datetime.fromisoformat(date_string.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"Unable to parse date: {date_string}")


def parse_date(date_string: str) -> datetime:
    """
    Parse date string (date only, time set to start of day).

    Args:
        date_string: Date string to parse

    Returns:
        datetime object at start of day in UTC
    """
    dt = parse_iso_datetime(date_string)
    # Reset to start of day
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def format_iso_datetime(dt: datetime) -> str:
    """
    Format datetime to ISO 8601 string.

    Args:
        dt: datetime object

    Returns:
        ISO 8601 formatted string
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def format_date(dt: datetime) -> str:
    """
    Format datetime to date string (YYYY-MM-DD).

    Args:
        dt: datetime object

    Returns:
        Date string in YYYY-MM-DD format
    """
    return dt.strftime("%Y-%m-%d")


def get_current_utc() -> datetime:
    """
    Get current UTC datetime.

    Returns:
        Current UTC datetime
    """
    return datetime.now(timezone.utc)


def get_start_of_day(dt: datetime) -> datetime:
    """
    Get start of day for given datetime.

    Args:
        dt: datetime object

    Returns:
        datetime at start of day (00:00:00)
    """
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def get_end_of_day(dt: datetime) -> datetime:
    """
    Get end of day for given datetime.

    Args:
        dt: datetime object

    Returns:
        datetime at end of day (23:59:59.999999)
    """
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def get_start_of_week(dt: datetime) -> datetime:
    """
    Get start of week (Monday) for given datetime.

    Args:
        dt: datetime object

    Returns:
        datetime at start of week
    """
    days_since_monday = dt.weekday()
    return get_start_of_day(dt - timedelta(days=days_since_monday))


def get_start_of_month(dt: datetime) -> datetime:
    """
    Get start of month for given datetime.

    Args:
        dt: datetime object

    Returns:
        datetime at start of month
    """
    return get_start_of_day(dt.replace(day=1))


def get_start_of_year(dt: datetime) -> datetime:
    """
    Get start of year for given datetime.

    Args:
        dt: datetime object

    Returns:
        datetime at start of year
    """
    return get_start_of_day(dt.replace(month=1, day=1))


def add_days(dt: datetime, days: int) -> datetime:
    """
    Add days to datetime.

    Args:
        dt: datetime object
        days: Number of days to add (can be negative)

    Returns:
        New datetime object
    """
    return dt + timedelta(days=days)


def add_hours(dt: datetime, hours: int) -> datetime:
    """
    Add hours to datetime.

    Args:
        dt: datetime object
        hours: Number of hours to add (can be negative)

    Returns:
        New datetime object
    """
    return dt + timedelta(hours=hours)


def add_minutes(dt: datetime, minutes: int) -> datetime:
    """
    Add minutes to datetime.

    Args:
        dt: datetime object
        minutes: Number of minutes to add (can be negative)

    Returns:
        New datetime object
    """
    return dt + timedelta(minutes=minutes)


def calculate_age(birth_date: datetime) -> int:
    """
    Calculate age in years from birth date.

    Args:
        birth_date: Birth date

    Returns:
        Age in years
    """
    today = get_current_utc()
    age = today.year - birth_date.year

    # Adjust if birthday hasn't occurred yet this year
    if today.month < birth_date.month or (
        today.month == birth_date.month and today.day < birth_date.day
    ):
        age -= 1

    return age


def is_date_range_overlapping(
    start1: datetime, end1: datetime, start2: datetime, end2: datetime
) -> bool:
    """
    Check if two date ranges overlap.

    Args:
        start1, end1: First date range
        start2, end2: Second date range

    Returns:
        True if ranges overlap
    """
    return start1 <= end2 and start2 <= end1


def get_time_ago(dt: datetime, reference: Optional[datetime] = None) -> str:
    """
    Get human-readable time ago string.

    Args:
        dt: datetime to compare
        reference: Reference datetime (defaults to now)

    Returns:
        Human-readable time ago string
    """
    if reference is None:
        reference = get_current_utc()

    diff = reference - dt

    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "just now"


def validate_date_range(start: Optional[datetime], end: Optional[datetime]) -> None:
    """
    Validate date range logic.

    Args:
        start: Start datetime
        end: End datetime

    Raises:
        ValueError: If date range is invalid
    """
    if start and end and start > end:
        raise ValueError("Start date cannot be after end date")


def get_relative_time(dt: datetime) -> str:
    """
    Get relative time string (today, yesterday, X days ago).

    Args:
        dt: datetime to format

    Returns:
        Relative time string
    """
    today = get_current_utc()
    dt_date = dt.date() if hasattr(dt, "date") else dt
    today_date = today.date()

    if dt_date == today_date:
        return "today"
    elif dt_date == today_date - timedelta(days=1):
        return "yesterday"
    elif dt_date > today_date - timedelta(days=7):
        days_ago = (today_date - dt_date).days
        return f"{days_ago} days ago"
    else:
        return format_date(dt)


# Time constants for commonly used periods
TIME_CONSTANTS = {
    "ONE_MINUTE": timedelta(minutes=1),
    "FIVE_MINUTES": timedelta(minutes=5),
    "FIFTEEN_MINUTES": timedelta(minutes=15),
    "ONE_HOUR": timedelta(hours=1),
    "SIX_HOURS": timedelta(hours=6),
    "ONE_DAY": timedelta(days=1),
    "ONE_WEEK": timedelta(weeks=1),
    "ONE_MONTH": timedelta(days=30),
    "ONE_YEAR": timedelta(days=365),
}


def get_time_constant(name: str) -> timedelta:
    """
    Get predefined time constant.

    Args:
        name: Time constant name

    Returns:
        timedelta object

    Raises:
        KeyError: If constant name not found
    """
    return TIME_CONSTANTS[name.upper()]
