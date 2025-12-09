"""
Notification scheduling logic with timezone handling.
"""

from datetime import datetime, timedelta, time, date
from typing import List, Dict, Any
from zoneinfo import ZoneInfo

import logging

logger = logging.getLogger(__name__)


def schedule_notifications_for_week(
    plan_id: int,
    user_id: int,
    timezone: str,
    selected_days: List[str],
    schedule_mode: str,
    fixed_start_time: time = None,
    fixed_end_time: time = None,
    flexible_periods: Dict = None,
    weekly_plan: Dict = None,
) -> List[Dict[str, Any]]:
    """Generate notification records for the upcoming week."""

    user_tz = ZoneInfo(timezone)
    utc_tz = ZoneInfo("UTC")
    now = datetime.now(user_tz)
    today = now.date()

    notifications = []

    for day_name in selected_days:
        # Find next occurrence of this day
        next_date = _find_next_weekday(today, day_name)

        # Skip if in the past
        if next_date < today:
            next_date += timedelta(days=7)

        # Get times for this day
        if schedule_mode == "fixed":
            start_time = fixed_start_time
            end_time = fixed_end_time
        else:
            periods = flexible_periods.get(day_name, [])
            if not periods:
                continue
            period = periods[0]
            start_time = _parse_time(period["startTime"])
            end_time = _parse_time(period["endTime"])

        # Combine date + time in user timezone
        local_workout_dt = datetime.combine(next_date, start_time, tzinfo=user_tz)

        # If workout already passed today, schedule for next week
        if local_workout_dt < now:
            local_workout_dt += timedelta(days=7)
            next_date += timedelta(days=7)

        # Get workout info from AI plan
        workout_info = weekly_plan.get(day_name, {}) if weekly_plan else {}
        exercise = workout_info.get("exercise", "Workout")
        duration = workout_info.get("duration_minutes", 60)
        calories = workout_info.get("estimated_calories", 300)

        # Generate 2 notifications: 5 min before and at start time
        notification_times = [
            (
                local_workout_dt - timedelta(minutes=5),
                f"5 phút trước khi bắt đầu {exercise}!",
                "reminder",
            ),
            (local_workout_dt, f"Bắt đầu {exercise}!", "start"),
        ]

        for local_notify_dt, title, notif_type in notification_times:
            # Skip if notification time is in the past
            if local_notify_dt < now:
                logger.debug(
                    f"Skipping past notification for {day_name} at {local_notify_dt}"
                )
                continue

            utc_notify_dt = local_notify_dt.astimezone(utc_tz)

            notifications.append(
                {
                    "schedule_plan_id": plan_id,
                    "user_id": user_id,
                    "scheduled_at": utc_notify_dt,
                    "workout_date": next_date,
                    "workout_day": day_name,
                    "workout_start_time": start_time,
                    "workout_end_time": end_time,
                    "title": title,
                    "body": f"Thời gian: {duration} phút · Calories: ~{calories} calo",
                    "data": {
                        "exercise": exercise,
                        "duration_minutes": duration,
                        "estimated_calories": calories,
                        "workout_date": next_date.isoformat(),
                        "notification_type": notif_type,
                    },
                }
            )

    logger.info(f"Scheduled {len(notifications)} notifications for plan {plan_id}")
    return notifications


def _find_next_weekday(start_date: date, day_name: str) -> date:
    """Find next occurrence of weekday."""
    days = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    target = days.get(day_name.lower(), 0)
    current = start_date.weekday()
    days_ahead = target - current
    if days_ahead < 0:
        days_ahead += 7
    return start_date + timedelta(days=days_ahead)


def _parse_time(time_str: str) -> time:
    """Parse time string to time object."""
    parts = str(time_str).split(":")
    return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
