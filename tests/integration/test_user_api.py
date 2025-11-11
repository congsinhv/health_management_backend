"""
Integration tests for user management API endpoints.

Tests the actual user endpoints that are available in the codebase.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from fastapi import status
from typing import List

from app.main import app
from app.schemas.user import UserResponse, Token


@pytest.mark.integration
class TestUserAPI:
    """Test cases for user management API endpoints."""

    @pytest.fixture
    def client(self, test_db_pool):
        """Test client with dependency overrides."""
        from app.main import app
        from app.db.database import get_database_pool

        app.dependency_overrides[get_database_pool] = lambda: test_db_pool
        return TestClient(app)

    @pytest.fixture
    def superuser_client(self, test_db_pool):
        """Test client with superuser authentication."""
        from app.main import app
        from app.db.database import get_database_pool
        from app.auth.dependencies import get_current_active_superuser
        from types import SimpleNamespace

        original_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_database_pool] = lambda: test_db_pool
        app.dependency_overrides[
            get_current_active_superuser
        ] = lambda: SimpleNamespace(
            id=1, email="admin@health.com", is_active=True, is_superuser=True
        )
        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides = original_overrides

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
    def sample_users_list(self):
        """Sample list of users."""
        from app.schemas.user_profile import UserProfileResponse

        base_time = datetime.now(timezone.utc)
        return [
            UserResponse(
                id=i,
                email=f"user{i}@example.com",
                is_active=True,
                provider="local",
                email_verified=True,
                created_at=base_time,
                updated_at=base_time,
                profile=UserProfileResponse(
                    id=i,
                    user_id=i,
                    first_name=f"User",
                    last_name=f"{i}",
                    created_at=base_time,
                    updated_at=base_time,
                ),
            )
            for i in range(1, 4)
        ]

    @pytest.fixture
    def sample_token(self):
        """Sample token response."""
        return Token(
            access_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.access_token",
            token_type="bearer",
        )

    # Test POST / (create user)

    @patch("app.api.user.UserService")
    async def test_create_user_success(
        self, mock_user_service_class, client, sample_user_response
    ):
        """Test successful user creation."""
        mock_user_service = AsyncMock()
        mock_user_service.create_user.return_value = sample_user_response
        mock_user_service_class.return_value = mock_user_service

        user_data = {
            "email": "test@example.com",
            "password": "password123",
            "first_name": "Test",
            "last_name": "User",
        }
        response = client.post("/api/v1/users/", json=user_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["profile"]["first_name"] == "Test"
        assert data["profile"]["last_name"] == "User"
        assert "password" not in data  # Password should not be in response

        mock_user_service.create_user.assert_called_once()

    @patch("app.api.user.UserService")
    async def test_create_user_email_exists(self, mock_user_service_class, client):
        """Test user creation with existing email."""
        mock_user_service = AsyncMock()
        # Service raises ValueError, API converts to HTTPException
        mock_user_service.create_user.side_effect = ValueError(
            "Email already registered"
        )
        mock_user_service_class.return_value = mock_user_service

        user_data = {
            "email": "existing@example.com",
            "password": "password123",
            "first_name": "Existing",
            "last_name": "User",
        }
        response = client.post("/api/v1/users/", json=user_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Email already registered" in response.json()["detail"]

    # Test GET / (list users)

    @patch("app.api.user.UserService")
    async def test_list_users_success(
        self, mock_user_service_class, superuser_client, sample_users_list
    ):
        """Test successful user listing."""
        mock_user_service = AsyncMock()
        mock_user_service.get_users.return_value = sample_users_list
        mock_user_service_class.return_value = mock_user_service

        response = superuser_client.get("/api/v1/users/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        assert data[0]["email"] == "user1@example.com"

        mock_user_service.get_users.assert_called_once_with(limit=100, offset=0)

    @patch("app.api.user.UserService")
    async def test_list_users_with_pagination(
        self, mock_user_service_class, superuser_client, sample_users_list
    ):
        """Test user listing with pagination."""
        mock_user_service = AsyncMock()
        mock_user_service.get_users.return_value = sample_users_list[
            :1
        ]  # First user only
        mock_user_service_class.return_value = mock_user_service

        response = superuser_client.get("/api/v1/users/?limit=1&offset=0")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1
        assert data[0]["email"] == "user1@example.com"

        mock_user_service.get_users.assert_called_once_with(limit=1, offset=0)

    # Test GET /{user_id}

    @patch("app.api.user.UserService")
    async def test_get_user_by_id_success(
        self, mock_user_service_class, client, sample_user_response
    ):
        """Test getting user by ID successfully."""
        mock_user_service = AsyncMock()
        mock_user_service.get_user_by_id.return_value = sample_user_response
        mock_user_service_class.return_value = mock_user_service

        response = client.get("/api/v1/users/1")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == 1
        assert data["email"] == "test@example.com"

        mock_user_service.get_user_by_id.assert_called_once_with(1)

    @patch("app.api.user.UserService")
    async def test_get_user_by_id_not_found(self, mock_user_service_class, client):
        """Test getting user by ID when not found."""
        from fastapi import HTTPException

        mock_user_service = AsyncMock()
        mock_user_service.get_user_by_id.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
        mock_user_service_class.return_value = mock_user_service

        response = client.get("/api/v1/users/999")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "User not found" in response.json()["detail"]

    # Test PUT /{user_id}

    @patch("app.api.user.UserService")
    async def test_update_user_success(
        self, mock_user_service_class, client, sample_user_response
    ):
        """Test successful user update."""
        updated_user = sample_user_response.model_copy()
        updated_user.profile.first_name = "Updated"
        updated_user.profile.last_name = "Name"
        updated_user.updated_at = datetime.now(timezone.utc)

        mock_user_service = AsyncMock()
        mock_user_service.update_user.return_value = updated_user
        mock_user_service_class.return_value = mock_user_service

        update_data = {"first_name": "Updated", "last_name": "Name"}
        response = client.put("/api/v1/users/1", json=update_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["profile"]["first_name"] == "Updated"
        assert data["profile"]["last_name"] == "Name"
        assert data["email"] == "test@example.com"  # Should remain unchanged

        mock_user_service.update_user.assert_called_once()

    @patch("app.api.user.UserService")
    async def test_update_user_not_found(self, mock_user_service_class, client):
        """Test updating user when not found."""
        from fastapi import HTTPException

        mock_user_service = AsyncMock()
        mock_user_service.update_user.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
        mock_user_service_class.return_value = mock_user_service

        update_data = {"first_name": "Updated", "last_name": "Name"}
        response = client.put("/api/v1/users/999", json=update_data)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "User not found" in response.json()["detail"]

    # Test DELETE /{user_id}

    @patch("app.api.user.UserService")
    async def test_delete_user_success(self, mock_user_service_class, client):
        """Test successful user deletion."""
        mock_user_service = AsyncMock()
        mock_user_service.delete_user.return_value = True
        mock_user_service_class.return_value = mock_user_service

        response = client.delete("/api/v1/users/1")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""  # No content on successful deletion

        mock_user_service.delete_user.assert_called_once_with(1)

    @patch("app.api.user.UserService")
    async def test_delete_user_not_found(self, mock_user_service_class, client):
        """Test deleting user when not found."""
        from fastapi import HTTPException

        mock_user_service = AsyncMock()
        mock_user_service.delete_user.side_effect = HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
        mock_user_service_class.return_value = mock_user_service

        response = client.delete("/api/v1/users/999")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "User not found" in response.json()["detail"]

    # Test POST /login

    @patch("app.api.user.UserService")
    async def test_login_success(
        self, mock_user_service_class, client, sample_user_response, sample_token
    ):
        """Test successful user login."""
        mock_user_service = AsyncMock()
        # The API calls login_user, which returns a Token
        mock_user_service.login_user.return_value = sample_token
        mock_user_service_class.return_value = mock_user_service

        login_data = {"email": "test@example.com", "password": "password123"}
        response = client.post("/api/v1/users/login", json=login_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        mock_user_service.login_user.assert_called_once()

    @patch("app.api.user.UserService")
    async def test_login_invalid_credentials(self, mock_user_service_class, client):
        """Test login with invalid credentials."""
        mock_user_service = AsyncMock()
        # Service raises ValueError, API converts to HTTPException
        mock_user_service.login_user.side_effect = ValueError(
            "Invalid email or password"
        )
        mock_user_service_class.return_value = mock_user_service

        login_data = {"email": "test@example.com", "password": "wrongpassword"}
        response = client.post("/api/v1/users/login", json=login_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid" in response.json()["detail"]

    # Test GET /count/total

    @patch("app.api.user.UserService")
    async def test_get_total_users_count(
        self, mock_user_service_class, superuser_client
    ):
        """Test getting total users count."""
        mock_user_service = AsyncMock()
        mock_user_service.count_users.return_value = 42
        mock_user_service_class.return_value = mock_user_service

        response = superuser_client.get("/api/v1/users/count/total")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_users"] == 42

        mock_user_service.count_users.assert_called_once()

    # Test Error Handling

    async def test_invalid_user_id_format(self, client):
        """Test handling of invalid user ID format."""
        response = client.get("/api/v1/users/invalid_id")

        # Should return 422 for invalid path parameter
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_invalid_json_payload(self, client):
        """Test handling of invalid JSON payload."""
        response = client.post(
            "/api/v1/users/",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch("app.api.user.UserService")
    async def test_nonexistent_endpoint(
        self, mock_user_service_class, superuser_client
    ):
        """Test accessing non-existent user."""
        mock_user_service = AsyncMock()
        mock_user_service.get_user_by_id.return_value = None
        mock_user_service_class.return_value = mock_user_service

        response = superuser_client.get("/api/v1/users/999999")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # Test Data Validation

    async def test_create_user_missing_required_fields(self, client):
        """Test user creation with missing required fields."""
        incomplete_data = {}  # Missing email entirely

        response = client.post("/api/v1/users/", json=incomplete_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_create_user_invalid_email_format(self, client):
        """Test user creation with invalid email format."""
        invalid_data = {
            "email": "invalid-email-format",
            "password": "password123",
            "first_name": "Test",
            "last_name": "User",
        }

        response = client.post("/api/v1/users/", json=invalid_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_create_user_weak_password(self, client):
        """Test user creation with weak password."""
        weak_password_data = {
            "email": "test@example.com",
            "password": "123",  # Too short
            "first_name": "Test",
            "last_name": "User",
        }

        response = client.post("/api/v1/users/", json=weak_password_data)

        # Should validate password strength either at API or service level
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ]

    async def test_update_user_invalid_data(self, client):
        """Test user update with invalid data."""
        invalid_update = {"email": "invalid-email-format"}

        response = client.put("/api/v1/users/1", json=invalid_update)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Test Pagination Edge Cases

    @patch("app.api.user.UserService")
    async def test_invalid_pagination_parameters(
        self, mock_user_service_class, superuser_client
    ):
        """Test handling of invalid pagination parameters."""
        mock_user_service = AsyncMock()
        mock_user_service.get_users.return_value = []
        mock_user_service_class.return_value = mock_user_service

        response = superuser_client.get("/api/v1/users/?limit=-1&offset=0")

        # Should validate pagination parameters
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Test Response Format Consistency

    @patch("app.api.user.UserService")
    async def test_user_response_format_consistency(
        self, mock_user_service_class, client, sample_user_response
    ):
        """Test that user responses have consistent format."""
        mock_user_service = AsyncMock()
        mock_user_service.get_user_by_id.return_value = sample_user_response
        mock_user_service_class.return_value = mock_user_service

        response = client.get("/api/v1/users/1")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify required fields are present
        required_fields = [
            "id",
            "email",
            "is_active",
            "email_verified",
            "provider",
            "created_at",
            "updated_at",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify sensitive fields are not present
        sensitive_fields = ["password", "password_hash"]
        for field in sensitive_fields:
            assert field not in data, f"Sensitive field should not be present: {field}"

    # Test Search and Filtering

    @patch("app.api.user.UserService")
    async def test_list_users_with_search(
        self, mock_user_service_class, superuser_client, sample_users_list
    ):
        """Test user listing with search parameter."""
        mock_user_service = AsyncMock()
        mock_user_service.get_users.return_value = sample_users_list[:1]
        mock_user_service_class.return_value = mock_user_service

        response = superuser_client.get("/api/v1/users/?search=test")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1

        mock_user_service.get_users.assert_called_once_with(limit=100, offset=0)

    @patch("app.api.user.UserService")
    async def test_list_users_with_filters(
        self, mock_user_service_class, superuser_client, sample_users_list
    ):
        """Test user listing with filters."""
        mock_user_service = AsyncMock()
        mock_user_service.get_users.return_value = sample_users_list
        mock_user_service_class.return_value = mock_user_service

        # Test with is_active filter
        response = superuser_client.get(
            "/api/v1/users/?filters=%7B%22is_active%22%3A%20true%7D"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3

        mock_user_service.get_users.assert_called_once()
        # Note: The API doesn't actually pass filters to get_users method in current implementation
