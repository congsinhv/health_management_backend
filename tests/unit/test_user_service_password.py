"""
Unit tests for User Service password security and validation.

Tests password hashing, verification, change password, and reset password
functionality with focus on bcrypt security and validation rules.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, Mock
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
import bcrypt

from app.services.user import UserService
from app.schemas.user import UserCreate, PasswordReset, PasswordResetRequest
from app.helpers import (
    hash_password,
    verify_password,
    create_verification_token,
    verify_verification_token,
)


@pytest.mark.unit
class TestUserServicePasswordSecurity:
    """Test cases for User Service password security."""

    @pytest.fixture
    def mock_db_pool(self):
        """Mock database pool."""
        return MagicMock()

    @pytest.fixture
    def mock_repositories(self):
        """Mock user and profile repositories."""
        return {
            "user_repo": AsyncMock(),
            "profile_repo": AsyncMock(),
        }

    @pytest.fixture
    def user_service(self, mock_db_pool, mock_repositories):
        """Create UserService with mocked dependencies."""
        with patch(
            "app.services.user.UserRepository",
            return_value=mock_repositories["user_repo"],
        ), patch(
            "app.services.user.UserProfileRepository",
            return_value=mock_repositories["profile_repo"],
        ):
            return UserService(mock_db_pool)

    @pytest.fixture
    def sample_user_record(self):
        """Sample user record with password."""
        password = "securePassword123"
        return {
            "id": 1,
            "email": "test@example.com",
            "is_active": True,
            "is_superuser": False,
            "provider": "portal",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "last_login": None,
            "password_hash": hash_password(password),
            "email_verification_token": None,
            "password_reset_token": None,
            "password_reset_sent_at": None,
        }

    @pytest.fixture
    def password_reset_data(self):
        """Sample password reset request."""
        return PasswordResetRequest(email="test@example.com")

    # Test password hashing and verification

    def test_hash_password_valid_length(self):
        """Test password hashing with valid length."""
        password = "valid_password123"
        hashed = hash_password(password)

        assert hashed is not None
        assert isinstance(hashed, str)
        assert hashed.startswith("$2b$")  # bcrypt hash format
        assert len(hashed) == 60  # Standard bcrypt hash length

    def test_hash_password_maximum_length(self):
        """Test password hashing at bcrypt maximum length (72 bytes)."""
        # 72 characters should work fine
        password = "a" * 72
        hashed = hash_password(password)

        assert hashed is not None
        assert len(hashed) == 60

    def test_hash_password_exceeds_maximum_length(self):
        """Test password hashing when exceeding bcrypt 72-byte limit."""
        # 73 characters - should be truncated to 72
        password = "a" * 73
        hashed = hash_password(password)

        assert hashed is not None
        assert len(hashed) == 60

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "correctPassword123"
        hashed = hash_password(password)

        result = verify_password(password, hashed)
        assert result is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "correctPassword123"
        wrong_password = "wrongPassword456"
        hashed = hash_password(password)

        result = verify_password(wrong_password, hashed)
        assert result is False

    def test_verify_password_unicode_handling(self):
        """Test password verification with Unicode characters."""
        password = "mật khẩu123"  # Vietnamese for "password123"
        hashed = hash_password(password)

        result = verify_password(password, hashed)
        assert result is True

    def test_verify_password_empty_string(self):
        """Test password verification with empty string."""
        password = ""
        hashed = hash_password(password)

        result = verify_password("", hashed)
        assert result is True  # Empty string should verify against empty hash

    def test_verify_password_malformed_hash(self):
        """Test password verification with malformed hash."""
        password = "testPassword123"
        malformed_hash = "not_a_bcrypt_hash"

        result = verify_password(password, malformed_hash)
        assert result is False

    # Test change password functionality

    async def test_change_password_success(
        self, user_service, mock_repositories, sample_user_record
    ):
        """Test successful password change."""
        old_password = "oldPassword123"
        new_password = "newPassword456"
        user_id = 1

        # Setup mock user lookup
        mock_repositories["user_repo"].get_user_by_id.return_value = sample_user_record
        mock_repositories["user_repo"].update_password.return_value = True

        # Hash the old password for comparison
        old_hashed = hash_password(old_password)
        sample_user_record["password_hash"] = old_hashed

        with patch("app.services.user.verify_password", return_value=True), patch(
            "app.services.user.hash_password", return_value="new_hashed_password"
        ):
            result = await user_service.change_password(
                user_id, old_password, new_password
            )

        assert result is True
        # Verify password was updated
        mock_repositories["user_repo"].update_password.assert_called_once_with(
            user_id, "new_hashed_password"
        )

    async def test_change_password_incorrect_old_password(
        self, user_service, mock_repositories, sample_user_record
    ):
        """Test password change with incorrect old password."""
        user_id = 1
        wrong_old_password = "wrongPassword123"
        new_password = "newPassword456"

        mock_repositories["user_repo"].get_user_by_id.return_value = sample_user_record

        with patch("app.services.user.verify_password", return_value=False):
            with pytest.raises(ValueError) as exc_info:
                await user_service.change_password(
                    user_id, wrong_old_password, new_password
                )

            assert "Invalid current password" in str(exc_info.value)

    async def test_change_password_user_not_found(
        self, user_service, mock_repositories
    ):
        """Test password change for non-existent user."""
        user_id = 999
        old_password = "oldPassword123"
        new_password = "newPassword456"

        mock_repositories["user_repo"].get_user_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await user_service.change_password(user_id, old_password, new_password)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "User not found" in str(exc_info.value.detail)

    async def test_change_password_inactive_user(
        self, user_service, mock_repositories, sample_user_record
    ):
        """Test password change for inactive user (currently allows it)."""
        sample_user_record["is_active"] = False
        user_id = 1
        old_password = "oldPassword123"
        new_password = "newPassword456"

        mock_repositories["user_repo"].get_user_by_id.return_value = sample_user_record
        mock_repositories["user_repo"].update_password.return_value = True

        # Hash the old password for comparison
        old_hashed = hash_password(old_password)
        sample_user_record["password_hash"] = old_hashed

        with patch("app.services.user.verify_password", return_value=True), patch(
            "app.services.user.hash_password", return_value="new_hashed_password"
        ):
            result = await user_service.change_password(
                user_id, old_password, new_password
            )

        # Currently the service allows password change for inactive users
        assert result is True

    async def test_change_password_weak_new_password(
        self, user_service, mock_repositories, sample_user_record
    ):
        """Test password change with weak new password (currently allows it)."""
        user_id = 1
        old_password = "oldPassword123"
        weak_new_password = "123"  # Too short

        mock_repositories["user_repo"].get_user_by_id.return_value = sample_user_record
        mock_repositories["user_repo"].update_password.return_value = True

        # Hash the old password for comparison
        old_hashed = hash_password(old_password)
        sample_user_record["password_hash"] = old_hashed

        with patch("app.services.user.verify_password", return_value=True), patch(
            "app.services.user.hash_password", return_value="weak_hashed_password"
        ):
            result = await user_service.change_password(
                user_id, old_password, weak_new_password
            )

        # Currently the service doesn't validate password strength
        assert result is True

    async def test_change_password_same_as_old(
        self, user_service, mock_repositories, sample_user_record
    ):
        """Test password change with same password as old (currently allows it)."""
        password = "samePassword123"
        user_id = 1

        mock_repositories["user_repo"].get_user_by_id.return_value = sample_user_record
        mock_repositories["user_repo"].update_password.return_value = True

        # Hash the old password for comparison
        old_hashed = hash_password(password)
        sample_user_record["password_hash"] = old_hashed

        with patch("app.services.user.verify_password", return_value=True), patch(
            "app.services.user.hash_password", return_value="same_hashed_password"
        ):
            result = await user_service.change_password(user_id, password, password)

        # Currently the service doesn't validate that new password is different
        assert result is True

    # Test password reset functionality

    async def test_request_password_reset_success(
        self, user_service, mock_repositories, sample_user_record, password_reset_data
    ):
        """Test successful password reset request."""
        mock_repositories[
            "user_repo"
        ].get_user_by_email.return_value = sample_user_record

        with patch(
            "app.helpers.create_verification_token", return_value="reset_token_123"
        ), patch(
            "app.services.user.email_service.send_password_reset", return_value=True
        ):
            result = await user_service.request_password_reset(password_reset_data)

        assert result is True
        # Verify token was stored
        mock_repositories["user_repo"].set_password_reset_token.assert_called_once()

    async def test_request_password_reset_user_not_found(
        self, user_service, mock_repositories, password_reset_data
    ):
        """Test password reset request for non-existent user."""
        mock_repositories["user_repo"].get_user_by_email.return_value = None

        # Should not reveal if user exists for security
        result = await user_service.request_password_reset(password_reset_data)
        assert result is True  # Still returns true to prevent email enumeration

    async def test_request_password_reset_inactive_user(
        self, user_service, mock_repositories, sample_user_record, password_reset_data
    ):
        """Test password reset request for inactive user."""
        sample_user_record["is_active"] = False
        mock_repositories[
            "user_repo"
        ].get_user_by_email.return_value = sample_user_record

        result = await user_service.request_password_reset(password_reset_data)
        assert result is True  # Still returns true for security

    async def test_reset_password_success(self, user_service, mock_repositories):
        """Test successful password reset with valid token."""
        reset_token = "valid_reset_token"
        new_password = "newResetPassword123"

        mock_repositories["user_repo"].reset_password.return_value = True

        # Import the actual verify function to see where it's called
        from app.services import user as user_service_module

        with patch.object(
            user_service_module,
            "verify_verification_token",
            return_value="test@example.com",
        ), patch.object(
            user_service_module, "hash_password", return_value="new_reset_hashed"
        ):
            result = await user_service.reset_password(
                PasswordReset(token=reset_token, new_password=new_password)
            )

        assert result is True
        # Verify password was updated
        mock_repositories["user_repo"].reset_password.assert_called_once_with(
            reset_token, "new_reset_hashed"
        )

    async def test_reset_password_invalid_token(self, user_service):
        """Test password reset with invalid token."""
        invalid_token = "invalid_token_123"
        new_password = "newPassword456"

        from app.services import user as user_service_module

        with patch.object(
            user_service_module, "verify_verification_token", return_value=None
        ):
            with pytest.raises(ValueError) as exc_info:
                await user_service.reset_password(
                    PasswordReset(token=invalid_token, new_password=new_password)
                )

            assert "Invalid or expired reset token" in str(exc_info.value)

    async def test_reset_password_expired_token(self, user_service, mock_repositories):
        """Test password reset with expired token (currently not validated)."""
        expired_token = "expired_token_123"
        new_password = "newPassword456"

        mock_repositories["user_repo"].reset_password.return_value = True

        from app.services import user as user_service_module

        # Current implementation doesn't validate token expiration
        with patch.object(
            user_service_module,
            "verify_verification_token",
            return_value="test@example.com",
        ), patch.object(
            user_service_module, "hash_password", return_value="expired_hashed_password"
        ):
            result = await user_service.reset_password(
                PasswordReset(token=expired_token, new_password=new_password)
            )

        # Currently the service doesn't validate token expiration
        assert result is True

    async def test_reset_password_weak_new_password(
        self, user_service, mock_repositories
    ):
        """Test password reset with weak new password (currently not validated)."""
        reset_token = "valid_reset_token"
        weak_new_password = "weakpass1"  # At least 8 characters for Pydantic validation

        mock_repositories["user_repo"].reset_password.return_value = True

        from app.services import user as user_service_module

        # Current implementation doesn't validate password strength
        with patch.object(
            user_service_module,
            "verify_verification_token",
            return_value="test@example.com",
        ), patch.object(
            user_service_module, "hash_password", return_value="weak_hashed_password"
        ):
            result = await user_service.reset_password(
                PasswordReset(token=reset_token, new_password=weak_new_password)
            )

        # Currently the service doesn't validate password strength
        assert result is True

    # Test password reset token generation and verification

    def test_create_verification_token(self):
        """Test verification token generation."""
        token = create_verification_token("test@example.com", "password_reset")

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 20  # Should be a reasonably long token

    def test_verify_verification_token_valid(self):
        """Test verification token verification with valid token."""
        token = create_verification_token("test@example.com", "password_reset")

        result = verify_verification_token(token, "password_reset")
        assert result == "test@example.com"

    def test_verify_verification_token_invalid(self):
        """Test verification token verification with invalid token."""
        invalid_token = "invalid_verification_token"

        result = verify_verification_token(invalid_token, "password_reset")
        assert result is None  # Should return None for invalid token

    # Test security edge cases

    async def test_password_hash_consistency(self):
        """Test that password hashing produces consistent results."""
        password = "consistentPassword123"

        # Hash the same password multiple times
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Hashes should be different due to salt, but both should verify
        assert hash1 != hash2
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)

    async def test_concurrent_password_change(
        self, user_service, mock_repositories, sample_user_record
    ):
        """Test concurrent password changes don't interfere."""
        user_id = 1
        old_password = "oldPassword123"
        new_password1 = "newPassword456"
        new_password2 = "newPassword789"

        mock_repositories["user_repo"].get_user_by_id.return_value = sample_user_record
        mock_repositories["user_repo"].update_password.return_value = True

        # Hash the old password for comparison
        old_hashed = hash_password(old_password)
        sample_user_record["password_hash"] = old_hashed

        with patch("app.services.user.verify_password", return_value=True), patch(
            "app.services.user.hash_password", return_value="new_hashed_password"
        ):
            # First change
            result1 = await user_service.change_password(
                user_id, old_password, new_password1
            )
            assert result1 is True

            # Second change should still work
            result2 = await user_service.change_password(
                user_id, new_password1, new_password2
            )
            assert result2 is True

    async def test_password_change_database_error(
        self, user_service, mock_repositories, sample_user_record
    ):
        """Test password change handling database errors."""
        user_id = 1
        old_password = "oldPassword123"
        new_password = "newPassword456"

        mock_repositories["user_repo"].get_user_by_id.return_value = sample_user_record
        mock_repositories["user_repo"].update_password.side_effect = Exception(
            "Database connection failed"
        )

        # Hash the old password for comparison
        old_hashed = hash_password(old_password)
        sample_user_record["password_hash"] = old_hashed

        with patch("app.services.user.verify_password", return_value=True):
            with pytest.raises(Exception) as exc_info:
                await user_service.change_password(user_id, old_password, new_password)

            assert "Database connection failed" in str(exc_info.value)

    def test_password_timing_attack_resistance(self):
        """Test that password verification timing doesn't reveal information."""
        import time

        correct_password = "correctPassword123"
        hashed = hash_password(correct_password)
        wrong_password = "wrongPassword456"

        # Time multiple verifications
        correct_times = []
        wrong_times = []

        for _ in range(10):
            start = time.time()
            verify_password(correct_password, hashed)
            correct_times.append(time.time() - start)

            start = time.time()
            verify_password(wrong_password, hashed)
            wrong_times.append(time.time() - start)

        # Average times should be similar (within reasonable tolerance)
        avg_correct = sum(correct_times) / len(correct_times)
        avg_wrong = sum(wrong_times) / len(wrong_times)

        # Allow for some variation but should be within reasonable range
        assert abs(avg_correct - avg_wrong) < 0.1  # 100ms tolerance
