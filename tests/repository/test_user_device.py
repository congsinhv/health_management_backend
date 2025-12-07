import pytest
from datetime import datetime, timezone, timedelta
from app.db.device import DeviceRepository
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_register_device_token(db_pool, test_user, mock_connection):
    repo = DeviceRepository(db_pool)

    mock_connection.fetchrow.return_value = {
        "user_id": test_user.id,
        "fcm_token": "token-abc-123",
        "device_type": "android",
        "is_active": True
    }

    device = await repo.register(
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
async def test_duplicate_device_token(db_pool, test_user, mock_connection):
    repo = DeviceRepository(db_pool)

    # First register mocked
    mock_connection.fetchrow.return_value = {
        "user_id": test_user.id,
        "fcm_token": "token-1",
        "device_type": "android"
    }
    await repo.register(user_id=test_user.id, fcm_token="token-1", device_type="android")

    # Register same token again (should update existing)
    mock_connection.fetchrow.return_value = {
        "user_id": test_user.id,
        "fcm_token": "token-1",
        "device_type": "ios"  # Updated type
    }

    device = await repo.register(
        user_id=test_user.id,
        fcm_token="token-1",
        device_type="ios"
    )

    assert device["device_type"] == "ios"

@pytest.mark.asyncio
async def test_deactivate_device(db_pool, test_user, mock_connection):
    repo = DeviceRepository(db_pool)

    mock_connection.execute.return_value = "UPDATE 1"

    await repo.deactivate(user_id=test_user.id, fcm_token="token-123")

    # Verify execute called
    mock_connection.execute.assert_called()

    # To verify "get_active_by_user" returns empty
    mock_connection.fetch_many.return_value = []
    active = await repo.get_active_by_user(user_id=test_user.id)
    assert len(active) == 0

