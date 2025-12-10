import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock
from app.main import app
from app.api.devices import get_schedule_service
from app.schemas.schedule import DeviceResponse
from datetime import datetime


@pytest.fixture
def mock_schedule_service_device():
    service = AsyncMock()

    response_data = {
        "id": 1,
        "device_type": "android",
        "device_name": "Pixel 6",
        "is_active": True,
        "last_used_at": datetime.now(),
    }

    response_obj = DeviceResponse(**response_data)
    service.register_device.return_value = response_obj
    service.unregister_device.return_value = True

    return service


from app.auth.dependencies import get_current_user
from app.schemas.user import UserInDB
from datetime import datetime, timezone


@pytest.fixture
def override_device_dependency(mock_schedule_service_device):
    app.dependency_overrides[
        get_schedule_service
    ] = lambda: mock_schedule_service_device

    async def mock_get_current_user():
        return UserInDB(
            id=1,
            email="test@example.com",
            password_hash="hash",
            first_name="Test",
            last_name="User",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield
    app.dependency_overrides.pop(get_schedule_service, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_register_device_success(
    client, auth_token, override_device_dependency, mock_schedule_service_device
):
    device_data = {
        "fcm_token": "a" * 150,
        "device_type": "android",
        "device_name": "Pixel 6",
    }

    response = await client.post(
        "/api/v1/devices/",
        json=device_data,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["is_active"] is True

    mock_schedule_service_device.register_device.assert_called_once()


@pytest.mark.asyncio
async def test_unregister_device_success(
    client, auth_token, override_device_dependency, mock_schedule_service_device
):
    token = "a" * 150
    response = await client.delete(
        f"/api/v1/devices/{token}", headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 204
    mock_schedule_service_device.unregister_device.assert_called_once()


@pytest.mark.asyncio
async def test_unregister_device_not_found(
    client, auth_token, override_device_dependency, mock_schedule_service_device
):
    mock_schedule_service_device.unregister_device.return_value = False

    token = "a" * 150
    response = await client.delete(
        f"/api/v1/devices/{token}", headers={"Authorization": f"Bearer {auth_token}"}
    )

    assert response.status_code == 404
