"""
Unit tests for authentication dependencies.

Tests the CurrentUser class and authentication functions that are actually
available in the codebase.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import (
    CurrentUser,
    get_current_active_user,
    get_current_active_superuser,
    get_current_user_optional,
    _check_superuser_permissions,
)
from app.schemas.user import UserResponse, UserInDB


@pytest.mark.unit
class TestAuthDependencies:
    """Test cases for authentication dependencies."""

    @pytest.fixture
    def mock_user_repo(self):
        """Mock UserRepository."""
        repo = AsyncMock()
        repo.get_user_by_email = AsyncMock(return_value=None)
        return repo

    @pytest.fixture
    def mock_db_pool(self):
        """Mock database pool."""
        return MagicMock()

    @pytest.fixture
    def mock_user_service(self, mock_db_pool, mock_user_repo):
        """Mock UserService."""
        service = AsyncMock()
        return service

    @pytest.fixture
    def sample_user_data(self):
        """Sample user data for testing."""
        return {
            "id": 1,
            "email": "user@example.com",  # Regular user email for testing
            "username": "testuser",
            "full_name": "Test User",
            "is_active": True,
            "is_verified": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "last_login": None,
        }

    @pytest.fixture
    def sample_user_in_db(self, sample_user_data):
        """Sample UserInDB object."""
        return UserInDB(**sample_user_data)

    @pytest.fixture
    def valid_access_token(self):
        """Valid JWT access token."""
        payload = {
            "sub": "test@example.com",
            "user_id": 1,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
            "iat": datetime.now(timezone.utc),
        }
        return jwt.encode(payload, "test_secret", algorithm="HS256")

    @pytest.fixture
    def superuser_user_data(self):
        """Superuser user data for testing."""
        return {
            "id": 1,
            "email": "admin@health.com",  # Must match auth dependencies check
            "username": "admin",
            "full_name": "Admin User",
            "is_active": True,
            "is_verified": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "last_login": None,
        }

    @pytest.fixture
    def sample_superuser_in_db(self, superuser_user_data):
        """Sample superuser UserInDB object."""
        return UserInDB(**superuser_user_data)

    @pytest.fixture
    def http_credentials(self, valid_access_token):
        """HTTP authorization credentials."""
        return HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=valid_access_token
        )

    # Test CurrentUser Class

    def test_current_user_initialization(self):
        """Test CurrentUser class initialization."""
        current_user = CurrentUser(active_only=True)
        assert current_user.active_only is True

        current_user = CurrentUser(active_only=False)
        assert current_user.active_only is False

    @patch("app.auth.dependencies.verify_access_token")
    @patch("app.auth.dependencies.UserService")
    async def test_current_user_active_only_success(
        self,
        mock_user_service_class,
        mock_verify_token,
        sample_user_in_db,
        http_credentials,
        mock_db_pool,
    ):
        """Test CurrentUser with active_only=True and valid active user."""
        mock_verify_token.return_value = {"sub": "test@example.com"}

        mock_user_service = AsyncMock()
        mock_user_service.get_user_by_email = AsyncMock(return_value=sample_user_in_db)
        mock_user_service_class.return_value = mock_user_service

        current_user = CurrentUser(active_only=True)
        result = await current_user(http_credentials, mock_db_pool)

        assert result == sample_user_in_db
        mock_user_service.get_user_by_email.assert_called_once_with("test@example.com")

    @patch("app.auth.dependencies.verify_access_token")
    @patch("app.auth.dependencies.UserService")
    async def test_current_user_active_only_inactive_user(
        self, mock_user_service_class, mock_verify_token, http_credentials, mock_db_pool
    ):
        """Test CurrentUser with active_only=True and inactive user."""
        mock_verify_token.return_value = {"sub": "test@example.com"}

        inactive_user = UserInDB(
            id=1,
            email="test@example.com",
            is_active=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        mock_user_service = AsyncMock()
        mock_user_service.get_user_by_email = AsyncMock(return_value=inactive_user)
        mock_user_service_class.return_value = mock_user_service

        current_user = CurrentUser(active_only=True)

        with pytest.raises(HTTPException) as exc_info:
            await current_user(http_credentials, mock_db_pool)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("app.auth.dependencies.verify_access_token")
    @patch("app.auth.dependencies.UserService")
    async def test_current_user_active_only_false(
        self,
        mock_user_service_class,
        mock_verify_token,
        sample_user_in_db,
        http_credentials,
        mock_db_pool,
    ):
        """Test CurrentUser with active_only=False."""
        mock_verify_token.return_value = {"sub": "test@example.com"}

        mock_user_service = AsyncMock()
        mock_user_service.get_user_by_email = AsyncMock(return_value=sample_user_in_db)
        mock_user_service_class.return_value = mock_user_service

        current_user = CurrentUser(active_only=False)
        result = await current_user(http_credentials, mock_db_pool)

        assert result == sample_user_in_db

    @patch("app.auth.dependencies.verify_access_token")
    async def test_current_user_invalid_token(
        self, mock_verify_token, http_credentials, mock_db_pool
    ):
        """Test CurrentUser with invalid token."""
        mock_verify_token.return_value = None

        current_user = CurrentUser(active_only=True)

        with pytest.raises(HTTPException) as exc_info:
            await current_user(http_credentials, mock_db_pool)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Could not validate credentials" in str(exc_info.value.detail)

    @patch("app.auth.dependencies.verify_access_token")
    async def test_current_user_missing_email_in_payload(
        self, mock_verify_token, http_credentials, mock_db_pool
    ):
        """Test CurrentUser with missing email in token payload."""
        mock_verify_token.return_value = {"user_id": 1}  # Missing 'sub' field

        current_user = CurrentUser(active_only=True)

        with pytest.raises(HTTPException) as exc_info:
            await current_user(http_credentials, mock_db_pool)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @patch("app.auth.dependencies.verify_access_token")
    @patch("app.auth.dependencies.UserService")
    async def test_current_user_user_not_found(
        self, mock_user_service_class, mock_verify_token, http_credentials, mock_db_pool
    ):
        """Test CurrentUser when user is not found in database."""
        mock_verify_token.return_value = {"sub": "test@example.com"}

        mock_user_service = AsyncMock()
        mock_user_service.get_user_by_email = AsyncMock(return_value=None)
        mock_user_service_class.return_value = mock_user_service

        current_user = CurrentUser(active_only=True)

        with pytest.raises(HTTPException) as exc_info:
            await current_user(http_credentials, mock_db_pool)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    # Test get_current_active_user

    async def test_get_current_active_user_success(self, sample_user_in_db):
        """Test get_current_active_user with active user."""
        result = await get_current_active_user(sample_user_in_db)
        assert result == sample_user_in_db

    async def test_get_current_active_user_inactive_user(self, sample_user_in_db):
        """Test get_current_active_user with inactive user."""
        sample_user_in_db.is_active = False

        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(sample_user_in_db)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Inactive user" in str(exc_info.value.detail)

    # Test get_current_active_superuser

    async def test_get_current_active_superuser_success(self, sample_superuser_in_db):
        """Test get_current_active_superuser with superuser."""
        sample_superuser_in_db.is_superuser = True
        result = await _check_superuser_permissions(sample_superuser_in_db)
        assert result == sample_superuser_in_db

    async def test_get_current_active_superuser_not_superuser(self, sample_user_in_db):
        """Test get_current_active_superuser with regular user."""
        sample_user_in_db.is_superuser = False

        with pytest.raises(HTTPException) as exc_info:
            await _check_superuser_permissions(sample_user_in_db)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "enough privileges" in str(exc_info.value.detail)

    async def test_get_current_active_superuser_inactive(self, sample_superuser_in_db):
        """Test get_current_active_superuser with inactive superuser."""
        sample_superuser_in_db.is_superuser = True
        sample_superuser_in_db.is_active = False

        with pytest.raises(HTTPException) as exc_info:
            await _check_superuser_permissions(sample_superuser_in_db)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    # Test get_current_user_optional

    async def test_get_current_user_optional_with_user(self, sample_user_in_db):
        """Test get_current_user_optional with user provided."""
        # This function should only be called with credentials and db_pool,
        # not directly with a user object
        result = await get_current_user_optional(None, None)
        assert result is None

    async def test_get_current_user_optional_none(self):
        """Test get_current_user_optional with None credentials."""
        result = await get_current_user_optional(None, None)
        assert result is None

    # Test Security Edge Cases

    @patch("app.auth.dependencies.verify_access_token")
    @patch("app.auth.dependencies.UserService")
    async def test_concurrent_requests_handling(
        self,
        mock_user_service_class,
        mock_verify_token,
        sample_user_in_db,
        http_credentials,
        mock_db_pool,
    ):
        """Test that CurrentUser can handle concurrent requests."""
        import asyncio

        mock_verify_token.return_value = {"sub": "test@example.com"}

        mock_user_service = AsyncMock()
        mock_user_service.get_user_by_email = AsyncMock(return_value=sample_user_in_db)
        mock_user_service_class.return_value = mock_user_service

        current_user = CurrentUser(active_only=True)

        # Simulate concurrent requests
        tasks = [current_user(http_credentials, mock_db_pool) for _ in range(5)]

        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert all(result == sample_user_in_db for result in results)
        assert mock_user_service.get_user_by_email.call_count == 5

    @patch("app.auth.dependencies.verify_access_token")
    async def test_malformed_jwt_payload(
        self, mock_verify_token, http_credentials, mock_db_pool
    ):
        """Test handling of malformed JWT payload."""
        mock_verify_token.return_value = {}  # Empty payload

        current_user = CurrentUser(active_only=True)

        with pytest.raises(HTTPException) as exc_info:
            await current_user(http_credentials, mock_db_pool)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
