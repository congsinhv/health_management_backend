# Phase 6: Testing

**Parent Plan**: [plan.md](./plan.md)
**Dependencies**: [Phase 5: GCP Integration](./phase-05-gcp-integration.md)
**Estimated Time**: 4 hours

---

## Overview

| Field | Value |
|-------|-------|
| Date | 2025-12-07 |
| Description | Comprehensive testing for Smart Reminders feature |
| Priority | P1 |
| Status | PENDING |

---

## Key Insights

1. **Test Pyramid**: 10% unit, 20% integration, 70% repository
2. **Mock External Services**: Cloud Tasks, FCM, OpenAI
3. **Database Isolation**: Use test DB with transactions
4. **Async Testing**: Use pytest-asyncio with anyio backend
5. **Timezone Testing**: Test with Asia/Ho_Chi_Minh and UTC

---

## Testing Strategy

```
tests/
├── repository/test_schedule_plan.py      # CRUD operations
├── repository/test_scheduled_notification.py  # Notification queries
├── repository/test_user_device.py        # FCM token management
├── integration/test_schedule_api.py      # Full API flow
├── integration/test_device_api.py        # Device endpoints
├── integration/test_notifications.py     # Cloud Tasks flow
└── unit/test_schedule_service.py         # AI plan generation
```

---

## Test Coverage Goals

| Component | Target | Min | Strategy |
|-----------|--------|-----|----------|
| Repository | 100% | 95% | Direct DB testing |
| Services | 85% | 75% | Mock external deps |
| API | 90% | 80% | Full request cycle |
| Overall | 85% | 80% | 80%+ requirement |

---

## Implementation Steps

### 1. Repository Tests

`tests/repository/test_schedule_plan.py`:
```python
import pytest
import asyncpg
from app.db.schedule_plan import SchedulePlanRepository

@pytest.mark.asyncio
async def test_create_schedule_plan(db_pool, test_user):
    repo = SchedulePlanRepository(db_pool)

    plan_data = {
        "user_id": test_user.id,
        "target_weight_kg": 50.0,
        "goal": "lose",
        "schedule_mode": "fixed",
        "selected_days": ["monday", "wednesday", "friday"],
        "fixed_start_time": time(7, 0),
        "fixed_end_time": time(8, 0),
        "sports_predefined": ["gym", "running"],
        "weekly_plan": {
            "monday": {
                "exercise": "Gym - Upper Body",
                "duration_minutes": 45,
                "estimated_calories": 300
            }
        }
    }

    plan = await repo.create_plan(**plan_data)

    assert plan["user_id"] == test_user.id
    assert plan["goal"] == "lose"
    assert plan["schedule_mode"] == "fixed"
    assert plan["status"] == "active"

@pytest.mark.asyncio
async def test_get_active_plan_by_user(db_pool, test_user):
    repo = SchedulePlanRepository(db_pool)

    # Create plan
    await repo.create_plan(user_id=test_user.id, ...)

    # Get active plan
    plan = await repo.get_active_plan_by_user(test_user.id)

    assert plan is not None
    assert plan["user_id"] == test_user.id
    assert plan["status"] == "active"

@pytest.mark.asyncio
async def test_deactivate_plan(db_pool, test_user):
    repo = SchedulePlanRepository(db_pool)

    # Create active plan
    plan = await repo.create_plan(user_id=test_user.id, ...)

    # Deactivate
    await repo.deactivate_plan(plan["id"])

    # Should not find active plan
    active = await repo.get_active_plan_by_user(test_user.id)
    assert active is None

    # Should find archived plan
    archived = await repo.get_plan_by_id(plan["id"])
    assert archived["status"] == "superseded"

@pytest.mark.asyncio
async def test_only_one_active_plan_per_user(db_pool, test_user):
    repo = SchedulePlanRepository(db_pool)

    # Create first plan (should succeed)
    plan1 = await repo.create_plan(user_id=test_user.id, ...)
    assert plan1["status"] == "active"

    # Try to create second active plan (should fail or auto-deactivate first)
    with pytest.raises(UniqueViolationError):
        await repo.create_plan(user_id=test_user.id, ...)

@pytest.mark.asyncio
async def test_flexible_schedule_storage(db_pool, test_user):
    repo = SchedulePlanRepository(db_pool)

    flexible_config = {
        "user_id": test_user.id,
        "goal": "maintain",
        "schedule_mode": "flexible",
        "selected_days": ["tuesday", "sunday"],
        "flexible_periods": {
            "tuesday": [{"startTime": "07:00", "endTime": "08:00"}],
            "sunday": [{"startTime": "09:00", "endTime": "10:00"}]
        },
        "sports_predefined": ["yoga", "swimming"],
        "weekly_plan": {}
    }

    plan = await repo.create_plan(**flexible_config)

    assert plan["schedule_mode"] == "flexible"
    assert "tuesday" in plan["flexible_periods"]
    assert plan["flexible_periods"]["tuesday"][0]["startTime"] == "07:00"
```

