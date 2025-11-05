"""
User profile-related Pydantic schemas.
"""

from datetime import date
from typing import Optional
from decimal import Decimal
from pydantic import Field

from app.schemas.base import BaseSchema, TimestampMixin, IDMixin


class UserProfileBase(BaseSchema):
    """Base user profile schema with common fields."""

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


class UserProfileCreate(UserProfileBase):
    """Schema for creating a new user profile."""

    user_id: int = Field(..., description="User ID")


class UserProfileUpdate(BaseSchema):
    """Schema for updating user profile information."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    avatar_url: Optional[str] = Field(None, max_length=500)
    gender: Optional[str] = Field(None, max_length=20)
    height_cm: Optional[Decimal] = Field(None, ge=0, le=300)
    weight_kg: Optional[Decimal] = Field(None, ge=0, le=500)
    date_of_birth: Optional[date] = None
    family_medical_history: Optional[str] = None
    goal: Optional[str] = Field(None, max_length=255)


class UserProfileResponse(UserProfileBase, IDMixin, TimestampMixin):
    """Schema for user profile response."""

    user_id: int = Field(..., description="User ID")
