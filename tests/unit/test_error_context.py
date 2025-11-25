"""
Unit tests for error context propagation functionality.

Tests ErrorContext class, context variables, middleware,
and context management across async boundaries.
"""

import asyncio
import pytest
import time
from uuid import uuid4

from app.core.error_context import (
    ErrorContext,
    ErrorContextMiddleware,
    with_error_context,
    request_id_var,
    user_id_var,
    correlation_id_var,
    request_start_time_var,
    additional_context_var,
    error_count_var,
)


class TestErrorContext:
    """Test core ErrorContext functionality."""

    def test_set_get_request_id(self):
        """Test setting and getting request ID."""
        # Clear context
        ErrorContext.clear()

        # Test auto-generated ID
        request_id = ErrorContext.set_request_id()
        assert request_id is not None
        assert len(request_id) > 0
        assert ErrorContext.get_request_id() == request_id

        # Test custom ID
        custom_id = "custom-request-123"
        returned_id = ErrorContext.set_request_id(custom_id)
        assert returned_id == custom_id
        assert ErrorContext.get_request_id() == custom_id

    def test_set_get_user_id(self):
        """Test setting and getting user ID."""
        # Clear context
        ErrorContext.clear()

        user_id = 12345
        ErrorContext.set_user_id(user_id)
        assert ErrorContext.get_user_id() == user_id

    def test_set_get_correlation_id(self):
        """Test setting and getting correlation ID."""
        # Clear context
        ErrorContext.clear()

        # Test auto-generated ID
        corr_id = ErrorContext.set_correlation_id()
        assert corr_id is not None
        assert len(corr_id) > 0
        assert ErrorContext.get_correlation_id() == corr_id

        # Test custom ID
        custom_corr_id = "custom-corr-456"
        returned_corr_id = ErrorContext.set_correlation_id(custom_corr_id)
        assert returned_corr_id == custom_corr_id
        assert ErrorContext.get_correlation_id() == custom_corr_id

    def test_add_get_additional_context(self):
        """Test adding and getting additional context."""
        # Clear context
        ErrorContext.clear()

        # Add single context item
        ErrorContext.add_context("operation", "create_user")
        context = ErrorContext.get_additional_context()
        assert context == {"operation": "create_user"}

        # Add multiple context items
        ErrorContext.add_context("user_id", 123)
        ErrorContext.add_context("endpoint", "/users")
        context = ErrorContext.get_additional_context()
        expected = {"operation": "create_user", "user_id": 123, "endpoint": "/users"}
        assert context == expected

    def test_get_request_duration(self):
        """Test getting request duration."""
        # Clear context
        ErrorContext.clear()

        # Initially should be None
        assert ErrorContext.get_request_duration() is None

        # Set request start time
        ErrorContext.set_request_id()
        time.sleep(0.01)  # Small delay
        duration = ErrorContext.get_request_duration()
        assert duration is not None
        assert duration >= 0.01

    def test_get_error_count(self):
        """Test getting error count."""
        # Clear context
        ErrorContext.clear()

        # Initially should be 0
        assert ErrorContext.get_error_count() == 0

    def test_get_all_context(self):
        """Test getting all context data."""
        # Clear context
        ErrorContext.clear()

        # Set various context items
        request_id = ErrorContext.set_request_id()
        ErrorContext.set_user_id(123)
        ErrorContext.set_correlation_id()
        ErrorContext.add_context("operation", "test_operation")
        time.sleep(0.01)  # For duration

        all_context = ErrorContext.get_all()

        assert all_context["request_id"] == request_id
        assert all_context["user_id"] == 123
        assert all_context["correlation_id"] is not None
        assert all_context["additional_context"] == {"operation": "test_operation"}
        assert all_context["request_duration"] is not None
        assert all_context["error_count"] == 0

        # Should not include None values
        assert "none_value" not in all_context

    def test_clear_context(self):
        """Test clearing all context."""
        # Clear context first to ensure test isolation
        ErrorContext.clear()

        # Set context
        ErrorContext.set_request_id()
        ErrorContext.set_user_id(123)
        ErrorContext.add_context("test", "value")

        # Verify context is set
        assert ErrorContext.get_request_id() is not None
        assert ErrorContext.get_user_id() == 123
        assert "test" in ErrorContext.get_additional_context()
        assert ErrorContext.get_additional_context()["test"] == "value"

        # Clear context
        ErrorContext.clear()

        # Verify context is cleared
        assert ErrorContext.get_request_id() is None
        assert ErrorContext.get_user_id() is None
        assert ErrorContext.get_correlation_id() is None
        assert ErrorContext.get_additional_context() == {}
        assert ErrorContext.get_error_count() == 0

    def test_format_context_string(self):
        """Test formatting context as string."""
        # Clear context
        ErrorContext.clear()

        # Empty context
        assert "no-context" in ErrorContext.format_context_string()

        # Set various context items
        ErrorContext.set_request_id("req-123")
        ErrorContext.set_user_id(456)
        ErrorContext.set_correlation_id("corr-789")
        ErrorContext.add_context("operation", "test")
        time.sleep(0.01)  # For duration

        context_str = ErrorContext.format_context_string()

        assert "req=req-123" in context_str
        assert "user=456" in context_str
        assert "corr=corr-789" in context_str
        assert "duration=" in context_str

    def test_create_log_extra(self):
        """Test creating log extra dictionary."""
        # Clear context
        ErrorContext.clear()

        # Set context
        ErrorContext.set_request_id("req-123")
        ErrorContext.add_context("operation", "test_operation")

        # Create log extra
        extra = ErrorContext.create_log_extra({"custom_field": "custom_value"})

        # Check required fields are present
        assert extra["request_id"] == "req-123"
        assert extra["additional_context"]["operation"] == "test_operation"
        assert extra["custom_field"] == "custom_value"
        # get_all() includes error_count and request_duration, which are expected
        assert "error_count" in extra


