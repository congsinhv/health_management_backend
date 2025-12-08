import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.schedule.service import ScheduleService
from app.schemas.schedule import (
    ScheduleCreateRequest,
    BasicInfo,
    ScheduleConfig,
    SportsPreferences,
    ScheduleNotes,
    ScheduleMode,
    GoalType,
    DayOfWeek,
)
from app.exceptions import ServiceUnavailableException, ResourceNotFoundException
from datetime import datetime, date, time


@pytest.fixture
def mock_pool():
    return AsyncMock()


@pytest.fixture
def service(mock_pool):
    s = ScheduleService(mock_pool)
    s.plan_repo = AsyncMock()
    s.notification_repo = AsyncMock()
    s.device_repo = AsyncMock()
    s.exercise_log_repo = AsyncMock()
    return s


def create_schedule_request():
    return ScheduleCreateRequest(
        basic_info=BasicInfo(
            height=1.75, weight=70, target_weight=65, goal=GoalType.LOSE
        ),
        schedule=ScheduleConfig(
            mode=ScheduleMode.FIXED,
            selected_days=[DayOfWeek.MONDAY],
            fixed_period={"start_time": "08:00", "end_time": "09:00"},
        ),
        sports=SportsPreferences(predefined=["running"]),
        timezone="UTC",
    )


@pytest.mark.asyncio
async def test_create_or_update_schedule_fixed(service):
    # Mock returns
    service.plan_repo.create.return_value = {"id": 1}
    service.plan_repo.update_weekly_plan.return_value = {
        "id": 1,
        "user_id": 1,
        "goal": "lose",
        "schedule_mode": "fixed",
        "selected_days": ["monday"],
        "timezone": "UTC",
        "weekly_plan": {},
        "status": "active",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }

    request = create_schedule_request()

    # Patch external functions
    with patch(
        "app.services.schedule.service.generate_weekly_plan", new_callable=AsyncMock
    ) as mock_gen, patch(
        "app.services.schedule.service.schedule_notifications_for_week"
    ) as mock_sched:
        mock_gen.return_value = {"monday": {"exercise": "run"}}
        mock_sched.return_value = [{"title": "Run"}]

        response = await service.create_or_update_schedule(1, request)

        assert response.id == 1
        service.plan_repo.deactivate.assert_called_with(1)
        service.plan_repo.create.assert_called_once()
        service.notification_repo.create_batch.assert_called_once()
        mock_gen.assert_called_once()
        mock_sched.assert_called_once()


@pytest.mark.asyncio
async def test_create_or_update_schedule_openai_failure(service):
    service.plan_repo.create.return_value = {"id": 1}
    request = create_schedule_request()

    with patch(
        "app.services.schedule.service.generate_weekly_plan", new_callable=AsyncMock
    ) as mock_gen:
        mock_gen.side_effect = Exception("OpenAI Error")

        with pytest.raises(Exception):
            await service.create_or_update_schedule(1, request)


@pytest.mark.asyncio
async def test_get_active_schedule(service):
    service.plan_repo.get_active_by_user.return_value = {
        "id": 1,
        "user_id": 1,
        "goal": "lose",
        "schedule_mode": "fixed",
        "selected_days": ["monday"],
        "timezone": "UTC",
        "weekly_plan": {},
        "status": "active",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }

    response = await service.get_active_schedule(1)
    assert response.id == 1
    service.plan_repo.get_active_by_user.assert_called_with(1)


@pytest.mark.asyncio
async def test_register_device(service):
    service.device_repo.register.return_value = {
        "id": 1,
        "device_type": "ios",
        "device_name": "iPhone",
        "is_active": True,
        "last_used_at": datetime.now(),
    }

    from app.schemas.schedule import DeviceRegisterRequest

    req = DeviceRegisterRequest(fcm_token="a" * 100, device_type="ios")

    response = await service.register_device(1, req)
    assert response.id == 1
    service.device_repo.register.assert_called_once()


@pytest.mark.asyncio
async def test_deactivate_schedule(service):
    service.plan_repo.get_active_by_user.return_value = {"id": 1}
    service.plan_repo.deactivate.return_value = True

    result = await service.deactivate_schedule(1)
    assert result is True
    service.notification_repo.delete_by_plan.assert_called_with(1)


@pytest.mark.asyncio
async def test_regenerate_plan(service):
    service.plan_repo.get_active_by_user.return_value = {
        "id": 1,
        "user_id": 1,
        "goal": "lose",
        "schedule_mode": "fixed",
        "selected_days": ["monday"],
        "timezone": "UTC",
        "weekly_plan": {},
        "status": "active",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "weight_kg": 70,
        "target_weight_kg": 65,
        "height_m": 1.75,
        "fixed_start_time": time(8, 0),
        "fixed_end_time": time(9, 0),
        "flexible_periods": None,
        "sports_predefined": ["running"],
        "sports_custom": [],
        "health_warnings": None,
    }

    service.plan_repo.update_weekly_plan.return_value = {
        "id": 1,
        "user_id": 1,
        "goal": "lose",
        "schedule_mode": "fixed",
        "selected_days": ["monday"],
        "timezone": "UTC",
        "weekly_plan": {},
        "status": "active",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "fixed_start_time": time(8, 0),
        "fixed_end_time": time(9, 0),
        "flexible_periods": None,
        "sports_predefined": ["running"],
        "sports_custom": [],
        "health_warnings": None,
    }

    with patch(
        "app.services.schedule.service.generate_weekly_plan", new_callable=AsyncMock
    ) as mock_gen, patch(
        "app.services.schedule.service.schedule_notifications_for_week"
    ) as mock_sched:
        mock_gen.return_value = {}
        mock_sched.return_value = []

        await service.regenerate_plan(1)

        mock_gen.assert_called_once()
        mock_sched.assert_called_once()
        service.plan_repo.update_weekly_plan.assert_called_once()


@pytest.mark.asyncio
async def test_log_exercise_from_notification(service):
    service.notification_repo.get_by_id.return_value = {
        "id": 1,
        "user_id": 1,
        "workout_date": date.today(),
        "data": '{"duration_minutes": 30, "estimated_calories": 200}',
    }

    await service.log_exercise_from_notification(1)
    service.exercise_log_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_unregister_device(service):
    service.device_repo.deactivate.return_value = True
    await service.unregister_device(1, "token")
    service.device_repo.deactivate.assert_called_with(1, "token")
