"""
Schedule service for workout reminder management.
"""

import logging
import json
from typing import Optional, Dict, Any
import asyncpg
from datetime import time

from app.db.schedule_plan import SchedulePlanRepository
from app.db.notification import NotificationRepository
from app.db.device import DeviceRepository
from app.db.exercise_log import ExerciseLogRepository
from app.schemas.schedule import (
    ScheduleCreateRequest,
    ScheduleResponse,
    DeviceRegisterRequest,
    DeviceResponse,
)
from app.services.schedule.ai_planner import generate_weekly_plan
from app.services.schedule.scheduler import schedule_notifications_for_week
from app.exceptions import (
    ResourceNotFoundException,
    BusinessLogicException,
    ValidationException,
)

logger = logging.getLogger(__name__)


class ScheduleService:
    """Service for schedule management."""

    def __init__(self, db_pool: asyncpg.Pool, cache_service=None):
        self.plan_repo = SchedulePlanRepository(db_pool)
        self.notification_repo = NotificationRepository(db_pool)
        self.device_repo = DeviceRepository(db_pool)
        self.exercise_log_repo = ExerciseLogRepository(db_pool)
        self.cache_service = cache_service

    async def create_or_update_schedule(
        self, user_id: int, request: ScheduleCreateRequest
    ) -> ScheduleResponse:
        """Create or update user's workout schedule."""

        # Deactivate existing plan
        await self.plan_repo.deactivate(user_id)

        # Create new plan
        plan_data = {
            "user_id": user_id,
            "height_m": request.basic_info.height,
            "weight_kg": request.basic_info.weight,
            "target_weight_kg": request.basic_info.target_weight,
            "goal": request.basic_info.goal.value,
            "schedule_mode": request.schedule.mode.value,
            "selected_days": [d.value for d in request.schedule.selected_days],
            "timezone": request.timezone,
            "sports_predefined": request.sports.predefined,
            "sports_custom": request.sports.custom,
            "personal_notes": request.notes.personal if request.notes else None,
            "health_warnings": request.notes.health_warnings if request.notes else None,
        }

        # Fixed mode times - convert string to time objects
        if request.schedule.mode.value == "fixed" and request.schedule.fixed_period:
            from datetime import datetime
            # Parse time strings to time objects
            start_time = datetime.strptime(request.schedule.fixed_period.start_time, "%H:%M:%S").time()
            end_time = datetime.strptime(request.schedule.fixed_period.end_time, "%H:%M:%S").time()
            plan_data["fixed_start_time"] = start_time
            plan_data["fixed_end_time"] = end_time

        # Flexible mode periods
        if request.schedule.mode.value == "flexible" and request.schedule.flexible_periods:
            plan_data["flexible_periods"] = {
                k.value: [{"startTime": p.start_time, "endTime": p.end_time} for p in v]
                for k, v in request.schedule.flexible_periods.items()
            }

        record = await self.plan_repo.create(plan_data)
        plan_id = record["id"]

        # Generate AI plan
        weekly_plan = await generate_weekly_plan(
            goal=request.basic_info.goal.value,
            weight_kg=request.basic_info.weight or 60,
            target_weight_kg=request.basic_info.target_weight,
            height_m=request.basic_info.height or 1.70,
            selected_days=plan_data["selected_days"],
            schedule_mode=plan_data["schedule_mode"],
            fixed_start_time=plan_data.get("fixed_start_time"),
            fixed_end_time=plan_data.get("fixed_end_time"),
            flexible_periods=plan_data.get("flexible_periods"),
            sports=request.sports.predefined + request.sports.custom,
            health_warnings=plan_data.get("health_warnings"),
        )

        # Update plan with AI result
        record = await self.plan_repo.update_weekly_plan(plan_id, weekly_plan)

        # Schedule notifications for week
        notifications = schedule_notifications_for_week(
            plan_id=plan_id,
            user_id=user_id,
            timezone=request.timezone,
            selected_days=plan_data["selected_days"],
            schedule_mode=plan_data["schedule_mode"],
            fixed_start_time=self._parse_time(plan_data.get("fixed_start_time")),
            fixed_end_time=self._parse_time(plan_data.get("fixed_end_time")),
            flexible_periods=plan_data.get("flexible_periods"),
            weekly_plan=weekly_plan,
        )

        if notifications:
            await self.notification_repo.create_batch(notifications)

        return self._to_response(record)

    async def log_exercise_from_notification(self, notification_id: int):
        """Log exercise when notification is sent."""
        notification = await self.notification_repo.get_by_id(notification_id)
        if not notification:
            return

        import json
        data = json.loads(notification["data"]) if notification["data"] else {}

        await self.exercise_log_repo.create({
            "user_id": notification["user_id"],
            "scheduled_notification_id": notification_id,
            "exercise_minutes": data.get("duration_minutes", 0),
            "calories": data.get("estimated_calories", 0),
            "date": notification["workout_date"],
        })

    async def get_active_schedule(self, user_id: int) -> Optional[ScheduleResponse]:
        """Get user's active schedule."""
        record = await self.plan_repo.get_active_by_user(user_id)
        if not record:
            return None
        return self._to_response(record)

    async def deactivate_schedule(self, user_id: int) -> bool:
        """Deactivate user's schedule and cancel pending notifications."""
        record = await self.plan_repo.get_active_by_user(user_id)
        if not record:
            raise ResourceNotFoundException(
                message="No active schedule found",
                details={"user_id": user_id},
            )

        # Delete pending notifications
        await self.notification_repo.delete_by_plan(record["id"])

        # Deactivate plan
        return await self.plan_repo.deactivate(user_id)

    async def regenerate_plan(self, user_id: int) -> ScheduleResponse:
        """Regenerate AI plan without changing schedule config."""
        record = await self.plan_repo.get_active_by_user(user_id)
        if not record:
            raise ResourceNotFoundException(
                message="No active schedule found",
                details={"user_id": user_id},
            )

        # Delete old notifications
        await self.notification_repo.delete_by_plan(record["id"])

        # Regenerate AI plan
        weekly_plan = await generate_weekly_plan(
            goal=record["goal"],
            weight_kg=record["weight_kg"] or 60,
            target_weight_kg=record["target_weight_kg"],
            height_m=record["height_m"] or 1.70,
            selected_days=list(record["selected_days"]),
            schedule_mode=record["schedule_mode"],
            fixed_start_time=str(record["fixed_start_time"]) if record["fixed_start_time"] else None,
            fixed_end_time=str(record["fixed_end_time"]) if record["fixed_end_time"] else None,
            flexible_periods=record["flexible_periods"],
            sports=list(record["sports_predefined"]) + list(record["sports_custom"] or []),
            health_warnings=record["health_warnings"],
        )

        record = await self.plan_repo.update_weekly_plan(record["id"], weekly_plan)

        # Reschedule notifications
        notifications = schedule_notifications_for_week(
            plan_id=record["id"],
            user_id=user_id,
            timezone=record["timezone"],
            selected_days=list(record["selected_days"]),
            schedule_mode=record["schedule_mode"],
            fixed_start_time=record["fixed_start_time"],
            fixed_end_time=record["fixed_end_time"],
            flexible_periods=record["flexible_periods"],
            weekly_plan=weekly_plan,
        )

        if notifications:
            await self.notification_repo.create_batch(notifications)

        return self._to_response(record)

    async def register_device(
        self, user_id: int, request: DeviceRegisterRequest
    ) -> DeviceResponse:
        """Register FCM device token."""
        record = await self.device_repo.register(
            user_id=user_id,
            fcm_token=request.fcm_token,
            device_type=request.device_type,
            device_name=request.device_name,
        )
        return DeviceResponse(
            id=record["id"],
            device_type=record["device_type"],
            device_name=record["device_name"],
            is_active=record["is_active"],
            last_used_at=record["last_used_at"],
        )

    async def unregister_device(self, user_id: int, fcm_token: str) -> bool:
        """Unregister FCM device token."""
        return await self.device_repo.deactivate(user_id, fcm_token)

    async def get_user_devices(self, user_id: int) -> list[DeviceResponse]:
        """Get all active devices for a user."""
        records = await self.device_repo.get_active_by_user(user_id)
        return [
            DeviceResponse(
                id=record["id"],
                device_type=record["device_type"],
                device_name=record["device_name"],
                is_active=record["is_active"],
                last_used_at=record["last_used_at"],
            )
            for record in records
        ]

    def _to_response(self, record: asyncpg.Record) -> ScheduleResponse:
        """Convert DB record to response."""
        weekly_plan = record["weekly_plan"]
        if isinstance(weekly_plan, str):
            weekly_plan = json.loads(weekly_plan)

        return ScheduleResponse(
            id=record["id"],
            user_id=record["user_id"],
            goal=record["goal"],
            schedule_mode=record["schedule_mode"],
            selected_days=list(record["selected_days"]),
            timezone=record["timezone"],
            weekly_plan=weekly_plan,
            status=record["status"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )

    def _parse_time(self, time_str: Optional[str]):
        """Parse time string to time object."""
        if not time_str:
            return None
        parts = str(time_str).split(":")
        return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
