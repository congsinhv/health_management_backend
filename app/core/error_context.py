"""
Error context propagation for VHealth application.

Provides request-scoped context for error handling, including
request IDs, user IDs, and correlation tracking across async boundaries.

Uses Python's contextvars module to maintain context across
async/await boundaries and background tasks.
"""

import logging
import time
from contextvars import ContextVar, Token
from typing import Any, Dict, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Context variables for error propagation
request_id_var: ContextVar[str] = ContextVar("request_id", default=None)
user_id_var: ContextVar[int] = ContextVar("user_id", default=None)
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default=None)
request_start_time_var: ContextVar[float] = ContextVar(
    "request_start_time", default=None
)
additional_context_var: ContextVar[Dict[str, Any]] = ContextVar(
    "additional_context", default=None
)

# Context variable for error tracking
error_count_var: ContextVar[int] = ContextVar("error_count", default=0)


class ErrorContext:
    """
    Context manager for error handling throughout the request lifecycle.

    Provides request-scoped context that propagates across async boundaries,
    enabling consistent error tracking and correlation.

    Usage:
        # Set context at request start
        request_id = ErrorContext.set_request_id()
        ErrorContext.set_user_id(user.id)
        ErrorContext.set_correlation_id()

        # Use in services
        with ErrorContext("operation_name", additional_data={"key": "value"}):
            # Your code here
            pass

        # Get context for logging
        context = ErrorContext.get_all()
        logger.info("Operation completed", extra=context)
    """

    def __init__(
        self, operation_name: str, additional_data: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize error context for an operation.

        Args:
            operation_name: Name of the operation being performed
            additional_data: Additional context data to include
        """
        self.operation_name = operation_name
        self.additional_data = additional_data or {}
        self.start_time = time.time()
        self.tokens: Dict[str, Token] = {}

    def __enter__(self) -> "ErrorContext":
        """Enter context manager and set operation context."""
        # Set operation-specific context
        current_context = additional_context_var.get() or {}
        operation_context = {
            "operation_name": self.operation_name,
            "operation_start_time": self.start_time,
            **self.additional_data,
            **current_context,
        }

        # Store token for restoration
        self.tokens["additional_context"] = additional_context_var.set(
            operation_context
        )

        # Log operation start
        logger.debug(
            f"Starting operation: {self.operation_name}", extra=ErrorContext.get_all()
        )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and restore previous context."""
        duration = time.time() - self.start_time

        if exc_type is not None:
            # Increment error count
            current_count = error_count_var.get() or 0
            error_count_var.set(current_count + 1)

            # Log error with context
            logger.error(
                f"Operation failed: {self.operation_name} (duration: {duration:.3f}s)",
                exc_info=(exc_type, exc_val, exc_tb),
                extra=ErrorContext.get_all(),
            )
        else:
            # Log success
            logger.debug(
                f"Operation completed: {self.operation_name} (duration: {duration:.3f}s)",
                extra=ErrorContext.get_all(),
            )

        # Restore previous context
        for name, token in self.tokens.items():
            if name == "additional_context":
                additional_context_var.reset(token)

    @staticmethod
    def set_request_id(request_id: Optional[str] = None) -> str:
        """
        Set request ID for current context.

        Args:
            request_id: Request ID to set, generates UUID if None

        Returns:
            The request ID that was set
        """
        if request_id is None:
            request_id = str(uuid4())

        request_id_var.set(request_id)
        request_start_time_var.set(time.time())

        return request_id

    @staticmethod
    def get_request_id() -> Optional[str]:
        """Get request ID from current context."""
        return request_id_var.get()

    @staticmethod
    def set_user_id(user_id: int) -> None:
        """Set user ID for current context."""
        user_id_var.set(user_id)

    @staticmethod
    def get_user_id() -> Optional[int]:
        """Get user ID from current context."""
        return user_id_var.get()

    @staticmethod
    def set_correlation_id(correlation_id: Optional[str] = None) -> str:
        """
        Set correlation ID for current context.

        Args:
            correlation_id: Correlation ID to set, generates UUID if None

        Returns:
            The correlation ID that was set
        """
        if correlation_id is None:
            correlation_id = str(uuid4())

        correlation_id_var.set(correlation_id)
        return correlation_id

    @staticmethod
    def get_correlation_id() -> Optional[str]:
        """Get correlation ID from current context."""
        return correlation_id_var.get()

    @staticmethod
    def add_context(key: str, value: Any) -> None:
        """
        Add additional context data.

        Args:
            key: Context key
            value: Context value
        """
        current_context = additional_context_var.get() or {}
        current_context[key] = value
        additional_context_var.set(current_context)

    @staticmethod
    def get_additional_context() -> Dict[str, Any]:
        """Get additional context data."""
        return additional_context_var.get() or {}

    @staticmethod
    def get_request_duration() -> Optional[float]:
        """Get request duration in seconds."""
        start_time = request_start_time_var.get()
        if start_time is not None:
            return time.time() - start_time
        return None

    @staticmethod
    def get_error_count() -> int:
        """Get error count for current request."""
        return error_count_var.get() or 0

    @staticmethod
    def get_all() -> Dict[str, Any]:
        """
        Get all context data as dictionary.

        Returns:
            Dictionary with all context information
        """
        context = {
            "request_id": ErrorContext.get_request_id(),
            "user_id": ErrorContext.get_user_id(),
            "correlation_id": ErrorContext.get_correlation_id(),
            "request_duration": ErrorContext.get_request_duration(),
            "error_count": ErrorContext.get_error_count(),
            "additional_context": ErrorContext.get_additional_context(),
        }

        # Remove None values
        return {k: v for k, v in context.items() if v is not None}

    @staticmethod
    def clear() -> None:
        """Clear all context variables."""
        request_id_var.set(None)
        user_id_var.set(None)
        correlation_id_var.set(None)
        request_start_time_var.set(None)
        additional_context_var.set(None)
        error_count_var.set(0)

    @staticmethod
    def create_log_extra(
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create log extra dictionary with context.

        Args:
            additional_data: Additional data to include

        Returns:
            Dictionary suitable for logger extra parameter
        """
        context = ErrorContext.get_all()
        if additional_data:
            context.update(additional_data)

        return context

    @staticmethod
    def format_context_string() -> str:
        """
        Format context as string for logging.

        Returns:
            Formatted context string
        """
        parts = []

        if request_id := ErrorContext.get_request_id():
            parts.append(f"req={request_id}")

        if user_id := ErrorContext.get_user_id():
            parts.append(f"user={user_id}")

        if correlation_id := ErrorContext.get_correlation_id():
            parts.append(f"corr={correlation_id}")

        if error_count := ErrorContext.get_error_count():
            parts.append(f"errors={error_count}")

        if duration := ErrorContext.get_request_duration():
            parts.append(f"duration={duration:.3f}s")

        return " ".join(parts) if parts else "no-context"


class ErrorContextMiddleware:
    """
    FastAPI middleware to initialize error context for each request.

    Automatically sets request ID, user ID (from JWT token), and correlation ID.
    """

    def __init__(self, app, extract_user_id=None):
        """
        Initialize middleware.

        Args:
            app: FastAPI application
            extract_user_id: Optional function to extract user ID from request
        """
        self.app = app
        self.extract_user_id = extract_user_id

    async def __call__(self, scope, receive, send):
        """ASGI middleware implementation."""
        if scope["type"] == "http":
            # Initialize context for HTTP requests
            request_id = ErrorContext.set_request_id()
            ErrorContext.set_correlation_id()

            # Try to extract user ID if function provided
            if self.extract_user_id:
                try:
                    # This is a simplified approach - in practice you'd
                    # need to parse the request and extract JWT token
                    user_id = await self.extract_user_id(scope)
                    if user_id:
                        ErrorContext.set_user_id(user_id)
                except Exception:
                    # User ID extraction should not break request processing
                    logger.warning("Failed to extract user ID from request")

        # Call the application
        await self.app(scope, receive, send)

        # Clean up context after request
        if scope["type"] == "http":
            # Log request completion
            logger.info(f"Request completed: {ErrorContext.format_context_string()}")
            ErrorContext.clear()


# Context decorator for automatic context management
def with_error_context(
    operation_name: str, additional_data: Optional[Dict[str, Any]] = None
):
    """
    Decorator to automatically wrap functions with error context.

    Args:
        operation_name: Name of the operation
        additional_data: Additional context data

    Usage:
        @with_error_context("database_query", {"table": "users"})
        async def get_user(user_id: int):
            # Function implementation
            pass
    """

    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            with ErrorContext(operation_name, additional_data):
                return await func(*args, **kwargs)

        def sync_wrapper(*args, **kwargs):
            with ErrorContext(operation_name, additional_data):
                return func(*args, **kwargs)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Utility functions for common patterns


async def extract_user_id_from_request(scope):
    """
    Extract user ID from FastAPI request scope.

    This is a placeholder implementation - in practice you'd need to
    parse JWT tokens or use FastAPI's dependency injection system.
    """
    # Implementation would depend on your authentication setup
    return None


def get_default_middleware():
    """Get default error context middleware."""
    return ErrorContextMiddleware(extract_user_id=extract_user_id_from_request)
