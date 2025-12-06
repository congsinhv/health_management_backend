"""
Practice schedule API endpoints.
"""

import asyncpg
from typing import List
from fastapi import APIRouter, Depends, status, Query, Path
from app.services.practice import PracticeService
from app.db.database import get_database_pool
from app.auth.dependencies import get_current_active_user
from app.core.error_context import ErrorContext
from app.exceptions import (
    ResourceNotFoundException,
    ValidationException,
    AuthorizationException,
)
from app.schemas.practice import (
    PracticeCreate,
    PracticeUpdate,
    PracticeResponse,
    PracticeListResponse,
)
from app.schemas.user import UserInDB

router = APIRouter()


async def create_practice_service(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> PracticeService:
    """Dependency to get practice service."""
    return PracticeService(db_pool)


@router.post("/", response_model=PracticeResponse, status_code=status.HTTP_201_CREATED)
async def create_practice(
    practice_data: PracticeCreate,
    practice_service: PracticeService = Depends(create_practice_service),
    current_user: UserInDB = Depends(get_current_active_user),
):
    """
    Create a new practice schedule.
    
    - **user_id**: User ID who owns this practice schedule
    - **day_of_week**: Day of week (1=Monday, 2=Tuesday, ..., 7=Sunday)
    - **start_time**: Practice start time (HH:MM:SS format)
    - **end_time**: Practice end time (HH:MM:SS format)
    - **exercises**: List of exercises to practice
    - **notes**: Optional notes for the practice
    """
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "create_practice")
    ErrorContext.add_context("operation", "practice_creation")
    ErrorContext.add_context("user_id", practice_data.user_id)
    ErrorContext.add_context("day_of_week", practice_data.day_of_week)

    # Authorization: Users can only create practices for themselves
    if current_user.id != practice_data.user_id:
        raise AuthorizationException(
            "You can only create practice schedules for yourself",
            details={"current_user_id": current_user.id, "target_user_id": practice_data.user_id}
        )

    with ErrorContext("create_practice", {"user_id": practice_data.user_id}):
        practice = await practice_service.create_practice(practice_data)
        ErrorContext.add_context("practice_id", practice.id)
        return practice


@router.get("/user/{user_id}", response_model=PracticeListResponse)
async def get_user_practices(
    user_id: int = Path(..., description="User ID to get practices for"),
    limit: int = Query(100, ge=1, le=1000, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    practice_service: PracticeService = Depends(create_practice_service),
    current_user: UserInDB = Depends(get_current_active_user),
):
    """
    Get all practice schedules for a specific user.
    
    Returns paginated list of practice schedules ordered by day and time.
    """
    # Set error context
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "get_user_practices")
    ErrorContext.add_context("operation", "practice_list_retrieval")
    ErrorContext.add_context("target_user_id", user_id)

    # Authorization: Users can only view their own practices
    if current_user.id != user_id:
        raise AuthorizationException(
            "You can only view your own practice schedules",
            details={"current_user_id": current_user.id, "target_user_id": user_id}
        )

    with ErrorContext("get_user_practices", {"user_id": user_id}):
        practices = await practice_service.get_practices_by_user(user_id, limit, offset)
        return practices


@router.get("/user/{user_id}/day/{day_of_week}", response_model=List[PracticeResponse])
async def get_user_practices_by_day(
    user_id: int = Path(..., description="User ID to get practices for"),
    day_of_week: int = Path(..., ge=1, le=7, description="Day of week (1=Mon, 7=Sun)"),
    practice_service: PracticeService = Depends(create_practice_service),
    current_user: UserInDB = Depends(get_current_active_user),
):
    """
    Get practice schedules for a specific user on a specific day.
    
    - **day_of_week**: 1=Monday, 2=Tuesday, ..., 7=Sunday
    
    Returns list of practices ordered by start time.
    """
    # Set error context
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "get_user_practices_by_day")
    ErrorContext.add_context("operation", "practice_day_retrieval")
    ErrorContext.add_context("target_user_id", user_id)
    ErrorContext.add_context("day_of_week", day_of_week)

    # Authorization: Users can only view their own practices
    if current_user.id != user_id:
        raise AuthorizationException(
            "You can only view your own practice schedules",
            details={"current_user_id": current_user.id, "target_user_id": user_id}
        )

    with ErrorContext("get_user_practices_by_day", {"user_id": user_id, "day": day_of_week}):
        practices = await practice_service.get_practices_by_user_and_day(user_id, day_of_week)
        return practices


