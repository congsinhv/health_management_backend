import pytest
from unittest.mock import AsyncMock
from app.db.device import DeviceRepository
from app.exceptions import DatabaseException
import asyncpg

@pytest.fixture
def mock_pool():
    return AsyncMock()

@pytest.fixture
def repo(mock_pool):
    return DeviceRepository(mock_pool)

@pytest.mark.asyncio
async def test_register_new(repo):
    repo.fetch_one = AsyncMock(return_value={"id": 1, "is_active": True})

    result = await repo.register(1, "token123", "ios", "iPhone")

    assert result["id"] == 1
    assert result["is_active"] is True
    repo.fetch_one.assert_called_once()

@pytest.mark.asyncio
async def test_get_active_by_user(repo):
    repo.fetch_many = AsyncMock(return_value=[{"id": 1}, {"id": 2}])

    result = await repo.get_active_by_user(1)

    assert len(result) == 2
    repo.fetch_many.assert_called_once()

@pytest.mark.asyncio
async def test_deactivate(repo):
    repo.execute = AsyncMock(return_value="UPDATE 1")

    result = await repo.deactivate(1, "token123")

    assert result is True
    repo.execute.assert_called_once()

@pytest.mark.asyncio
async def test_deactivate_token(repo):
    repo.execute = AsyncMock(return_value="UPDATE 5")

    count = await repo.deactivate_token("expired_token")

    assert count == 5
    repo.execute.assert_called_once()

@pytest.mark.asyncio
async def test_update_last_used(repo):
    repo.execute = AsyncMock(return_value="UPDATE 1")

    result = await repo.update_last_used(1)

    assert result is True
    repo.execute.assert_called_once()
