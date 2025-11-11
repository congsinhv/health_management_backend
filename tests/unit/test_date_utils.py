"""
Tests for app/utils/date_utils.py date utility functions.
"""

import pytest
from datetime import datetime, timezone, timedelta
from app.utils.date_utils import (
    parse_iso_datetime,
    parse_date,
    format_iso_datetime,
    format_date,
    get_current_utc,
    get_start_of_day,
    get_end_of_day,
    get_start_of_week,
    get_start_of_month,
    get_start_of_year,
    add_days,
    add_hours,
    add_minutes,
    calculate_age,
    is_date_range_overlapping,
    get_time_ago,
    validate_date_range,
    get_relative_time,
    get_time_constant,
)


class TestParseIsoDatetime:
    """Tests for parse_iso_datetime function."""

    def test_parse_iso_format(self):
        """Test parsing ISO format datetime."""
        result = parse_iso_datetime("2024-01-15T10:30:00Z")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30

    def test_parse_with_timezone(self):
        """Test parsing datetime with timezone."""
        result = parse_iso_datetime("2024-01-15T10:30:00+00:00")
        assert result.tzinfo is not None

    def test_parse_with_microseconds(self):
        """Test parsing datetime with microseconds."""
        result = parse_iso_datetime("2024-01-15T10:30:00.123456Z")
        assert result.microsecond == 123456

    def test_parse_date_only(self):
        """Test parsing date only format."""
        result = parse_iso_datetime("2024-01-15")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_empty_string_raises_error(self):
        """Test parsing empty string raises ValueError."""
        with pytest.raises(ValueError, match="Date string cannot be empty"):
            parse_iso_datetime("")

    def test_parse_invalid_format_raises_error(self):
        """Test parsing invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Unable to parse date"):
            parse_iso_datetime("not-a-date")


class TestParseDate:
    """Tests for parse_date function."""

    def test_parse_date_sets_start_of_day(self):
        """Test parse_date sets time to start of day."""
        result = parse_date("2024-01-15T15:30:45Z")
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.microsecond == 0


class TestFormatIsoDatetime:
    """Tests for format_iso_datetime function."""

    def test_format_iso_datetime(self):
        """Test formatting datetime to ISO string."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_iso_datetime(dt)
        assert "2024-01-15" in result
        assert "10:30:00" in result

    def test_format_adds_timezone_if_missing(self):
        """Test formatting adds UTC timezone if missing."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = format_iso_datetime(dt)
        assert "+00:00" in result or "Z" in result


class TestFormatDate:
    """Tests for format_date function."""

    def test_format_date(self):
        """Test formatting datetime to date string."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = format_date(dt)
        assert result == "2024-01-15"


class TestGetCurrentUtc:
    """Tests for get_current_utc function."""

    def test_get_current_utc_returns_aware_datetime(self):
        """Test get_current_utc returns timezone-aware datetime."""
        result = get_current_utc()
        assert result.tzinfo == timezone.utc


class TestGetStartOfDay:
    """Tests for get_start_of_day function."""

    def test_get_start_of_day(self):
        """Test getting start of day."""
        dt = datetime(2024, 1, 15, 15, 30, 45, 123456)
        result = get_start_of_day(dt)
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        assert result.microsecond == 0
        assert result.date() == dt.date()


class TestGetEndOfDay:
    """Tests for get_end_of_day function."""

    def test_get_end_of_day(self):
        """Test getting end of day."""
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = get_end_of_day(dt)
        assert result.hour == 23
        assert result.minute == 59
        assert result.second == 59
        assert result.microsecond == 999999
        assert result.date() == dt.date()


class TestGetStartOfWeek:
    """Tests for get_start_of_week function."""

    def test_get_start_of_week(self):
        """Test getting start of week (Monday)."""
        # Wednesday 2024-01-17
        dt = datetime(2024, 1, 17, 15, 30, 0)
        result = get_start_of_week(dt)
        # Should be Monday 2024-01-15 00:00:00
        assert result.weekday() == 0  # Monday
        assert result.hour == 0
        assert result.day == 15


class TestGetStartOfMonth:
    """Tests for get_start_of_month function."""

    def test_get_start_of_month(self):
        """Test getting start of month."""
        dt = datetime(2024, 1, 15, 15, 30, 0)
        result = get_start_of_month(dt)
        assert result.day == 1
        assert result.hour == 0
        assert result.month == dt.month


class TestGetStartOfYear:
    """Tests for get_start_of_year function."""

    def test_get_start_of_year(self):
        """Test getting start of year."""
        dt = datetime(2024, 6, 15, 15, 30, 0)
        result = get_start_of_year(dt)
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 0
        assert result.year == dt.year


class TestAddDays:
    """Tests for add_days function."""

    def test_add_days_positive(self):
        """Test adding positive days."""
        dt = datetime(2024, 1, 15)
        result = add_days(dt, 5)
        assert result.day == 20

    def test_add_days_negative(self):
        """Test adding negative days (subtraction)."""
        dt = datetime(2024, 1, 15)
        result = add_days(dt, -5)
        assert result.day == 10


class TestAddHours:
    """Tests for add_hours function."""

    def test_add_hours_positive(self):
        """Test adding positive hours."""
        dt = datetime(2024, 1, 15, 10, 0, 0)
        result = add_hours(dt, 5)
        assert result.hour == 15

    def test_add_hours_negative(self):
        """Test adding negative hours (subtraction)."""
        dt = datetime(2024, 1, 15, 10, 0, 0)
        result = add_hours(dt, -5)
        assert result.hour == 5


class TestAddMinutes:
    """Tests for add_minutes function."""

    def test_add_minutes_positive(self):
        """Test adding positive minutes."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = add_minutes(dt, 15)
        assert result.minute == 45

    def test_add_minutes_negative(self):
        """Test adding negative minutes (subtraction)."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        result = add_minutes(dt, -15)
        assert result.minute == 15