@router.get("/{practice_id}", response_model=PracticeResponse)
async def get_practice(
    practice_id: int = Path(..., description="Practice schedule ID"),
    practice_service: PracticeService = Depends(create_practice_service),
    current_user: UserInDB = Depends(get_current_active_user),
):
    """
    Get a specific practice schedule by ID.
    """
    # Set error context
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "get_practice")
    ErrorContext.add_context("operation", "practice_retrieval")
    ErrorContext.add_context("practice_id", practice_id)

    with ErrorContext("get_practice", {"practice_id": practice_id}):
        practice = await practice_service.get_practice_by_id(practice_id)
        if not practice:
            raise ResourceNotFoundException(
                "Practice schedule not found",
                details={"practice_id": practice_id}
            )

        # Authorization: Users can only view their own practices
        if current_user.id != practice.user_id:
            raise AuthorizationException(
                "You can only view your own practice schedules",
                details={"current_user_id": current_user.id, "practice_user_id": practice.user_id}
            )

        return practice


@router.put("/{practice_id}", response_model=PracticeResponse)
async def update_practice(
    practice_id: int = Path(..., description="Practice schedule ID"),
    practice_data: PracticeUpdate = ...,
    practice_service: PracticeService = Depends(create_practice_service),
    current_user: UserInDB = Depends(get_current_active_user),
):
    """
    Update a practice schedule.
    
    All fields are optional. Only provided fields will be updated.
    """
    # Set error context
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "update_practice")
    ErrorContext.add_context("operation", "practice_update")
    ErrorContext.add_context("practice_id", practice_id)

    with ErrorContext("update_practice", {"practice_id": practice_id}):
        # Check if practice exists and user has permission
        existing_practice = await practice_service.get_practice_by_id(practice_id)
        if not existing_practice:
            raise ResourceNotFoundException(
                "Practice schedule not found",
                details={"practice_id": practice_id}
            )

        # Authorization: Users can only update their own practices
        if current_user.id != existing_practice.user_id:
            raise AuthorizationException(
                "You can only update your own practice schedules",
                details={"current_user_id": current_user.id, "practice_user_id": existing_practice.user_id}
            )

        # Validate time range if both times are being updated
        if practice_data.start_time and practice_data.end_time:
            if practice_data.end_time <= practice_data.start_time:
                raise ValidationException(
                    "end_time must be after start_time",
                    details={"start_time": str(practice_data.start_time), "end_time": str(practice_data.end_time)}
                )

        practice = await practice_service.update_practice(practice_id, practice_data)
        if not practice:
            raise ResourceNotFoundException(
                "Practice schedule not found or update failed",
                details={"practice_id": practice_id}
            )

        return practice


@router.delete("/{practice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_practice(
    practice_id: int = Path(..., description="Practice schedule ID"),
    practice_service: PracticeService = Depends(create_practice_service),
    current_user: UserInDB = Depends(get_current_active_user),
):
    """
    Delete a practice schedule (soft delete).
    """
    # Set error context
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "delete_practice")
    ErrorContext.add_context("operation", "practice_deletion")
    ErrorContext.add_context("practice_id", practice_id)

    with ErrorContext("delete_practice", {"practice_id": practice_id}):
        # Check if practice exists and user has permission
        existing_practice = await practice_service.get_practice_by_id(practice_id)
        if not existing_practice:
            raise ResourceNotFoundException(
                "Practice schedule not found",
                details={"practice_id": practice_id}
            )

        # Authorization: Users can only delete their own practices
        if current_user.id != existing_practice.user_id:
            raise AuthorizationException(
                "You can only delete your own practice schedules",
                details={"current_user_id": current_user.id, "practice_user_id": existing_practice.user_id}
            )

        success = await practice_service.delete_practice(practice_id)
        if not success:
            raise ResourceNotFoundException(
                "Practice schedule not found for deletion",
                details={"practice_id": practice_id}
            )

        return None


@router.get("/", response_model=PracticeListResponse)
async def get_all_practices(
    limit: int = Query(100, ge=1, le=1000, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    practice_service: PracticeService = Depends(create_practice_service),
    current_user: UserInDB = Depends(get_current_active_user),
):
    """
    Get all practice schedules (admin only).
    
    Returns paginated list of all practice schedules across all users.
    """
    # Set error context
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "get_all_practices")
    ErrorContext.add_context("operation", "practice_admin_list")

    # Note: In a real app, you'd check if user is admin here
    # For now, allowing all authenticated users

    with ErrorContext("get_all_practices", {}):
        practices = await practice_service.get_all_practices(limit, offset)
        return practices
