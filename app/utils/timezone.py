"""
Timezone utilities for Vietnam timezone (UTC+7)
"""

from datetime import datetime, timezone, timedelta, time as dt_time

# Vietnam timezone is UTC+7
VIETNAM_TZ = timezone(timedelta(hours=7))


def get_vietnam_now() -> datetime:
    """Get current time in Vietnam timezone (UTC+7) as naive datetime (without timezone info)."""
    now = datetime.now(VIETNAM_TZ)
    # Remove seconds, microseconds and timezone info
    # Return as naive datetime so PostgreSQL won't convert it
    return now.replace(second=0, microsecond=0, tzinfo=None)


def utc_to_vietnam(dt: datetime) -> datetime:
    """Convert UTC datetime to Vietnam timezone."""
    if dt.tzinfo is None:
        # If naive datetime, assume it's UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(VIETNAM_TZ)


def vietnam_to_utc(dt: datetime) -> datetime:
    """Convert Vietnam datetime to UTC."""
    if dt.tzinfo is None:
        # If naive datetime, assume it's Vietnam time
        dt = dt.replace(tzinfo=VIETNAM_TZ)
    return dt.astimezone(timezone.utc)


def format_time_hhmm(time_obj: dt_time) -> str:
    """Format time to HH:MM (without seconds)."""
    if time_obj:
        return time_obj.strftime("%H:%M")
    return None

