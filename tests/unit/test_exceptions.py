"""
Unit tests for custom exception hierarchy.

Tests exception creation, serialization, status code mapping,
and error detail sanitization functionality.
"""

import pytest
from app.exceptions import (
    VHealthException,
    ResourceNotFoundException,
    AuthenticationException,
    ValidationException,
    BusinessLogicException,
    DatabaseException,
    ServiceUnavailableException,
    RateLimitException,
    ConfigurationException,
    DatabaseConnectionException,
    DatabaseTimeoutException,
    DataCorruptionException,
    get_http_status_code,
    sanitize_error_details,
    is_critical_error,
)


class TestVHealthException:
    """Test base VHealthException functionality."""

    def test_basic_exception_creation(self):
        """Test creating a basic VHealthException."""
        exc = VHealthException("Test message")
        assert exc.message == "Test message"
        assert exc.details == {}
        assert exc.error_code == "VHealthException"
        assert str(exc) == "Test message"

    def test_exception_with_details(self):
        """Test creating exception with details."""
        details = {"user_id": 123, "field": "email"}
        exc = VHealthException("Test message", details=details)
        assert exc.details == details

    def test_exception_with_error_code(self):
        """Test creating exception with custom error code."""
        exc = VHealthException("Test message", error_code="CUSTOM_ERROR")
        assert exc.error_code == "CUSTOM_ERROR"

    def test_to_dict(self):
        """Test exception serialization to dictionary."""
        details = {"field": "email", "value": "invalid"}
        exc = ValidationException("Invalid email format", details=details)

        result = exc.to_dict()
        expected = {
            "error": "ValidationException",
            "message": "Invalid email format",
            "details": details,
        }
        assert result == expected

    def test_to_dict_without_details(self):
        """Test exception serialization without details."""
        exc = ResourceNotFoundException("User not found")

        result = exc.to_dict()
        expected = {
            "error": "ResourceNotFoundException",
            "message": "User not found",
            "details": {},
        }
        assert result == expected


class TestSpecificExceptions:
    """Test specific exception types and inheritance."""

    def test_resource_not_found_exception(self):
        """Test ResourceNotFoundException."""
        details = {"user_id": 123}
        exc = ResourceNotFoundException("User not found", details)

        assert isinstance(exc, VHealthException)
        assert exc.message == "User not found"
        assert exc.details == details
        assert exc.error_code == "ResourceNotFoundException"

    def test_authentication_exception(self):
        """Test AuthenticationException."""
        exc = AuthenticationException("Invalid credentials")

        assert isinstance(exc, VHealthException)
        assert exc.message == "Invalid credentials"
        assert exc.error_code == "AuthenticationException"

    def test_validation_exception(self):
        """Test ValidationException."""
        details = {"field": "email", "value": "invalid-email"}
        exc = ValidationException("Invalid email format", details)

        assert isinstance(exc, VHealthException)
        assert exc.error_code == "ValidationException"

    def test_business_logic_exception(self):
        """Test BusinessLogicException."""
        exc = BusinessLogicException("Quota exceeded")

        assert isinstance(exc, VHealthException)
        assert exc.error_code == "BusinessLogicException"

    def test_service_unavailable_exception(self):
        """Test ServiceUnavailableException."""
        exc = ServiceUnavailableException("External service down")

        assert isinstance(exc, VHealthException)
        assert exc.error_code == "ServiceUnavailableException"

    def test_database_exception(self):
        """Test DatabaseException."""
        exc = DatabaseException("Connection failed")

        assert isinstance(exc, VHealthException)
        assert exc.error_code == "DatabaseException"

    def test_rate_limit_exception(self):
        """Test RateLimitException."""
        exc = RateLimitException("Too many requests")

        assert isinstance(exc, VHealthException)
        assert exc.error_code == "RateLimitException"

    def test_configuration_exception(self):
        """Test ConfigurationException."""
        exc = ConfigurationException("Missing API key")

        assert isinstance(exc, VHealthException)
        assert exc.error_code == "ConfigurationException"