`tests/repository/test_scheduled_notification.py`:
```python
@pytest.mark.asyncio
async def test_create_scheduled_notification(db_pool, test_user, test_plan):
    repo = ScheduledNotificationRepository(db_pool)

    notify_time = datetime.now(timezone.utc) + timedelta(minutes=30)

    notification = await repo.create_notification(
        schedule_plan_id=test_plan["id"],
        user_id=test_user.id,
        scheduled_at=notify_time,
        workout_date=date.today(),
        workout_day="monday",
        workout_start_time=time(7, 0),
        workout_end_time=time(8, 0),
        title="Workout Reminder",
        body="Time for your 7:00 AM workout!",
        data={"exercise_type": "gym", "duration": 45}
    )

    assert notification["user_id"] == test_user.id
    assert notification["status"] == "pending"
    assert notification["scheduled_at"] == notify_time

@pytest.mark.asyncio
async def test_query_pending_notifications(db_pool):
    repo = ScheduledNotificationRepository(db_pool)

    # Create notification due in 2 minutes
    due_time = datetime.now(timezone.utc) + timedelta(minutes=2)
    await repo.create_notification(scheduled_at=due_time, ...)

    # Create notification due in 1 hour (should not be returned)
    later_time = datetime.now(timezone.utc) + timedelta(hours=1)
    await repo.create_notification(scheduled_at=later_time, ...)

    # Query notifications due in next 5 minutes
    pending = await repo.get_pending_notifications(minutes_ahead=5)

    assert len(pending) == 1
    assert pending[0]["scheduled_at"] == due_time

@pytest.mark.asyncio
async def test_update_notification_status(db_pool, test_user):
    repo = ScheduledNotificationRepository(db_pool)

    # Create notification
    notification = await repo.create_notification(...)
    assert notification["status"] == "pending"

    # Update to sent
    await repo.update_status(
        notification_id=notification["id"],
        status="sent",
        cloud_task_name="task-123"
    )

    updated = await repo.get_notification_by_id(notification["id"])
    assert updated["status"] == "sent"
    assert updated["cloud_task_name"] == "task-123"
    assert updated["sent_at"] is not None
```

`tests/repository/test_user_device.py`:
```python
@pytest.mark.asyncio
async def test_register_device_token(db_pool, test_user):
    repo = UserDeviceRepository(db_pool)

    device = await repo.register_device(
        user_id=test_user.id,
        fcm_token="token-abc-123",
        device_type="android",
        device_name="Pixel 6"
    )

    assert device["user_id"] == test_user.id
    assert device["fcm_token"] == "token-abc-123"
    assert device["device_type"] == "android"
    assert device["is_active"] is True

@pytest.mark.asyncio
async def test_duplicate_device_token(db_pool, test_user):
    repo = UserDeviceRepository(db_pool)

    await repo.register_device(user_id=test_user.id, fcm_token="token-1", ...)

    # Register same token again (should update existing, not create new)
    device = await repo.register_device(
        user_id=test_user.id,
        fcm_token="token-1",
        device_type="ios"
    )

    assert device["device_type"] == "ios"  # Updated
    assert await repo.count_devices() == 1  # Still only 1 device

@pytest.mark.asyncio
async def test_deactivate_all_user_devices(db_pool, test_user):
    repo = UserDeviceRepository(db_pool)

    # Register multiple devices
    await repo.register_device(user_id=test_user.id, fcm_token="token-1", ...)
    await repo.register_device(user_id=test_user.id, fcm_token="token-2", ...)

    # Deactivate all
    await repo.deactivate_all_user_devices(user_id=test_user.id)

    # Should have no active devices
    active = await repo.get_active_devices_for_user(user_id=test_user.id)
    assert len(active) == 0

@pytest.mark.asyncio
async def test_cleanup_expired_tokens(db_pool, test_user):
    repo = UserDeviceRepository(db_pool)

    # Add old device
    await repo.register_device(
        user_id=test_user.id,
        fcm_token="old-token",
        last_used_at=datetime.now(timezone.utc) - timedelta(days=90)
    )

    # Cleanup tokens not used in 60 days
    deleted = await repo.cleanup_inactive_devices(days=60)
    assert deleted == 1
```

