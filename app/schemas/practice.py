"""
Practice schedule-related Pydantic schemas.
"""

from datetime import time, datetime
from typing import Optional, List
from pydantic import Field, field_validator, field_serializer

from app.schemas.base import BaseSchema, TimestampMixin, IDMixin


class PracticeBase(BaseSchema):
    """Base practice schedule schema with common fields."""

    day_of_week: int = Field(
        ..., ge=1, le=7, description="Day of week: 1=Monday, 2=Tuesday, ..., 7=Sunday"
    )
    start_time: time = Field(..., description="Practice start time (HH:MM)")
    end_time: time = Field(..., description="Practice end time (HH:MM)")
    exercises: List[str] = Field(
        ..., min_length=1, description="List of exercises to practice"
    )
    notes: Optional[str] = Field(None, description="Additional notes for the practice")

    @field_serializer('start_time', 'end_time')
    def serialize_time(self, value: time) -> str:
        """Serialize time to HH:MM format (without seconds)."""
        if value:
            return value.strftime("%H:%M")
        return None

    @field_validator("end_time")
    @classmethod
    def validate_time_range(cls, end_time: time, info):
        """Validate that end_time is after start_time."""
        if "start_time" in info.data:
            start_time = info.data["start_time"]
            if end_time <= start_time:
                raise ValueError("end_time must be after start_time")
        return end_time

    @field_validator("exercises")
    @classmethod
    def validate_exercises(cls, exercises: List[str]):
        """Validate that exercises list is not empty and has no duplicates."""
        if not exercises:
            raise ValueError("exercises list cannot be empty")
        if len(exercises) != len(set(exercises)):
            raise ValueError("exercises list contains duplicates")
        return exercises


class PracticeCreate(PracticeBase):
    """Schema for creating a new practice schedule."""

    user_id: int = Field(..., description="User ID who owns this practice schedule")


class PracticeUpdate(BaseSchema):
    """Schema for updating practice schedule information."""

    day_of_week: Optional[int] = Field(
        None, ge=1, le=7, description="Day of week: 1=Monday, ..., 7=Sunday"
    )
    start_time: Optional[time] = Field(None, description="Practice start time")
    end_time: Optional[time] = Field(None, description="Practice end time")
    exercises: Optional[List[str]] = Field(
        None, min_length=1, description="List of exercises to practice"
    )
    notes: Optional[str] = Field(None, description="Additional notes for the practice")

    @field_validator("exercises")
    @classmethod
    def validate_exercises(cls, exercises: Optional[List[str]]):
        """Validate that exercises list is not empty and has no duplicates."""
        if exercises is not None:
            if not exercises:
                raise ValueError("exercises list cannot be empty")
            if len(exercises) != len(set(exercises)):
                raise ValueError("exercises list contains duplicates")
        return exercises


class PracticeResponse(PracticeBase, IDMixin, TimestampMixin):
    """Schema for practice schedule response."""

    user_id: int = Field(..., description="User ID who owns this practice schedule")

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value: datetime) -> str:
        """Serialize datetime to YYYY-MM-DD HH:MM format (without seconds)."""
        if value:
            return value.strftime("%Y-%m-%d %H:%M")
        return None


class PracticeListResponse(BaseSchema):
    """Schema for paginated practice schedule list response."""

    items: List[PracticeResponse] = Field(..., description="List of practice schedules")
    total: int = Field(..., description="Total number of practice schedules")
    limit: int = Field(..., description="Number of items per page")
    offset: int = Field(..., description="Number of items to skip")
