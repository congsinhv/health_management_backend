"""
Schedule API endpoints for workout reminders.
"""

import asyncpg
from typing_extensions import Annotated
from fastapi import APIRouter, Depends, status, Request

from app.config import logger
from app.services.schedule.service import ScheduleService
from app.db.database import get_database_pool
from app.auth.dependencies import get_current_active_user
from app.schemas.user import UserInDB
from app.core.error_context import ErrorContext
from app.schemas.schedule import (
    ScheduleCreateRequest,
    ScheduleResponse,
    ScheduleStatusUpdate,
)

router = APIRouter()


async def get_schedule_service(
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ScheduleService:
    """Get schedule service with cache."""
    cache_service = getattr(request.app.state, "cache_service", None)
    return ScheduleService(db_pool, cache_service=cache_service)


@router.post("/", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    request_data: ScheduleCreateRequest,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    service: ScheduleService = Depends(get_schedule_service),
):
    """Create or update workout schedule.

    Creates a new weekly workout schedule with AI-generated exercise plan.
    If user already has an active schedule, it will be superseded.
    """
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "create_schedule")

    with ErrorContext(
        "create_schedule",
        {
            "user_id": current_user.id,
            "goal": request_data.basic_info.goal.value,
            "days_count": len(request_data.schedule.selected_days),
        },
    ):
        schedule = await service.create_or_update_schedule(
            current_user.id, request_data
        )
        ErrorContext.add_context("schedule_id", schedule.id)
        return schedule


@router.get("/", response_model=ScheduleResponse)
async def list_schedules(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    service: ScheduleService = Depends(get_schedule_service),
):
    """List all workout schedules for the current user."""
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "list_schedules")

    with ErrorContext("list_schedules", {"user_id": current_user.id}):
        return await service.list_schedules(current_user.id)


@router.patch("/{schedule_id}/", response_model=ScheduleResponse)
async def update_schedule_status(
    schedule_id: int,
    request_data: ScheduleStatusUpdate,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    service: ScheduleService = Depends(get_schedule_service),
):
    """Toggle schedule on/off.

    Activates or pauses a specific schedule.
    Only 1 schedule can be active per user at a time.

    - When activated: notifications are scheduled for the week
    - When paused: pending notifications are cancelled
    """
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "update_schedule_status")

    with ErrorContext(
        "update_schedule_status",
        {
            "user_id": current_user.id,
            "schedule_id": schedule_id,
            "is_active": request_data.is_active,
        },
    ):
        schedule = await service.toggle_schedule_status(
            current_user.id, schedule_id, request_data.is_active
        )
        return schedule


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    service: ScheduleService = Depends(get_schedule_service),
):
    """Deactivate workout schedule and cancel pending notifications."""
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "delete_schedule")

    with ErrorContext("delete_schedule", {"user_id": current_user.id}):
        await service.deactivate_schedule(current_user.id)


@router.post("/regenerate", response_model=ScheduleResponse)
async def regenerate_plan(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    service: ScheduleService = Depends(get_schedule_service),
):
    """Regenerate AI workout plan without changing schedule config."""
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "regenerate_plan")

    with ErrorContext("regenerate_plan", {"user_id": current_user.id}):
        schedule = await service.regenerate_plan(current_user.id)
        return schedule
