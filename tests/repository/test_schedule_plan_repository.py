import pytest
from unittest.mock import AsyncMock, MagicMock
from app.db.schedule_plan import SchedulePlanRepository
from app.exceptions import DatabaseException, ResourceNotFoundException, DuplicateResourceException
import asyncpg

@pytest.fixture
def mock_pool():
    return AsyncMock()

@pytest.fixture
def repo(mock_pool):
    return SchedulePlanRepository(mock_pool)

@pytest.mark.asyncio
async def test_create_success(repo):
    repo.fetch_one = AsyncMock(return_value={"id": 1, "user_id": 1, "status": "active"})

    data = {
        "user_id": 1,
        "goal": "lose",
        "selected_days": ["MON", "WED"],
        "sports_predefined": ["running"]
    }

    result = await repo.create(data)

    assert result["id"] == 1
    assert result["status"] == "active"
    repo.fetch_one.assert_called_once()

@pytest.mark.asyncio
async def test_create_duplicate(repo):
    repo.fetch_one = AsyncMock(side_effect=asyncpg.UniqueViolationError())

    data = {
        "user_id": 1,
        "goal": "lose",
        "selected_days": ["MON"],
        "sports_predefined": ["running"]
    }

    with pytest.raises(DuplicateResourceException):
        await repo.create(data)

@pytest.mark.asyncio
async def test_get_active_by_user(repo):
    repo.fetch_one = AsyncMock(return_value={"id": 1, "status": "active"})

    result = await repo.get_active_by_user(1)

    assert result["id"] == 1
    repo.fetch_one.assert_called_once()

@pytest.mark.asyncio
async def test_update_weekly_plan(repo):
    repo.fetch_one = AsyncMock(return_value={"id": 1, "weekly_plan": {}})

    result = await repo.update_weekly_plan(1, {"day1": "exercise"})

    assert result["weekly_plan"] == {}
    repo.fetch_one.assert_called_once()

@pytest.mark.asyncio
async def test_update_weekly_plan_not_found(repo):
    repo.fetch_one = AsyncMock(return_value=None)

    with pytest.raises(ResourceNotFoundException):
        await repo.update_weekly_plan(1, {})

@pytest.mark.asyncio
async def test_deactivate(repo):
    repo.execute = AsyncMock(return_value="UPDATE 1")

    result = await repo.deactivate(1)

    assert result is True
    repo.execute.assert_called_once()
