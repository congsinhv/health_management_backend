"""
Tests for timezone handling in Smart Reminders.
"""

import pytest
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo


class TestTimezoneConversion:
    """Tests for timezone conversion utilities."""

    def test_vietnam_to_utc_conversion(self):
        """Test converting Vietnam time to UTC."""
        # Vietnam is UTC+7
        vietnam_tz = ZoneInfo("Asia/Ho_Chi_Minh")

        # 7:00 AM Vietnam time
        local_dt = datetime(2025, 1, 15, 7, 0, tzinfo=vietnam_tz)

        # Convert to UTC
        utc_dt = local_dt.astimezone(timezone.utc)

        # Should be midnight UTC (7:00 - 7 hours = 0:00)
        assert utc_dt.hour == 0
        assert utc_dt.minute == 0
        assert utc_dt.tzinfo == timezone.utc

    def test_utc_to_vietnam_conversion(self):
        """Test converting UTC to Vietnam time."""
        vietnam_tz = ZoneInfo("Asia/Ho_Chi_Minh")

        # 12:00 noon UTC
        utc_dt = datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)

        # Convert to Vietnam time
        local_dt = utc_dt.astimezone(vietnam_tz)

        # Should be 7:00 PM Vietnam (12:00 + 7 hours = 19:00)
        assert local_dt.hour == 19
        assert local_dt.minute == 0

    def test_notification_schedule_time_conversion(self):
        """Test notification scheduled_at is properly converted."""
        vietnam_tz = ZoneInfo("Asia/Ho_Chi_Minh")

        # User wants workout at 7:00 AM Vietnam time
        workout_start = time(7, 0)
        workout_date = date(2025, 1, 15)

        # Notification should be 5 minutes before
        notify_time_local = datetime.combine(
            workout_date, time(6, 55), tzinfo=vietnam_tz  # 5 min before 7:00
        )

        # Store in UTC
        notify_time_utc = notify_time_local.astimezone(timezone.utc)

        # Verify UTC time is correct
        expected_utc = datetime(2025, 1, 14, 23, 55, tzinfo=timezone.utc)
        assert notify_time_utc == expected_utc

    def test_batch_processing_window_utc(self):
        """Test batch processing uses UTC for window calculations."""
        # Cloud Scheduler runs in UTC
        now_utc = datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc)

        # 5-minute window
        window_end = now_utc + timedelta(minutes=5)

        # Vietnam notification at 7:00 AM local = 0:00 UTC
        vietnam_tz = ZoneInfo("Asia/Ho_Chi_Minh")
        vietnam_notify = datetime(2025, 1, 15, 7, 0, tzinfo=vietnam_tz)
        vietnam_utc = vietnam_notify.astimezone(timezone.utc)

        # Should be within window
        assert now_utc <= vietnam_utc <= window_end

    def test_different_timezone_same_utc_instant(self):
        """Test same instant in different timezones."""
        vietnam_tz = ZoneInfo("Asia/Ho_Chi_Minh")
        tokyo_tz = ZoneInfo("Asia/Tokyo")  # UTC+9

        # Same instant
        instant_utc = datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)

        # Convert to local times
        vietnam_time = instant_utc.astimezone(vietnam_tz)  # 19:00 (UTC+7)
        tokyo_time = instant_utc.astimezone(tokyo_tz)  # 21:00 (UTC+9)

        # Different local times
        assert vietnam_time.hour == 19
        assert tokyo_time.hour == 21

        # Same instant
        assert vietnam_time == tokyo_time

    def test_date_boundary_crossing(self):
        """Test handling when UTC conversion crosses date boundary."""
        vietnam_tz = ZoneInfo("Asia/Ho_Chi_Minh")

        # Early morning Vietnam (6:00 AM on Jan 15)
        local_dt = datetime(2025, 1, 15, 6, 0, tzinfo=vietnam_tz)

        # Convert to UTC
        utc_dt = local_dt.astimezone(timezone.utc)

        # Should be 23:00 on Jan 14 UTC (crosses date boundary)
        assert utc_dt.day == 14
        assert utc_dt.hour == 23
        assert utc_dt.month == 1


class TestWeeklyScheduleTimezone:
    """Tests for weekly schedule timezone handling."""

    def test_next_workout_day_calculation(self):
        """Test calculating next workout day respects timezone."""
        vietnam_tz = ZoneInfo("Asia/Ho_Chi_Minh")

        # Current time: Saturday 23:00 UTC = Sunday 6:00 Vietnam
        now_utc = datetime(2025, 1, 18, 23, 0, tzinfo=timezone.utc)
        now_vietnam = now_utc.astimezone(vietnam_tz)

        # In Vietnam it's already Sunday
        assert now_vietnam.weekday() == 6  # Sunday

        # In UTC it's still Saturday
        assert now_utc.weekday() == 5  # Saturday

    def test_selected_days_mapping(self):
        """Test selected days are stored consistently."""
        # Days are stored as lowercase strings
        selected_days = ["monday", "wednesday", "friday"]

        # Map to Python weekday numbers (0=Monday, 6=Sunday)
        day_mapping = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }

        weekday_numbers = [day_mapping[day] for day in selected_days]
        assert weekday_numbers == [0, 2, 4]


