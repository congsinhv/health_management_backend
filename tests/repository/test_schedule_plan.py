import pytest
import asyncpg
from datetime import time
from app.db.schedule_plan import SchedulePlanRepository
from app.exceptions import DuplicateResourceException
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_create_schedule_plan(db_pool, test_user, mock_connection):
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

    # Mock return value
    mock_connection.fetchrow.return_value = {
        "id": 1,
        "user_id": test_user.id,
        "goal": "lose",
        "schedule_mode": "fixed",
        "status": "active"
    }

    plan = await repo.create(plan_data)

    assert plan["user_id"] == test_user.id
    assert plan["goal"] == "lose"
    assert plan["schedule_mode"] == "fixed"
    assert plan["status"] == "active"

@pytest.mark.asyncio
async def test_get_active_plan_by_user(db_pool, test_user, mock_connection):
    repo = SchedulePlanRepository(db_pool)

    # Mock return value
    mock_connection.fetchrow.return_value = {
        "id": 1,
        "user_id": test_user.id,
        "status": "active"
    }

    # Get active plan
    plan = await repo.get_active_by_user(test_user.id)

    assert plan is not None
    assert plan["user_id"] == test_user.id
    assert plan["status"] == "active"

@pytest.mark.asyncio
async def test_deactivate_plan(db_pool, test_user, mock_connection):
    repo = SchedulePlanRepository(db_pool)

    # Mock return values
    mock_connection.execute.return_value = "UPDATE 1"

    await repo.deactivate(test_user.id)

    # Verify execute was called
    mock_connection.execute.assert_called()

@pytest.mark.asyncio
async def test_only_one_active_plan_per_user(db_pool, test_user, mock_connection):
    repo = SchedulePlanRepository(db_pool)

    # Mock create to raise UniqueViolationError
    mock_connection.fetchrow.side_effect = asyncpg.UniqueViolationError()

    with pytest.raises(DuplicateResourceException):
        await repo.create({
             "user_id": test_user.id,
             "target_weight_kg": 50.0,
             "goal": "lose",
             "schedule_mode": "fixed",
             "selected_days": ["monday"],
             "fixed_start_time": time(7, 0),
             "fixed_end_time": time(8, 0),
             "sports_predefined": ["gym"],
             "weekly_plan": {}
        })

@pytest.mark.asyncio
async def test_flexible_schedule_storage(db_pool, test_user, mock_connection):
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
        "weekly_plan": {},
        "target_weight_kg": 60.0,
        "fixed_start_time": None,
        "fixed_end_time": None
    }

    # Mock return
    mock_connection.fetchrow.return_value = {
        "id": 1,
        "schedule_mode": "flexible",
        "flexible_periods": flexible_config["flexible_periods"]
    }

    plan = await repo.create(flexible_config)

    assert plan["schedule_mode"] == "flexible"
    assert "tuesday" in plan["flexible_periods"]
    assert plan["flexible_periods"]["tuesday"][0]["startTime"] == "07:00"
