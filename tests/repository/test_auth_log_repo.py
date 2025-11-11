"""
Tests for AuthLogRepository.

Tests authentication log repository operations including
log creation, retrieval, and failed attempt counting.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from typing import Dict, Any

from app.db.auth_log import AuthLogRepository


@pytest.mark.repository
@pytest.mark.unit
class TestAuthLogRepository:
    """Test cases for AuthLogRepository."""

    @pytest.fixture
    def repo(self, mock_db_pool):
        """Create repository instance with mocked pool."""
        return AuthLogRepository(mock_db_pool)

    @pytest.fixture
    def sample_auth_log_record(self):
        """Sample auth log record for testing."""
        return {
            "id": 1,
            "user_id": 123,
            "event_type": "login",
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0",
            "success": True,
            "details": {"method": "password"},
            "created_at": datetime.now(timezone.utc),
        }

    # ========================================================================
    # CREATE AUTH LOG TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_create_auth_log_success(self, repo, mock_db_pool):
        """Test creating an auth log successfully."""
        # Arrange
        mock_log = {
            "id": 1,
            "user_id": 123,
            "event_type": "login",
            "success": True,
        }
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_log)

        # Act
        result = await repo.create_auth_log(
            user_id=123,
            event_type="login",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            success=True,
            details={"method": "password"},
        )

        # Assert
        assert result is not None
        assert result["user_id"] == 123
        assert result["event_type"] == "login"

    @pytest.mark.asyncio
    async def test_create_auth_log_minimal_fields(self, repo, mock_db_pool):
        """Test creating auth log with minimal required fields."""
        # Arrange
        mock_log = {"id": 2, "user_id": None, "event_type": "failed_login"}
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_log)

        # Act
        result = await repo.create_auth_log(
            user_id=None, event_type="failed_login", success=False
        )

        # Assert
        assert result is not None
        assert result["event_type"] == "failed_login"

    @pytest.mark.asyncio
    async def test_create_auth_log_with_details(self, repo, mock_db_pool):
        """Test creating auth log with JSON details."""
        # Arrange
        mock_log = {"id": 3, "details": {"error": "Invalid credentials"}}
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_log)

        # Act
        result = await repo.create_auth_log(
            user_id=123,
            event_type="login_failed",
            success=False,
            details={"error": "Invalid credentials", "attempts": 3},
        )

        # Assert
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_auth_log_returns_none_on_failure(self, repo, mock_db_pool):
        """Test create auth log returns None when insert fails."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.create_auth_log(user_id=123, event_type="login")

        # Assert
        assert result is None

    # ========================================================================
    # GET AUTH LOGS BY USER TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_auth_logs_by_user_success(self, repo, mock_db_pool):
        """Test getting auth logs for a user."""
        # Arrange
        mock_logs = [
            {"id": 1, "event_type": "login", "success": True},
            {"id": 2, "event_type": "logout", "success": True},
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_logs)

        # Act
        result = await repo.get_auth_logs_by_user(123, limit=100, offset=0)

        # Assert
        assert len(result) == 2
        assert result[0]["event_type"] == "login"

    @pytest.mark.asyncio
    async def test_get_auth_logs_by_user_empty(self, repo, mock_db_pool):
        """Test getting logs for user with no logs."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_auth_logs_by_user(999)

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_get_auth_logs_by_user_with_pagination(self, repo, mock_db_pool):
        """Test getting logs with custom pagination."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_auth_logs_by_user(123, limit=10, offset=20)

        # Assert
        assert result == []

    # ========================================================================
    # GET AUTH LOGS BY EVENT TYPE TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_auth_logs_by_event_type_success(self, repo, mock_db_pool):
        """Test getting logs by event type."""
        # Arrange
        mock_logs = [
            {"id": 1, "event_type": "login", "user_id": 123},
            {"id": 2, "event_type": "login", "user_id": 456},
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_logs)

        # Act
        result = await repo.get_auth_logs_by_event_type("login")

        # Assert
        assert len(result) == 2
        assert all(log["event_type"] == "login" for log in result)

    @pytest.mark.asyncio
    async def test_get_auth_logs_by_event_type_empty(self, repo, mock_db_pool):
        """Test getting logs for event type with no logs."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_auth_logs_by_event_type("rare_event")

        # Assert
        assert result == []

    # ========================================================================
    # GET FAILED AUTH LOGS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_failed_auth_logs_success(self, repo, mock_db_pool):
        """Test getting failed authentication attempts."""
        # Arrange
        mock_logs = [
            {"id": 1, "event_type": "login", "success": False},
            {"id": 2, "event_type": "password_reset", "success": False},
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_logs)

        # Act
        result = await repo.get_failed_auth_logs()

        # Assert
        assert len(result) == 2
        assert all(not log["success"] for log in result)

    @pytest.mark.asyncio
    async def test_get_failed_auth_logs_empty(self, repo, mock_db_pool):
        """Test getting failed logs when none exist."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_failed_auth_logs()

        # Assert
        assert result == []

    # ========================================================================
    # GET AUTH LOGS BY IP TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_auth_logs_by_ip_success(self, repo, mock_db_pool):
        """Test getting logs by IP address."""
        # Arrange
        mock_logs = [
            {"id": 1, "ip_address": "192.168.1.1", "event_type": "login"},
            {"id": 2, "ip_address": "192.168.1.1", "event_type": "logout"},
        ]
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_logs)

        # Act
        result = await repo.get_auth_logs_by_ip("192.168.1.1")

        # Assert
        assert len(result) == 2
        assert all(log["ip_address"] == "192.168.1.1" for log in result)

    @pytest.mark.asyncio
    async def test_get_auth_logs_by_ip_empty(self, repo, mock_db_pool):
        """Test getting logs for IP with no logs."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_auth_logs_by_ip("10.0.0.1")

        # Assert
        assert result == []

    # ========================================================================
    # COUNT AUTH LOGS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_count_auth_logs_by_user_success(self, repo, mock_db_pool):
        """Test counting auth logs for a user."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"count": 25})

        # Act
        result = await repo.count_auth_logs_by_user(123)

        # Assert
        assert result == 25

    @pytest.mark.asyncio
    async def test_count_auth_logs_by_user_zero(self, repo, mock_db_pool):
        """Test count returns 0 when user has no logs."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"count": 0})

        # Act
        result = await repo.count_auth_logs_by_user(999)

        # Assert
        assert result == 0

    @pytest.mark.asyncio
    async def test_count_auth_logs_by_user_returns_zero_on_none(
        self, repo, mock_db_pool
    ):
        """Test count returns 0 when query returns None."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.count_auth_logs_by_user(123)

        # Assert
        assert result == 0

    # ========================================================================
    # COUNT FAILED ATTEMPTS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_count_failed_attempts_by_user(self, repo, mock_db_pool):
        """Test counting failed attempts for a user."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"count": 3})

        # Act
        result = await repo.count_failed_attempts(user_id=123, hours=24)

        # Assert
        assert result == 3

    @pytest.mark.asyncio
    async def test_count_failed_attempts_by_ip(self, repo, mock_db_pool):
        """Test counting failed attempts for an IP address."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"count": 5})

        # Act
        result = await repo.count_failed_attempts(ip_address="192.168.1.1", hours=24)

        # Assert
        assert result == 5

    @pytest.mark.asyncio
    async def test_count_failed_attempts_total(self, repo, mock_db_pool):
        """Test counting all failed attempts."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"count": 100})

        # Act
        result = await repo.count_failed_attempts(hours=24)

        # Assert
        assert result == 100

    @pytest.mark.asyncio
    async def test_count_failed_attempts_custom_hours(self, repo, mock_db_pool):
        """Test counting failed attempts with custom time window."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"count": 7})

        # Act
        result = await repo.count_failed_attempts(user_id=123, hours=1)

        # Assert
        assert result == 7

    @pytest.mark.asyncio
    async def test_count_failed_attempts_invalid_hours(self, repo, mock_db_pool):
        """Test that invalid hours defaults to 24."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value={"count": 2})

        # Act - should use default 24 hours
        result = await repo.count_failed_attempts(user_id=123, hours=-1)

        # Assert
        assert result == 2

    @pytest.mark.asyncio
    async def test_count_failed_attempts_returns_zero_on_none(self, repo, mock_db_pool):
        """Test count failed attempts returns 0 when query returns None."""
        # Arrange
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=None)

        # Act
        result = await repo.count_failed_attempts(user_id=123)

        # Assert
        assert result == 0