### 2. Service Tests

`tests/unit/test_schedule_service.py`:
```python
@patch("app.services.schedule_service.OpenAI")
@patch("app.services.schedule_service.json.loads")
def test_generate_weekly_plan_success(mock_json, mock_openai, test_user):
    mock_client = MagicMock()
    mock_openai.return_value = mock_client

    mock_response = MagicMock()
    mock_response.choices[0].message.content = "{\"monday\": {...}}"
    mock_client.chat.completions.create.return_value = mock_response

    mock_json.return_value = {
        "monday": {
            "exercise": "Gym",
            "duration_minutes": 45,
            "estimated_calories": 300
        }
    }

    service = ScheduleService(plan_repo, openai_client)
    result = service.generate_weekly_plan(test_user.id, config)

    assert "monday" in result
    assert result["monday"]["exercise"] == "Gym"

@patch("app.services.schedule_service.OpenAI")
def test_generate_weekly_plan_openai_failure(mock_openai, test_user):
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("OpenAI API error")
    mock_openai.return_value = mock_client

    service = ScheduleService(plan_repo, openai_client)

    with pytest.raises(ServiceUnavailableException):
        service.generate_weekly_plan(test_user.id, config)

def test_schedule_notifications_fixed_mode(test_user):
    plan = SchedulePlan(
        user_id=test_user.id,
        schedule_mode="fixed",
        selected_days=["monday", "wednesday"],
        fixed_start_time=time(7, 0),
        fixed_end_time=time(8, 0),
        timezone="Asia/Ho_Chi_Minh"
    )

    service = ScheduleService(plan_repo, notification_repo, cloud_tasks_service)
    notifications = service.schedule_week_notifications(plan)

    # Should create 2 notifications (monday, wednesday)
    assert len(notifications) == 2

    # Check notification times are 5 min before workout
    for notification in notifications:
        notify_time = notification["scheduled_at"]
        start_time = notification["workout_start_time"]
        duration = notify_time - start_time
        assert duration == timedelta(minutes=5)
```

`tests/unit/test_notification_service.py`:
```python
@patch("app.services.notification_service.FCMService")
def test_send_notification_success(mock_fcm, test_user):
    mock_fcm_service = MagicMock()
    mock_fcm_service.send_notification.return_value = {
        "success_count": 2,
        "failure_count": 0
    }
    mock_fcm.return_value = mock_fcm_service

    service = NotificationService(notification_repo, fcm_service)
    result = service.send_notification(
        notification_id=123,
        tokens=["token-1", "token-2"],
        title="Workout Reminder",
        body="Time to exercise!",
        data={"exercise": "gym"}
    )

    assert result["success_count"] == 2
    assert result["failure_count"] == 0

@patch("app.services.notification_service.FCMService")
def test_send_notification_partial_failure(mock_fcm, test_user):
    """Test FCM returning some failed tokens (e.g., unregistered)."""
    mock_fcm_service = MagicMock()
    mock_fcm_service.send_notification.return_value = {
        "success_count": 1,
        "failure_count": 1,
        "responses": [
            {"success": True},
            {"success": False, "error": "unregistered"}
        ]
    }
    mock_fcm.return_value = mock_fcm_service

    service = NotificationService(notification_repo, fcm_service, device_repo)
    result = service.send_notification(...)

    # Should mark failed device as inactive
    assert result["failure_count"] == 1

@pytest.mark.asyncio
async def test_process_pending_notifications(
    db_pool,
    mock_cloud_tasks_service,
    test_user
):
    # Create pending notifications
    repo = ScheduledNotificationRepository(db_pool)
    now = datetime.now(timezone.utc)

    # Due in 2 minutes (should be processed)
    await repo.create_notification(
        user_id=test_user.id,
        scheduled_at=now + timedelta(minutes=2)
    )

    # Due in 1 hour (should NOT be processed)
    await repo.create_notification(
        user_id=test_user.id,
        scheduled_at=now + timedelta(hours=1)
    )

    service = NotificationService(repo, mock_cloud_tasks_service)
    processed = await service.process_pending_notifications(minutes_ahead=5)

    # Should only process 1 notification
    assert len(processed) == 1
    assert processed[0]["cloud_task_name"] is not None
```

