import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, time, timezone

from app.main import app
from app.api.schedules import get_schedule_service
from app.services.schedule.service import ScheduleService
from app.schemas.schedule import (
    ScheduleResponse,
    GoalType,
    ScheduleMode,
    DayOfWeek,
    ScheduleConfig,
    DeviceRegisterRequest,
    DeviceResponse,
)


@pytest.fixture
def mock_schedule_service():
    service = AsyncMock(spec=ScheduleService)

    # Create valid response object
    response_data = {
        "id": 1,
        "user_id": 1,
        "goal": "lose",
        "schedule_mode": "fixed",
        "selected_days": ["monday", "wednesday"],
        "timezone": "Asia/Ho_Chi_Minh",
        "weekly_plan": {
            "monday": {
                "exercise": "Gym",
                "duration_minutes": 45,
                "estimated_calories": 300,
                "description": "Gym",
            }
        },
        "status": "active",
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }

    response_obj = ScheduleResponse(**response_data)

    service.create_or_update_schedule.return_value = response_obj
    service.get_active_schedule.return_value = response_obj
    service.regenerate_plan.return_value = response_obj
    service.deactivate_schedule.return_value = True

    return service


from app.auth.dependencies import get_current_user
from app.schemas.user import UserInDB


@pytest.fixture
def override_dependency(mock_schedule_service):
    app.dependency_overrides[get_schedule_service] = lambda: mock_schedule_service

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
async def test_create_schedule_success(
    client, auth_token, override_dependency, mock_schedule_service
):
    schedule_data = {
        "basic_info": {
            "height": 1.75,
            "weight": 70.0,
            "target_weight": 65.0,
            "goal": "lose",
        },
        "schedule": {
            "mode": "fixed",
            "selected_days": ["monday", "wednesday"],
            "fixed_period": {"start_time": "07:00", "end_time": "08:00"},
        },
        "sports": {"predefined": ["gym", "running"], "custom": []},
        "notes": {"personal": "Test notes", "health_warnings": "None"},
        "timezone": "Asia/Ho_Chi_Minh",
    }

    response = await client.post(
        "/api/v1/schedules/",
        json=schedule_data,
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    mock_schedule_service.create_or_update_schedule.assert_called_once()


@pytest.mark.asyncio
async def test_get_schedule_success(
    client, auth_token, override_dependency, mock_schedule_service
):
    response = await client.get(
        "/api/v1/schedules/", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    mock_schedule_service.get_active_schedule.assert_called_once()


@pytest.mark.asyncio
async def test_get_schedule_not_found(
    client, auth_token, override_dependency, mock_schedule_service
):
    mock_schedule_service.get_active_schedule.return_value = None
    response = await client.get(
        "/api/v1/schedules/", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_schedule(
    client, auth_token, override_dependency, mock_schedule_service
):
    response = await client.delete(
        "/api/v1/schedules/", headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 204
    mock_schedule_service.deactivate_schedule.assert_called_once()


@pytest.mark.asyncio
async def test_regenerate_plan(
    client, auth_token, override_dependency, mock_schedule_service
):
    response = await client.post(
        "/api/v1/schedules/regenerate",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    mock_schedule_service.regenerate_plan.assert_called_once()


class TestScheduleAPI:
    """Tests for schedule API endpoints (unauthorized)."""

    @pytest.mark.asyncio
    async def test_create_schedule_unauthorized(self):
        """Test creating schedule without auth returns 401."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/schedules/", json={})
            assert response.status_code == 403  # No auth header

    @pytest.mark.asyncio
    async def test_get_schedule_unauthorized(self):
        """Test getting schedule without auth returns 401."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/schedules/")
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_delete_schedule_unauthorized(self):
        """Test deleting schedule without auth returns 401."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.delete("/api/v1/schedules/")
            assert response.status_code == 403


from pydantic import ValidationError


class TestScheduleValidation:
    """Tests for schedule request validation."""

    def test_schedule_mode_fixed_requires_fixed_period(self):
        """Test fixed mode requires fixed_period."""
        # Should raise without fixed_period
        with pytest.raises(ValidationError):
            ScheduleConfig(
                mode=ScheduleMode.FIXED,
                selected_days=[DayOfWeek.MONDAY]
                # Missing fixed_period
            )

    def test_schedule_mode_flexible_requires_flexible_periods(self):
        """Test flexible mode requires flexible_periods."""
        # Should raise without flexible_periods
        with pytest.raises(ValidationError):
            ScheduleConfig(
                mode=ScheduleMode.FLEXIBLE,
                selected_days=[DayOfWeek.MONDAY]
                # Missing flexible_periods
            )

    def test_schedule_config_fixed_valid(self):
        """Test valid fixed schedule config."""
        config = ScheduleConfig(
            mode=ScheduleMode.FIXED,
            selected_days=[DayOfWeek.MONDAY, DayOfWeek.WEDNESDAY],
            fixed_period={"start_time": "07:00", "end_time": "08:00"},
        )
        assert config.mode == ScheduleMode.FIXED
        assert len(config.selected_days) == 2

    def test_schedule_config_flexible_valid(self):
        """Test valid flexible schedule config."""
        config = ScheduleConfig(
            mode=ScheduleMode.FLEXIBLE,
            selected_days=[DayOfWeek.TUESDAY],
            flexible_periods={
                DayOfWeek.TUESDAY: [
                    {"start_time": "07:00", "end_time": "08:00"},
                    {"start_time": "18:00", "end_time": "19:00"},
                ]
            },
        )
        assert config.mode == ScheduleMode.FLEXIBLE
        assert DayOfWeek.TUESDAY in config.flexible_periods


class TestDeviceValidation:
    """Tests for device registration validation."""

    def test_fcm_token_minimum_length(self):
        """Test FCM token must be at least 100 characters."""
        # Should raise with short token
        with pytest.raises(ValueError):
            DeviceRegisterRequest(fcm_token="short_token", device_type="ios")

    def test_fcm_token_valid(self):
        """Test valid FCM token passes validation."""
        valid_token = "a" * 152
        request = DeviceRegisterRequest(fcm_token=valid_token, device_type="android")
        assert request.fcm_token == valid_token
        assert request.device_type == "android"

    def test_device_type_enum(self):
        """Test device type must be valid enum value."""
        valid_token = "a" * 152
        for device_type in ["ios", "android", "web"]:
            request = DeviceRegisterRequest(
                fcm_token=valid_token, device_type=device_type
            )
            assert request.device_type == device_type


class TestScheduleResponseModel:
    """Tests for schedule response models."""

    def test_schedule_response_conversion(self):
        """Test converting DB record to response model."""
        db_record = {
            "id": 1,
            "user_id": 1,
            "goal": "lose",
            "schedule_mode": "fixed",
            "selected_days": ["monday"],
            "fixed_start_time": time(7, 0),
            "fixed_end_time": time(8, 0),
            "flexible_periods": None,
            "timezone": "UTC",
            "weekly_plan": {
                "monday": {
                    "exercise": "Gym",
                    "duration_minutes": 45,
                    "estimated_calories": 300,
                    "description": "Gym",
                }
            },
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        # Pydantic model can accept dict if strict=False or passed via **
        response = ScheduleResponse(**db_record)

        assert response.id == 1
        assert response.goal == "lose"
        assert response.schedule_mode == "fixed"

    def test_device_response_conversion(self):
        """Test converting DB record to device response model."""
        db_record = {
            "id": 1,
            "device_type": "ios",
            "device_name": "iPhone 14",
            "is_active": True,
            "last_used_at": datetime.now(timezone.utc),
        }

        response = DeviceResponse(**db_record)

        assert response.id == 1
        assert response.device_type == "ios"
        assert response.is_active is True
