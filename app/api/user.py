"""
User API endpoints.
"""

import asyncpg
from typing import List, Annotated
from app.services.user import UserService
from app.db.database import get_database_pool
from app.auth.dependencies import get_current_active_user, get_current_active_superuser
from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    Token,
    UserInDB,
)

router = APIRouter()


async def get_user_service(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> UserService:
    """Dependency to get user service."""
    return UserService(db_pool)


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate, user_service: UserService = Depends(get_user_service)
):
    """Create a new user."""
    try:
        user = await user_service.create_user(user_data)
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )


@router.get("/", response_model=List[UserResponse])
async def get_users(
    current_user: Annotated[UserInDB, Depends(get_current_active_superuser)],
    user_service: UserService = Depends(get_user_service),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """Get all users with pagination (admin only)."""
    try:
        users = await user_service.get_users(limit=limit, offset=offset)
        return users
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch users",
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, user_service: UserService = Depends(get_user_service)):
    """Get user by ID."""
    try:
        user = await user_service.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch user",
        )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    user_service: UserService = Depends(get_user_service),
):
    """Update user information."""
    try:
        user = await user_service.update_user(user_id, user_data)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user",
        )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int, user_service: UserService = Depends(get_user_service)
):
    """Delete user."""
    try:
        success = await user_service.delete_user(user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user",
        )


@router.post("/login", response_model=Token)
async def login(
    login_data: UserLogin, user_service: UserService = Depends(get_user_service)
):
    """User login."""
    try:
        token = await user_service.login_user(login_data)
        return token
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to login"
        )


@router.get("/count/total")
async def get_user_count(
    current_user: Annotated[UserInDB, Depends(get_current_active_superuser)],
    user_service: UserService = Depends(get_user_service),
):
    """Get total user count (admin only)."""
    try:
        count = await user_service.count_users()
        return {"total_users": count}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user count",
        )
