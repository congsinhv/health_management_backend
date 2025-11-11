"""
User business logic and services.
"""

import asyncpg
from typing import Optional, List, Dict, Any
from datetime import timedelta, datetime, timezone
from app.constants import UserProviders
from app.db.user import UserRepository
from app.db.user_profile import UserProfileRepository
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserInDB,
    UserLogin,
    Token,
    TokenPair,
    PasswordResetRequest,
    PasswordReset,
    EmailVerification,
    GoogleOAuthCallback,
)
from app.schemas.user_profile import UserProfileCreate, UserProfileResponse
from app.helpers import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    hash_refresh_token,
    create_verification_token,
    verify_verification_token,
)
from app.config import settings
from app.services.email import email_service
from fastapi import HTTPException, status


class UserService:
    """Service layer for user operations."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.user_repo = UserRepository(db_pool)
        self.profile_repo = UserProfileRepository(db_pool)

    def _transform_user_record(self, record) -> Dict[str, Any]:
        """Transform database record or UserInDB object to UserResponse format."""
        # Handle both dict-like records (asyncpg.Record) and UserInDB Pydantic objects
        if hasattr(record, "dict") or hasattr(record, "model_dump"):
            # It's a Pydantic model (UserInDB or similar)
            if hasattr(record, "model_dump"):
                source_data = record.model_dump()
            else:
                source_data = record.dict()
        else:
            # It's a database record (asyncpg.Record or similar)
            source_data = record

        user_data = {
            "id": source_data["id"],
            "email": source_data["email"],
            "is_active": source_data["is_active"],
            "provider": source_data["provider"],
            "email_verified": source_data["email_verified"],
            "created_at": source_data["created_at"],
            "updated_at": source_data["updated_at"],
        }

        # Include password_hash for UserInDB if present
        if "password_hash" in source_data:
            user_data["password_hash"] = source_data["password_hash"]

        # Include other auth fields if present
        for field in [
            "is_superuser",
            "google_id",
            "email_verification_token",
            "email_verification_sent_at",
            "password_reset_token",
            "password_reset_sent_at",
        ]:
            if field in source_data:
                user_data[field] = source_data[field]

        # Build profile if profile data exists
        if source_data.get("profile_id") is not None:
            profile_data = {
                "id": source_data["profile_id"],
                "user_id": source_data["id"],
                "first_name": source_data.get("first_name"),
                "last_name": source_data.get("last_name"),
                "avatar_url": source_data.get("avatar_url"),
                "gender": source_data.get("gender"),
                "height_cm": source_data.get("height_cm"),
                "weight_kg": source_data.get("weight_kg"),
                "date_of_birth": source_data.get("date_of_birth"),
                "family_medical_history": source_data.get("family_medical_history"),
                "goal": source_data.get("goal"),
                "created_at": source_data.get("profile_created_at"),
                "updated_at": source_data.get("profile_updated_at"),
            }
            user_data["profile"] = UserProfileResponse(**profile_data)
        else:
            user_data["profile"] = None

        return user_data

    async def create_user(
        self, user_data: UserCreate, send_verification: bool = True
    ) -> UserResponse:
        """Create a new user."""
        # Check if user already exists
        existing_user = await self.user_repo.get_user_by_email(user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # For OAuth users, check if Google ID already exists
        if user_data.google_id:
            existing_google_user = await self.user_repo.get_user_by_google_id(
                user_data.google_id
            )
            if existing_google_user:
                raise ValueError("User with this Google account already exists")

        # Hash password if provided (not required for OAuth users)
        password_hash = None
        if user_data.password:
            password_hash = hash_password(user_data.password)
        elif user_data.provider == UserProviders.PORTAL:
            raise ValueError("Password is required for portal accounts")

        # Create user
        user_record = await self.user_repo.create_user(user_data, password_hash)
        if not user_record:
            raise RuntimeError("Failed to create user")

        # Create profile if profile fields are provided
        if user_data.first_name or user_data.last_name or user_data.avatar_url:
            profile_create = UserProfileCreate(
                user_id=user_record["id"],
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                avatar_url=user_data.avatar_url,
            )
            await self.profile_repo.create_profile(profile_create)
            # Re-fetch user with profile
            user_record = await self.user_repo.get_user_by_id(user_record["id"])

        # Send email verification for portal accounts (OAuth users are pre-verified)
        if (
            send_verification
            and user_data.provider == UserProviders.PORTAL
            and not user_data.email_verified
        ):
            first_name = user_data.first_name or "User"
            await self._send_email_verification(
                user_record["id"], user_data.email, first_name
            )

        return UserResponse(**self._transform_user_record(user_record))

    async def get_user_by_id(self, user_id: int) -> UserResponse:
        """Get user by ID."""
        user_record = await self.user_repo.get_user_by_id(user_id)
        if not user_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        return UserResponse(**self._transform_user_record(user_record))

    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        """Get user by email (includes password hash for authentication)."""
        user_record = await self.user_repo.get_user_by_email(email)
        if not user_record:
            return None

        return UserInDB(**self._transform_user_record(user_record))

    async def get_users(self, limit: int = 100, offset: int = 0) -> List[UserResponse]:
        """Get all users with pagination."""
        user_records = await self.user_repo.get_users(limit, offset)
        return [
            UserResponse(**self._transform_user_record(record))
            for record in user_records
        ]

    async def update_user(self, user_id: int, user_data: UserUpdate) -> UserResponse:
        """Update user information and profile."""
        # Check if user exists
        existing_user = await self.user_repo.get_user_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Check if email is being changed and if it's already taken
        if user_data.email and user_data.email != existing_user["email"]:
            email_user = await self.user_repo.get_user_by_email(user_data.email)
            if email_user:
                raise ValueError("Email is already taken")

        # Extract profile fields
        profile_fields = {
            "first_name": user_data.first_name,
            "last_name": user_data.last_name,
            "avatar_url": user_data.avatar_url,
            "gender": user_data.gender,
            "height_cm": user_data.height_cm,
            "weight_kg": user_data.weight_kg,
            "date_of_birth": user_data.date_of_birth,
            "family_medical_history": user_data.family_medical_history,
            "goal": user_data.goal,
        }

        # Check if any profile fields are being updated
        has_profile_updates = any(
            value is not None for value in profile_fields.values()
        )

        # Update user (only email and is_active are used by UserRepository)
        user_record = await self.user_repo.update_user(user_id, user_data)
        if not user_record:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update user",
            )

        # Update or create profile if profile fields are provided
        if has_profile_updates:
            # Check if profile exists
            existing_profile = await self.profile_repo.get_profile_by_user_id(user_id)

            if existing_profile:
                # Update existing profile
                from app.schemas.user_profile import UserProfileUpdate

                profile_update = UserProfileUpdate(**profile_fields)
                await self.profile_repo.update_profile(user_id, profile_update)
            else:
                # Create new profile
                from app.schemas.user_profile import UserProfileCreate

                profile_create = UserProfileCreate(user_id=user_id, **profile_fields)
                await self.profile_repo.create_profile(profile_create)

        # Re-fetch user with profile
        user_record = await self.user_repo.get_user_by_id(user_id)
        return UserResponse(**self._transform_user_record(user_record))

    async def delete_user(self, user_id: int) -> bool:
        """Delete user (soft delete)."""
        # Check if user exists
        existing_user = await self.user_repo.get_user_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        result = await self.user_repo.delete_user(user_id)
        return result is not None

    async def authenticate_user(self, email: str, password: str) -> Optional[UserInDB]:
        """Authenticate user by email and password."""
        user = await self.get_user_by_email(email)
        if not user:
            return None

        if not verify_password(password, user.password_hash):
            return None

        if not user.is_active:
            return None

        return user

    async def login_user(self, login_data: UserLogin) -> Token:
        """Login user and return access token."""
        user = await self.authenticate_user(login_data.email, login_data.password)
        if not user:
            raise ValueError("Invalid email or password")

        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.email, "user_id": user.id},
            expires_delta=access_token_expires,
        )

        return Token(access_token=access_token)

    async def count_users(self) -> int:
        """Count total users."""
        return await self.user_repo.count_users()

    # Enhanced Authentication Methods

    async def _send_email_verification(
        self, user_id: int, email: str, first_name: str
    ) -> bool:
        """Send email verification token to user."""
        # Generate verification token
        verification_token = create_verification_token(email, "email_verification")

        # Store token in database
        await self.user_repo.set_email_verification_token(user_id, verification_token)
        base_url = settings.webui_url
        # Send verification email
        return await email_service.send_email_verification(
            email, first_name, verification_token, base_url
        )

    async def verify_email(self, verification_data: EmailVerification) -> bool:
        """Verify user email with token."""
        # Verify token and get email
        email = verify_verification_token(verification_data.token, "email_verification")
        if not email:
            raise ValueError("Invalid or expired verification token")

        # Update user in database
        result = await self.user_repo.verify_email(verification_data.token)
        return result is not None

    async def request_password_reset(self, reset_request: PasswordResetRequest) -> bool:
        """Request password reset for user."""
        # Check if user exists
        user = await self.user_repo.get_user_by_email(reset_request.email)
        if not user:
            # Don't reveal if email exists or not
            return True

        # Check if user is active
        if not user.get("is_active", True):
            # Don't reveal if user is inactive or not
            return True

        # Generate reset token
        reset_token = create_verification_token(reset_request.email, "password_reset")

        # Store token in database
        await self.user_repo.set_password_reset_token(reset_request.email, reset_token)

        # Send reset email
        first_name = user.get("first_name") or "User"  # Profile field if exists
        return await email_service.send_password_reset(
            reset_request.email, first_name, reset_token
        )

    async def reset_password(self, reset_data: PasswordReset) -> bool:
        """Reset user password with token."""
        # Verify token and get email
        email = verify_verification_token(reset_data.token, "password_reset")
        if not email:
            raise ValueError("Invalid or expired reset token")

        # Hash new password
        password_hash = hash_password(reset_data.new_password)

        # Update password in database
        result = await self.user_repo.reset_password(reset_data.token, password_hash)
        return result is not None

    async def change_password(
        self, user_id: int, old_password: str, new_password: str
    ) -> bool:
        """Change user password (requires old password verification)."""
        # Get current user
        user = await self.get_user_by_email_with_password(user_id)
        if not user or not user.password_hash:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or has no password",
            )

        # Verify old password
        if not verify_password(old_password, user.password_hash):
            raise ValueError("Invalid current password")

        # Hash new password
        password_hash = hash_password(new_password)

        # Update password
        return await self.user_repo.update_password(user_id, password_hash)

    async def get_user_by_email_with_password(self, user_id: int) -> Optional[UserInDB]:
        """Get user with password hash (for password verification)."""
        user_record = await self.user_repo.get_user_by_id(user_id)
        if not user_record:
            return None
        return UserInDB(**self._transform_user_record(user_record))

    # OAuth Methods

    async def create_oauth_user(self, oauth_data: GoogleOAuthCallback) -> UserResponse:
        """Create user from OAuth data."""
        user_data = UserCreate(
            email=oauth_data.email,
            first_name=oauth_data.given_name or "User",
            last_name=oauth_data.family_name or "Unknown",
            provider="google",
            google_id=oauth_data.id,
            avatar_url=oauth_data.picture,
            email_verified=oauth_data.email_verified,
        )

        return await self.create_user(user_data, send_verification=False)

    async def authenticate_oauth_user(
        self, oauth_data: GoogleOAuthCallback
    ) -> UserInDB:
        """Authenticate user with OAuth data."""
        # Try to find user by Google ID first
        user_record = await self.user_repo.get_user_by_google_id(oauth_data.id)

        if user_record:
            return UserInDB(**self._transform_user_record(user_record))

        # Try to find user by email
        user_record = await self.user_repo.get_user_by_email(oauth_data.email)

        if user_record:
            # Link Google account to existing user
            await self.user_repo.link_google_account(
                user_record["id"], oauth_data.id, oauth_data.picture
            )
            # Get updated user record
            user_record = await self.user_repo.get_user_by_id(user_record["id"])
            return UserInDB(**self._transform_user_record(user_record))

        # Create new user
        user_response = await self.create_oauth_user(oauth_data)
        user_record = await self.user_repo.get_user_by_id(user_response.id)
        return UserInDB(**self._transform_user_record(user_record))

    async def login_with_oauth(self, oauth_data: GoogleOAuthCallback) -> TokenPair:
        """Login user with OAuth and return token pair."""
        user = await self.authenticate_oauth_user(oauth_data)

        if not user.is_active:
            raise ValueError("User account is disabled")

        # Create access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.email, "user_id": user.id},
            expires_delta=access_token_expires,
        )

        # Create refresh token
        refresh_token_expires = timedelta(days=settings.refresh_token_expire_days)
        refresh_token = create_refresh_token(
            data={"sub": user.email, "user_id": user.id},
            expires_delta=refresh_token_expires,
        )

        # Store refresh token in database
        token_hash = hash_refresh_token(refresh_token)
        expires_at = datetime.now(timezone.utc) + refresh_token_expires
        await self.user_repo.store_refresh_token(user.id, token_hash, expires_at)

        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    # Enhanced login with refresh token support
    async def login_with_refresh_token(self, login_data: UserLogin) -> TokenPair:
        """Login user and return access and refresh tokens."""
        user = await self.authenticate_user(login_data.email, login_data.password)
        if not user:
            raise ValueError("Invalid email or password")

        # Create access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.email, "user_id": user.id},
            expires_delta=access_token_expires,
        )

        # Create refresh token
        refresh_token_expires = timedelta(days=settings.refresh_token_expire_days)
        refresh_token = create_refresh_token(
            data={"sub": user.email, "user_id": user.id},
            expires_delta=refresh_token_expires,
        )

        # Store refresh token in database
        token_hash = hash_refresh_token(refresh_token)
        expires_at = datetime.now(timezone.utc) + refresh_token_expires
        await self.user_repo.store_refresh_token(user.id, token_hash, expires_at)

        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    async def refresh_access_token(self, refresh_token: str) -> TokenPair:
        """Refresh access token using a refresh token."""
        # Verify refresh token JWT
        payload = verify_refresh_token(refresh_token)
        if not payload:
            raise ValueError("Invalid refresh token")

        # Check if token exists in database and is valid
        token_hash = hash_refresh_token(refresh_token)
        token_record = await self.user_repo.get_refresh_token_by_hash(token_hash)

        if not token_record:
            raise ValueError("Refresh token not found or already revoked")

        # Check if token is expired (handle timezone-aware comparison)
        expires_at = token_record["expires_at"]
        if not isinstance(expires_at, datetime):
            raise ValueError("Invalid token expiry data")

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) > expires_at:
            raise ValueError("Refresh token has expired")

        # Get user
        user_id = payload.get("user_id")
        if not user_id:
            raise ValueError("Invalid token payload")

        user = await self.get_user_by_id(user_id)
        if not user or not user.is_active:
            raise ValueError("User not found or inactive")

        # Revoke old refresh token
        await self.user_repo.revoke_refresh_token(token_hash)

        # Create new access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = create_access_token(
            data={"sub": user.email, "user_id": user.id},
            expires_delta=access_token_expires,
        )

        # Create new refresh token (token rotation)
        refresh_token_expires = timedelta(days=settings.refresh_token_expire_days)
        new_refresh_token = create_refresh_token(
            data={"sub": user.email, "user_id": user.id},
            expires_delta=refresh_token_expires,
        )

        # Store new refresh token in database
        new_token_hash = hash_refresh_token(new_refresh_token)
        expires_at = datetime.now(timezone.utc) + refresh_token_expires
        await self.user_repo.store_refresh_token(user.id, new_token_hash, expires_at)

        return TokenPair(access_token=access_token, refresh_token=new_refresh_token)

    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke a refresh token."""
        token_hash = hash_refresh_token(refresh_token)
        return await self.user_repo.revoke_refresh_token(token_hash)

    async def logout_user(self, user_id: int) -> bool:
        """Logout user by revoking all refresh tokens."""
        return await self.user_repo.revoke_all_user_refresh_tokens(user_id)