class TestErrorContextManager:
    """Test ErrorContext context manager functionality."""

    def test_context_manager_success(self):
        """Test context manager with successful operation."""
        # Clear context
        ErrorContext.clear()

        with ErrorContext("test_operation", {"test_param": "test_value"}):
            # Context should be set
            context = ErrorContext.get_additional_context()
            assert context["operation_name"] == "test_operation"
            assert context["test_param"] == "test_value"
            assert "operation_start_time" in context

        # Context should be restored after exit
        context = ErrorContext.get_additional_context()
        assert "operation_name" not in context
        assert "test_param" not in context

    def test_context_manager_with_exception(self):
        """Test context manager with exception."""
        # Clear context
        ErrorContext.clear()

        initial_error_count = ErrorContext.get_error_count()

        try:
            with ErrorContext("failing_operation"):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Error count should be incremented
        assert ErrorContext.get_error_count() == initial_error_count + 1

        # Context should be restored
        context = ErrorContext.get_additional_context()
        assert "operation_name" not in context

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """Test context manager with async operations."""
        # Clear context
        ErrorContext.clear()

        async def async_operation():
            with ErrorContext("async_operation"):
                await asyncio.sleep(0.01)
                context = ErrorContext.get_additional_context()
                assert context["operation_name"] == "async_operation"
                return "success"

        result = await async_operation()
        assert result == "success"

        # Context should be restored
        context = ErrorContext.get_additional_context()
        assert "operation_name" not in context


