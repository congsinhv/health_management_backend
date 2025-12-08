"""
Unit tests for Cloud Tasks service.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, AsyncMock

from google.cloud import tasks_v2
from google.api_core import exceptions as google_exceptions


class TestCloudTasksService:
    """Tests for CloudTasksService."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        with patch("app.services.cloud_tasks.settings") as mock:
            mock.gcp_project_id = "test-project"
            mock.cloud_tasks_location = "asia-southeast1"
            mock.cloud_tasks_queue = "test-queue"
            mock.cloud_tasks_service_account = (
                "test-sa@test-project.iam.gserviceaccount.com"
            )
            mock.backend_url = "https://api.test.com"
            yield mock

    @pytest.fixture
    def cloud_tasks_service(self, mock_settings):
        """Create CloudTasksService instance with mock settings."""
        from app.services.cloud_tasks import CloudTasksService

        return CloudTasksService()

    def test_initialization(self, mock_settings):
        """Test service initialization."""
        from app.services.cloud_tasks import CloudTasksService

        service = CloudTasksService()

        assert service.project_id == "test-project"
        assert service.location == "asia-southeast1"
        assert service.queue == "test-queue"
        assert service.service_account == "test-sa@test-project.iam.gserviceaccount.com"
        assert (
            service.parent
            == "projects/test-project/locations/asia-southeast1/queues/test-queue"
        )

    def test_initialization_without_project_raises(self):
        """Test that initialization without project ID raises error."""
        with patch("app.services.cloud_tasks.settings") as mock:
            mock.gcp_project_id = None
            mock.cloud_tasks_location = "asia-southeast1"
            mock.cloud_tasks_queue = "test-queue"
            mock.cloud_tasks_service_account = None
            mock.backend_url = None

            from app.services.cloud_tasks import CloudTasksService

            with pytest.raises(ValueError, match="GCP project ID is required"):
                CloudTasksService()

    def test_initialization_with_custom_params(self, mock_settings):
        """Test service initialization with custom parameters."""
        from app.services.cloud_tasks import CloudTasksService

        service = CloudTasksService(
            project_id="custom-project",
            location="us-central1",
            queue="custom-queue",
            service_account="custom@custom.iam.gserviceaccount.com",
        )

        assert service.project_id == "custom-project"
        assert service.location == "us-central1"
        assert service.queue == "custom-queue"
        assert service.service_account == "custom@custom.iam.gserviceaccount.com"

    @pytest.mark.asyncio
    async def test_create_notification_task_without_backend_url(self, mock_settings):
        """Test task creation fails without backend URL."""
        mock_settings.backend_url = None

        from app.services.cloud_tasks import CloudTasksService

        service = CloudTasksService()

        with pytest.raises(ValueError, match="Backend URL is required"):
            await service.create_notification_task(
                notification_id=1, scheduled_at=datetime.utcnow() + timedelta(minutes=5)
            )

    @pytest.mark.asyncio
    async def test_create_notification_task_success(self, cloud_tasks_service):
        """Test successful task creation."""
        mock_response = MagicMock()
        mock_response.name = "projects/test-project/locations/asia-southeast1/queues/test-queue/tasks/notif-1"

        with patch.object(cloud_tasks_service, "_client", None):
            mock_client = MagicMock()
            mock_client.create_task.return_value = mock_response

            with patch.object(tasks_v2, "CloudTasksClient", return_value=mock_client):
                cloud_tasks_service._client = None  # Reset client

                scheduled_at = datetime.utcnow() + timedelta(minutes=5)
                task_name = await cloud_tasks_service.create_notification_task(
                    notification_id=1, scheduled_at=scheduled_at
                )

                assert task_name == mock_response.name
                mock_client.create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_notification_task_already_exists(self, cloud_tasks_service):
        """Test task creation when task already exists."""
        with patch.object(cloud_tasks_service, "_client", None):
            mock_client = MagicMock()
            mock_client.create_task.side_effect = Exception(
                "ALREADY_EXISTS: Task already exists"
            )

            with patch.object(tasks_v2, "CloudTasksClient", return_value=mock_client):
                cloud_tasks_service._client = None

                scheduled_at = datetime.utcnow() + timedelta(minutes=5)
                task_name = await cloud_tasks_service.create_notification_task(
                    notification_id=1, scheduled_at=scheduled_at
                )

                # Should return task name without raising
                assert "notif-1" in task_name

    @pytest.mark.asyncio
    async def test_delete_task_success(self, cloud_tasks_service):
        """Test successful task deletion."""
        with patch.object(cloud_tasks_service, "_client", None):
            mock_client = MagicMock()
            mock_client.delete_task.return_value = None

            with patch.object(tasks_v2, "CloudTasksClient", return_value=mock_client):
                cloud_tasks_service._client = None

                result = await cloud_tasks_service.delete_task(
                    "projects/test/locations/test/queues/test/tasks/notif-1"
                )

                assert result is True
                mock_client.delete_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, cloud_tasks_service):
        """Test task deletion when task not found."""
        with patch.object(cloud_tasks_service, "_client", None):
            mock_client = MagicMock()
            mock_client.delete_task.side_effect = Exception("NOT_FOUND: Task not found")

            with patch.object(tasks_v2, "CloudTasksClient", return_value=mock_client):
                cloud_tasks_service._client = None

                result = await cloud_tasks_service.delete_task(
                    "projects/test/locations/test/queues/test/tasks/notif-999"
                )

                assert result is False

    @pytest.mark.asyncio
    async def test_get_queue_stats_success(self, cloud_tasks_service):
        """Test getting queue statistics."""
        with patch.object(cloud_tasks_service, "_client", None):
            mock_queue = MagicMock()
            mock_queue.name = "projects/test/locations/test/queues/test"
            mock_queue.state.name = "RUNNING"
            mock_queue.rate_limits.max_dispatches_per_second = 500
            mock_queue.rate_limits.max_burst_size = 100
            mock_queue.rate_limits.max_concurrent_dispatches = 1000
            mock_queue.retry_config.max_attempts = 3
            mock_queue.retry_config.max_retry_duration = None
            mock_queue.retry_config.min_backoff = MagicMock(__str__=lambda x: "1s")
            mock_queue.retry_config.max_backoff = MagicMock(__str__=lambda x: "3600s")

            mock_client = MagicMock()
            mock_client.get_queue.return_value = mock_queue

            with patch.object(tasks_v2, "CloudTasksClient", return_value=mock_client):
                cloud_tasks_service._client = None

                stats = await cloud_tasks_service.get_queue_stats()

                assert stats["state"] == "RUNNING"
                assert stats["rate_limits"]["max_dispatches_per_second"] == 500
                assert stats["retry_config"]["max_attempts"] == 3

    @pytest.mark.asyncio
    async def test_get_queue_stats_error(self, cloud_tasks_service):
        """Test getting queue statistics when error occurs."""
        with patch.object(cloud_tasks_service, "_client", None):
            mock_client = MagicMock()
            mock_client.get_queue.side_effect = Exception("Queue not found")

            with patch.object(tasks_v2, "CloudTasksClient", return_value=mock_client):
                cloud_tasks_service._client = None

                stats = await cloud_tasks_service.get_queue_stats()

                assert "error" in stats

    @pytest.mark.asyncio
    async def test_pause_queue(self, cloud_tasks_service):
        """Test pausing queue."""
        with patch.object(cloud_tasks_service, "_client", None):
            mock_client = MagicMock()
            mock_client.pause_queue.return_value = None

            with patch.object(tasks_v2, "CloudTasksClient", return_value=mock_client):
                cloud_tasks_service._client = None

                result = await cloud_tasks_service.pause_queue()

                assert result is True
                mock_client.pause_queue.assert_called_once()

    @pytest.mark.asyncio
    async def test_resume_queue(self, cloud_tasks_service):
        """Test resuming queue."""
        with patch.object(cloud_tasks_service, "_client", None):
            mock_client = MagicMock()
            mock_client.resume_queue.return_value = None

            with patch.object(tasks_v2, "CloudTasksClient", return_value=mock_client):
                cloud_tasks_service._client = None

                result = await cloud_tasks_service.resume_queue()

                assert result is True
                mock_client.resume_queue.assert_called_once()