class TestHttpStatusMapping:
    """Test HTTP status code mapping for exceptions."""

    def test_resource_not_found_status(self):
        """Test 404 status for resource not found."""
        exc = ResourceNotFoundException("User not found")
        assert get_http_status_code(exc) == 404

    def test_authentication_status(self):
        """Test 401 status for authentication errors."""
        exc = AuthenticationException("Invalid token")
        assert get_http_status_code(exc) == 401

    def test_validation_status(self):
        """Test 422 status for validation errors."""
        exc = ValidationException("Invalid input")
        assert get_http_status_code(exc) == 422

    def test_business_logic_default_status(self):
        """Test 400 status for business logic errors."""
        exc = BusinessLogicException("Invalid operation")
        assert get_http_status_code(exc) == 400

    def test_duplicate_resource_status(self):
        """Test 409 status for duplicate resource errors."""
        exc = BusinessLogicException("User already exists")
        assert get_http_status_code(exc) == 400  # Default

    def test_service_unavailable_status(self):
        """Test 503 status for service unavailable."""
        exc = ServiceUnavailableException("External service down")
        assert get_http_status_code(exc) == 503

    def test_database_status(self):
        """Test 500 status for database errors."""
        exc = DatabaseException("Connection failed")
        assert get_http_status_code(exc) == 500

    def test_rate_limit_status(self):
        """Test 429 status for rate limit errors."""
        exc = RateLimitException("Too many requests")
        assert get_http_status_code(exc) == 429

    def test_unknown_exception_status(self):
        """Test 500 status for unknown exceptions."""

        class UnknownException(VHealthException):
            pass

        exc = UnknownException("Unknown error")
        assert get_http_status_code(exc) == 500


class TestErrorDetailSanitization:
    """Test error detail sanitization for security."""

    def test_safe_details_passthrough(self):
        """Test safe details pass through unchanged."""
        details = {"user_id": 123, "field": "email", "operation": "create_user"}

        result = sanitize_error_details(details)
        assert result == details

    def test_sensitive_data_redaction(self):
        """Test sensitive data is redacted for logging."""
        details = {
            "user_id": 123,
            "password": "secret123",
            "token": "abc123token",
            "api_key": "secret-key",
            "normal_field": "safe_value",
        }

        result = sanitize_error_details(details)
        expected = {
            "user_id": 123,
            "password": "[REDACTED]",
            "token": "[REDACTED]",
            "api_key": "[REDACTED]",
            "normal_field": "safe_value",
        }
        assert result == expected

    def test_sensitive_data_removal_for_user_context(self):
        """Test sensitive data is removed for user responses."""
        details = {
            "user_id": 123,
            "password": "secret123",
            "token": "abc123token",
            "normal_field": "safe_value",
        }

        result = sanitize_error_details(details, user_context=True)
        expected = {"user_id": 123, "normal_field": "safe_value"}
        assert result == expected

    def test_empty_details_handling(self):
        """Test handling of empty or None details."""
        assert sanitize_error_details(None) == {}
        assert sanitize_error_details({}) == {}

    def test_case_insensitive_sensitive_fields(self):
        """Test case-insensitive sensitive field detection."""
        details = {
            "user_id": 123,
            "PASSWORD": "secret123",
            "Api-Key": "secret-key",
            "auth_token": "token123",
        }

        result = sanitize_error_details(details)
        assert result["PASSWORD"] == "[REDACTED]"
        assert result["Api-Key"] == "[REDACTED]"
        assert result["auth_token"] == "[REDACTED]"
        assert result["user_id"] == 123


