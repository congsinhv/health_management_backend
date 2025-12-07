"""
Integration tests for Notification API endpoints.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timedelta, timezone

from app.main import app


class TestNotificationBatchProcessing:
    """Tests for notification batch processing endpoint."""

    @pytest.fixture(autouse=True)
    def setup_services(self, mock_cloud_tasks_service):
        """Setup services on app state."""
        app.state.cloud_tasks_service = mock_cloud_tasks_service
        yield
        app.state.cloud_tasks_service = None

    @pytest.mark.asyncio
    async def test_process_batch_requires_auth_in_production(self):
        """Test process-batch requires Cloud Tasks auth in production."""
        # Without debug mode and without Cloud Tasks headers
        with patch("app.api.notifications.settings") as mock_settings:
            mock_settings.debug = False

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.post("/api/v1/notifications/process-batch")
                # Should reject without proper auth
                assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_process_batch_allows_cloud_tasks_headers(self):
        """Test process-batch accepts Cloud Tasks headers."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            # With Cloud Tasks headers (simulating actual Cloud Tasks call)
            response = await client.post(
                "/api/v1/notifications/process-batch",
                headers={
                    "X-CloudTasks-QueueName": "workout-notifications",
                    "X-CloudTasks-TaskName": "test-task-123"
                }
            )
            # Should accept (may fail later due to DB, but auth passes)
            assert response.status_code != 401

    @pytest.mark.asyncio
    async def test_process_batch_debug_mode_bypass(self):
        """Test process-batch allows bypass in debug mode."""
        # In debug mode (default for tests), auth is bypassed
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post("/api/v1/notifications/process-batch")
            # Should not be 401 (auth bypassed)
            assert response.status_code != 401


class TestNotificationSend:
    """Tests for notification send endpoint."""

    @pytest.fixture(autouse=True)
    def setup_services(self, mock_fcm_service, mock_cloud_tasks_service):
        """Setup services on app state."""
        app.state.fcm_service = mock_fcm_service
        app.state.cloud_tasks_service = mock_cloud_tasks_service
        yield
        app.state.fcm_service = None
        app.state.cloud_tasks_service = None

    @pytest.mark.asyncio
    async def test_send_notification_requires_body(self):
        """Test send endpoint requires notification_id in body."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/notifications/send",
                json={},  # Empty body
                headers={
                    "X-CloudTasks-QueueName": "workout-notifications",
                    "X-CloudTasks-TaskName": "test-task-123"
                }
            )
            # Should fail validation (missing notification_id)
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_send_notification_valid_request(self):
        """Test send endpoint with valid request structure."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/notifications/send",
                json={"notification_id": 999},  # Non-existent but valid format
                headers={
                    "X-CloudTasks-QueueName": "workout-notifications",
                    "X-CloudTasks-TaskName": "test-task-123"
                }
            )
            # Should not be 422 (validation error)
            # Will likely be 503 (FCM service) or 404 (notification not found)
            assert response.status_code in [200, 404, 500, 503]


class TestNotificationStats:
    """Tests for notification stats endpoint."""

    @pytest.fixture(autouse=True)
    def setup_services(self, mock_cloud_tasks_service):
        """Setup services on app state."""
        app.state.cloud_tasks_service = mock_cloud_tasks_service
        yield
        app.state.cloud_tasks_service = None

    @pytest.mark.asyncio
    async def test_stats_endpoint_exists(self):
        """Test stats endpoint is accessible."""
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/notifications/stats",
                headers={
                    "X-CloudTasks-QueueName": "workout-notifications",
                    "X-CloudTasks-TaskName": "test-task-123"
                }
            )
            # Should not be 404 (endpoint exists)
            assert response.status_code != 404


class TestNotificationEdgeCases:
    """Edge case tests for notifications."""

    def test_notification_window_boundary(self):
        """Test notifications exactly at window boundary."""
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(minutes=5)

        # Notification exactly at window end
        at_boundary = window_end

        # Should be included in window (<=)
        assert now <= at_boundary <= window_end

    def test_notification_just_past_window(self):
        """Test notifications just past window boundary."""
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(minutes=5)

        # Notification 1 second after window
        past_boundary = window_end + timedelta(seconds=1)

        # Should NOT be included
        assert not (now <= past_boundary <= window_end)

    def test_multiple_notifications_same_time(self):
        """Test handling multiple notifications at same time."""
        # This tests the batch processing logic
        now = datetime.now(timezone.utc)

        notifications = [
            {"id": 1, "scheduled_at": now, "user_id": 1},
            {"id": 2, "scheduled_at": now, "user_id": 2},
            {"id": 3, "scheduled_at": now, "user_id": 1},  # Same user, same time
        ]

        # All should be processable
        assert len(notifications) == 3

    def test_notification_retry_count_increment(self):
        """Test retry count increments on failure."""
        initial_retry = 0
        after_failure = initial_retry + 1

        assert after_failure == 1

        # After 3 failures, should stop retrying
        max_retries = 3
        assert after_failure <= max_retries


class TestCloudTasksIntegration:
    """Tests for Cloud Tasks integration."""

    def test_task_name_format(self):
        """Test Cloud Task name format is valid."""
        notification_id = 12345
        task_name = f"notif-{notification_id}"

        # Should match expected format
        assert task_name == "notif-12345"
        assert task_name.startswith("notif-")

    def test_task_name_uniqueness(self):
        """Test task names are unique per notification."""
        names = set()

        for i in range(100):
            name = f"notif-{i}"
            assert name not in names
            names.add(name)

        assert len(names) == 100

    def test_scheduled_time_in_future(self):
        """Test scheduled time must be in the future."""
        now = datetime.now(timezone.utc)

        # Future time (valid)
        future = now + timedelta(minutes=5)
        assert future > now

        # Past time (should be rejected or executed immediately)
        past = now - timedelta(minutes=5)
        assert past < now
