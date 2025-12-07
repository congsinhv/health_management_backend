"""
Internal notification endpoints for Cloud Tasks integration.
"""

import asyncpg
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request, Header, HTTPException

from app.config import settings, logger
from app.db.database import get_database_pool
from app.db.notification import NotificationRepository
from app.db.device import DeviceRepository
from app.services.fcm import FCMService
from app.services.schedule.service import ScheduleService
from app.core.error_context import ErrorContext

router = APIRouter()


class ProcessBatchRequest(BaseModel):
    """Batch processing request (empty - uses current time)."""
    pass


class SendNotificationRequest(BaseModel):
    """Single notification send request."""
    notification_id: int


async def verify_cloud_tasks_auth(
    x_cloudtasks_queuename: Optional[str] = Header(None),
    x_cloudtasks_taskname: Optional[str] = Header(None),
):
    """Verify request is from Cloud Tasks.

    Cloud Tasks adds specific headers. In development (debug=True),
    requests without headers are allowed for testing.
    In production, only Cloud Tasks requests are accepted.
    """
    # Check for Cloud Tasks headers (production-safe)
    if x_cloudtasks_queuename and x_cloudtasks_taskname:
        logger.debug(f"Cloud Tasks request: queue={x_cloudtasks_queuename}, task={x_cloudtasks_taskname}")
        return True

    # In production, reject requests without Cloud Tasks headers
    if not settings.debug:
        raise HTTPException(status_code=401, detail="Unauthorized - Cloud Tasks headers required")

    # Allow in development mode for testing
    logger.warning("Cloud Tasks auth bypassed in debug mode")
    return True


async def get_fcm_service(request: Request) -> FCMService:
    """Get FCM service from app state."""
    fcm = getattr(request.app.state, "fcm_service", None)
    if not fcm:
        raise HTTPException(status_code=503, detail="FCM service not available")
    return fcm


async def get_schedule_service(
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ScheduleService:
    """Get schedule service."""
    cache_service = getattr(request.app.state, "cache_service", None)
    return ScheduleService(db_pool, cache_service=cache_service)


@router.post("/process-batch")
async def process_notification_batch(
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    _auth: bool = Depends(verify_cloud_tasks_auth),
):
    """Process pending notifications for the next window.

    Called by Cloud Scheduler every 5 minutes.
    Finds pending notifications and creates Cloud Tasks for sending.
    """
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "process_notification_batch")

    notification_repo = NotificationRepository(db_pool)

    now = datetime.now(ZoneInfo("UTC"))
    window_end = now + timedelta(minutes=5)

    with ErrorContext("process_batch", {"window_end": window_end.isoformat()}):
        # Get pending notifications in window
        notifications = await notification_repo.get_pending_in_window(now, window_end)

        if not notifications:
            return {"processed": 0, "message": "No pending notifications"}

        # Import Cloud Tasks service (Phase 5)
        try:
            from app.services.cloud_tasks import CloudTasksService
            tasks_service = CloudTasksService()
        except ImportError:
            # Cloud Tasks not implemented yet (Phase 5)
            logger.warning("Cloud Tasks service not available yet")
            return {
                "processed": len(notifications),
                "queued": 0,
                "message": "Cloud Tasks service not implemented",
            }

        queued_count = 0
        errors = []

        for notif in notifications:
            try:
                # Create Cloud Task for each notification
                task_name = await tasks_service.create_notification_task(
                    notification_id=notif["id"],
                    scheduled_at=notif["scheduled_at"],
                )

                # Update status to queued
                await notification_repo.update_status(
                    notification_id=notif["id"],
                    status="queued",
                    cloud_task_name=task_name,
                )
                queued_count += 1

            except Exception as e:
                logger.error(f"Failed to queue notification {notif['id']}: {e}")
                errors.append({"id": notif["id"], "error": str(e)})

        return {
            "processed": len(notifications),
            "queued": queued_count,
            "errors": errors if errors else None,
        }


@router.post("/send")
async def send_notification(
    request_data: SendNotificationRequest,
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
    fcm_service: FCMService = Depends(get_fcm_service),
    schedule_service: ScheduleService = Depends(get_schedule_service),
    _auth: bool = Depends(verify_cloud_tasks_auth),
):
    """Send a single notification via FCM.

    Called by Cloud Tasks when notification is due.
    """
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "send_notification")
    ErrorContext.add_context("notification_id", request_data.notification_id)

    notification_repo = NotificationRepository(db_pool)
    device_repo = DeviceRepository(db_pool)

    with ErrorContext("send_notification", {"notification_id": request_data.notification_id}):
        # Get notification
        notif = await notification_repo.get_by_id(request_data.notification_id)
        if not notif:
            return {"success": False, "error": "Notification not found"}

        if notif["status"] == "sent":
            return {"success": True, "message": "Already sent"}

        # Get user devices
        devices = await device_repo.get_active_by_user(notif["user_id"])
        if not devices:
            await notification_repo.update_status(
                notification_id=notif["id"],
                status="failed",
                error_message="No active devices",
            )
            return {"success": False, "error": "No active devices"}

        tokens = [d["fcm_token"] for d in devices]

        # Send via FCM
        data = json.loads(notif["data"]) if notif["data"] else None

        result = await fcm_service.send_notification(
            tokens=tokens,
            title=notif["title"],
            body=notif["body"],
            data=data,
        )

        # Handle invalid tokens
        if result.get("invalid_tokens"):
            for invalid_token in result["invalid_tokens"]:
                await device_repo.deactivate_token(invalid_token)

        # Update notification status
        if result.get("success_count", 0) > 0:
            await notification_repo.update_status(
                notification_id=notif["id"],
                status="sent",
            )

            # Log exercise from notification
            await schedule_service.log_exercise_from_notification(notif["id"])

            return {"success": True, "delivered_to": result["success_count"]}
        else:
            await notification_repo.update_status(
                notification_id=notif["id"],
                status="failed",
                error_message=result.get("error", "All deliveries failed"),
            )
            return {"success": False, "error": result.get("error")}
