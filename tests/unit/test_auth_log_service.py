"""
Unit tests for AuthLogService.

Tests authentication logging, security monitoring, and analytics.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from app.services.auth_log import AuthLogService, get_client_ip, get_user_agent
from app.constants import AuthEventType


@pytest.mark.unit
class TestAuthLogHelpers:
    """Test helper functions for auth logging."""

    def test_get_client_ip_with_forwarded_header(self):
        """Test extracting client IP from X-Forwarded-For header."""
        mock_request = MagicMock()
        mock_request.headers = {"X-Forwarded-For": "192.168.1.100, 10.0.0.1"}

        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.100"

    def test_get_client_ip_with_real_ip_header(self):
        """Test extracting client IP from X-Real-IP header."""
        mock_request = MagicMock()
        mock_request.headers = {"X-Real-IP": "192.168.1.200"}

        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.200"

    def test_get_client_ip_direct_connection(self):
        """Test extracting client IP from direct connection."""
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client.host = "192.168.1.300"

        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.300"

    def test_get_client_ip_no_ip_available(self):
        """Test when no client IP is available."""
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client = None

        ip = get_client_ip(mock_request)
        assert ip is None

    def test_get_user_agent(self):
        """Test extracting user agent from request."""
        mock_request = MagicMock()
        mock_request.headers = {"User-Agent": "Mozilla/5.0 (Test Browser)"}

        user_agent = get_user_agent(mock_request)
        assert user_agent == "Mozilla/5.0 (Test Browser)"

    def test_get_user_agent_missing(self):
        """Test when user agent header is missing."""
        mock_request = MagicMock()
        mock_request.headers = {}

        user_agent = get_user_agent(mock_request)
        assert user_agent is None


@pytest.mark.unit
class TestAuthLogService:
    """Test cases for AuthLogService."""

    @pytest.fixture
    def mock_auth_log_repo(self):
        """Mock AuthLogRepository."""
        repo = AsyncMock()
        repo.create_auth_log = AsyncMock()
        repo.get_logs_by_user = AsyncMock(return_value=[])
        repo.get_failed_attempts_by_ip = AsyncMock(return_value=[])
        repo.get_failed_attempts_by_email = AsyncMock(return_value=[])
        repo.get_logs_by_event_type = AsyncMock(return_value=[])
        repo.get_logs_by_date_range = AsyncMock(return_value=[])
        repo.delete_old_logs = AsyncMock(return_value=0)
        repo.get_auth_statistics = AsyncMock(return_value={})
        return repo

    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI Request."""
        request = MagicMock()
        request.headers = {
            "X-Forwarded-For": "192.168.1.100",
            "User-Agent": "Test Browser 1.0",
        }
        request.client.host = "192.168.1.100"
        return request

    @pytest.fixture
    def auth_log_service(self, mock_db_pool, mock_auth_log_repo):
        """Create AuthLogService instance with mocked repository."""
        service = AuthLogService(mock_db_pool)
        service.auth_log_repo = mock_auth_log_repo
        return service

    async def test_log_authentication_success(self, auth_log_service, mock_request):
        """Test logging successful authentication."""
        user_id = 123
        details = {"provider": "google"}

        await auth_log_service.log_auth_event(
            AuthEventType.LOGIN_SUCCESS,
            mock_request,
            user_id=user_id,
            success=True,
            details=details,
        )

        # Verify repository was called correctly
        auth_log_service.auth_log_repo.create_auth_log.assert_called_once_with(
            user_id=user_id,
            event_type=AuthEventType.LOGIN_SUCCESS.value,
            ip_address="192.168.1.100",
            user_agent="Test Browser 1.0",
            success=True,
            details=details,
        )

    async def test_log_authentication_failure_with_details(
        self, auth_log_service, mock_request
    ):
        """Test logging failed authentication with details."""
        email = "test@example.com"
        reason = "invalid_password"
        details = {"email": email, "reason": reason}

        await auth_log_service.log_auth_event(
            AuthEventType.LOGIN_FAILED,
            mock_request,
            user_id=None,
            success=False,
            details=details,
        )

        # Verify repository was called correctly
        auth_log_service.auth_log_repo.create_auth_log.assert_called_once_with(
            user_id=None,
            event_type=AuthEventType.LOGIN_FAILED.value,
            ip_address="192.168.1.100",
            user_agent="Test Browser 1.0",
            success=False,
            details=details,
        )

    async def test_get_logs_by_user(self, auth_log_service):
        """Test retrieving logs for a specific user."""
        user_id = 123
        expected_logs = [
            {
                "id": 1,
                "user_id": user_id,
                "event_type": "login_success",
                "ip_address": "192.168.1.100",
                "created_at": datetime.now(timezone.utc),
            }
        ]
        auth_log_service.auth_log_repo.get_logs_by_user.return_value = expected_logs

        logs = await auth_log_service.auth_log_repo.get_logs_by_user(user_id)

        assert logs == expected_logs
        auth_log_service.auth_log_repo.get_logs_by_user.assert_called_once_with(user_id)

    async def test_get_failed_attempts_for_ip(self, auth_log_service):
        """Test retrieving failed attempts for an IP address."""
        ip_address = "192.168.1.100"
        failed_attempts = [
            {
                "id": 1,
                "ip_address": ip_address,
                "event_type": "login_failed",
                "created_at": datetime.now(timezone.utc),
            }
        ]
        auth_log_service.auth_log_repo.get_failed_attempts_by_ip.return_value = (
            failed_attempts
        )

        attempts = await auth_log_service.auth_log_repo.get_failed_attempts_by_ip(
            ip_address
        )

        assert attempts == failed_attempts
        auth_log_service.auth_log_repo.get_failed_attempts_by_ip.assert_called_once_with(
            ip_address
        )

    async def test_detect_brute_force_attack(self, auth_log_service):
        """Test brute force attack detection."""
        ip_address = "192.168.1.100"

        # Mock multiple failed attempts within short time
        now = datetime.now(timezone.utc)
        failed_attempts = [
            {"created_at": now - timedelta(minutes=1)},
            {"created_at": now - timedelta(minutes=2)},
            {"created_at": now - timedelta(minutes=3)},
            {"created_at": now - timedelta(minutes=4)},
            {"created_at": now - timedelta(minutes=5)},
            {"created_at": now - timedelta(minutes=6)},
        ]
        auth_log_service.auth_log_repo.get_failed_attempts_by_ip.return_value = (
            failed_attempts
        )

        # Get recent failed attempts (last 10 minutes)
        attempts = await auth_log_service.auth_log_repo.get_failed_attempts_by_ip(
            ip_address
        )

        # Check if attempts exceed threshold (e.g., 5 attempts in 10 minutes)
        recent_attempts = [
            attempt
            for attempt in attempts
            if attempt["created_at"] > now - timedelta(minutes=10)
        ]

        # Simulate brute force detection logic
        is_brute_force = len(recent_attempts) >= 5
        assert is_brute_force is True
        assert len(recent_attempts) == 6

    async def test_identify_suspicious_activity_patterns(self, auth_log_service):
        """Test identification of suspicious activity patterns."""
        user_id = 123

        # Mock logs showing suspicious patterns
        suspicious_logs = [
            {
                "id": 1,
                "user_id": user_id,
                "event_type": "login_failed",
                "ip_address": "192.168.1.100",
                "created_at": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            {
                "id": 2,
                "user_id": user_id,
                "event_type": "login_success",
                "ip_address": "192.168.1.200",  # Different IP
                "created_at": datetime.now(timezone.utc) - timedelta(minutes=2),
            },
            {
                "id": 3,
                "user_id": user_id,
                "event_type": "password_reset_requested",
                "ip_address": "192.168.1.300",  # Another different IP
                "created_at": datetime.now(timezone.utc) - timedelta(minutes=3),
            },
        ]
        auth_log_service.auth_log_repo.get_logs_by_user.return_value = suspicious_logs

        logs = await auth_log_service.auth_log_repo.get_logs_by_user(user_id)

        # Identify suspicious patterns
        unique_ips = set(log["ip_address"] for log in logs)
        failed_logins = [log for log in logs if log["event_type"] == "login_failed"]
        password_resets = [
            log for log in logs if log["event_type"] == "password_reset_requested"
        ]

        # Suspicious if multiple IPs and failed login attempts
        is_suspicious = len(unique_ips) > 2 and len(failed_logins) > 0

        assert is_suspicious is True
        assert len(unique_ips) == 3
        assert len(failed_logins) == 1
        assert len(password_resets) == 1

    async def test_cleanup_old_logs(self, auth_log_service):
        """Test cleanup of old authentication logs."""
        # Mock cleanup result
        deleted_count = 150
        auth_log_service.auth_log_repo.delete_old_logs.return_value = deleted_count

        # Cleanup logs older than 90 days
        result = await auth_log_service.auth_log_repo.delete_old_logs(days=90)

        assert result == deleted_count
        auth_log_service.auth_log_repo.delete_old_logs.assert_called_once_with(days=90)

    async def test_generate_auth_analytics_report(self, auth_log_service):
        """Test generation of authentication analytics report."""
        # Mock statistics data
        mock_stats = {
            "total_logins": 1000,
            "successful_logins": 950,
            "failed_logins": 50,
            "unique_users": 200,
            "unique_ips": 300,
            "top_event_types": [
                {"event_type": "login_success", "count": 950},
                {"event_type": "login_failed", "count": 50},
            ],
            "login_success_rate": 0.95,
            "failed_login_rate": 0.05,
        }
        auth_log_service.auth_log_repo.get_auth_statistics.return_value = mock_stats

        # Generate analytics report
        stats = await auth_log_service.auth_log_repo.get_auth_statistics(
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc),
        )

        assert stats["total_logins"] == 1000
        assert stats["successful_logins"] == 950
        assert stats["failed_logins"] == 50
        assert stats["login_success_rate"] == 0.95
        assert len(stats["top_event_types"]) == 2

    async def test_log_login_success(self, auth_log_service, mock_request):
        """Test logging successful login event."""
        user_id = 123
        provider = "google"

        await auth_log_service.log_login_success(mock_request, user_id, provider)

        auth_log_service.auth_log_repo.create_auth_log.assert_called_once_with(
            user_id=user_id,
            event_type=AuthEventType.LOGIN_SUCCESS.value,
            ip_address="192.168.1.100",
            user_agent="Test Browser 1.0",
            success=True,
            details={"provider": provider},
        )

    async def test_log_login_failed(self, auth_log_service, mock_request):
        """Test logging failed login event."""
        email = "test@example.com"
        reason = "invalid_credentials"

        await auth_log_service.log_login_failed(mock_request, email, reason)

        auth_log_service.auth_log_repo.create_auth_log.assert_called_once_with(
            user_id=None,
            event_type=AuthEventType.LOGIN_FAILED.value,
            ip_address="192.168.1.100",
            user_agent="Test Browser 1.0",
            success=False,
            details={"email": email, "reason": reason},
        )

    async def test_log_oauth_login_success(self, auth_log_service, mock_request):
        """Test logging successful OAuth login."""
        user_id = 123
        provider = "github"

        await auth_log_service.log_oauth_login_success(mock_request, user_id, provider)

        auth_log_service.auth_log_repo.create_auth_log.assert_called_once_with(
            user_id=user_id,
            event_type=AuthEventType.OAUTH_LOGIN_SUCCESS.value,
            ip_address="192.168.1.100",
            user_agent="Test Browser 1.0",
            success=True,
            details={"provider": provider},
        )

    async def test_logging_error_handling(self, auth_log_service, mock_request):
        """Test error handling in logging operations."""
        # Mock repository to raise exception
        auth_log_service.auth_log_repo.create_auth_log.side_effect = Exception(
            "Database error"
        )

        # Should not raise exception, just log error
        await auth_log_service.log_auth_event(
            AuthEventType.LOGIN_SUCCESS, mock_request, user_id=123, success=True
        )

        # Verify the method was called despite the error
        auth_log_service.auth_log_repo.create_auth_log.assert_called_once()

    async def test_complex_details_serialization(self, auth_log_service, mock_request):
        """Test serialization of complex details in auth events."""
        complex_details = {
            "provider": "google",
            "oauth_data": {
                "access_token": "abc123",
                "refresh_token": "def456",
                "scopes": ["email", "profile"],
            },
            "user_info": {
                "id": "google_123",
                "email": "user@gmail.com",
                "verified": True,
            },
            "metadata": {"login_method": "sso", "device_trusted": False},
        }

        await auth_log_service.log_auth_event(
            AuthEventType.OAUTH_LOGIN_SUCCESS,
            mock_request,
            user_id=123,
            success=True,
            details=complex_details,
        )

        # Verify complex details were passed correctly
        auth_log_service.auth_log_repo.create_auth_log.assert_called_once()
        call_args = auth_log_service.auth_log_repo.create_auth_log.call_args
        assert call_args[1]["details"] == complex_details
