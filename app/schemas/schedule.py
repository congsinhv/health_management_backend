"""
Schedule-related Pydantic schemas.
"""

from datetime import time, date, datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum


class GoalType(str, Enum):
    LOSE = "lose"
    GAIN = "gain"
    MAINTAIN = "maintain"


class ScheduleMode(str, Enum):
    FIXED = "fixed"
    FLEXIBLE = "flexible"


class DayOfWeek(str, Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class TimePeriod(BaseModel):
    """Time period for workout."""

    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}(:\d{2})?$")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}(:\d{2})?$")


class BasicInfo(BaseModel):
    """User basic info for plan generation."""

    height: Optional[float] = Field(
        None, ge=0.5, le=2.5, description="Height in meters"
    )
    weight: Optional[float] = Field(None, ge=20, le=300, description="Weight in kg")
    target_weight: Optional[float] = Field(None, ge=20, le=300)
    goal: GoalType


class ScheduleConfig(BaseModel):
    """Schedule configuration."""

    mode: ScheduleMode = ScheduleMode.FIXED
    selected_days: List[DayOfWeek] = Field(..., min_length=1, max_length=7)
    fixed_period: Optional[TimePeriod] = None
    flexible_periods: Optional[Dict[DayOfWeek, List[TimePeriod]]] = None

    @model_validator(mode="after")
    def validate_periods(self):
        """Validate period configuration matches mode."""
        if self.mode == ScheduleMode.FIXED and not self.fixed_period:
            raise ValueError("fixed_period required for fixed mode")
        if self.mode == ScheduleMode.FLEXIBLE and not self.flexible_periods:
            raise ValueError("flexible_periods required for flexible mode")
        return self


class SportsPreferences(BaseModel):
    """Sports preferences."""

    predefined: List[str] = Field(default_factory=list)
    custom: List[str] = Field(default_factory=list)


class ScheduleNotes(BaseModel):
    """User notes."""

    personal: Optional[str] = Field(None, max_length=1000)
    health_warnings: Optional[str] = Field(None, max_length=1000)


class ScheduleCreateRequest(BaseModel):
    """Request to create/update schedule."""

    basic_info: BasicInfo
    schedule: ScheduleConfig
    sports: SportsPreferences
    notes: Optional[ScheduleNotes] = None
    timezone: str = Field(default="Asia/Ho_Chi_Minh")


class WorkoutStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class WorkoutPlan(BaseModel):
    """AI-generated workout for a day."""

    exercise: str
    duration_minutes: int
    estimated_calories: int
    description: str
    status: WorkoutStatus = WorkoutStatus.PENDING
    error_message: Optional[str] = None


class ScheduleResponse(BaseModel):
    """Schedule response."""

    id: int
    user_id: int
    goal: GoalType
    schedule_mode: ScheduleMode
    selected_days: List[str]
    timezone: str
    weekly_plan: Optional[Dict[str, WorkoutPlan]] = None
    status: str
    created_at: datetime
    updated_at: datetime


class ScheduleStatusUpdate(BaseModel):
    """Request to update schedule status (on/off)."""

    is_active: bool = Field(
        ..., description="True to activate, False to pause schedule"
    )


class DeviceRegisterRequest(BaseModel):
    """FCM device registration."""

    fcm_token: str = Field(
        ...,
        min_length=100,
        max_length=500,
        pattern=r"^[A-Za-z0-9_:/-]+$",
        description="FCM registration token (typically 150-165 chars)",
    )
    device_type: Optional[str] = Field(None, pattern=r"^(ios|android|web)$")
    device_name: Optional[str] = Field(None, max_length=100)


class DeviceResponse(BaseModel):
    """Device response."""

    id: int
    device_type: Optional[str]
    device_name: Optional[str]
    is_active: bool
    last_used_at: Optional[datetime]
