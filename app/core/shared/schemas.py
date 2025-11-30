"""
Shared Pydantic models for VHealth microservices.

Provides common response models and base schemas used across all services.
Usage:
    from app.core.shared.schemas import BaseResponse, ErrorResponse, SuccessResponse
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Generic, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar('T')


class BaseResponse(BaseModel):
    """Base response model with common fields."""

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    status: str = "success"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    request_id: Optional[str] = None


class ErrorResponse(BaseResponse):
    """Error response model."""

    status: str = "error"
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None


class SuccessResponse(BaseResponse, Generic[T]):
    """Success response model with data payload."""

    data: Optional[T] = None
    message: Optional[str] = None


class PaginatedResponse(BaseResponse, Generic[T]):
    """Paginated response model."""

    items: List[T]
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


class HealthCheckResponse(BaseResponse):
    """Health check response model."""

    service: str
    status: str = "healthy"
    version: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[Dict[str, Any]] = None


class ValidationErrorResponse(BaseResponse):
    """Validation error response model."""

    status: str = "error"
    error: str = "validation_error"
    message: str = "Input validation failed"
    details: Dict[str, List[str]]  # field -> list of error messages


class ServiceRequest(BaseModel):
    """Base model for service-to-service requests."""

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
    )

    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ServiceResponse(BaseResponse):
    """Base model for service-to-service responses."""

    service: str
    processing_time_ms: Optional[int] = None
    details: Optional[Dict[str, Any]] = None


class BatchRequest(BaseModel):
    """Batch request model for bulk operations."""

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
    )

    items: List[Dict[str, Any]]
    batch_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BatchResponse(BaseResponse):
    """Batch response model for bulk operations."""

    batch_id: Optional[str] = None
    total_items: int
    successful_items: int
    failed_items: int
    results: List[Dict[str, Any]]
    errors: List[Dict[str, Any]] = []


class FileUploadResponse(BaseResponse):
    """File upload response model."""

    filename: str
    file_size: int
    file_url: Optional[str] = None
    file_id: Optional[str] = None
    content_type: Optional[str] = None
    upload_time: datetime = Field(default_factory=datetime.utcnow)