class TestCloudTasksConfig:
    """Tests for Cloud Tasks configuration."""

    def test_config_defaults(self):
        """Test default Cloud Tasks configuration values."""
        from app.config import Settings

        # Create settings with minimal required fields
        with patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql://test:test@localhost/test",
                "SECRET_KEY": "test-secret-key",
            },
        ):
            settings = Settings()

        assert settings.cloud_tasks_enabled is True
        assert settings.cloud_tasks_queue == "workout-notifications"
        assert settings.cloud_tasks_location == "asia-southeast1"
        assert settings.cloud_tasks_service_account is None
        assert settings.backend_url is None

    def test_config_from_env(self):
        """Test Cloud Tasks configuration from environment."""
        from app.config import Settings

        with patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "postgresql://test:test@localhost/test",
                "SECRET_KEY": "test-secret-key",
                "CLOUD_TASKS_ENABLED": "true",
                "CLOUD_TASKS_QUEUE": "custom-queue",
                "CLOUD_TASKS_LOCATION": "us-central1",
                "CLOUD_TASKS_SERVICE_ACCOUNT": "test-sa@project.iam.gserviceaccount.com",
                "BACKEND_URL": "https://api.example.com",
            },
        ):
            settings = Settings()

        assert settings.cloud_tasks_enabled is True
        assert settings.cloud_tasks_queue == "custom-queue"
        assert settings.cloud_tasks_location == "us-central1"
        assert (
            settings.cloud_tasks_service_account
            == "test-sa@project.iam.gserviceaccount.com"
        )
        assert settings.backend_url == "https://api.example.com"
