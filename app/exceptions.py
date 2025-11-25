"""
Custom exception hierarchy for VHealth application.

Provides standardized error handling with proper categorization,
context propagation, and user-friendly error messages.

Usage:
    from app.exceptions import ResourceNotFoundException, ValidationException

    # Resource not found
    raise ResourceNotFoundException(
        message="User not found",
        details={"user_id": 123}
    )

    # Validation error
    raise ValidationException(
        message="Invalid email format",
        details={"field": "email", "value": "invalid-email"}
    )
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class VHealthException(Exception):
    """
    Base exception for VHealth application.

    All custom exceptions should inherit from this class.
    Provides consistent error structure with message, details, and error code.
    """

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        self.message = message
        self.details = details or {}
        self.error_code = error_code or self.__class__.__name__
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }

    def log(self, level: str = "error", extra: Optional[Dict[str, Any]] = None):
        """Log exception with context."""
        log_data = {
            "error_code": self.error_code,
            "details": self.details,
            **(extra or {}),
        }
        getattr(logger, level)(self.message, extra=log_data)


# Resource Errors (HTTP 404)


class ResourceNotFoundException(VHealthException):
    """Resource not found."""

    pass


class ResourceConflictException(VHealthException):
    """Resource conflict (duplicate, constraint violation)."""

    pass


class ResourceGoneException(VHealthException):
    """Resource no longer available."""

    pass


# Authentication/Authorization Errors (HTTP 401/403)


class AuthenticationException(VHealthException):
    """Authentication failed."""

    pass


class AuthorizationException(VHealthException):
    """Authorization failed (insufficient permissions)."""

    pass


class TokenExpiredException(AuthenticationException):
    """Authentication token expired."""

    pass


class TokenInvalidException(AuthenticationException):
    """Authentication token invalid."""

    pass


class InvalidCredentialsException(AuthenticationException):
    """Invalid username/password."""

    pass


class AccountDisabledException(AuthenticationException):
    """User account is disabled."""

    pass


class AccountNotVerifiedException(AuthenticationException):
    """User account not verified."""

    pass


# Validation Errors (HTTP 422)


class ValidationException(VHealthException):
    """Input validation failed."""

    pass


class MissingFieldException(ValidationException):
    """Required field missing."""

    pass


class InvalidFormatException(ValidationException):
    """Field format invalid."""

    pass


class OutOfRangeException(ValidationException):
    """Field value out of allowed range."""

    pass


# Business Logic Errors (HTTP 400/409)


class BusinessLogicException(VHealthException):
    """Business logic constraint violated."""

    pass


class InsufficientCreditsException(BusinessLogicException):
    """User has insufficient credits."""

    pass


class QuotaExceededException(BusinessLogicException):
    """User quota exceeded."""

    pass


class FeatureNotAvailableException(BusinessLogicException):
    """Feature not available for user."""

    pass


class DuplicateResourceException(BusinessLogicException):
    """Resource already exists."""

    pass


class InvalidStateException(BusinessLogicException):
    """Invalid state for operation."""

    pass


# Service/Infrastructure Errors (HTTP 502/503/504)


class ServiceUnavailableException(VHealthException):
    """External service unavailable."""

    pass


class ExternalServiceException(VHealthException):
    """External service error (OpenAI, GCS, etc.)."""

    pass


class DatabaseException(VHealthException):
    """Database operation failed."""

    pass


class DatabaseConnectionException(DatabaseException):
    """Database connection failed."""

    pass


class DatabaseTimeoutException(DatabaseException):
    """Database operation timed out."""

    pass


class DatabaseConstraintException(DatabaseException):
    """Database constraint violated."""

    pass


# Data Processing Errors (HTTP 422/500)


class DataProcessingException(VHealthException):
    """Data processing error."""

    pass


class ModelNotLoadedException(DataProcessingException):
    """ML model not loaded."""

    pass


class InvalidDataFormatException(DataProcessingException):
    """Invalid data format."""

    pass


class DataCorruptionException(DataProcessingException):
    """Data corruption detected."""

    pass


# Rate Limiting Errors (HTTP 429)


class RateLimitException(VHealthException):
    """Rate limit exceeded."""

    pass


class TooManyRequestsException(RateLimitException):
    """Too many requests."""

    pass


# Configuration Errors (HTTP 500)


class ConfigurationException(VHealthException):
    """Configuration error."""

    pass


class MissingConfigurationException(ConfigurationException):
    """Required configuration missing."""

    pass


class InvalidConfigurationException(ConfigurationException):
    """Configuration value invalid."""

    pass


# Cache Errors (HTTP 500/503)


class CacheException(VHealthException):
    """Cache operation failed."""

    pass


class CacheUnavailableException(CacheException):
    """Cache service unavailable."""

    pass


class CacheTimeoutException(CacheException):
    """Cache operation timed out."""

    pass


# File/Storage Errors (HTTP 400/500)


class FileOperationException(VHealthException):
    """File operation failed."""

    pass


class FileNotFoundException(ResourceNotFoundException):
    """File not found."""

    pass


class FileCorruptedException(DataProcessingException):
    """File corrupted."""

    pass


class StorageException(ServiceUnavailableException):
    """Storage service error."""

    pass


# Email Service Errors (HTTP 500/503)


class EmailException(VHealthException):
    """Email service error."""

    pass


class EmailConfigurationException(EmailException, ConfigurationException):
    """Email configuration error."""

    pass


class EmailSendException(EmailException, ServiceUnavailableException):
    """Failed to send email."""

    pass


class EmailTemplateException(EmailException):
    """Email template error."""

    pass


# PDF Generation Errors (HTTP 500)


class PDFGenerationException(VHealthException):
    """PDF generation failed."""

    pass


class PDFTemplateException(PDFGenerationException):
    """PDF template error."""

    pass


class PDFFontException(PDFGenerationException):
    """PDF font error."""

    pass


# Q&A Service Errors (HTTP 500/503)


class QAServiceException(VHealthException):
    """Q&A service error."""

    pass


class QAModelNotLoadedException(ModelNotLoadedException, QAServiceException):
    """Q&A model not loaded."""

    pass


class QADatasetException(DataProcessingException, QAServiceException):
    """Q&A dataset error."""

    pass


class QAModelException(DataProcessingException, QAServiceException):
    """Q&A model processing error."""

    pass


# AI Service Errors (HTTP 500/503)


class AIServiceException(VHealthException):
    """AI service error."""

    pass


class OpenAIException(ExternalServiceException, AIServiceException):
    """OpenAI API error."""

    pass


class AIServiceUnavailableException(ServiceUnavailableException, AIServiceException):
    """AI service unavailable."""

    pass


class AIServiceRateLimitException(RateLimitException, AIServiceException):
    """AI service rate limit exceeded."""

    pass


# Prediction Service Errors


class PredictionException(VHealthException):
    """Prediction service error."""

    pass


class PredictionModelException(ModelNotLoadedException, PredictionException):
    """Prediction model error."""

    pass


class PredictionDataException(ValidationException, PredictionException):
    """Prediction data error."""

    pass


# OAuth Service Errors


class OAuthException(VHealthException):
    """OAuth service error."""

    pass


class OAuthTokenException(AuthenticationException, OAuthException):
    """OAuth token error."""

    pass


class OAuthProviderException(ExternalServiceException, OAuthException):
    """OAuth provider error."""

    pass


class OAuthStateException(ValidationException, OAuthException):
    """OAuth state error."""

    pass


# Utility functions for exception handling


def is_critical_error(exception: Exception) -> bool:
    """Check if exception is critical (requires immediate attention)."""
    critical_exceptions = (
        DatabaseConnectionException,
        DatabaseTimeoutException,
        ServiceUnavailableException,
        ConfigurationException,
        DataCorruptionException,
    )
    return isinstance(exception, critical_exceptions)


def get_http_status_code(exception: VHealthException) -> int:
    """Get appropriate HTTP status code for exception."""
    status_mapping = {
        # Resource errors (404)
        ResourceNotFoundException: 404,
        FileNotFoundException: 404,
        ResourceGoneException: 410,
        # Authentication/Authorization errors (401/403)
        AuthenticationException: 401,
        TokenExpiredException: 401,
        TokenInvalidException: 401,
        InvalidCredentialsException: 401,
        AccountDisabledException: 401,
        AccountNotVerifiedException: 401,
        AuthorizationException: 403,
        # Validation errors (422)
        ValidationException: 422,
        MissingFieldException: 422,
        InvalidFormatException: 422,
        OutOfRangeException: 422,
        InvalidDataFormatException: 422,
        # Business logic errors (400/409)
        BusinessLogicException: 400,
        InvalidStateException: 400,
        DuplicateResourceException: 409,
        ResourceConflictException: 409,
        # Rate limiting (429)
        RateLimitException: 429,
        TooManyRequestsException: 429,
        AIServiceRateLimitException: 429,
        # Service/Infrastructure errors (502/503/504)
        ServiceUnavailableException: 503,
        ExternalServiceException: 502,
        CacheUnavailableException: 503,
        StorageException: 503,
        EmailSendException: 503,
        AIServiceUnavailableException: 503,
        # Configuration/Database errors (500)
        ConfigurationException: 500,
        DatabaseConnectionException: 503,
        DatabaseTimeoutException: 504,
        DatabaseConstraintException: 422,
        ModelNotLoadedException: 503,
        DatabaseException: 500,  # Put parent class last
        # Default to 500 for unhandled exceptions
    }

    for exception_type, status_code in status_mapping.items():
        if isinstance(exception, exception_type):
            return status_code

    return 500


def sanitize_error_details(
    details: Dict[str, Any], user_context: bool = False
) -> Dict[str, Any]:
    """Sanitize error details for logging vs user responses."""
    if not details:
        return {}

    sensitive_keys = {
        "password",
        "token",
        "secret",
        "key",
        "credential",
        "api_key",
        "private_key",
        "auth",
        "authorization",
    }

    sanitized = {}
    for key, value in details.items():
        if isinstance(key, str) and any(
            sensitive in key.lower() for sensitive in sensitive_keys
        ):
            if not user_context:
                sanitized[key] = "[REDACTED]"
            else:
                # For user context, completely remove sensitive fields
                continue
        else:
            sanitized[key] = value

    return sanitized
