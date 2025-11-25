"""
User API endpoints.
"""

import asyncpg
from typing import List
from typing_extensions import Annotated
from app.services.user import UserService
from app.db.database import get_database_pool
from app.auth.dependencies import get_current_active_user, get_current_active_superuser
from fastapi import APIRouter, Depends, status, Query
from app.core.error_context import ErrorContext
from app.exceptions import (
    ResourceNotFoundException,
    ValidationException,
    DatabaseException,
    AuthorizationException,
)
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserInDB,
)

router = APIRouter()


async def create_user_service(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> UserService:
    """Dependency to get user service."""
    return UserService(db_pool)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate, user_service: UserService = Depends(create_user_service)
):
    """Create a new user."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "create_user")
    ErrorContext.add_context("operation", "user_creation")
    ErrorContext.add_context("email", user_data.email)

    with ErrorContext("create_user", {"email": user_data.email}):
        user = await user_service.create_user(user_data)
        ErrorContext.add_context("user_id", user.id)
        return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int, user_service: UserService = Depends(create_user_service)
):
    """Get user by ID."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "get_user")
    ErrorContext.add_context("operation", "user_retrieval")
    ErrorContext.add_context("target_user_id", user_id)

    with ErrorContext("get_user", {"target_user_id": user_id}):
        user = await user_service.get_user_by_id(user_id)
        if not user:
            raise ResourceNotFoundException(
                "User not found", details={"user_id": user_id}
            )
        return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    user_service: UserService = Depends(create_user_service),
):
    """Update user information."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "update_user")
    ErrorContext.add_context("operation", "user_update")
    ErrorContext.add_context("target_user_id", user_id)

    with ErrorContext("update_user", {"target_user_id": user_id}):
        user = await user_service.update_user(user_id, user_data)
        if not user:
            raise ResourceNotFoundException(
                "User not found", details={"user_id": user_id}
            )
        return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int, user_service: UserService = Depends(create_user_service)
):
    """Delete user."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "delete_user")
    ErrorContext.add_context("operation", "user_deletion")
    ErrorContext.add_context("target_user_id", user_id)

    with ErrorContext("delete_user", {"target_user_id": user_id}):
        success = await user_service.delete_user(user_id)
        if not success:
            raise ResourceNotFoundException(
                "User not found", details={"user_id": user_id}
            )