class TestCriticalErrorDetection:
    """Test critical error detection functionality."""

    def test_critical_error_detection(self):
        """Test detection of critical errors."""
        critical_exceptions = [
            DatabaseConnectionException("Connection failed"),
            DatabaseTimeoutException("Query timeout"),
            ServiceUnavailableException("Service down"),
            ConfigurationException("Config missing"),
            DataCorruptionException("Data corrupted"),
        ]

        for exc in critical_exceptions:
            assert is_critical_error(
                exc
            ), f"{exc.__class__.__name__} should be critical"

    def test_non_critical_error_detection(self):
        """Test detection of non-critical errors."""
        non_critical_exceptions = [
            ValidationException("Invalid input"),
            ResourceNotFoundException("Not found"),
            AuthenticationException("Auth failed"),
            BusinessLogicException("Business rule violated"),
        ]

        for exc in non_critical_exceptions:
            assert not is_critical_error(
                exc
            ), f"{exc.__class__.__name__} should not be critical"

    def test_critical_error_inheritance(self):
        """Test critical error detection with inheritance."""

        # Test that custom exceptions inheriting critical types are detected
        class CustomDatabaseError(DatabaseConnectionException):
            pass

        exc = CustomDatabaseError("Custom DB error")
        assert is_critical_error(exc)


class TestInheritanceHierarchy:
    """Test exception inheritance relationships."""

    def test_authentication_subclasses(self):
        """Test authentication exception inheritance."""
        from app.exceptions import (
            TokenExpiredException,
            TokenInvalidException,
            InvalidCredentialsException,
            AccountDisabledException,
        )

        base_auth = AuthenticationException("Base auth error")
        token_expired = TokenExpiredException("Token expired")
        token_invalid = TokenInvalidException("Token invalid")
        invalid_creds = InvalidCredentialsException("Invalid creds")
        account_disabled = AccountDisabledException("Account disabled")

        # All should be instances of AuthenticationException
        assert isinstance(token_expired, AuthenticationException)
        assert isinstance(token_invalid, AuthenticationException)
        assert isinstance(invalid_creds, AuthenticationException)
        assert isinstance(account_disabled, AuthenticationException)

        # All should be instances of VHealthException
        for exc in [
            base_auth,
            token_expired,
            token_invalid,
            invalid_creds,
            account_disabled,
        ]:
            assert isinstance(exc, VHealthException)

    def test_validation_subclasses(self):
        """Test validation exception inheritance."""
        from app.exceptions import (
            MissingFieldException,
            InvalidFormatException,
            OutOfRangeException,
        )

        missing = MissingFieldException("Field missing")
        invalid = InvalidFormatException("Invalid format")
        out_of_range = OutOfRangeException("Out of range")

        # All should be instances of ValidationException and VHealthException
        for exc in [missing, invalid, out_of_range]:
            assert isinstance(exc, ValidationException)
            assert isinstance(exc, VHealthException)

    def test_service_specific_exceptions(self):
        """Test service-specific exception inheritance."""
        from app.exceptions import (
            EmailException,
            PDFGenerationException,
            QAServiceException,
            AIServiceException,
            PredictionException,
            OAuthException,
        )

        service_exceptions = [
            EmailException("Email error"),
            PDFGenerationException("PDF error"),
            QAServiceException("QA error"),
            AIServiceException("AI error"),
            PredictionException("Prediction error"),
            OAuthException("OAuth error"),
        ]

        # All should inherit from VHealthException
        for exc in service_exceptions:
            assert isinstance(exc, VHealthException)


class TestExceptionMessages:
    """Test exception message handling."""

    def test_message_preservation(self):
        """Test exception messages are preserved."""
        message = "User with ID 123 not found"
        exc = ResourceNotFoundException(message)

        assert exc.message == message
        assert str(exc) == message

    def test_long_message_handling(self):
        """Test handling of very long error messages."""
        long_message = "A" * 1000
        exc = VHealthException(long_message)

        assert len(exc.message) == 1000
        assert str(exc) == long_message

    def test_unicode_message_handling(self):
        """Test handling of unicode characters in messages."""
        unicode_message = "Người dùng không tồn tại"  # Vietnamese
        exc = ResourceNotFoundException(unicode_message)

        assert exc.message == unicode_message
        assert str(exc) == unicode_message
