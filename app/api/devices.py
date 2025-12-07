"""
Device API endpoints for FCM token management.
"""

import asyncpg
from typing_extensions import Annotated
from fastapi import APIRouter, Depends, status, Request, Path

from app.config import logger
from app.services.schedule.service import ScheduleService
from app.db.database import get_database_pool
from app.auth.dependencies import get_current_active_user
from app.schemas.user import UserInDB
from app.core.error_context import ErrorContext
from app.exceptions import ResourceNotFoundException
from app.schemas.schedule import DeviceRegisterRequest, DeviceResponse

router = APIRouter()


async def get_schedule_service(
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ScheduleService:
    """Get schedule service."""
    cache_service = getattr(request.app.state, "cache_service", None)
    return ScheduleService(db_pool, cache_service=cache_service)


@router.post("/", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    request_data: DeviceRegisterRequest,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    service: ScheduleService = Depends(get_schedule_service),
):
    """Register FCM device token for push notifications.

    Registers or updates device for receiving workout reminders.
    Same token can be re-registered to update device info.
    """
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "register_device")

    with ErrorContext(
        "register_device",
        {
            "user_id": current_user.id,
            "device_type": request_data.device_type,
        },
    ):
        device = await service.register_device(current_user.id, request_data)
        return device


@router.delete("/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_device(
    token: Annotated[str, Path(min_length=10)],
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    service: ScheduleService = Depends(get_schedule_service),
):
    """Unregister FCM device token.

    Removes device from receiving notifications.
    """
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "unregister_device")

    with ErrorContext("unregister_device", {"user_id": current_user.id}):
        success = await service.unregister_device(current_user.id, token)
        if not success:
            raise ResourceNotFoundException(
                message="Device not found",
                details={"user_id": current_user.id},
            )
