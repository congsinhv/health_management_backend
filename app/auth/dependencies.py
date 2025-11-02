"""
Authentication dependencies for protected routes.
"""

import asyncpg
from typing import Optional, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings
from app.helpers import verify_access_token
from app.db.database import get_database_pool
from app.services.user import UserService
from app.schemas.user import UserInDB

# Security scheme
security = HTTPBearer()


class CurrentUser:
    """Dependency to get current authenticated user."""

    def __init__(self, active_only: bool = True):
        self.active_only = active_only

    async def __call__(
        self,
        credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
        db_pool: Annotated[asyncpg.Pool, Depends(get_database_pool)],
    ) -> UserInDB:
        """Get current authenticated user from JWT token."""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        try:
            # Verify and decode the token
            payload = verify_access_token(credentials.credentials)
            if payload is None:
                raise credentials_exception

            email: str = payload.get("sub")
            if email is None:
                raise credentials_exception

            # Get user from database
            user_service = UserService(db_pool)
            user = await user_service.get_user_by_email(email)

            if user is None:
                raise credentials_exception

            # Check if user should be active
            if self.active_only and not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Inactive user",
                )

            return user

        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise credentials_exception


# Dependency instances
get_current_user = CurrentUser(active_only=True)
get_current_user_inactive = CurrentUser(active_only=False)


async def get_current_active_user(
    current_user: Annotated[UserInDB, Depends(get_current_user)]
) -> UserInDB:
    """Get current active user."""
    return current_user


async def get_current_active_superuser(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)]
) -> UserInDB:
    """Get current active superuser."""
    # For now, we'll implement a simple superuser check based on email
    # In a real application, you might have a separate is_superuser field
    if current_user.email != "admin@health.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges",
        )
    return current_user


# Optional user dependency for routes that work with or without authentication
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> Optional[UserInDB]:
    """Get current user if authenticated, None otherwise."""
    if not credentials:
        return None

    try:
        payload = verify_access_token(credentials.credentials)
        if payload is None:
            return None

        email: str = payload.get("sub")
        if email is None:
            return None

        user_service = UserService(db_pool)
        user = await user_service.get_user_by_email(email)

        return user if user and user.is_active else None

    except Exception:
        return None