class TestDSTHandling:
    """Tests for Daylight Saving Time handling."""

    def test_vietnam_no_dst(self):
        """Vietnam doesn't have DST, so offset is always +7."""
        vietnam_tz = ZoneInfo("Asia/Ho_Chi_Minh")

        # Summer date
        summer = datetime(2025, 7, 1, 12, 0, tzinfo=vietnam_tz)
        summer_utc = summer.astimezone(timezone.utc)

        # Winter date
        winter = datetime(2025, 1, 1, 12, 0, tzinfo=vietnam_tz)
        winter_utc = winter.astimezone(timezone.utc)

        # Both should have same offset (7 hours)
        assert (
            summer.hour - summer_utc.hour == 7 or summer.hour - summer_utc.hour == -17
        )
        assert (
            winter.hour - winter_utc.hour == 7 or winter.hour - winter_utc.hour == -17
        )

    def test_us_timezone_dst_transition(self):
        """Test handling US timezone with DST (for travelers)."""
        ny_tz = ZoneInfo("America/New_York")

        # Summer (EDT = UTC-4)
        summer = datetime(2025, 7, 1, 7, 0, tzinfo=ny_tz)
        summer_utc = summer.astimezone(timezone.utc)
        assert summer_utc.hour == 11  # 7 AM EDT = 11 AM UTC

        # Winter (EST = UTC-5)
        winter = datetime(2025, 1, 1, 7, 0, tzinfo=ny_tz)
        winter_utc = winter.astimezone(timezone.utc)
        assert winter_utc.hour == 12  # 7 AM EST = 12 PM UTC


class TestNotificationScheduling:
    """Tests for notification scheduling with timezones."""

    def test_schedule_notification_5min_before(self):
        """Test notifications are scheduled 5 minutes before workout."""
        vietnam_tz = ZoneInfo("Asia/Ho_Chi_Minh")

        # Workout at 7:00 AM Vietnam
        workout_time = datetime(2025, 1, 15, 7, 0, tzinfo=vietnam_tz)

        # Notification should be at 6:55 AM Vietnam
        notification_time = workout_time - timedelta(minutes=5)

        assert notification_time.hour == 6
        assert notification_time.minute == 55

        # In UTC
        notification_utc = notification_time.astimezone(timezone.utc)
        assert notification_utc.hour == 23  # Previous day
        assert notification_utc.minute == 55

    def test_weekly_notifications_utc_storage(self):
        """Test weekly notifications are stored in UTC."""
        vietnam_tz = ZoneInfo("Asia/Ho_Chi_Minh")

        # Workout schedule: Monday 7:00 AM Vietnam
        workout_day = "monday"
        workout_time = time(7, 0)
        user_timezone = "Asia/Ho_Chi_Minh"

        # Find next Monday from a known date
        base_date = date(2025, 1, 13)  # This is a Monday
        workout_datetime = datetime.combine(base_date, workout_time, tzinfo=vietnam_tz)

        # Notification time (5 min before) in UTC
        notification_utc = (workout_datetime - timedelta(minutes=5)).astimezone(
            timezone.utc
        )

        # Store this in DB
        stored_scheduled_at = notification_utc

        # Verify it's timezone-aware UTC
        assert stored_scheduled_at.tzinfo == timezone.utc

        # Verify correct time
        assert stored_scheduled_at.day == 12  # Day before in UTC
        assert stored_scheduled_at.hour == 23
        assert stored_scheduled_at.minute == 55


@pytest.mark.asyncio
async def test_scheduler_function_logic():
    """Test the actual scheduler function logic."""
    from app.services.schedule.scheduler import schedule_notifications_for_week

    tz_name = "Asia/Ho_Chi_Minh"
    fixed_start = time(7, 0)

    notifications = schedule_notifications_for_week(
        plan_id=1,
        user_id=1,
        timezone=tz_name,
        selected_days=["monday"],
        schedule_mode="fixed",
        fixed_start_time=fixed_start,
        fixed_end_time=time(8, 0),
        weekly_plan={"monday": {"exercise": "run"}},
    )

    assert len(notifications) >= 1
    scheduled_at = notifications[0]["scheduled_at"]

    # Verify it is UTC
    assert str(scheduled_at.tzinfo) == "UTC" or scheduled_at.tzinfo == timezone.utc

    # Verify local time is 6:55 AM
    local_time = scheduled_at.astimezone(ZoneInfo(tz_name))
    assert local_time.hour == 6
    assert local_time.minute == 55
