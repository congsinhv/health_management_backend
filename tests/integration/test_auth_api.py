"""
Integration tests for authentication API endpoints.

Tests the actual authentication endpoints that are available in the codebase.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from fastapi import status

from app.main import app
from app.schemas.user import UserResponse, TokenPair


@pytest.mark.integration
class TestAuthAPI:
    """Test cases for authentication API endpoints."""

    @pytest.fixture
    def client(self, test_db_pool):
        """Test client with dependency overrides."""
        from app.main import app
        from app.db.database import get_database_pool

        app.dependency_overrides[get_database_pool] = lambda: test_db_pool
        return TestClient(app)

    @pytest.fixture
    def sample_user_response(self):
        """Sample user response data."""
        from app.schemas.user_profile import UserProfileResponse

        return UserResponse(
            id=1,
            email="test@example.com",
            is_active=True,
            provider="local",
            email_verified=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            profile=UserProfileResponse(
                id=1,
                user_id=1,
                first_name="Test",
                last_name="User",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            ),
        )

    @pytest.fixture
    def sample_token_pair(self):
        """Sample token pair response."""
        return TokenPair(
            access_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.access_token",
            refresh_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.refresh_token",
        )

    # Test GET /me endpoint

    async def test_get_current_user_success(self, client, sample_user_response):
        """Test getting current authenticated user."""
        from app.auth.dependencies import get_current_active_user
        from app.main import app

        # Override the dependency to return our sample user
        app.dependency_overrides[get_current_active_user] = lambda: sample_user_response

        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer valid_token"}
        )

        # Clean up override
        app.dependency_overrides.pop(get_current_active_user, None)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["profile"]["first_name"] == "Test"
        assert data["profile"]["last_name"] == "User"
        assert data["is_active"] is True

    async def test_get_current_user_unauthorized(self, client):
        """Test getting current user without authentication."""
        # Don't provide authorization header, should fail auth
        response = client.get("/api/v1/auth/me")

        # Should return 401 or 403 depending on auth implementation
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    # Test POST /verify-email endpoint

    @patch("app.api.auth.UserService")
    async def test_verify_email_success(self, mock_user_service_class, client):
        """Test successful email verification."""
        mock_user_service = AsyncMock()
        mock_user_service.verify_email.return_value = True
        mock_user_service_class.return_value = mock_user_service

        verification_data = {"token": "verification_token_123"}
        response = client.post("/api/v1/auth/verify-email", json=verification_data)

        assert response.status_code == status.HTTP_200_OK
        assert "successfully" in response.json()["message"].lower()

        # verify_email takes EmailVerification object
        from app.schemas.user import EmailVerification

        mock_user_service.verify_email.assert_called_once()
        call_args = mock_user_service.verify_email.call_args[0][0]
        assert isinstance(call_args, EmailVerification)
        assert call_args.token == "verification_token_123"

    @patch("app.api.auth.UserService")
    async def test_verify_email_invalid_token(self, mock_user_service_class, client):
        """Test email verification with invalid token."""
        mock_user_service = AsyncMock()
        # Service raises ValueError, API converts to HTTPException
        mock_user_service.verify_email.side_effect = ValueError(
            "Invalid or expired token"
        )
        mock_user_service_class.return_value = mock_user_service

        verification_data = {"token": "invalid_token"}
        response = client.post("/api/v1/auth/verify-email", json=verification_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid" in response.json()["detail"]

    # Test GET /verify-email endpoint

    @patch("app.api.auth.UserService")
    async def test_get_verify_email_success(self, mock_user_service_class, client):
        """Test email verification via GET endpoint."""
        mock_user_service = AsyncMock()
        mock_user_service.verify_email.return_value = True
        mock_user_service_class.return_value = mock_user_service

        response = client.get("/api/v1/auth/verify-email?token=verification_token_123")

        assert response.status_code == status.HTTP_200_OK

    # Test POST /request-password-reset endpoint

    @patch("app.api.auth.UserService")
    async def test_request_password_reset_success(
        self, mock_user_service_class, client
    ):
        """Test successful password reset request."""
        mock_user_service = AsyncMock()
        mock_user_service.request_password_reset.return_value = True
        mock_user_service_class.return_value = mock_user_service

        reset_data = {"email": "test@example.com"}
        response = client.post("/api/v1/auth/request-password-reset", json=reset_data)

        assert response.status_code == status.HTTP_200_OK
        # Check for actual response message from API
        assert "email exists" in response.json()["message"].lower()

        # request_password_reset takes PasswordResetRequest object
        from app.schemas.user import PasswordResetRequest

        mock_user_service.request_password_reset.assert_called_once()
        call_args = mock_user_service.request_password_reset.call_args[0][0]
        assert isinstance(call_args, PasswordResetRequest)
        assert call_args.email == "test@example.com"

    # Test POST /reset-password endpoint

    @patch("app.api.auth.UserService")
    async def test_reset_password_success(self, mock_user_service_class, client):
        """Test successful password reset."""
        mock_user_service = AsyncMock()
        mock_user_service.reset_password.return_value = True
        mock_user_service_class.return_value = mock_user_service

        reset_data = {
            "token": "reset_token_123",
            "new_password": "new_password_123",
        }
        response = client.post("/api/v1/auth/reset-password", json=reset_data)

        assert response.status_code == status.HTTP_200_OK
        assert "reset successfully" in response.json()["message"].lower()

        # reset_password takes PasswordReset object
        from app.schemas.user import PasswordReset

        mock_user_service.reset_password.assert_called_once()
        call_args = mock_user_service.reset_password.call_args[0][0]
        assert isinstance(call_args, PasswordReset)
        assert call_args.token == "reset_token_123"
        assert call_args.new_password == "new_password_123"

    # Test POST /change-password endpoint

    @patch("app.api.auth.UserService")
    async def test_change_password_success(
        self,
        mock_user_service_class,
        client,
        sample_user_response,
    ):
        """Test successful password change."""
        from app.auth.dependencies import get_current_active_user
        from app.main import app

        # Override auth dependency
        app.dependency_overrides[get_current_active_user] = lambda: sample_user_response

        mock_user_service = AsyncMock()
        mock_user_service.change_password.return_value = True
        mock_user_service_class.return_value = mock_user_service

        # API expects old_password and new_password as parameters
        response = client.post(
            "/api/v1/auth/change-password?old_password=password123&new_password=newpassword123",
            headers={"Authorization": "Bearer valid_token"},
        )

        # Clean up override
        app.dependency_overrides.pop(get_current_active_user, None)

        assert response.status_code == status.HTTP_200_OK
        assert "changed successfully" in response.json()["message"].lower()

        mock_user_service.change_password.assert_called_once_with(
            sample_user_response.id, "password123", "newpassword123"
        )

    # Test POST /refresh endpoint

    @patch("app.api.auth.UserService")
    async def test_refresh_token_success(
        self, mock_user_service_class, client, sample_user_response, sample_token_pair
    ):
        """Test successful token refresh."""
        mock_user_service = AsyncMock()
        # The API calls refresh_access_token, not validate_refresh_token
        mock_user_service.refresh_access_token.return_value = sample_token_pair
        mock_user_service_class.return_value = mock_user_service

        refresh_data = {"refresh_token": "valid_refresh_token"}
        response = client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

        mock_user_service.refresh_access_token.assert_called_once_with(
            "valid_refresh_token"
        )

    # Test POST /logout endpoint

    @patch("app.api.auth.UserService")
    async def test_logout_success(
        self, mock_user_service_class, client, sample_token_pair
    ):
        """Test successful user logout."""
        mock_user_service = AsyncMock()
        mock_user_service.revoke_refresh_token.return_value = True
        mock_user_service_class.return_value = mock_user_service

        # Logout expects refresh_token in body
        logout_data = {"refresh_token": sample_token_pair.refresh_token}
        response = client.post("/api/v1/auth/logout", json=logout_data)

        assert response.status_code == status.HTTP_200_OK
        assert "successfully" in response.json()["message"].lower()

    # Test Google OAuth endpoints (basic structure)

    def test_google_oauth_login_redirect(self, client):
        """Test Google OAuth login redirect."""
        response = client.get("/api/v1/auth/google/login")

        # Should redirect to Google OAuth
        assert response.status_code in [status.HTTP_302_FOUND, status.HTTP_200_OK]

    @patch("app.api.auth.UserService")
    @patch("app.api.auth.google_oauth_service")
    async def test_google_oauth_callback_success(
        self,
        mock_oauth_service,
        mock_user_service_class,
        client,
        sample_user_response,
        sample_token_pair,
    ):
        """Test Google OAuth callback success."""
        # Mock the verify_oauth_token method that is actually called in the API
        from app.schemas.user import GoogleOAuthCallback

        sample_oauth_data = GoogleOAuthCallback(
            id="123456789",
            email="test@example.com",
            given_name="Test",
            family_name="User",
            picture="https://example.com/avatar.jpg",
            email_verified=True,
        )

        mock_oauth_service.verify_oauth_token = AsyncMock(
            return_value=sample_oauth_data
        )

        # Mock the user service login_with_oauth method
        mock_user_service = AsyncMock()
        mock_user_service.login_with_oauth.return_value = sample_token_pair
        mock_user_service_class.return_value = mock_user_service

        # Mock the OAuth callback data
        oauth_data = {"code": "auth_code", "state": "state_token"}
        response = client.post("/api/v1/auth/google/callback", json=oauth_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data

    # Test Error Handling

    async def test_invalid_endpoint(self, client):
        """Test accessing non-existent endpoint."""
        response = client.post("/api/v1/auth/nonexistent-endpoint", json={})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_invalid_json_payload(self, client):
        """Test handling of invalid JSON payload."""
        response = client.post(
            "/api/v1/auth/verify-email",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Test Missing Required Fields

    async def test_verify_email_missing_fields(self, client):
        """Test email verification with missing required fields."""
        incomplete_data = {}  # Missing token

        response = client.post("/api/v1/auth/verify-email", json=incomplete_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_password_reset_missing_fields(self, client):
        """Test password reset with missing required fields."""
        incomplete_data = {"token": "valid_token"}  # Missing new_password

        response = client.post("/api/v1/auth/reset-password", json=incomplete_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Test Security Validation

    async def test_weak_password_validation(self, client):
        """Test weak password validation."""
        weak_password_data = {
            "token": "valid_token",
            "new_password": "123",  # Too short
        }

        response = client.post("/api/v1/auth/reset-password", json=weak_password_data)

        # Should validate password strength either at API or service level
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    # Test Email Validation

    async def test_invalid_email_format(self, client):
        """Test invalid email format in password reset."""
        invalid_email_data = {"email": "invalid-email-format"}

        response = client.post(
            "/api/v1/auth/request-password-reset", json=invalid_email_data
        )

        # Should validate email format either at API or service level
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]