class TestErrorContextDecorator:
    """Test with_error_context decorator functionality."""

    def test_decorator_sync_function(self):
        """Test decorator with synchronous function."""
        # Clear context
        ErrorContext.clear()

        @with_error_context("decorated_operation", {"decorated_param": "value"})
        def test_function(param1, param2):
            context = ErrorContext.get_additional_context()
            assert context["operation_name"] == "decorated_operation"
            assert context["decorated_param"] == "value"
            return param1 + param2

        result = test_function(1, 2)
        assert result == 3

        # Context should be restored
        context = ErrorContext.get_additional_context()
        assert "operation_name" not in context

    @pytest.mark.asyncio
    async def test_decorator_async_function(self):
        """Test decorator with asynchronous function."""
        # Clear context
        ErrorContext.clear()

        @with_error_context("async_decorated_operation")
        async def async_test_function(value):
            await asyncio.sleep(0.01)
            context = ErrorContext.get_additional_context()
            assert context["operation_name"] == "async_decorated_operation"
            return value * 2

        result = await async_test_function(21)
        assert result == 42

        # Context should be restored
        context = ErrorContext.get_additional_context()
        assert "operation_name" not in context

    def test_decorator_with_exception(self):
        """Test decorator when function raises exception."""
        # Clear context
        ErrorContext.clear()

        initial_error_count = ErrorContext.get_error_count()

        @with_error_context("failing_decorated_operation")
        def failing_function():
            raise RuntimeError("Test error")

        try:
            failing_function()
        except RuntimeError:
            pass

        # Error count should be incremented
        assert ErrorContext.get_error_count() == initial_error_count + 1


class TestErrorContextVariables:
    """Test individual context variables."""

    def test_request_id_variable(self):
        """Test request_id context variable."""
        # Clear context
        ErrorContext.clear()

        assert request_id_var.get() is None

        ErrorContext.set_request_id("test-123")
        assert request_id_var.get() == "test-123"

    def test_user_id_variable(self):
        """Test user_id context variable."""
        # Clear context
        ErrorContext.clear()

        assert user_id_var.get() is None

        ErrorContext.set_user_id(999)
        assert user_id_var.get() == 999

    def test_correlation_id_variable(self):
        """Test correlation_id context variable."""
        # Clear context
        ErrorContext.clear()

        assert correlation_id_var.get() is None

        ErrorContext.set_correlation_id("corr-test")
        assert correlation_id_var.get() == "corr-test"

    def test_request_start_time_variable(self):
        """Test request_start_time context variable."""
        # Clear context
        ErrorContext.clear()

        assert request_start_time_var.get() is None

        ErrorContext.set_request_id()
        start_time = request_start_time_var.get()
        assert start_time is not None
        assert isinstance(start_time, float)

    def test_additional_context_variable(self):
        """Test additional_context context variable."""
        # Clear context
        ErrorContext.clear()

        assert additional_context_var.get() is None

        ErrorContext.add_context("test_key", "test_value")
        context = additional_context_var.get()
        assert context == {"test_key": "test_value"}

    def test_error_count_variable(self):
        """Test error_count context variable."""
        # Clear context
        ErrorContext.clear()

        assert error_count_var.get() == 0

        # Simulate error increment
        initial_count = error_count_var.get()
        error_count_var.set(initial_count + 1)
        assert error_count_var.get() == 1


class TestErrorContextMiddleware:
    """Test ErrorContextMiddleware functionality."""

    def test_middleware_initialization(self):
        """Test middleware initialization."""
        mock_app = None

        # Test without extract_user_id function
        middleware = ErrorContextMiddleware(mock_app)
        assert middleware.app == mock_app
        assert middleware.extract_user_id is None

        # Test with extract_user_id function
        async def mock_extract_user_id(scope):
            return 123

        middleware = ErrorContextMiddleware(mock_app, mock_extract_user_id)
        assert middleware.extract_user_id == mock_extract_user_id

    @pytest.mark.asyncio
    async def test_middleware_http_request(self):
        """Test middleware with HTTP request."""
        # Clear context
        ErrorContext.clear()

        mock_app_called = False
        context_set = False

        async def mock_app(scope, receive, send):
            nonlocal mock_app_called, context_set
            mock_app_called = True
            context_set = ErrorContext.get_request_id() is not None

        # Create HTTP scope
        scope = {"type": "http", "path": "/test", "method": "GET"}

        middleware = ErrorContextMiddleware(mock_app)

        # Mock receive and send functions
        async def receive():
            return {"type": "http.request", "body": b""}

        async def send(message):
            pass

        await middleware(scope, receive, send)

        assert mock_app_called
        assert context_set


