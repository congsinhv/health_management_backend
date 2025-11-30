# Error Handling Guide

**VHealth Backend - Comprehensive Error Handling Documentation**

Last Updated: 2025-11-25 (Phase 4: Error Handling Standardization)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Exception Hierarchy](#2-exception-hierarchy)
3. [ErrorContext System](#3-errorcontext-system)
4. [Layer-Specific Patterns](#4-layer-specific-patterns)
5. [Security Considerations](#5-security-considerations)
6. [Monitoring and Alerting](#6-monitoring-and-alerting)
7. [Testing Error Scenarios](#7-testing-error-scenarios)
8. [Migration Guide](#8-migration-guide)
9. [Best Practices](#9-best-practices)

---

## 1. Overview

VHealth implements a comprehensive error handling system designed to provide:

- **Consistent Error Responses**: Standardized error format across all APIs
- **Context Propagation**: Request-scoped context tracking across async boundaries
- **Security**: Sensitive data protection and information disclosure prevention
- **Observability**: Structured logging with context for debugging and monitoring
- **Graceful Degradation**: Fallback mechanisms when dependencies fail
- **Developer Experience**: Clear error categories and actionable messages

### Key Benefits

1. **Debugging Efficiency**: Context tracking makes troubleshooting much easier
2. **Security**: Automatic sanitization of sensitive information
3. **Consistency**: Uniform error handling patterns across the codebase
4. **Monitoring**: Built-in support for critical error detection and alerting
5. **Maintainability**: Clear separation of concerns and standardized patterns

---

## 2. Exception Hierarchy

### 2.1 Base Exception Class

All custom exceptions inherit from `VHealthException`:

```python
class VHealthException(Exception):
    """
    Base exception for VHealth application.

    Provides consistent error structure with message, details, and error code.
    """

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        self.message = message
        self.details = details or {}
        self.error_code = error_code or self.__class__.__name__
        super().__init__(self.message)
```

### 2.2 Exception Categories

#### Resource Errors (HTTP 404/410)
```python
ResourceNotFoundException    # 404 - Resource not found
ResourceConflictException   # 409 - Resource conflict/duplicate
ResourceGoneException       # 410 - Resource no longer available
```

#### Authentication/Authorization (HTTP 401/403)
```python
AuthenticationException        # 401 - Authentication failed
AuthorizationException         # 403 - Authorization failed
TokenExpiredException          # 401 - Token expired
TokenInvalidException          # 401 - Token invalid
InvalidCredentialsException    # 401 - Invalid credentials
AccountDisabledException       # 401 - Account disabled
AccountNotVerifiedException    # 401 - Account not verified
```

#### Validation Errors (HTTP 422)
```python
ValidationException       # 422 - Input validation failed
MissingFieldException     # 422 - Required field missing
InvalidFormatException     # 422 - Field format invalid
OutOfRangeException        # 422 - Field value out of range
```

#### Business Logic (HTTP 400/409)
```python
BusinessLogicException      # 400 - Business logic constraint
DuplicateResourceException  # 409 - Resource already exists
InvalidStateException       # 400 - Invalid state for operation
InsufficientCreditsException # 400 - Insufficient credits
QuotaExceededException      # 400 - User quota exceeded
FeatureNotAvailableException # 400 - Feature not available
```

#### Service/Infrastructure (HTTP 502/503/504)
```python
ServiceUnavailableException  # 503 - Service unavailable
ExternalServiceException     # 502 - External service error
DatabaseException           # 500 - Database operation failed
DatabaseConnectionException # 503 - Database connection failed
DatabaseTimeoutException    # 504 - Database operation timed out
DatabaseConstraintException # 422 - Database constraint violated
```

#### Data Processing (HTTP 422/500)
```python
DataProcessingException     # 500 - Data processing error
ModelNotLoadedException     # 503 - ML model not loaded
InvalidDataFormatException  # 422 - Invalid data format
DataCorruptionException     # 500 - Data corruption detected
```

#### Rate Limiting (HTTP 429)
```python
RateLimitException         # 429 - Rate limit exceeded
TooManyRequestsException   # 429 - Too many requests
AIServiceRateLimitException # 429 - AI service rate limit
```

#### Configuration (HTTP 500)
```python
ConfigurationException       # 500 - Configuration error
MissingConfigurationException # 500 - Required config missing
InvalidConfigurationException # 500 - Configuration value invalid
```

#### Service-Specific Exceptions
```python
# Cache
CacheException              # 500 - Cache operation failed
CacheUnavailableException   # 503 - Cache service unavailable

# PDF Generation
PDFGenerationException      # 500 - PDF generation failed
PDFTemplateException        # 500 - PDF template error
PDFFontException           # 500 - PDF font error

# Q&A Service
QAServiceException         # 500 - Q&A service error
QAModelNotLoadedException   # 503 - Q&A model not loaded
QADatasetException         # 422 - Q&A dataset error

# AI Service
AIServiceException         # 500 - AI service error
OpenAIException            # 502 - OpenAI API error
AIServiceUnavailableException # 503 - AI service unavailable

# Email Service
EmailException             # 500 - Email service error
EmailSendException         # 503 - Failed to send email
EmailTemplateException     # 500 - Email template error

# Prediction Service
PredictionException        # 500 - Prediction service error
PredictionModelException   # 503 - Prediction model error
PredictionDataException    # 422 - Prediction data error

# OAuth Service
OAuthException             # 500 - OAuth service error
OAuthTokenException        # 401 - OAuth token error
OAuthProviderException     # 502 - OAuth provider error

# WebSocket
WebSocketException         # 500 - WebSocket operation failed
WebSocketConnectionException # 500 - WebSocket connection failed
WebSocketMessageException  # 422 - WebSocket message invalid
```

### 2.3 Creating New Exceptions

When adding new exception types:

```python
class CustomServiceException(VHealthException):
    """Custom service error."""
    pass

class CustomSpecificException(CustomServiceException):
    """Specific error with custom logic."""

    def __init__(self, resource_id: str, **kwargs):
        details = {"resource_id": resource_id, **kwargs.pop("details", {})}
        super().__init__(
            message=f"Custom error for resource {resource_id}",
            details=details,
            **kwargs
        )
```

---

## 3. ErrorContext System

### 3.1 Purpose

ErrorContext provides request-scoped context that propagates across async boundaries, enabling:

- **Request Tracking**: Unique request and correlation IDs
- **User Context**: Authentication information across service calls
- **Operation Tracking**: Current operation and performance metrics
- **Debugging Information**: Context data for troubleshooting

### 3.2 Basic Usage

#### Context Manager
```python
from app.core.error_context import ErrorContext

# Set context at request start
request_id = ErrorContext.set_request_id()
ErrorContext.set_user_id(user.id)
ErrorContext.set_correlation_id()

# Wrap operations with context
with ErrorContext("create_conversation", {"user_id": user.id}):
    # Your code here
    conversation = await conversation_service.create(data)

    # Add additional context
    ErrorContext.add_context("conversation_id", conversation.id)
    return conversation
```

#### Decorator
```python
from app.core.error_context import with_error_context

@with_error_context("database_query", {"table": "users"})
async def get_user(user_id: int):
    return await self.user_repo.get_by_id(user_id)
```

#### Manual Context Management
```python
# Set initial context
request_id = ErrorContext.set_request_id()
ErrorContext.set_user_id(user.id)
ErrorContext.set_correlation_id()

# Add context during execution
ErrorContext.add_context("operation", "user_lookup")
ErrorContext.add_context("cache_hit", True)

# Get context for logging
context = ErrorContext.get_all()
logger.info("Operation completed", extra=context)
```

### 3.3 Context Data

The context system automatically tracks:

- **request_id**: UUID for request tracking
- **user_id**: Authenticated user ID
- **correlation_id**: UUID for cross-service correlation
- **operation_name**: Current operation being performed
- **request_duration**: Time since request start
- **error_count**: Number of errors in request lifecycle
- **additional_context**: Custom key-value pairs

### 3.4 Context Propagation

Context automatically propagates across:

- **Async/await boundaries**: Maintained through contextvars
- **Service calls**: Available in all downstream services
- **Background tasks**: Can be manually propagated if needed
- **Database operations**: Available for query logging

```python
# Context propagates through async calls
async def outer_function():
    with ErrorContext("outer_operation"):
        result = await inner_function()  # Context automatically available
        return result

async def inner_function():
    # Context from outer_function is available
    context = ErrorContext.get_all()
    logger.info("Inner operation", extra=context)
```

### 3.5 Middleware Integration

For automatic context management in FastAPI:

```python
from app.core.error_context import ErrorContextMiddleware

# Add to FastAPI app
app.add_middleware(ErrorContextMiddleware)

# Custom middleware with user extraction
app.add_middleware(
    ErrorContextMiddleware,
    extract_user_id=extract_user_id_from_request
)
```

---

## 4. Layer-Specific Patterns

### 4.1 API Layer (Routers)

#### Responsibilities
- Convert service exceptions to HTTP responses
- Add context headers (X-Request-ID, X-Correlation-ID)
- Sanitize error responses for production
- Log unhandled exceptions

#### Pattern Implementation
```python
from fastapi import HTTPException
from app.exceptions import (
    VHealthException,
    get_http_status_code,
    sanitize_error_details
)
from app.core.error_context import ErrorContext

@router.post("/conversations/")
async def create_conversation(
    request: ConversationCreate,
    current_user: User = Depends(get_current_user)
):
    """Create conversation with standardized error handling."""
    try:
        # Set context at entry point
        ErrorContext.set_user_id(current_user.id)

        with ErrorContext("api_create_conversation", {"user_id": current_user.id}):
            result = await conversation_service.create(request, current_user.id)
            return result

    except VHealthException as e:
        # Log with context
        e.log("error", ErrorContext.get_all())

        # Convert to HTTP response
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail={
                "error": e.error_code,
                "message": e.message,
                "details": sanitize_error_details(e.details, user_context=True)
            }
        )
    except Exception as e:
        # Unexpected errors
        logger.error(
            f"Unexpected error in create_conversation: {e}",
            exc_info=True,
            extra=ErrorContext.get_all()
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )

# Add context headers middleware
@app.middleware("http")
async def add_context_headers(request: Request, call_next):
    response = await call_next(request)

    # Add context headers if available
    if request_id := ErrorContext.get_request_id():
        response.headers["X-Request-ID"] = request_id
    if correlation_id := ErrorContext.get_correlation_id():
        response.headers["X-Correlation-ID"] = correlation_id

    return response
```

### 4.2 Service Layer

#### Responsibilities
- Use custom exceptions for business logic errors
- Wrap external service errors appropriately
- Add operation context using ErrorContext
- Handle database exceptions and convert to service exceptions
- Implement graceful degradation where appropriate

#### Pattern Implementation
```python
from app.exceptions import (
    ResourceNotFoundException,
    BusinessLogicException,
    ServiceUnavailableException,
    DatabaseException,
    ExternalServiceException
)

class ConversationService:
    async def create(self, request: ConversationCreate, user_id: int) -> ConversationResponse:
        """Create conversation with comprehensive error handling."""
        with ErrorContext("service_create_conversation", {"user_id": user_id}):
            try:
                # Validate business rules
                if await self._has_active_conversation(user_id):
                    raise BusinessLogicException(
                        message="User already has active conversation",
                        details={"user_id": user_id, "max_active": 1}
                    )

                # Create conversation
                conversation_data = {
                    "user_id": user_id,
                    "title": request.title,
                    "metadata": request.metadata or {}
                }

                result = await self.conversation_repo.create(conversation_data)
                ErrorContext.add_context("conversation_id", result["id"])

                return ConversationResponse(**result)

            except DatabaseException as e:
                e.log("error", {"operation": "create_conversation"})
                raise ServiceUnavailableException(
                    message="Database service temporarily unavailable",
                    details={"original_error": e.error_code}
                )

            except ResourceNotFoundException as e:
                # User not found
                e.log("warning", {"user_id": user_id})
                raise

            except Exception as e:
                logger.error(
                    f"Unexpected error in conversation service: {e}",
                    exc_info=True,
                    extra=ErrorContext.get_all()
                )
                raise ServiceUnavailableException(
                    message="Conversation service temporarily unavailable"
                )

    async def _has_active_conversation(self, user_id: int) -> bool:
        """Check if user has active conversation with error handling."""
        try:
            with ErrorContext("check_active_conversation", {"user_id": user_id}):
                return await self.conversation_repo.has_active_conversation(user_id)
        except DatabaseException as e:
            logger.warning(
                f"Failed to check active conversation: {e}",
                extra=ErrorContext.get_all()
            )
            # Assume no active conversation on database error
            return False
```

### 4.3 Repository Layer

#### Responsibilities
- Handle database-specific errors
- Use parameterized queries to prevent SQL injection
- Convert database exceptions to appropriate repository exceptions
- Add database operation context
- Let critical database errors bubble up to service layer

#### Pattern Implementation
```python
import asyncpg
from app.exceptions import (
    DatabaseException,
    DatabaseConnectionException,
    DatabaseTimeoutException,
    DatabaseConstraintException
)

class ConversationRepository:
    async def create(self, conversation_data: dict) -> dict:
        """Create conversation with database error handling."""
        query = """
            INSERT INTO conversations (user_id, title, metadata, created_at)
            VALUES ($1, $2, $3, NOW())
            RETURNING id, user_id, title, metadata, created_at
        """

        with ErrorContext("repo_create_conversation", {"table": "conversations"}):
            try:
                async with self.pool.acquire() as conn:
                    result = await conn.fetchrow(
                        query,
                        conversation_data["user_id"],
                        conversation_data["title"],
                        conversation_data["metadata"]
                    )
                    return dict(result)

            except asyncpg.PostgresConnectionError as e:
                raise DatabaseConnectionException(
                    message="Failed to connect to database",
                    details={"operation": "create_conversation", "error": str(e)}
                )

            except asyncpg.QueryCanceledError as e:
                raise DatabaseTimeoutException(
                    message="Database query timed out",
                    details={"operation": "create_conversation", "timeout": 30}
                )

            except asyncpg.UniqueViolationError as e:
                raise DatabaseConstraintException(
                    message="Database constraint violation",
                    details={"constraint": str(e.constraint), "operation": "create_conversation"}
                )

            except asyncpg.PostgresError as e:
                raise DatabaseException(
                    message="Database operation failed",
                    details={"operation": "create_conversation", "error": str(e)}
                )

    async def has_active_conversation(self, user_id: int) -> bool:
        """Check if user has active conversation."""
        query = """
            SELECT EXISTS(
                SELECT 1 FROM conversations
                WHERE user_id = $1 AND deleted_at IS NULL
            )
        """

        with ErrorContext("repo_has_active_conversation", {"user_id": user_id}):
            try:
                async with self.pool.acquire() as conn:
                    result = await conn.fetchval(query, user_id)
                    return result
            except asyncpg.PostgresError as e:
                raise DatabaseException(
                    message="Failed to check active conversation",
                    details={"user_id": user_id, "error": str(e)}
                )
```

### 4.4 External Service Integration

#### Pattern Implementation
```python
from app.exceptions import (
    ExternalServiceException,
    ServiceUnavailableException,
    AIServiceRateLimitException
)
import aiohttp
import asyncio

class OpenAIService:
    def __init__(self, api_key: str, timeout: int = 30):
        self.api_key = api_key
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def generate_summary(self, text: str) -> str:
        """Generate summary with comprehensive error handling."""
        with ErrorContext("openai_generate_summary", {"text_length": len(text)}):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }

                    payload = {
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": f"Summarize: {text}"}],
                        "max_tokens": 150
                    }

                    async with session.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers=headers,
                        json=payload
                    ) as response:
                        if response.status == 429:
                            retry_after = response.headers.get("Retry-After", 60)
                            raise AIServiceRateLimitException(
                                message="OpenAI API rate limit exceeded",
                                details={"retry_after": int(retry_after)}
                            )

                        elif response.status == 401:
                            raise ExternalServiceException(
                                message="OpenAI API authentication failed",
                                details={"service": "openai", "status": response.status}
                            )

                        elif response.status >= 500:
                            raise ServiceUnavailableException(
                                message="OpenAI service temporarily unavailable",
                                details={"service": "openai", "status": response.status}
                            )

                        response.raise_for_status()
                        data = await response.json()
                        return data["choices"][0]["message"]["content"]

            except asyncio.TimeoutError:
                raise ServiceUnavailableException(
                    message="OpenAI API request timed out",
                    details={"service": "openai", "timeout": self.timeout.total}
                )

            except aiohttp.ClientError as e:
                raise ExternalServiceException(
                    message="OpenAI API connection failed",
                    details={"service": "openai", "error": str(e)}
                )
```

---

## 5. Security Considerations

### 5.1 Sensitive Data Protection

The error handling system automatically sanitizes sensitive information:

```python
from app.exceptions import sanitize_error_details

# Error details with sensitive information
error_details = {
    "user_id": 123,
    "email": "user@example.com",
    "api_key": "sk-1234567890abcdef",
    "database_url": "postgresql://user:password@host:5432/database",
    "credit_card": "4111-1111-1111-1111",
    "password": "supersecret123"
}

# For internal logging (preserve but redact sensitive)
log_details = sanitize_error_details(error_details, user_context=False)
# Returns: {
#     "user_id": 123,
#     "email": "user@example.com",
#     "api_key": "[REDACTED]",
#     "database_url": "[REDACTED]",
#     "credit_card": "[REDACTED]",
#     "password": "[REDACTED]"
# }

# For user responses (remove sensitive entirely)
user_details = sanitize_error_details(error_details, user_context=True)
# Returns: {
#     "user_id": 123,
#     "email": "user@example.com"
# }
```

### 5.2 Information Disclosure Prevention

#### Production Error Responses
```python
def create_error_response(exception: VHealthException) -> dict:
    """Create user-safe error response."""
    if settings.DEBUG:
        # Development: include full details
        return {
            "error": exception.error_code,
            "message": exception.message,
            "details": exception.details
        }
    else:
        # Production: sanitize and use generic messages
        return {
            "error": exception.error_code,
            "message": get_user_safe_message(exception.error_code),
            "details": sanitize_error_details(exception.details, user_context=True)
        }

def get_user_safe_message(error_code: str) -> str:
    """Map error codes to user-safe messages."""
    user_messages = {
        "DatabaseConnectionException": "Service temporarily unavailable",
        "ExternalServiceException": "Third-party service unavailable",
        "AIServiceException": "AI service temporarily unavailable",
        "ValidationException": "Invalid input provided",
        "AuthenticationException": "Authentication required",
        "AuthorizationException": "Access denied",
        # ... more mappings
    }
    return user_messages.get(error_code, "An error occurred")
```

### 5.3 Security Headers

```python
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Error-specific headers
    if response.status_code >= 400:
        # Add context headers for debugging
        if request_id := ErrorContext.get_request_id():
            response.headers["X-Request-ID"] = request_id
        if correlation_id := ErrorContext.get_correlation_id():
            response.headers["X-Correlation-ID"] = correlation_id

        # Add error code header for client handling
        if hasattr(response, "error_code"):
            response.headers["X-Error-Code"] = response.error_code

    return response
```

### 5.4 Logging Security

```python
import logging
from app.core.error_context import ErrorContext

# Configure secure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Never log sensitive data
logger.info("User login successful", extra={
    "user_id": user.id,
    "timestamp": datetime.now().isoformat()
    # DON'T log: password, token, api_key, etc.
})

# Use ErrorContext for secure logging
with ErrorContext("user_authentication", {"user_id": user.id}):
    try:
        # Authentication logic
        pass
    except AuthenticationException as e:
        # Log with context (automatically sanitized)
        e.log("warning", {"component": "auth_service"})
        raise
```

---

## 6. Monitoring and Alerting

### 6.1 Critical Error Detection

The system provides automatic detection of critical errors that require immediate attention:

```python
from app.exceptions import is_critical_error

# Critical errors include:
# - DatabaseConnectionException
# - DatabaseTimeoutException
# - ServiceUnavailableException
# - ConfigurationException
# - DataCorruptionException

try:
    result = await critical_operation()
except Exception as e:
    if is_critical_error(e):
        # Send alert to monitoring system
        await alert_service.send_critical_alert(
            error=str(e),
            context=ErrorContext.get_all(),
            severity="critical",
            component="database_service"
        )

    # Log with appropriate level
    logger.error(
        f"Critical operation failed: {e}",
        exc_info=True,
        extra=ErrorContext.get_all()
    )
    raise
```

### 6.2 Error Metrics

```python
import time
from collections import defaultdict
from typing import Dict, Counter

class ErrorMetrics:
    """Track error metrics for monitoring."""

    def __init__(self):
        self.error_counts: Counter[str] = defaultdict(int)
        self.error_rates: Dict[str, float] = {}
        self.last_reset = time.time()

    def record_error(self, exception: Exception):
        """Record an error occurrence."""
        error_type = exception.__class__.__name__
        self.error_counts[error_type] += 1

        # Check for alerting thresholds
        if self.error_counts[error_type] > 10:  # Alert after 10 errors
            self._send_alert(error_type)

    def get_error_rate(self, time_window: int = 300) -> float:
        """Get error rate for the last N seconds."""
        # Implementation would track errors over time
        pass

# Global metrics instance
error_metrics = ErrorMetrics()

# Use in exception handling
try:
    await some_operation()
except Exception as e:
    error_metrics.record_error(e)
    raise
```

### 6.3 Health Checks

```python
@app.get("/health/errors")
async def error_health_check():
    """Health check endpoint for error monitoring."""
    try:
        metrics = await get_error_metrics()

        health_status = {
            "status": "healthy",
            "error_rate": metrics["error_rate"],
            "critical_errors": metrics["critical_errors"],
            "last_reset": metrics["last_reset"]
        }

        # Determine health status
        if metrics["error_rate"] > 0.1:  # 10% error rate
            health_status["status"] = "degraded"
            return JSONResponse(health_status, status_code=200)

        if metrics["critical_errors"] > 0:
            health_status["status"] = "unhealthy"
            return JSONResponse(health_status, status_code=503)

        return JSONResponse(health_status, status_code=200)

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            {"status": "unhealthy", "error": "Health check failed"},
            status_code=503
        )
```

---

## 7. Testing Error Scenarios

### 7.1 Unit Testing Exception Handling

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.exceptions import ResourceNotFoundException, DatabaseException
from app.services.conversation import ConversationService

class TestConversationServiceErrors:
    """Test error scenarios in conversation service."""

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self):
        """Test getting non-existent conversation."""
        service = ConversationService(mock_db_pool)

        # Mock repository to raise not found
        service.conversation_repo.get_by_id = AsyncMock(
            side_effect=DatabaseException("Conversation not found")
        )

        with pytest.raises(ResourceNotFoundException) as exc_info:
            await service.get_conversation(999)

        assert "not found" in str(exc_info.value)
        assert exc_info.value.details["conversation_id"] == 999

    @pytest.mark.asyncio
    async def test_create_conversation_database_error(self):
        """Test conversation creation with database error."""
        service = ConversationService(mock_db_pool)

        # Mock repository to raise database error
        service.conversation_repo.create = AsyncMock(
            side_effect=DatabaseException("Connection failed")
        )

        with pytest.raises(ServiceUnavailableException) as exc_info:
            await service.create({"title": "Test"}, 1)

        assert "temporarily unavailable" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_error_context_propagation(self):
        """Test that ErrorContext is properly propagated."""
        with ErrorContext("test_operation", {"test_id": 123}):
            service = ConversationService(mock_db_pool)

            # Mock to raise exception
            service.conversation_repo.get_by_id = AsyncMock(
                side_effect=DatabaseException("Test error")
            )

            with pytest.raises(DatabaseException):
                await service.get_conversation(1)

            # Verify context was set
            context = ErrorContext.get_all()
            assert context["test_id"] == 123
            assert context["operation_name"] == "test_operation"
```

### 7.2 Integration Testing Error Handling

```python
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient

class TestAPIErrorHandling:
    """Test API error handling."""

    @pytest.mark.asyncio
    async def test_404_error_response(self, client: AsyncClient):
        """Test 404 error response format."""
        response = await client.get("/api/v1/conversations/99999")

        assert response.status_code == 404
        error_data = response.json()

        assert "error" in error_data
        assert "message" in error_data
        assert "details" in error_data
        assert error_data["error"] == "ResourceNotFoundException"

        # Check for context headers
        assert "X-Request-ID" in response.headers

    @pytest.mark.asyncio
    async def test_validation_error_response(self, client: AsyncClient):
        """Test validation error response."""
        response = await client.post(
            "/api/v1/conversations/",
            json={"invalid_field": "value"}  # Missing required title
        )

        assert response.status_code == 422
        error_data = response.json()

        assert error_data["error"] == "ValidationException"
        assert "Invalid input" in error_data["message"]

    @pytest.mark.asyncio
    async def test_error_sanitization(self, client: AsyncClient):
        """Test error response sanitization in production."""
        # Mock production mode
        with patch("app.config.settings.DEBUG", False):
            response = await client.get("/api/v1/conversations/99999")

            error_data = response.json()

            # Ensure no sensitive information leaked
            assert "password" not in str(error_data)
            assert "api_key" not in str(error_data)
            assert "database" not in str(error_data).lower()
```

### 7.3 Error Context Testing

```python
def test_error_context_functionality():
    """Test ErrorContext functionality."""
    from app.core.error_context import ErrorContext

    # Test context setting and getting
    request_id = ErrorContext.set_request_id("test-123")
    assert request_id == "test-123"
    assert ErrorContext.get_request_id() == "test-123"

    # Test user context
    ErrorContext.set_user_id(456)
    assert ErrorContext.get_user_id() == 456

    # Test correlation ID
    correlation_id = ErrorContext.set_correlation_id("corr-789")
    assert correlation_id == "corr-789"
    assert ErrorContext.get_correlation_id() == "corr-789"

    # Test additional context
    ErrorContext.add_context("operation", "test")
    ErrorContext.add_context("cache_hit", True)

    additional = ErrorContext.get_additional_context()
    assert additional["operation"] == "test"
    assert additional["cache_hit"] is True

    # Test full context
    full_context = ErrorContext.get_all()
    assert full_context["request_id"] == "test-123"
    assert full_context["user_id"] == 456
    assert full_context["correlation_id"] == "corr-789"
    assert full_context["additional_context"]["operation"] == "test"

    # Test context clearing
    ErrorContext.clear()
    assert ErrorContext.get_request_id() is None
    assert ErrorContext.get_user_id() is None
```

---

## 8. Migration Guide

### 8.1 Migrating Existing Error Handling

#### From Basic Exception Handling
```python
# OLD CODE
async def get_user(user_id: int):
    try:
        result = await db.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        if not result:
            return None
        return User(**result)
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise ValueError("User not found")

# NEW CODE
async def get_user(user_id: int):
    with ErrorContext("get_user", {"user_id": user_id}):
        try:
            result = await self.user_repo.get_by_id(user_id)
            if not result:
                raise ResourceNotFoundException(
                    message="User not found",
                    details={"user_id": user_id}
                )
            return result
        except DatabaseException:
            # Re-raise database exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting user {user_id}: {e}")
            raise DatabaseException(
                message="Database operation failed",
                details={"user_id": user_id, "operation": "get_user"}
            )
```

#### From FastAPI HTTPException
```python
# OLD CODE
@router.get("/users/{user_id}")
async def get_user(user_id: int):
    user = await user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# NEW CODE
@router.get("/users/{user_id}")
async def get_user(user_id: int):
    try:
        with ErrorContext("api_get_user", {"user_id": user_id}):
            user = await user_service.get_user(user_id)
            return user
    except ResourceNotFoundException as e:
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail=e.to_dict()
        )
```

### 8.2 Adding ErrorContext to Existing Functions

#### Step 1: Add Basic Context
```python
# BEFORE
async def process_data(data_id: str):
    data = await get_data(data_id)
    result = await transform_data(data)
    return result

# AFTER
async def process_data(data_id: str):
    with ErrorContext("process_data", {"data_id": data_id}):
        data = await get_data(data_id)
        result = await transform_data(data)
        return result
```

#### Step 2: Add Custom Exceptions
```python
# AFTER
async def process_data(data_id: str):
    with ErrorContext("process_data", {"data_id": data_id}):
        try:
            data = await get_data(data_id)
            if not data:
                raise ResourceNotFoundException(
                    message="Data not found",
                    details={"data_id": data_id}
                )

            result = await transform_data(data)
            return result

        except ResourceNotFoundException:
            raise  # Re-raise our custom exceptions
        except DatabaseException as e:
            raise ServiceUnavailableException(
                message="Data processing temporarily unavailable",
                details={"original_error": e.error_code}
            )
```

#### Step 3: Add Context Throughout Call Chain
```python
# Repository level
async def get_data(data_id: str):
    with ErrorContext("repo_get_data", {"table": "data"}):
        try:
            query = "SELECT * FROM data WHERE id = $1"
            async with self.pool.acquire() as conn:
                result = await conn.fetchrow(query, data_id)
                return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Failed to retrieve data",
                details={"data_id": data_id, "error": str(e)}
            )

# Transform function
async def transform_data(data: dict):
    with ErrorContext("transform_data", {"data_type": data.get("type")}):
        # Transform logic here
        pass
```

### 8.3 Migration Checklist

- [ ] Replace generic `Exception` with specific `VHealthException` subclasses
- [ ] Add `ErrorContext` to all service methods
- [ ] Update API layer to handle custom exceptions
- [ ] Add error sanitization for user responses
- [ ] Update logging to use context
- [ ] Add tests for error scenarios
- [ ] Update monitoring to track custom exceptions
- [ ] Add error headers to responses
- [ ] Review security of error messages
- [ ] Document any new exception types

---

## 9. Best Practices

### 9.1 Exception Design Principles

1. **Be Specific**: Use the most specific exception type possible
2. **Include Context**: Always include relevant details in exception constructor
3. **Don't Catch Too Early**: Handle exceptions at the appropriate layer
4. **Log with Context**: Always log errors with relevant context information
5. **Sanitize for Users**: Remove sensitive information from user-facing errors

### 9.2 ErrorContext Best Practices

```python
# DO: Set context early
async def api_handler():
    ErrorContext.set_user_id(current_user.id)
    with ErrorContext("api_operation"):
        # Operation code
        pass

# DO: Add relevant context
with ErrorContext("database_query", {"table": "users", "operation": "select"}):
    result = await db.fetchrow(query, params)

# DON'T: Include sensitive data
ErrorContext.add_context("password", user.password)  # WRONG

# DO: Add operation-specific context
ErrorContext.add_context("cache_hit", True)
ErrorContext.add_context("query_time_ms", 150)
```

### 9.3 Service Layer Patterns

```python
# DO: Validate business rules explicitly
async def create_conversation(user_id: int, data: dict):
    with ErrorContext("create_conversation", {"user_id": user_id}):
        # Validate business rules
        if await self._has_active_conversation(user_id):
            raise BusinessLogicException(
                message="User already has active conversation",
                details={"user_id": user_id, "current_limit": 1}
            )

        # Continue with creation
        pass

# DO: Handle external service failures gracefully
async def call_external_api(data: dict):
    try:
        return await external_service.process(data)
    except ExternalServiceException as e:
        e.log("warning", {"fallback": "cached_result"})
        return await get_cached_result(data)
```

### 9.4 Testing Error Scenarios

```python
# DO: Test both success and error cases
@pytest.mark.asyncio
async def test_service_error_handling():
    service = MyService(mock_repo)

    # Test success case
    mock_repo.get_data.return_value = {"id": 1, "name": "test"}
    result = await service.get_data(1)
    assert result["id"] == 1

    # Test error case
    mock_repo.get_data.side_effect = DatabaseException("Connection failed")
    with pytest.raises(ServiceUnavailableException):
        await service.get_data(1)

# DO: Test error context propagation
def test_error_context_propagation():
    with ErrorContext("test_operation"):
        try:
            raise DatabaseException("Test error")
        except Exception as e:
            context = ErrorContext.get_all()
            assert context["operation_name"] == "test_operation"
            raise
```

### 9.5 Performance Considerations

```python
# DO: Minimize context overhead
def lightweight_operation():
    # For simple operations, decorator might be overkill
    return simple_calculation()

# DON'T: Add context to every tiny operation
def add_context_to_every_line():
    ErrorContext.add_context("step", 1)  # Probably unnecessary
    result = step1()
    ErrorContext.add_context("step", 2)  # Probably unnecessary
    result = step2(result)

# DO: Focus on meaningful boundaries
async def api_handler():
    with ErrorContext("api_handler"):
        # Group related operations
        result1 = await service.operation1()
        result2 = await service.operation2()
        return combine_results(result1, result2)
```

### 9.6 Security Best Practices

```python
# DO: Sanitize all error responses
def create_error_response(exception: VHealthException) -> dict:
    return {
        "error": exception.error_code,
        "message": get_user_safe_message(exception.error_code),
        "details": sanitize_error_details(exception.details, user_context=True)
    }

# DO: Never expose internal details
try:
    result = await database_operation()
except DatabaseException as e:
    # DON'T include e.details["database_url"] in user response
    logger.error(f"Database error: {e.details}")  # OK for logs
    raise ServiceUnavailableException("Service unavailable")  # User response

# DO: Use generic messages for security-sensitive operations
async def authenticate_user(credentials):
    try:
        user = await get_user_by_email(credentials.email)
        if not user or not verify_password(credentials.password, user.password_hash):
            # Use generic message to prevent email enumeration
            raise InvalidCredentialsException("Invalid email or password")
        return user
    except Exception:
        raise InvalidCredentialsException("Invalid email or password")
```

---

## Conclusion

This comprehensive error handling system provides VHealth with robust, secure, and maintainable error management. The standardized approach ensures consistency across all services while maintaining security and providing excellent debugging capabilities.

Key benefits achieved through Phase 4 implementation:

1. **Consistency**: All services now use the same error handling patterns
2. **Security**: Automatic sanitization protects sensitive information
3. **Observability**: Context tracking enables effective monitoring and debugging
4. **Maintainability**: Clear patterns make the codebase easier to understand and modify
5. **Reliability**: Graceful degradation ensures the application remains functional during partial failures

The system is designed to evolve with the application, making it easy to add new exception types, expand context tracking, and enhance monitoring capabilities as needed.