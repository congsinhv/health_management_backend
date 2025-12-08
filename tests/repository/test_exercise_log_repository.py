import pytest
from unittest.mock import AsyncMock
from app.db.exercise_log import ExerciseLogRepository
from app.exceptions import DatabaseException
from datetime import date
import asyncpg


@pytest.fixture
def mock_pool():
    return AsyncMock()


@pytest.fixture
def repo(mock_pool):
    return ExerciseLogRepository(mock_pool)


@pytest.mark.asyncio
async def test_create_success(repo):
    repo.fetch_one = AsyncMock(return_value={"id": 1, "exercise_minutes": 30})

    data = {"user_id": 1, "exercise_minutes": 30, "calories": 200, "date": date.today()}

    result = await repo.create(data)

    assert result["id"] == 1
    assert result["exercise_minutes"] == 30
    repo.fetch_one.assert_called_once()


@pytest.mark.asyncio
async def test_get_by_user_and_date(repo):
    repo.fetch_many = AsyncMock(return_value=[{"id": 1}, {"id": 2}])

    result = await repo.get_by_user_and_date(1, date.today())

    assert len(result) == 2
    repo.fetch_many.assert_called_once()


@pytest.mark.asyncio
async def test_create_error(repo):
    repo.fetch_one = AsyncMock(side_effect=asyncpg.PostgresError("db error"))

    data = {"user_id": 1, "exercise_minutes": 30, "calories": 200, "date": date.today()}

    with pytest.raises(DatabaseException):
        await repo.create(data)
