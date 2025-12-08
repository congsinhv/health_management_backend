import pytest
from unittest.mock import AsyncMock
from app.db.notification import NotificationRepository
from app.exceptions import DatabaseException, ResourceNotFoundException
from datetime import datetime, timedelta
import asyncpg


@pytest.fixture
def mock_pool():
    return AsyncMock()


@pytest.fixture
def repo(mock_pool):
    return NotificationRepository(mock_pool)


@pytest.mark.asyncio
async def test_create_success(repo):
    repo.fetch_one = AsyncMock(return_value={"id": 1, "status": "pending"})

    data = {
        "schedule_plan_id": 1,
        "user_id": 1,
        "scheduled_at": datetime.now(),
        "workout_date": datetime.now().date(),
        "workout_day": "MON",
        "workout_start_time": datetime.now().time(),
        "workout_end_time": datetime.now().time(),
        "title": "Workout",
        "body": "Time to train",
    }

    result = await repo.create(data)

    assert result["id"] == 1
    repo.fetch_one.assert_called_once()


@pytest.mark.asyncio
async def test_create_batch_success(repo):
    repo.execute = AsyncMock(return_value="INSERT 0 5")

    notifications = [{"title": "n1"}, {"title": "n2"}] * 2 + [{"title": "n5"}]

    count = await repo.create_batch(notifications)

    assert count == 5
    repo.execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_batch_empty(repo):
    count = await repo.create_batch([])
    assert count == 0
    # execute should not be called


@pytest.mark.asyncio
async def test_get_pending_in_window(repo):
    repo.fetch_many = AsyncMock(return_value=[{"id": 1}, {"id": 2}])

    result = await repo.get_pending_in_window(
        datetime.now(), datetime.now() + timedelta(hours=1)
    )

    assert len(result) == 2
    repo.fetch_many.assert_called_once()


@pytest.mark.asyncio
async def test_update_status(repo):
    repo.fetch_one = AsyncMock(return_value={"id": 1, "status": "sent"})

    result = await repo.update_status(1, "sent")

    assert result["status"] == "sent"
    repo.fetch_one.assert_called_once()


@pytest.mark.asyncio
async def test_update_status_not_found(repo):
    repo.fetch_one = AsyncMock(return_value=None)

    with pytest.raises(ResourceNotFoundException):
        await repo.update_status(999, "sent")


@pytest.mark.asyncio
async def test_delete_by_plan(repo):
    repo.execute = AsyncMock(return_value="DELETE 3")

    count = await repo.delete_by_plan(1)

    assert count == 3
    repo.execute.assert_called_once()
