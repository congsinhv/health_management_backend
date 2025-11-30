"""
Shared test utilities for VHealth microservices testing.

Provides common assertion helpers, mock utilities, and test data generators
used across all test suites to ensure consistency and reduce duplication.

Usage:
    from tests.shared_utils import (
        assert_success_response, assert_error_response,
        create_mock_user, create_mock_qa_request,
        assert_exception_matches_schema
    )
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List
from unittest.mock import Mock
import pytest

from app.core.shared.schemas import BaseResponse, ErrorResponse, SuccessResponse
from app.core.shared.exceptions import VHealthException
from app.interfaces.qa_interface import QARequest
from app.interfaces.predict_interface import PredictionRequest


def assert_success_response(
    response: BaseResponse, status: str = "success", has_data: bool = False
) -> None:
    """Assert response is successful with expected structure."""
    assert (
        response.status == status
    ), f"Expected status '{status}', got '{response.status}'"
    assert isinstance(
        response.timestamp, datetime
    ), "Response timestamp should be datetime"

    if has_data and hasattr(response, "data"):
        assert response.data is not None, "Response should have data when has_data=True"


def assert_error_response(
    response: ErrorResponse,
    expected_status: str = "error",
    expected_error: Optional[str] = None,
    expected_message_contains: Optional[str] = None,
) -> None:
    """Assert error response has expected structure."""
    assert (
        response.status == expected_status
    ), f"Expected status '{expected_status}', got '{response.status}'"
    assert isinstance(response.error, str), "Response should have error field"
    assert isinstance(response.message, str), "Response should have message field"
    assert isinstance(
        response.timestamp, datetime
    ), "Response timestamp should be datetime"

    if expected_error:
        assert (
            response.error == expected_error
        ), f"Expected error '{expected_error}', got '{response.error}'"

    if expected_message_contains:
        assert (
            expected_message_contains in response.message
        ), f"Message '{response.message}' should contain '{expected_message_contains}'"


def assert_exception_matches_schema(
    exception: VHealthException,
    expected_type: type,
    expected_message_contains: Optional[str] = None,
) -> None:
    """Assert exception matches expected type and has valid structure."""
    assert isinstance(
        exception, expected_type
    ), f"Expected {expected_type}, got {type(exception)}"
    assert hasattr(exception, "message"), "Exception should have message attribute"
    assert hasattr(exception, "details"), "Exception should have details attribute"
    assert hasattr(
        exception, "error_code"
    ), "Exception should have error_code attribute"

    assert isinstance(exception.message, str), "Exception message should be string"
    assert isinstance(exception.details, dict), "Exception details should be dict"
    assert isinstance(
        exception.error_code, str
    ), "Exception error_code should be string"

    if expected_message_contains:
        assert (
            expected_message_contains in exception.message
        ), f"Exception message '{exception.message}' should contain '{expected_message_contains}'"


def create_mock_user(
    user_id: int = 1,
    email: str = "test@example.com",
    is_verified: bool = True,
    is_active: bool = True,
) -> Dict[str, Any]:
    """Create mock user data for testing."""
    return {
        "id": user_id,
        "email": email,
        "is_verified": is_verified,
        "is_active": is_active,
        "created_at": datetime.utcnow(),
        "updated_at": None,
    }


def create_mock_qa_request(
    question: str = "What is diabetes?",
    user_id: Optional[int] = 1,
    conversation_id: Optional[int] = None,
) -> QARequest:
    """Create mock QA request for testing."""
    return QARequest(
        question=question,
        user_id=user_id,
        conversation_id=conversation_id,
        threshold=0.55,
    )


def create_mock_prediction_request(
    age: int = 30,
    gender: str = "male",
    height: float = 175.0,
    weight: float = 70.0,
    user_id: Optional[int] = 1,
) -> PredictionRequest:
    """Create mock prediction request for testing."""
    return PredictionRequest(
        age=age,
        gender=gender,
        height=height,
        weight=weight,
        activity_level="moderate",
        smoking_status="never",
        alcohol_consumption="moderate",
        user_id=user_id,
        prediction_type="general",
    )


def create_mock_service_client() -> Mock:
    """Create mock service client for testing service-to-service communication."""
    client = Mock()
    client.post.return_value = {
        "status": "success",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {},
    }
    client.get.return_value = {
        "status": "success",
        "timestamp": datetime.utcnow().isoformat(),
        "data": {},
    }
    client.health_check.return_value = {
        "status": "success",
        "service": "test-service",
        "timestamp": datetime.utcnow().isoformat(),
    }
    return client


def assert_http_status_code(exception: VHealthException, expected_code: int) -> None:
    """Assert exception maps to expected HTTP status code."""
    from app.core.shared.exceptions import get_http_status_code

    actual_code = get_http_status_code(exception)
    assert (
        actual_code == expected_code
    ), f"Expected HTTP {expected_code}, got {actual_code}"


def create_mock_conversation(
    conversation_id: int = 1, user_id: int = 1, title: str = "Health Questions"
) -> Dict[str, Any]:
    """Create mock conversation data for testing."""
    return {
        "id": conversation_id,
        "user_id": user_id,
        "title": title,
        "created_at": datetime.utcnow(),
        "updated_at": None,
        "metadata": {},
    }


def create_mock_message(
    message_id: int = 1,
    conversation_id: int = 1,
    content: str = "What is diabetes?",
    role: str = "user",
) -> Dict[str, Any]:
    """Create mock message data for testing."""
    return {
        "id": message_id,
        "conversation_id": conversation_id,
        "content": content,
        "role": role,
        "created_at": datetime.utcnow(),
        "metadata": {},
    }


def assert_sanitized_error_details(
    details: Dict[str, Any], user_context: bool = False, should_redact: bool = False
) -> None:
    """Assert error details are properly sanitized."""
    from app.core.shared.exceptions import sanitize_error_details

    # Add some sensitive data
    test_details = details.copy()
    test_details.update(
        {
            "password": "secret123",
            "token": "token123",
            "api_key": "key123",
            "public_field": "public_value",
        }
    )

    sanitized = sanitize_error_details(test_details, user_context)

    # Check sensitive fields are handled correctly
    if user_context:
        assert (
            "password" not in sanitized
        ), "Sensitive fields should be removed in user context"
        assert (
            "token" not in sanitized
        ), "Sensitive fields should be removed in user context"
    else:
        if should_redact:
            assert (
                sanitized["password"] == "[REDACTED]"
            ), "Sensitive fields should be redacted"
            assert (
                sanitized["token"] == "[REDACTED]"
            ), "Sensitive fields should be redacted"

    # Check non-sensitive fields are preserved
    assert "public_field" in sanitized, "Non-sensitive fields should be preserved"
    assert (
        sanitized["public_field"] == "public_value"
    ), "Non-sensitive fields should have original values"


async def async_test_wrapper(test_func: callable, *args, **kwargs) -> Any:
    """Wrapper for async test functions to handle event loop properly."""
    if asyncio.iscoroutinefunction(test_func):
        return await test_func(*args, **kwargs)
    else:
        return test_func(*args, **kwargs)


def create_batch_test_data(count: int, data_factory: callable) -> List[Dict[str, Any]]:
    """Create batch test data using factory function."""
    return [data_factory(i) for i in range(count)]


def assert_pagination_response(
    response,
    expected_page: int,
    expected_page_size: int,
    expected_total: int,
    has_next: Optional[bool] = None,
    has_prev: Optional[bool] = None,
) -> None:
    """Assert paginated response has correct structure."""
    assert response.page == expected_page
    assert response.page_size == expected_page_size
    assert response.total_items == expected_total
    assert (
        response.total_pages
        == (expected_total + expected_page_size - 1) // expected_page_size
    )

    if has_next is not None:
        assert response.has_next == has_next
    else:
        # Calculate expected has_next
        expected_has_next = (expected_page * expected_page_size) < expected_total
        assert response.has_next == expected_has_next

    if has_prev is not None:
        assert response.has_prev == has_prev
    else:
        # Calculate expected has_prev
        expected_has_prev = expected_page > 1
        assert response.has_prev == expected_has_prev


def create_test_file_data(
    filename: str = "test.pdf",
    content_type: str = "application/pdf",
    file_size: int = 1024,
) -> Dict[str, Any]:
    """Create mock file upload data for testing."""
    return {
        "filename": filename,
        "content_type": content_type,
        "file_size": file_size,
        "upload_time": datetime.utcnow(),
        "file_url": f"https://example.com/files/{filename}",
        "file_id": f"file_{filename}_{datetime.utcnow().timestamp()}",
    }


class MockAsyncContext:
    """Mock async context manager for testing."""

    def __init__(self, return_value=None):
        self.return_value = return_value
        self.enter_called = False
        self.exit_called = False

    async def __aenter__(self):
        self.enter_called = True
        return self.return_value

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.exit_called = True
        return False


def assert_datetime_close(
    dt1: datetime, dt2: datetime, tolerance_seconds: int = 5
) -> None:
    """Assert two datetimes are close within tolerance."""
    diff = abs(dt1 - dt2)
    assert (
        diff.total_seconds() <= tolerance_seconds
    ), f"Datetime difference {diff.total_seconds()}s exceeds tolerance {tolerance_seconds}s"


def create_mock_health_check(
    service_name: str = "test-service",
    status: str = "healthy",
    version: Optional[str] = "1.0.0",
) -> Dict[str, Any]:
    """Create mock health check response."""
    return {
        "status": "success",
        "service": service_name,
        "service_status": status,
        "version": version,
        "timestamp": datetime.utcnow(),
        "details": {},
    }