class TestContextIsolation:
    """Test context isolation between different operations."""

    @pytest.mark.asyncio
    async def test_concurrent_context_isolation(self):
        """Test context isolation between concurrent operations."""
        # Clear context
        ErrorContext.clear()

        async def operation_a():
            ErrorContext.set_request_id("request-a")
            ErrorContext.set_user_id(100)
            await asyncio.sleep(0.01)
            return ErrorContext.get_all()

        async def operation_b():
            ErrorContext.set_request_id("request-b")
            ErrorContext.set_user_id(200)
            await asyncio.sleep(0.01)
            return ErrorContext.get_all()

        # Run operations concurrently
        task_a = asyncio.create_task(operation_a())
        task_b = asyncio.create_task(operation_b())

        result_a = await task_a
        result_b = await task_b

        # Verify contexts are isolated
        assert result_a["request_id"] == "request-a"
        assert result_a["user_id"] == 100

        assert result_b["request_id"] == "request-b"
        assert result_b["user_id"] == 200

    def test_context_restoration_after_exception(self):
        """Test context restoration after exception in context manager."""
        # Clear context
        ErrorContext.clear()

        # Set initial context
        ErrorContext.set_request_id("initial-request")
        ErrorContext.add_context("initial", "value")

        initial_context = ErrorContext.get_all()

        try:
            with ErrorContext("failing_operation"):
                ErrorContext.add_context("temporary", "temp_value")
                raise RuntimeError("Test error")
        except RuntimeError:
            pass

        # Context should be restored to initial state
        final_context = ErrorContext.get_all()
        assert final_context["request_id"] == "initial-request"
        assert final_context["additional_context"]["initial"] == "value"
        assert "temporary" not in final_context["additional_context"]


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_multiple_set_operations(self):
        """Test multiple set operations for same context."""
        # Clear context
        ErrorContext.clear()

        # Set request ID multiple times
        id1 = ErrorContext.set_request_id()
        id2 = ErrorContext.set_request_id()
        id3 = ErrorContext.set_request_id("custom")

        assert id2 != id1  # Auto-generated should be different
        assert id3 == "custom"
        assert ErrorContext.get_request_id() == "custom"

    def test_empty_additional_context(self):
        """Test handling of empty additional context."""
        # Clear context
        ErrorContext.clear()

        # Test get_additional_context when empty
        context = ErrorContext.get_additional_context()
        assert context == {}

        # Test get_all - empty additional_context {} is included (not None)
        context = ErrorContext.get_all()
        # Empty dict is not None, so it's included in get_all()
        assert context.get("additional_context", {}) == {}

    def test_uuid_uniqueness(self):
        """Test that generated UUIDs are unique."""
        # Clear context
        ErrorContext.clear()

        # Generate multiple request IDs
        ids = []
        for _ in range(10):
            ErrorContext.clear()
            request_id = ErrorContext.set_request_id()
            ids.append(request_id)

        # All IDs should be unique
        assert len(set(ids)) == len(ids)

    def test_context_with_none_values(self):
        """Test context handling with None values."""
        # Clear context
        ErrorContext.clear()

        # Add context with None value
        ErrorContext.add_context("test_key", None)
        context = ErrorContext.get_additional_context()
        assert "test_key" in context
        assert context["test_key"] is None

        # Test get_all filters None values properly
        all_context = ErrorContext.get_all()
        # None values in additional_context should still be included
        assert "test_key" in all_context["additional_context"]
