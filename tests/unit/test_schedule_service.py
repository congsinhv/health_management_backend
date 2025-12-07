
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.schedule import ScheduleService
from app.schemas.schedule import ScheduleCreateRequest, GoalType, ScheduleMode, DayOfWeek, SportsPreferences, BasicInfo, ScheduleConfig
from datetime import datetime, date, time

@pytest.fixture
def mock_pool():
    return AsyncMock()

@pytest.fixture
def service(mock_pool):
    return ScheduleService(mock_pool)

@pytest.mark.asyncio
async def test_create_or_update_schedule_fixed(service):
    # Setup mocks
    service.plan_repo.create = AsyncMock(return_value={"id": 1, "user_id": 1, "status": "active"})
    service.plan_repo.deactivate = AsyncMock(return_value=True)
    service.plan_repo.update_weekly_plan = AsyncMock(return_value={
        "id": 1, "user_id": 1, "goal": "lose", "schedule_mode": "fixed",
        "selected_days": ["monday"], "timezone": "UTC", "weekly_plan": {},
        "status": "active", "created_at": datetime.now(), "updated_at": datetime.now()
    })
    service.notification_repo.create_batch = AsyncMock(return_value=1)

    # Request data
    request = ScheduleCreateRequest(
        basic_info=BasicInfo(height=1.75, weight=70, target_weight=65, goal=GoalType.LOSE),
        schedule=ScheduleConfig(
            mode=ScheduleMode.FIXED,
            selected_days=[DayOfWeek.MONDAY],
            fixed_period={"start_time": "08:00", "end_time": "09:00"}
        ),
        sports=SportsPreferences(predefined=["running"])
    )

    # Call
    response = await service.create_or_update_schedule(1, request)

    # Assertions
    assert response.id == 1
    service.plan_repo.deactivate.assert_called_with(1)
    service.plan_repo.create.assert_called_once()
    service.plan_repo.update_weekly_plan.assert_called_once()
    service.notification_repo.create_batch.assert_called_once()

@pytest.mark.asyncio
async def test_get_active_schedule(service):
    service.plan_repo.get_active_by_user = AsyncMock(return_value={
        "id": 1, "user_id": 1, "goal": "lose", "schedule_mode": "fixed",
        "selected_days": ["monday"], "timezone": "UTC", "weekly_plan": {},
        "status": "active", "created_at": datetime.now(), "updated_at": datetime.now()
    })

    response = await service.get_active_schedule(1)
    assert response.id == 1
    service.plan_repo.get_active_by_user.assert_called_with(1)

@pytest.mark.asyncio
async def test_register_device(service):
    service.device_repo.register = AsyncMock(return_value={
        "id": 1, "device_type": "ios", "device_name": "iPhone", "is_active": True, "last_used_at": datetime.now()
    })

    from app.schemas.schedule import DeviceRegisterRequest
    req = DeviceRegisterRequest(fcm_token="token123456", device_type="ios")

    response = await service.register_device(1, req)
    assert response.id == 1
    service.device_repo.register.assert_called_once()

@pytest.mark.asyncio
async def test_deactivate_schedule(service):
    service.plan_repo.get_active_by_user = AsyncMock(return_value={"id": 1})
    service.notification_repo.delete_by_plan = AsyncMock()
    service.plan_repo.deactivate = AsyncMock(return_value=True)

    result = await service.deactivate_schedule(1)
    assert result is True
    service.plan_repo.get_active_by_user.assert_called_with(1)
    service.notification_repo.delete_by_plan.assert_called_with(1)
    service.plan_repo.deactivate.assert_called_with(1)

@pytest.mark.asyncio
async def test_regenerate_plan(service):
    service.plan_repo.get_active_by_user = AsyncMock(return_value={
        "id": 1, "user_id": 1, "goal": "lose", "schedule_mode": "fixed",
        "selected_days": ["monday"], "timezone": "UTC", "weekly_plan": {},
        "status": "active", "created_at": datetime.now(), "updated_at": datetime.now(),
        "weight_kg": 70, "target_weight_kg": 65, "height_m": 1.75,
        "fixed_start_time": time(8, 0), "fixed_end_time": time(9, 0),
        "flexible_periods": None, "sports_predefined": ["running"], "sports_custom": [],
        "health_warnings": None
    })
    service.notification_repo.delete_by_plan = AsyncMock()
    service.plan_repo.update_weekly_plan = AsyncMock(return_value={
        "id": 1, "user_id": 1, "goal": "lose", "schedule_mode": "fixed",
        "selected_days": ["monday"], "timezone": "UTC",
        "weekly_plan": {
            "monday": {
                "exercise": "Running",
                "duration_minutes": 30,
                "estimated_calories": 200,
                "description": "Run in the park"
            }
        },
        "status": "active", "created_at": datetime.now(), "updated_at": datetime.now(),
        "fixed_start_time": time(8, 0), "fixed_end_time": time(9, 0), "flexible_periods": None
    })
    service.notification_repo.create_batch = AsyncMock()

    response = await service.regenerate_plan(1)
    assert response.id == 1
    service.notification_repo.delete_by_plan.assert_called_with(1)
    service.plan_repo.update_weekly_plan.assert_called_once()
    service.notification_repo.create_batch.assert_called_once()

@pytest.mark.asyncio
async def test_log_exercise_from_notification(service):
    service.notification_repo.get_by_id = AsyncMock(return_value={
        "id": 1, "user_id": 1, "workout_date": date.today(),
        "data": '{"duration_minutes": 30, "estimated_calories": 200}'
    })
    service.exercise_log_repo.create = AsyncMock()

    await service.log_exercise_from_notification(1)
    service.exercise_log_repo.create.assert_called_once()

@pytest.mark.asyncio
async def test_unregister_device(service):
    service.device_repo.deactivate = AsyncMock(return_value=True)
    result = await service.unregister_device(1, "token123")
    assert result is True
    service.device_repo.deactivate.assert_called_with(1, "token123")

@pytest.mark.asyncio
async def test_create_or_update_schedule_flexible(service):
    # Setup mocks
    service.plan_repo.create = AsyncMock(return_value={"id": 1, "user_id": 1, "status": "active"})
    service.plan_repo.deactivate = AsyncMock(return_value=True)
    service.plan_repo.update_weekly_plan = AsyncMock(return_value={
        "id": 1, "user_id": 1, "goal": "lose", "schedule_mode": "flexible",
        "selected_days": ["monday"], "timezone": "UTC", "weekly_plan": {},
        "status": "active", "created_at": datetime.now(), "updated_at": datetime.now(),
        "flexible_periods": {"monday": [{"startTime": "08:00", "endTime": "09:00"}]}
    })
    service.notification_repo.create_batch = AsyncMock(return_value=1)

    # Request data
    request = ScheduleCreateRequest(
        basic_info=BasicInfo(height=1.75, weight=70, target_weight=65, goal=GoalType.LOSE),
        schedule=ScheduleConfig(
            mode=ScheduleMode.FLEXIBLE,
            selected_days=[DayOfWeek.MONDAY],
            flexible_periods={DayOfWeek.MONDAY: [{"start_time": "08:00", "end_time": "09:00"}]}
        ),
        sports=SportsPreferences(predefined=["running"])
    )

    # Call
    response = await service.create_or_update_schedule(1, request)

    # Assertions
    assert response.id == 1
    service.plan_repo.create.assert_called_once()
    # Check that plan_data contains flexible_periods
    call_args = service.plan_repo.create.call_args[0][0]
    assert call_args["schedule_mode"] == "flexible"
    assert "flexible_periods" in call_args