class TestCalculateAge:
    """Tests for calculate_age function."""

    def test_calculate_age(self):
        """Test calculating age from birth date."""
        # Person born 30 years ago
        birth_date = get_current_utc() - timedelta(days=365 * 30)
        age = calculate_age(birth_date)
        assert 29 <= age <= 30  # Account for leap years

    def test_calculate_age_before_birthday_this_year(self):
        """Test age calculation before birthday this year."""
        # Birth date is next month
        today = get_current_utc()
        birth_date = today.replace(year=today.year - 25, month=(today.month % 12) + 1)
        age = calculate_age(birth_date)
        # Should be 24 if birthday hasn't occurred yet
        assert age in [24, 25]


class TestIsDateRangeOverlapping:
    """Tests for is_date_range_overlapping function."""

    def test_overlapping_ranges(self):
        """Test detecting overlapping date ranges."""
        start1 = datetime(2024, 1, 1)
        end1 = datetime(2024, 1, 15)
        start2 = datetime(2024, 1, 10)
        end2 = datetime(2024, 1, 20)
        assert is_date_range_overlapping(start1, end1, start2, end2) is True

    def test_non_overlapping_ranges(self):
        """Test detecting non-overlapping date ranges."""
        start1 = datetime(2024, 1, 1)
        end1 = datetime(2024, 1, 10)
        start2 = datetime(2024, 1, 15)
        end2 = datetime(2024, 1, 20)
        assert is_date_range_overlapping(start1, end1, start2, end2) is False

    def test_adjacent_ranges(self):
        """Test adjacent date ranges (touch but don't overlap)."""
        start1 = datetime(2024, 1, 1)
        end1 = datetime(2024, 1, 10)
        start2 = datetime(2024, 1, 10)
        end2 = datetime(2024, 1, 20)
        # Touching ranges are considered overlapping
        assert is_date_range_overlapping(start1, end1, start2, end2) is True


class TestGetTimeAgo:
    """Tests for get_time_ago function."""

    def test_time_ago_minutes(self):
        """Test time ago for minutes."""
        now = get_current_utc()
        dt = now - timedelta(minutes=5)
        result = get_time_ago(dt, now)
        assert "5 minute" in result

    def test_time_ago_hours(self):
        """Test time ago for hours."""
        now = get_current_utc()
        dt = now - timedelta(hours=3)
        result = get_time_ago(dt, now)
        assert "3 hour" in result

    def test_time_ago_days(self):
        """Test time ago for days."""
        now = get_current_utc()
        dt = now - timedelta(days=5)
        result = get_time_ago(dt, now)
        assert "5 day" in result

    def test_time_ago_months(self):
        """Test time ago for months."""
        now = get_current_utc()
        dt = now - timedelta(days=60)
        result = get_time_ago(dt, now)
        assert "month" in result

    def test_time_ago_just_now(self):
        """Test time ago for very recent time."""
        now = get_current_utc()
        dt = now - timedelta(seconds=5)
        result = get_time_ago(dt, now)
        assert result == "just now"


class TestValidateDateRange:
    """Tests for validate_date_range function."""

    def test_valid_date_range(self):
        """Test validating correct date range."""
        start = datetime(2024, 1, 1)
        end = datetime(2024, 12, 31)
        validate_date_range(start, end)  # Should not raise

    def test_invalid_date_range(self):
        """Test validation fails when start is after end."""
        start = datetime(2024, 12, 31)
        end = datetime(2024, 1, 1)
        with pytest.raises(ValueError, match="Start date cannot be after end date"):
            validate_date_range(start, end)

    def test_none_dates_valid(self):
        """Test None dates are valid."""
        validate_date_range(None, None)  # Should not raise
        validate_date_range(datetime(2024, 1, 1), None)  # Should not raise
        validate_date_range(None, datetime(2024, 1, 1))  # Should not raise


class TestGetRelativeTime:
    """Tests for get_relative_time function."""

    def test_relative_time_today(self):
        """Test relative time for today."""
        dt = get_current_utc()
        result = get_relative_time(dt)
        assert result == "today"

    def test_relative_time_yesterday(self):
        """Test relative time for yesterday."""
        dt = get_current_utc() - timedelta(days=1)
        result = get_relative_time(dt)
        assert result == "yesterday"

    def test_relative_time_recent_days(self):
        """Test relative time for recent days (within a week)."""
        dt = get_current_utc() - timedelta(days=3)
        result = get_relative_time(dt)
        assert "3 days ago" in result

    def test_relative_time_older(self):
        """Test relative time for older dates."""
        dt = get_current_utc() - timedelta(days=30)
        result = get_relative_time(dt)
        # Should return formatted date (YYYY-MM-DD format)
        assert "-" in result and len(result) == 10  # Format: YYYY-MM-DD


class TestGetTimeConstant:
    """Tests for get_time_constant function."""

    def test_get_time_constant_one_hour(self):
        """Test getting ONE_HOUR time constant."""
        result = get_time_constant("ONE_HOUR")
        assert result == timedelta(hours=1)

    def test_get_time_constant_one_day(self):
        """Test getting ONE_DAY time constant."""
        result = get_time_constant("ONE_DAY")
        assert result == timedelta(days=1)

    def test_get_time_constant_case_insensitive(self):
        """Test time constant lookup is case insensitive."""
        result = get_time_constant("one_hour")
        assert result == timedelta(hours=1)

    def test_get_time_constant_invalid_raises_error(self):
        """Test getting invalid constant raises KeyError."""
        with pytest.raises(KeyError):
            get_time_constant("INVALID_CONSTANT")
