"""
Cloud Tasks service for scheduling notifications.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

from app.config import settings

logger = logging.getLogger(__name__)


class CloudTasksService:
    """Cloud Tasks service for creating and managing notification tasks."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        location: Optional[str] = None,
        queue: Optional[str] = None,
        service_account: Optional[str] = None,
    ):
        """Initialize Cloud Tasks service.

        Args:
            project_id: GCP project ID (defaults to settings)
            location: Cloud Tasks location (defaults to settings)
            queue: Queue name (defaults to settings)
            service_account: Service account for OIDC (defaults to settings)
        """
        self.project_id = project_id or settings.gcp_project_id
        self.location = location or settings.cloud_tasks_location
        self.queue = queue or settings.cloud_tasks_queue
        self.service_account = service_account or settings.cloud_tasks_service_account
        self.backend_url = settings.backend_url

        if not self.project_id:
            raise ValueError("GCP project ID is required for Cloud Tasks")

        self.parent = (
            f"projects/{self.project_id}/locations/{self.location}/queues/{self.queue}"
        )

        # Initialize client (lazy - only when needed)
        self._client: Optional[tasks_v2.CloudTasksClient] = None

    @property
    def client(self) -> tasks_v2.CloudTasksClient:
        """Get or create Cloud Tasks client."""
        if self._client is None:
            self._client = tasks_v2.CloudTasksClient()
        return self._client

    async def create_notification_task(
        self, notification_id: int, scheduled_at: datetime
    ) -> str:
        """Create a Cloud Task to send a notification.

        Args:
            notification_id: ID of the notification to send
            scheduled_at: When to send the notification (UTC)

        Returns:
            Task name (full resource path)
        """
        if not self.backend_url:
            raise ValueError("Backend URL is required for Cloud Tasks")

        # Build HTTP request
        url = f"{self.backend_url}/api/v1/notifications/send"
        payload = json.dumps({"notification_id": notification_id}).encode()

        http_request = {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": url,
            "headers": {"Content-Type": "application/json"},
            "body": payload,
        }

        # Add OIDC token if service account is configured
        if self.service_account:
            http_request["oidc_token"] = {
                "service_account_email": self.service_account,
                "audience": self.backend_url,
            }

        # Build task with schedule time
        task = {
            "http_request": http_request,
            "name": f"{self.parent}/tasks/notif-{notification_id}-{scheduled_at.isoformat().replace(':', '-')}",
        }

        # Set schedule time if in the future
        from datetime import timezone

        now_utc = datetime.now(timezone.utc)

        # Ensure scheduled_at is timezone-aware for comparison
        if scheduled_at.tzinfo is None:
            # Assume naive datetimes are UTC
            scheduled_at_aware = scheduled_at.replace(tzinfo=timezone.utc)
        else:
            scheduled_at_aware = scheduled_at

        if scheduled_at_aware > now_utc:
            timestamp = timestamp_pb2.Timestamp()
            # FromDatetime requires a naive UTC datetime
            timestamp.FromDatetime(scheduled_at_aware.replace(tzinfo=None))
            task["schedule_time"] = timestamp

        try:
            response = self.client.create_task(
                request={"parent": self.parent, "task": task}
            )
            logger.info(
                f"Created Cloud Task: {response.name} for notification {notification_id}"
            )
            return response.name

        except Exception as e:
            # Handle duplicate task (already exists)
            if "ALREADY_EXISTS" in str(e):
                logger.warning(
                    f"Task already exists for notification {notification_id}"
                )
                return task["name"]
            raise

    async def delete_task(self, task_name: str) -> bool:
        """Delete a Cloud Task.

        Args:
            task_name: Full task resource name

        Returns:
            True if deleted, False if not found
        """
        try:
            self.client.delete_task(request={"name": task_name})
            logger.info(f"Deleted Cloud Task: {task_name}")
            return True

        except Exception as e:
            if "NOT_FOUND" in str(e):
                logger.warning(f"Task not found: {task_name}")
                return False
            logger.error(f"Failed to delete task {task_name}: {e}")
            raise

    async def get_queue_stats(self) -> dict:
        """Get queue statistics for monitoring.

        Returns:
            Queue stats including state, rate limits, retry config
        """
        try:
            queue = self.client.get_queue(request={"name": self.parent})

            return {
                "name": queue.name,
                "state": queue.state.name,
                "rate_limits": {
                    "max_dispatches_per_second": queue.rate_limits.max_dispatches_per_second,
                    "max_burst_size": queue.rate_limits.max_burst_size,
                    "max_concurrent_dispatches": queue.rate_limits.max_concurrent_dispatches,
                },
                "retry_config": {
                    "max_attempts": queue.retry_config.max_attempts,
                    "max_retry_duration": (
                        str(queue.retry_config.max_retry_duration)
                        if queue.retry_config.max_retry_duration
                        else None
                    ),
                    "min_backoff": (
                        str(queue.retry_config.min_backoff)
                        if queue.retry_config.min_backoff
                        else None
                    ),
                    "max_backoff": (
                        str(queue.retry_config.max_backoff)
                        if queue.retry_config.max_backoff
                        else None
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {"error": str(e)}

    async def pause_queue(self) -> bool:
        """Pause the queue (stop dispatching tasks)."""
        try:
            self.client.pause_queue(request={"name": self.parent})
            logger.info(f"Paused queue: {self.parent}")
            return True
        except Exception as e:
            logger.error(f"Failed to pause queue: {e}")
            return False

    async def resume_queue(self) -> bool:
        """Resume the queue (start dispatching tasks)."""
        try:
            self.client.resume_queue(request={"name": self.parent})
            logger.info(f"Resumed queue: {self.parent}")
            return True
        except Exception as e:
            logger.error(f"Failed to resume queue: {e}")
            return False
