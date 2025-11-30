"""
Error context management for Chat AI microservice.

Provides request-scoped context for error tracking, correlation,
and debugging across service boundaries.

Usage:
    from app.core.error_context import ErrorContext

    # Set context at request start
    request_id = ErrorContext.set_request_id()
    ErrorContext.set_user_id(user.id)
    ErrorContext.add_context("operation", "qa_inference")

    # Use context manager for operations
    with ErrorContext("process_question", {"question_length": len(question)}):
        result = await process_question(question)

    # Get context for logging
    context = ErrorContext.get_all()
    logger.info("Operation completed", extra=context)
"""

import logging
import threading
import time
import uuid
from typing import Any, Dict, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class ErrorContext:
    """Thread-local context for error tracking and correlation."""

    _context = threading.local()

    @classmethod
    def set_request_id(cls, request_id: Optional[str] = None) -> str:
        """Set or generate request ID for correlation."""
        if request_id is None:
            request_id = str(uuid.uuid4())[:8]
        cls._ensure_context()
        cls._context.request_id = request_id
        return request_id

    @classmethod
    def set_user_id(cls, user_id: Optional[str] = None) -> None:
        """Set user ID in context."""
        cls._ensure_context()
        cls._context.user_id = user_id

    @classmethod
    def set_correlation_id(cls, correlation_id: Optional[str] = None) -> str:
        """Set or generate correlation ID for distributed tracing."""
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())[:8]
        cls._ensure_context()
        cls._context.correlation_id = correlation_id
        return correlation_id

    @classmethod
    def add_context(cls, key: str, value: Any) -> None:
        """Add arbitrary context information."""
        cls._ensure_context()
        if not hasattr(cls._context, 'custom'):
            cls._context.custom = {}
        cls._context.custom[key] = value

    @classmethod
    def get_request_id(cls) -> Optional[str]:
        """Get current request ID."""
        return getattr(cls._context, 'request_id', None)

    @classmethod
    def get_user_id(cls) -> Optional[str]:
        """Get current user ID."""
        return getattr(cls._context, 'user_id', None)

    @classmethod
    def get_correlation_id(cls) -> Optional[str]:
        """Get current correlation ID."""
        return getattr(cls._context, 'correlation_id', None)

    @classmethod
    def get_custom_context(cls) -> Dict[str, Any]:
        """Get custom context dictionary."""
        return getattr(cls._context, 'custom', {})

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        """Get all context information."""
        return {
            "request_id": cls.get_request_id(),
            "user_id": cls.get_user_id(),
            "correlation_id": cls.get_correlation_id(),
            "timestamp": time.time(),
            **cls.get_custom_context(),
        }

    @classmethod
    def clear(cls) -> None:
        """Clear all context information."""
        cls._context.__dict__.clear()

    @classmethod
    def _ensure_context(cls) -> None:
        """Ensure context dictionary exists."""
        if not hasattr(cls._context, 'initialized'):
            cls._context.initialized = True
            cls._context.request_id = None
            cls._context.user_id = None
            cls._context.correlation_id = None
            cls._context.custom = {}

    @classmethod
    @contextmanager
    def operation(cls, operation: str, context: Optional[Dict[str, Any]] = None):
        """Context manager for operation tracking."""
        start_time = time.time()
        cls.add_context("operation", operation)
        cls.add_context("operation_start", start_time)

        if context:
            for key, value in context.items():
                cls.add_context(key, value)

        try:
            yield
            duration = time.time() - start_time
            cls.add_context("operation_duration", duration)
            cls.add_context("operation_success", True)

        except Exception as e:
            duration = time.time() - start_time
            cls.add_context("operation_duration", duration)
            cls.add_context("operation_success", False)
            cls.add_context("operation_error", str(e))
            raise

        finally:
            # Clean up operation-specific context
            cls.remove_context("operation")
            cls.remove_context("operation_start")
            cls.remove_context("operation_duration")
            cls.remove_context("operation_success")
            cls.remove_context("operation_error")

    @classmethod
    def remove_context(cls, key: str) -> None:
        """Remove a specific context key."""
        custom = cls.get_custom_context()
        if key in custom:
            del custom[key]


# Legacy compatibility
ErrorContext.operation = ErrorContext.operation