"""
Tests for UserRepository.

Tests user repository operations including CRUD operations,
OAuth authentication, email verification, password reset, and token management.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock
from typing import Dict, Any

from app.db.user import UserRepository
from app.schemas.user import UserCreate, UserUpdate


@pytest.mark.repository
@pytest.mark.unit
class TestUserRepository:
    """Test cases for UserRepository."""

    @pytest.fixture
    def repo(self, mock_db_pool):
        """Create repository instance with mocked pool."""
        return UserRepository(mock_db_pool)

    @pytest.fixture
    def sample_user_record(self):
        """Sample user record for testing."""
        return {
            "id": 1,
            "email": "test@example.com",
            "password_hash": "hashed_password",
            "is_active": True,
            "provider": "email",
            "google_id": None,
            "email_verified": True,
            "email_verification_token": None,
            "email_verification_sent_at": None,
            "password_reset_token": None,
            "password_reset_sent_at": None,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "profile_id": 1,
            "first_name": "Test",
            "last_name": "User",
            "avatar_url": None,
        }

    @pytest.fixture
    def user_create_data(self):
        """Sample user creation data."""
        return UserCreate(
            email="newuser@example.com",
            is_active=True,
            provider="email",
            email_verified=False,
        )

    # ========================================================================
    # CREATE USER TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_create_user_success(self, repo, mock_db_pool, user_create_data):
        """Test creating a user successfully."""
        # Arrange
        mock_user = {
            "id": 1,
            "email": "newuser@example.com",
            "is_active": True,
            "provider": "email",
        }
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_user)

        # Act
        result = await repo.create_user(user_create_data, password_hash="hashed")

        # Assert
        assert result is not None
        assert result["email"] == "newuser@example.com"
        mock_db_pool._mock_connection.fetchrow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_user_with_google(self, repo, mock_db_pool):
        """Test creating a user with Google OAuth."""
        # Arrange
        google_user = UserCreate(
            email="google@example.com",
            provider="google",
            google_id="google123",
            email_verified=True,
            is_active=True,
        )
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            return_value={"id": 2, "email": "google@example.com"}
        )

        # Act
        result = await repo.create_user(google_user)

        # Assert
        assert result is not None
        assert result["id"] == 2

    @pytest.mark.asyncio
    async def test_create_user_returns_none_on_failure(
        self, repo, mock_db_pool, user_create_data
    ):
        """Test create user returns None when insert fails."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.create_user(user_create_data)

        # Assert
        assert result is None

    # ========================================================================
    # GET USER TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, repo, mock_db_pool, sample_user_record):
        """Test getting user by ID."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            return_value=sample_user_record
        )

        # Act
        result = await repo.get_user_by_id(1)

        # Assert
        assert result is not None
        assert result["id"] == 1
        assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, repo, mock_db_pool):
        """Test getting non-existent user returns None."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.get_user_by_id(9999)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_email_success(
        self, repo, mock_db_pool, sample_user_record
    ):
        """Test getting user by email."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            return_value=sample_user_record
        )

        # Act
        result = await repo.get_user_by_email("test@example.com")

        # Assert
        assert result is not None
        assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found(self, repo, mock_db_pool):
        """Test getting user by non-existent email."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.get_user_by_email("notfound@example.com")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_google_id_success(self, repo, mock_db_pool):
        """Test getting user by Google ID."""
        # Arrange
        mock_user = {"id": 1, "google_id": "google123", "email": "google@example.com"}
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_user)

        # Act
        result = await repo.get_user_by_google_id("google123")

        # Assert
        assert result is not None
        assert result["google_id"] == "google123"

    @pytest.mark.asyncio
    async def test_get_user_by_google_id_not_found(self, repo, mock_db_pool):
        """Test getting user by non-existent Google ID."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.get_user_by_google_id("notfound")

        # Assert
        assert result is None

    # ========================================================================
    # LIST USERS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_users_success(self, repo, mock_db_pool):
        """Test getting users with pagination."""
        # Arrange
        mock_users = [
            {"id": 1, "email": "user1@example.com"},
            {"id": 2, "email": "user2@example.com"},
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_users)

        # Act
        result = await repo.get_users(limit=100, offset=0)

        # Assert
        assert len(result) == 2
        assert result[0]["id"] == 1

    @pytest.mark.asyncio
    async def test_get_users_empty(self, repo, mock_db_pool):
        """Test getting users when none exist."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_users()

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_count_users_success(self, repo, mock_db_pool):
        """Test counting users."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"count": 42})

        # Act
        result = await repo.count_users()

        # Assert
        assert result == 42

    @pytest.mark.asyncio
    async def test_count_users_zero(self, repo, mock_db_pool):
        """Test count returns 0 when no users."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"count": 0})

        # Act
        result = await repo.count_users()

        # Assert
        assert result == 0

    # ========================================================================
    # UPDATE USER TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_update_user_success(self, repo, mock_db_pool):
        """Test updating user successfully."""
        # Arrange
        user_update = UserUpdate(email="updated@example.com", is_active=True)
        mock_updated = {"id": 1, "email": "updated@example.com", "is_active": True}
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_updated)

        # Act
        result = await repo.update_user(1, user_update)

        # Assert
        assert result is not None
        assert result["email"] == "updated@example.com"

    @pytest.mark.asyncio
    async def test_update_user_not_found(self, repo, mock_db_pool):
        """Test updating non-existent user."""
        # Arrange
        user_update = UserUpdate(email="updated@example.com")
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.update_user(9999, user_update)

        # Assert
        assert result is None

    # ========================================================================
    # DELETE USER TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_delete_user_success(self, repo, mock_db_pool):
        """Test soft deleting user."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"id": 1})

        # Act
        result = await repo.delete_user(1)

        # Assert
        assert result is not None
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, repo, mock_db_pool):
        """Test deleting non-existent user."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.delete_user(9999)

        # Assert
        assert result is None

    # ========================================================================
    # EMAIL VERIFICATION TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_set_email_verification_token_success(self, repo, mock_db_pool):
        """Test setting email verification token."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.set_email_verification_token(1, "token123")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_set_email_verification_token_user_not_found(
        self, repo, mock_db_pool
    ):
        """Test setting token for non-existent user."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 0")

        # Act
        result = await repo.set_email_verification_token(9999, "token123")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_verify_email_success(self, repo, mock_db_pool):
        """Test verifying email with token."""
        # Arrange
        mock_verified = {"id": 1, "email": "test@example.com"}
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_verified)

        # Act
        result = await repo.verify_email("valid_token")

        # Assert
        assert result is not None
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_verify_email_invalid_token(self, repo, mock_db_pool):
        """Test verifying email with invalid token."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.verify_email("invalid_token")

        # Assert
        assert result is None

    # ========================================================================
    # PASSWORD RESET TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_set_password_reset_token_success(self, repo, mock_db_pool):
        """Test setting password reset token."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.set_password_reset_token("test@example.com", "reset123")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_set_password_reset_token_email_not_found(self, repo, mock_db_pool):
        """Test setting reset token for non-existent email."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 0")

        # Act
        result = await repo.set_password_reset_token("notfound@example.com", "reset123")

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_reset_password_success(self, repo, mock_db_pool):
        """Test resetting password with token."""
        # Arrange
        mock_reset = {"id": 1, "email": "test@example.com"}
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_reset)

        # Act
        result = await repo.reset_password("valid_token", "new_hash")

        # Assert
        assert result is not None
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_reset_password_invalid_token(self, repo, mock_db_pool):
        """Test resetting password with invalid token."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.reset_password("invalid_token", "new_hash")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_update_password_success(self, repo, mock_db_pool):
        """Test updating user password."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.update_password(1, "new_password_hash")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_update_password_user_not_found(self, repo, mock_db_pool):
        """Test updating password for non-existent user."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 0")

        # Act
        result = await repo.update_password(9999, "new_hash")

        # Assert
        assert result is False

    # ========================================================================
    # GOOGLE ACCOUNT LINKING TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_link_google_account_success(self, repo, mock_db_pool):
        """Test linking Google account to user."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.link_google_account(1, "google123")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_link_google_account_with_avatar(self, repo, mock_db_pool):
        """Test linking Google account with avatar URL."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.link_google_account(
            1, "google123", avatar_url="https://example.com/avatar.jpg"
        )

        # Assert
        assert result is True
        # Should be called twice: once for user, once for profile
        assert mock_db_pool._mock_connection.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_link_google_account_user_not_found(self, repo, mock_db_pool):
        """Test linking Google account for non-existent user."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 0")

        # Act
        result = await repo.link_google_account(9999, "google123")

        # Assert
        assert result is False

    # ========================================================================
    # REFRESH TOKEN TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_store_refresh_token_success(self, repo, mock_db_pool):
        """Test storing refresh token."""
        # Arrange
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        mock_token = {
            "id": 1,
            "user_id": 1,
            "token_hash": "hashed_token",
            "expires_at": expires_at,
        }
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_token)

        # Act
        result = await repo.store_refresh_token(1, "hashed_token", expires_at)

        # Assert
        assert result is not None
        assert result["user_id"] == 1

    @pytest.mark.asyncio
    async def test_store_refresh_token_returns_none_on_failure(
        self, repo, mock_db_pool
    ):
        """Test storing refresh token when insert fails."""
        # Arrange
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.store_refresh_token(1, "hashed_token", expires_at)

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_refresh_token_by_hash_success(self, repo, mock_db_pool):
        """Test getting refresh token by hash."""
        # Arrange
        mock_token = {
            "id": 1,
            "token_hash": "hashed_token",
            "revoked": False,
        }
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_token)

        # Act
        result = await repo.get_refresh_token_by_hash("hashed_token")

        # Assert
        assert result is not None
        assert result["token_hash"] == "hashed_token"

    @pytest.mark.asyncio
    async def test_get_refresh_token_by_hash_not_found(self, repo, mock_db_pool):
        """Test getting non-existent refresh token."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.get_refresh_token_by_hash("notfound")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_revoke_refresh_token_success(self, repo, mock_db_pool):
        """Test revoking refresh token."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 1")

        # Act
        result = await repo.revoke_refresh_token("hashed_token")

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_revoke_refresh_token_not_found(self, repo, mock_db_pool):
        """Test revoking non-existent token still returns True."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 0")

        # Act
        result = await repo.revoke_refresh_token("notfound")

        # Assert
        assert result is True  # Method returns True even for UPDATE 0

    @pytest.mark.asyncio
    async def test_revoke_all_user_refresh_tokens(self, repo, mock_db_pool):
        """Test revoking all user tokens."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="UPDATE 5")

        # Act
        result = await repo.revoke_all_user_refresh_tokens(1)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_cleanup_expired_refresh_tokens_success(self, repo, mock_db_pool):
        """Test cleaning up expired tokens."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="DELETE 10")

        # Act
        result = await repo.cleanup_expired_refresh_tokens()

        # Assert
        assert result == 10

    @pytest.mark.asyncio
    async def test_cleanup_expired_refresh_tokens_none_found(self, repo, mock_db_pool):
        """Test cleanup when no expired tokens."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="DELETE 0")

        # Act
        result = await repo.cleanup_expired_refresh_tokens()

        # Assert
        assert result == 0

    @pytest.mark.asyncio
    async def test_cleanup_expired_refresh_tokens_invalid_result(
        self, repo, mock_db_pool
    ):
        """Test cleanup with invalid result format."""
        # Arrange
        mock_db_pool._mock_connection.execute = AsyncMock(return_value="INVALID")

        # Act
        result = await repo.cleanup_expired_refresh_tokens()

        # Assert
        assert result == 0
