import pytest
from datetime import datetime, timezone, timedelta, date, time
from app.db.notification import NotificationRepository
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_create_scheduled_notification(
    db_pool, test_user, test_schedule_plan, mock_connection
):
    repo = NotificationRepository(db_pool)

    notify_time = datetime.now(timezone.utc) + timedelta(minutes=30)

    # We need an id for test_schedule_plan if it's a mock result
    plan_id = (
        test_schedule_plan.get("id", 1) if isinstance(test_schedule_plan, dict) else 1
    )

    # Mock return value
    mock_connection.fetchrow.return_value = {
        "id": 1,
        "user_id": test_user.id,
        "status": "pending",
        "scheduled_at": notify_time,
    }

    notification = await repo.create(
        {
            "schedule_plan_id": plan_id,
            "user_id": test_user.id,
            "scheduled_at": notify_time,
            "workout_date": date.today(),
            "workout_day": "monday",
            "workout_start_time": time(7, 0),
            "workout_end_time": time(8, 0),
            "title": "Workout Reminder",
            "body": "Time for your 7:00 AM workout!",
            "data": {"exercise_type": "gym", "duration": 45},
        }
    )

    assert notification["user_id"] == test_user.id
    assert notification["status"] == "pending"
    assert notification["scheduled_at"] == notify_time


@pytest.mark.asyncio
async def test_query_pending_notifications(db_pool, mock_connection):
    repo = NotificationRepository(db_pool)

    due_time = datetime.now(timezone.utc) + timedelta(minutes=2)

    # Mock return value for fetch (list of rows)
    mock_connection.fetch.return_value = [
        {"id": 1, "scheduled_at": due_time, "status": "pending"}
    ]

    # Query notifications due in next 5 minutes
    window_start = datetime.now(timezone.utc)
    window_end = window_start + timedelta(minutes=5)
    pending = await repo.get_pending_in_window(
        window_start=window_start, window_end=window_end
    )

    assert len(pending) == 1
    assert pending[0]["scheduled_at"] == due_time


@pytest.mark.asyncio
async def test_update_notification_status(db_pool, test_user, mock_connection):
    repo = NotificationRepository(db_pool)

    # Mocking execution
    mock_connection.execute.return_value = None

    # Mocking get_notification_by_id
    mock_connection.fetchrow.return_value = {
        "id": 123,
        "status": "sent",
        "cloud_task_name": "task-123",
        "sent_at": datetime.now(timezone.utc),
    }

    await repo.update_status(
        notification_id=123, status="sent", cloud_task_name="task-123"
    )

    updated = await repo.get_by_id(123)
    assert updated["status"] == "sent"
    assert updated["cloud_task_name"] == "task-123"
    assert updated["sent_at"] is not None