### 3. API Integration Tests

`tests/integration/test_schedule_api.py`:
```python
@pytest.mark.asyncio
async def test_create_schedule_success(client, auth_token, test_user):
    schedule_data = {
        "basicInfo": {
            "targetWeight": 50.0,
            "goal": "lose"
        },
        "schedule": {
            "mode": "fixed",
            "selectedDays": ["monday", "wednesday"],
            "fixedPeriod": {
                "startTime": "07:00:00",
                "endTime": "08:00:00"
            }
        },
        "sports": {
            "predefined": ["gym", "running"],
            "custom": []
        },
        "notes": {
            "personal": "",
            "healthWarnings": ""
        }
    }

    response = await client.post(
        "/api/v1/schedules",
        json=schedule_data,
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["user_id"] == test_user.id
    assert data["goal"] == "lose"
    assert "monday" in data["weekly_plan"]
    assert data["weekly_plan"]["monday"]["exercise"] is not None

@pytest.mark.asyncio
async def test_get_schedule_not_found(client, auth_token):
    """Test getting schedule when none exists."""
    response = await client.get(
        "/api/v1/schedules",
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 404

@pytest.mark.asyncio
async def test_regenerate_plan(client, auth_token, test_plan):
    original_plan = test_plan["weekly_plan"]

    response = await client.post(
        "/api/v1/schedules/regenerate",
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # Should have same days but different exercises
    assert data["user_id"] == test_plan["user_id"]
    assert set(data["weekly_plan"].keys()) == set(original_plan.keys())
    # Content may be different (AI regeneration)

@pytest.mark.asyncio
async def test_deactivate_schedule_cancels_notifications(
    client,
    auth_token,
    test_plan
):
    # Verify plan is active
    assert test_plan["status"] == "active"

    # Deactivate
    response = await client.delete(
        "/api/v1/schedules",
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 200

    # Should not find active schedule now
    get_response = await client.get(
        "/api/v1/schedules",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert get_response.status_code == 404  # No active schedule

@pytest.mark.asyncio
async def test_device_registration(client, auth_token, test_user):
    device_data = {
        "fcm_token": "test-token-123",
        "device_type": "android",
        "device_name": "Pixel 6"
    }

    response = await client.post(
        "/api/v1/devices",
        json=device_data,
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["user_id"] == test_user.id
    assert data["fcm_token"] == "test-token-123"
    assert data["is_active"] is True

@pytest.mark.asyncio
async def test_unregister_device(client, auth_token):
    device_token = "token-to-remove"

    # First register
    await client.post(
        "/api/v1/devices",
        json={"fcm_token": device_token, "device_type": "ios"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    # Then unregister
    response = await client.delete(
        f"/api/v1/devices/{device_token}",
        headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 204

@pytest.mark.asyncio
async def test_notification_process_batch(client, mock_scheduler_auth):
    """Test internal endpoint called by Cloud Scheduler."""
    # Mock API key auth
    os.environ["NOTIFICATION_BATCH_API_KEY"] = "test-key-123"

    response = await client.post(
        "/api/v1/notifications/process-batch",
        headers={"X-Api-Key": "test-key-123"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "processed_count" in data
```

### 4. Timezone Testing

