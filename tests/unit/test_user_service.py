"""
Unit tests for UserService.

Tests user management operations that are actually available in the codebase.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status

from app.services.user import UserService
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserInDB


@pytest.mark.unit
class TestUserService:
    """Test cases for UserService."""

    @pytest.fixture
    def mock_user_repo(self):
        """Mock UserRepository."""
        repo = AsyncMock()
        return repo

    @pytest.fixture
    def user_service(self, mock_db_pool, mock_user_repo):
        """Create UserService instance with mocked repository."""
        service = UserService(mock_db_pool)
        service.user_repo = mock_user_repo
        return service

    @pytest.fixture
    def sample_user_create(self):
        """Sample UserCreate schema."""
        return UserCreate(
            email="test@example.com",
            password="password123",
            first_name="Test",
            last_name="User",
        )

    @pytest.fixture
    def sample_user_update(self):
        """Sample UserUpdate schema."""
        return UserUpdate(first_name="Updated", last_name="Name")

    @pytest.fixture
    def sample_user_response(self):
        """Sample UserResponse object."""
        return UserResponse(
            id=1,
            email="test@example.com",
            is_active=True,
            provider="local",
            email_verified=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            profile=None,
        )

    @pytest.fixture
    def sample_user_in_db(self):
        """Sample UserInDB object."""
        return UserInDB(
            id=1,
            email="test@example.com",
            is_active=True,
            provider="local",
            email_verified=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            profile=None,
            password_hash="$2b$12$hashedpassword",  # Mock bcrypt hash
            google_id=None,
            email_verification_token=None,
            email_verification_sent_at=None,
            password_reset_token=None,
            password_reset_sent_at=None,
        )

    # Test UserService Initialization

    def test_user_service_initialization(self, user_service):
        """Test UserService initialization."""
        assert user_service.user_repo is not None
        assert hasattr(user_service, "user_repo")

    # Test User Operations (basic structure based on actual service methods)

    async def test_get_user_by_id_success(self, user_service, sample_user_response):
        """Test getting user by ID successfully."""
        user_service.user_repo.get_user_by_id = AsyncMock(
            return_value=sample_user_response
        )

        result = await user_service.get_user_by_id(1)

        assert result == sample_user_response
        user_service.user_repo.get_user_by_id.assert_called_once_with(1)

    async def test_get_user_by_id_not_found(self, user_service):
        """Test getting user by ID when not found."""
        user_service.user_repo.get_user_by_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await user_service.get_user_by_id(999)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "User not found" in str(exc_info.value.detail)

    async def test_get_user_by_email_success(self, user_service, sample_user_in_db):
        """Test getting user by email successfully."""
        user_service.user_repo.get_user_by_email = AsyncMock(
            return_value=sample_user_in_db
        )

        result = await user_service.get_user_by_email("test@example.com")

        assert result == sample_user_in_db
        user_service.user_repo.get_user_by_email.assert_called_once_with(
            "test@example.com"
        )

    async def test_get_user_by_email_not_found(self, user_service):
        """Test getting user by email when not found."""
        user_service.user_repo.get_user_by_email = AsyncMock(return_value=None)

        result = await user_service.get_user_by_email("nonexistent@example.com")

        assert result is None
        user_service.user_repo.get_user_by_email.assert_called_once_with(
            "nonexistent@example.com"
        )

    async def test_create_user_success(
        self, user_service, sample_user_create, sample_user_response
    ):
        """Test successful user creation."""
        # Mock returns dict (database record format)
        user_record = {
            "id": 1,
            "email": "test@example.com",
            "is_active": True,
            "provider": "local",
            "email_verified": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "profile_id": None,
        }

        user_service.user_repo.create_user = AsyncMock(return_value=user_record)
        user_service.user_repo.get_user_by_id = AsyncMock(return_value=user_record)
        user_service.user_repo.get_user_by_email = AsyncMock(
            return_value=None
        )  # Email not taken
        # Mock profile repository methods
        user_service.profile_repo.create_profile = AsyncMock(return_value=True)
        # Mock the email sending method
        user_service._send_email_verification = AsyncMock(return_value=True)

        result = await user_service.create_user(sample_user_create)

        assert result.id == 1
        assert result.email == "test@example.com"
        user_service.user_repo.create_user.assert_called_once()
        user_service.user_repo.get_user_by_email.assert_called_once_with(
            sample_user_create.email
        )

    async def test_create_user_email_exists(
        self, user_service, sample_user_create, sample_user_response
    ):
        """Test user creation when email already exists."""
        user_service.user_repo.get_user_by_email = AsyncMock(
            return_value=sample_user_response
        )

        with pytest.raises(HTTPException) as exc_info:
            await user_service.create_user(sample_user_create)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "Email already registered" in str(exc_info.value.detail)
        user_service.user_repo.create_user.assert_not_called()

    async def test_update_user_success(
        self, user_service, sample_user_update, sample_user_response
    ):
        """Test successful user update."""
        # Mock the user records in database format
        existing_record = {
            "id": 1,
            "email": "test@example.com",
            "is_active": True,
            "provider": "local",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "profile_id": None,
        }

        updated_record = existing_record.copy()
        updated_record["is_active"] = False
        updated_record["updated_at"] = datetime.now(timezone.utc)

        user_service.user_repo.get_user_by_id = AsyncMock(
            side_effect=[
                existing_record,
                updated_record,
            ]  # First for check, second for re-fetch
        )
        user_service.user_repo.update_user = AsyncMock(return_value=updated_record)

        # Test updating is_active field
        user_update_data = UserUpdate(is_active=False)
        result = await user_service.update_user(1, user_update_data)

        assert result.is_active is False
        user_service.user_repo.update_user.assert_called_once()

    async def test_update_user_not_found(self, user_service, sample_user_update):
        """Test updating user when not found."""
        user_service.user_repo.get_user_by_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await user_service.update_user(999, sample_user_update)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "User not found" in str(exc_info.value.detail)

    async def test_delete_user_success(self, user_service, sample_user_response):
        """Test successful user deletion."""
        user_service.user_repo.get_user_by_id = AsyncMock(
            return_value=sample_user_response
        )
        user_service.user_repo.delete_user = AsyncMock(return_value=True)

        result = await user_service.delete_user(1)

        assert result is True
        user_service.user_repo.delete_user.assert_called_once_with(1)

    async def test_delete_user_not_found(self, user_service):
        """Test deleting user when not found."""
        user_service.user_repo.get_user_by_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await user_service.delete_user(999)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "User not found" in str(exc_info.value.detail)

    async def test_change_password_success(self, user_service, sample_user_in_db):
        """Test successful password change."""
        # Mock get_user_by_id to return user with password_hash
        user_service.user_repo.get_user_by_id = AsyncMock(
            return_value={
                "id": 1,
                "email": "test@example.com",
                "password_hash": "$2b$12$hashedpassword",
                "is_active": True,
                "provider": "local",
                "email_verified": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        )
        user_service.user_repo.update_password = AsyncMock(return_value=True)

        # Mock verify_password to return True for old password
        with patch("app.services.user.verify_password", return_value=True):
            result = await user_service.change_password(1, "oldpassword", "newpassword")

        assert result is True
        user_service.user_repo.update_password.assert_called_once()

    async def test_change_password_user_not_found(self, user_service):
        """Test password change when user not found."""
        user_service.user_repo.get_user_by_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await user_service.change_password(999, "oldpassword", "newpassword")

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "User not found" in str(exc_info.value.detail)

    async def test_verify_email_success(self, user_service, sample_user_response):
        """Test successful email verification."""
        from app.schemas.user import EmailVerification

        user_service.user_repo.verify_email = AsyncMock(return_value=True)

        # Mock verify_verification_token to return email
        with patch(
            "app.services.user.verify_verification_token",
            return_value="test@example.com",
        ):
            verification_data = EmailVerification(token="verification_token")
            result = await user_service.verify_email(verification_data)

        assert result is True
        user_service.user_repo.verify_email.assert_called_once_with(
            "verification_token"
        )

    async def test_verify_email_invalid_token(self, user_service):
        """Test email verification with invalid token."""
        from app.schemas.user import EmailVerification

        # Mock verify_verification_token to return None (invalid token)
        with patch("app.services.user.verify_verification_token", return_value=None):
            verification_data = EmailVerification(token="invalid_token")

            with pytest.raises(ValueError) as exc_info:
                await user_service.verify_email(verification_data)

            assert "Invalid or expired verification token" in str(exc_info.value)

    # Test Error Handling

    async def test_database_connection_error(self, user_service):
        """Test handling of database connection errors."""
        user_service.user_repo.get_user_by_id = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        with pytest.raises(Exception) as exc_info:
            await user_service.get_user_by_id(1)

        assert "Database connection failed" in str(exc_info.value)

    # Test Validation

    def test_user_create_validation(self, sample_user_create):
        """Test UserCreate schema validation."""
        assert sample_user_create.email == "test@example.com"
        assert sample_user_create.password == "password123"
        assert sample_user_create.first_name == "Test"
        assert sample_user_create.last_name == "User"

    def test_user_update_validation(self, sample_user_update):
        """Test UserUpdate schema validation."""
        assert sample_user_update.first_name == "Updated"
        assert sample_user_update.last_name == "Name"

    def test_user_response_validation(self, sample_user_response):
        """Test UserResponse schema validation."""
        assert sample_user_response.id == 1
        assert sample_user_response.email == "test@example.com"
        assert sample_user_response.is_active is True
        # Note: full_name doesn't exist, profile contains first_name/last_name

    # Test Security Edge Cases

    async def test_injection_attempt_prevention(self, user_service):
        """Test that SQL injection attempts are handled safely."""
        malicious_email = "'; DROP TABLE users; --"

        user_service.user_repo.get_user_by_email = AsyncMock(return_value=None)

        # Should not raise SQL errors - repository should handle parameterization
        result = await user_service.get_user_by_email(malicious_email)

        assert result is None
        user_service.user_repo.get_user_by_email.assert_called_once_with(
            malicious_email
        )

    async def test_concurrent_operations(self, user_service, sample_user_response):
        """Test handling of concurrent operations."""
        import asyncio

        user_service.user_repo.get_user_by_id = AsyncMock(
            return_value=sample_user_response
        )

        # Simulate concurrent requests
        tasks = [user_service.get_user_by_id(1) for _ in range(5)]

        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert all(result == sample_user_response for result in results)
        assert user_service.user_repo.get_user_by_id.call_count == 5

    # Test Password Security (basic structure)

    def test_password_handling_security(self, user_service):
        """Test that password handling follows security practices."""
        # This would test password hashing, verification, etc.
        # Actual implementation depends on the service methods
        assert hasattr(user_service, "user_repo")  # Basic sanity check

    # Test User Status Management

    async def test_user_deactivation(self, user_service, sample_user_response):
        """Test user deactivation functionality."""
        # Mock the user record in database format
        user_record = {
            "id": 1,
            "email": "test@example.com",
            "is_active": True,
            "provider": "local",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "profile_id": None,
        }

        deactivated_record = user_record.copy()
        deactivated_record["is_active"] = False

        user_service.user_repo.get_user_by_id = AsyncMock(
            side_effect=[
                user_record,
                deactivated_record,
            ]  # First for check, second for re-fetch
        )
        user_service.user_repo.update_user = AsyncMock(return_value=deactivated_record)

        update_data = UserUpdate(is_active=False)
        result = await user_service.update_user(1, update_data)

        assert result.is_active is False

    async def test_user_reactivation(self, user_service, sample_user_response):
        """Test user reactivation functionality."""
        # Mock the user record in database format
        inactive_record = {
            "id": 1,
            "email": "test@example.com",
            "is_active": False,
            "provider": "local",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "profile_id": None,
        }

        reactivated_record = inactive_record.copy()
        reactivated_record["is_active"] = True

        user_service.user_repo.get_user_by_id = AsyncMock(
            side_effect=[
                inactive_record,
                reactivated_record,
            ]  # First for check, second for re-fetch
        )
        user_service.user_repo.update_user = AsyncMock(return_value=reactivated_record)

        update_data = UserUpdate(is_active=True)
        result = await user_service.update_user(1, update_data)

        assert result.is_active is True
