"""
User-related Pydantic schemas.
"""

from datetime import datetime, date
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.schemas.base import BaseSchema, TimestampMixin, IDMixin
from app.schemas.user_profile import UserProfileResponse


class UserBase(BaseSchema):
    """Base user schema with common fields."""

    email: EmailStr = Field(..., description="User email address")
    is_active: bool = Field(
        default=True, description="Whether the user account is active"
    )
    provider: str = Field(default="local", description="Authentication provider")
    email_verified: bool = Field(default=False, description="Email verification status")


class UserCreate(UserBase):
    """Schema for creating a new user."""

    password: Optional[str] = Field(
        None, min_length=8, max_length=128, description="User password"
    )
    google_id: Optional[str] = Field(None, description="Google OAuth ID")
    # Profile fields for initial creation
    first_name: Optional[str] = Field(
        None, min_length=1, max_length=50, description="User first name"
    )
    last_name: Optional[str] = Field(
        None, min_length=1, max_length=50, description="User last name"
    )
    avatar_url: Optional[str] = Field(
        None, max_length=500, description="User avatar URL"
    )


class UserUpdate(BaseSchema):
    """Schema for updating user information."""

    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    # Profile fields for updating profile
    first_name: Optional[str] = Field(
        None, min_length=1, max_length=50, description="User first name"
    )
    last_name: Optional[str] = Field(
        None, min_length=1, max_length=50, description="User last name"
    )
    avatar_url: Optional[str] = Field(
        None, max_length=500, description="User avatar URL"
    )
    gender: Optional[str] = Field(None, max_length=20, description="User gender")
    height_cm: Optional[Decimal] = Field(
        None, ge=0, le=300, description="User height in centimeters"
    )
    weight_kg: Optional[Decimal] = Field(
        None, ge=0, le=500, description="User weight in kilograms"
    )
    date_of_birth: Optional[date] = Field(None, description="User date of birth")
    family_medical_history: Optional[str] = Field(
        None, description="Family medical history"
    )
    goal: Optional[str] = Field(None, max_length=255, description="User health goal")


class UserResponse(UserBase, IDMixin, TimestampMixin):
    """Schema for user response."""

    profile: Optional[UserProfileResponse] = Field(
        None, description="User profile information"
    )


class UserInDB(UserResponse):
    """Schema for user data stored in database."""

    password_hash: Optional[str] = Field(None, description="Hashed password")
    google_id: Optional[str] = Field(None, description="Google OAuth ID")
    email_verification_token: Optional[str] = Field(
        None, description="Email verification token"
    )
    email_verification_sent_at: Optional[datetime] = Field(
        None, description="Email verification sent timestamp"
    )
    password_reset_token: Optional[str] = Field(
        None, description="Password reset token"
    )
    password_reset_sent_at: Optional[datetime] = Field(
        None, description="Password reset sent timestamp"
    )


class UserLogin(BaseSchema):
    """Schema for user login."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class Token(BaseSchema):
    """Schema for authentication token."""

    access_token: str
    token_type: str = "bearer"


class TokenData(BaseSchema):
    """Schema for token data."""

    email: Optional[str] = None
    user_id: Optional[int] = None


class RefreshToken(BaseSchema):
    """Schema for refresh token."""

    refresh_token: str


class TokenPair(BaseSchema):
    """Schema for access and refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PasswordResetRequest(BaseSchema):
    """Schema for password reset request."""

    email: EmailStr = Field(..., description="User email address")


class PasswordReset(BaseSchema):
    """Schema for password reset."""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password"
    )


class EmailVerification(BaseSchema):
    """Schema for email verification."""

    token: str = Field(..., description="Email verification token")


class GoogleOAuthRequest(BaseSchema):
    """Schema for Google OAuth request."""

    code: str = Field(..., description="OAuth authorization code")
    state: Optional[str] = Field(None, description="OAuth state parameter")


class GoogleOAuthCallback(BaseSchema):
    """Schema for Google OAuth callback data."""

    id: str = Field(..., description="Google user ID")
    email: EmailStr = Field(..., description="Google user email")
    given_name: str = Field(..., description="Google user given name")
    family_name: str = Field(..., description="Google user family name")
    picture: Optional[str] = Field(None, description="Google user profile picture")
    email_verified: bool = Field(
        default=True, description="Google email verification status"
    )