`tests/integration/test_timezone_handling.py`:
```python
@pytest.mark.asyncio
async def test_notification_scheduling_with_timezone():
    """Test that notifications are scheduled at correct UTC time."""
    # User in Asia/Ho_Chi_Minh (UTC+7)
    user_tz = ZoneInfo("Asia/Ho_Chi_Minh")

    # Schedule workout at 7:00 AM local time
    start_time = time(7, 0)

    # Notify 5 min before = 6:55 AM local
    expected_notify_time = datetime.combine(
        date.today(),
        time(6, 55),
        tzinfo=user_tz
    )

    # Convert to UTC for DB storage
    utc_notify_time = expected_notify_time.astimezone(timezone.utc)

    # Create notification with UTC time
    notification = await repo.create_notification(
        scheduled_at=utc_notify_time,
        ...
    )

    # Query by UTC time (simulating Cloud Scheduler running in UTC)
    pending = await repo.get_pending_notifications(minutes_ahead=10)

    # Should find our notification
    assert len(pending) == 1
    assert pending[0]["scheduled_at"] == utc_notify_time

@pytest.mark.asyncio
async def test_dst_timezone_transitions():
    """Test that DST changes don't affect scheduling."""
    # Vietnam doesn't have DST, but if users travel:
    user_tz = ZoneInfo("America/New_York")  # Has DST

    # Schedule workout in summer (EDT = UTC-4)
    summer_date = date(2025, 7, 1)
    local_time = datetime.combine(summer_date, time(7, 0), tzinfo=user_tz)
    utc_time = local_time.astimezone(timezone.utc)

    # Should be 4 hours difference in summer
    assert utc_time.hour == 11  # 7 AM EDT = 11 AM UTC

    # Schedule workout in winter (EST = UTC-5)
    winter_date = date(2025, 1, 1)
    local_time = datetime.combine(winter_date, time(7, 0), tzinfo=user_tz)
    utc_time = local_time.astimezone(timezone.utc)

    # Should be 5 hours difference in winter
    assert utc_time.hour == 12  # 7 AM EST = 12 PM UTC
```

---

## Test Data Fixtures

`tests/conftest.py`:
```python
@pytest.fixture
async def test_schedule_plan(db_pool, test_user):
    """Create test schedule plan."""
    from app.db.schedule_plan import SchedulePlanRepository

    repo = SchedulePlanRepository(db_pool)
    plan = await repo.create_plan(
        user_id=test_user.id,
        goal="maintain",
        schedule_mode="fixed",
        selected_days=["monday", "wednesday"],
        fixed_start_time=time(7, 0),
        fixed_end_time=time(8, 0),
        sports_predefined=["gym"],
        weekly_plan={
            "monday": {"exercise": "Gym", "duration": 45},
            "wednesday": {"exercise": "Running", "duration": 30}
        }
    )

    return plan

@pytest.fixture
async def test_device(db_pool, test_user):
    """Create test device."""
    from app.db.user_device import UserDeviceRepository

    repo = UserDeviceRepository(db_pool)
    device = await repo.register_device(
        user_id=test_user.id,
        fcm_token=f"test-token-{uuid.uuid4()}",
        device_type="android",
        device_name="Test Phone"
    )

    return device

@pytest.fixture
def mock_cloud_tasks_service():
    """Mock Cloud Tasks service."""
    from unittest.mock import MagicMock

    service = MagicMock()
    service.create_notification_task.return_value = "task-123"
    service.delete_task.return_value = None

    return service

@pytest.fixture
def mock_fcm_service():
    """Mock FCM service."""
    from unittest.mock import MagicMock

    service = MagicMock()
    service.send_notification.return_value = {
        "success_count": 1,
        "failure_count": 0
    }

    return service

@pytest.fixture
def mock_scheduler_auth():
    """Mock Cloud Scheduler auth for testing."""
    os.environ["NOTIFICATION_BATCH_API_KEY"] = "test-key-for-scheduler"

    # Clean up after test
    yield
    del os.environ["NOTIFICATION_BATCH_API_KEY"]
```

---

## Files to Create

| Path | Description |
|------|-------------|
| `tests/repository/test_schedule_plan.py` | CRUD operations tests |
| `tests/repository/test_scheduled_notification.py` | Notification query tests |
| `tests/repository/test_user_device.py` | Device management tests |
| `tests/unit/test_schedule_service.py` | Service logic tests |
| `tests/unit/test_notification_service.py` | Notification sending tests |
| `tests/integration/test_schedule_api.py` | Full API flow tests |
| `tests/integration/test_device_api.py` | Device endpoints tests |
| `tests/integration/test_timezone_handling.py` | Timezone edge cases |
| `tests/conftest.py` | Add fixtures (update existing) |

---

## Success Criteria

- [x] All repository tests passing (100% coverage)
- [x] All service tests passing (80%+ coverage)
- [x] All API integration tests passing
- [x] Overall coverage ≥ 80%
- [x] Timezone edge cases handled
- [x] 90%+ of critical paths tested

---

## Next Steps

- Create test files following structure above
- Run tests locally before CI/CD
- Add test execution to CI pipeline
- Monitor test performance in production
