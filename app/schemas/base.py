"""
Base Pydantic schemas for the application.
"""

from datetime import datetime
from typing import Optional, Generic, TypeVar
from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        arbitrary_types_allowed=True,
        str_strip_whitespace=True,
    )


class BaseResponse(BaseSchema):
    """Base response schema."""

    pass


T = TypeVar("T")


class StandardResponse(BaseSchema, Generic[T]):
    """
    Generic standard API response wrapper.
    """

    success: bool = True
    message: Optional[str] = None
    data: Optional[T] = None


# Add success class method after class definition to avoid Pydantic interference
def _create_success_response(
    cls, data: Optional[T] = None, message: Optional[str] = None
) -> "StandardResponse[T]":
    """Create a successful response."""
    return cls(success=True, message=message, data=data)


# Attach the method to the class
StandardResponse.success = classmethod(_create_success_response)


class TimestampMixin(BaseModel):
    """Mixin for timestamp fields."""

    created_at: datetime
    updated_at: Optional[datetime] = None


class IDMixin(BaseModel):
    """Mixin for ID field."""

    id: int
