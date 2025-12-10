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
    WorkoutPlan,
    WorkoutStatus,
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

        # Build plan data
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
            start_time = datetime.strptime(
                request.schedule.fixed_period.start_time, "%H:%M:%S"
            ).time()
            end_time = datetime.strptime(
                request.schedule.fixed_period.end_time, "%H:%M:%S"
            ).time()
            plan_data["fixed_start_time"] = start_time
            plan_data["fixed_end_time"] = end_time

        # Flexible mode periods
        if (
            request.schedule.mode.value == "flexible"
            and request.schedule.flexible_periods
        ):
            plan_data["flexible_periods"] = {
                k.value: [{"startTime": p.start_time, "endTime": p.end_time} for p in v]
                for k, v in request.schedule.flexible_periods.items()
            }

        # Atomically deactivate existing and create new plan in one transaction
        record = await self.plan_repo.deactivate_and_create(plan_data)
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

        return await self._to_response(record)

    async def log_exercise_from_notification(self, notification_id: int):
        """Log exercise when notification is sent."""
        notification = await self.notification_repo.get_by_id(notification_id)
        if not notification:
            return

        import json

        data = json.loads(notification["data"]) if notification["data"] else {}

        await self.exercise_log_repo.create(
            {
                "user_id": notification["user_id"],
                "scheduled_notification_id": notification_id,
                "exercise_minutes": data.get("duration_minutes", 0),
                "calories": data.get("estimated_calories", 0),
                "date": notification["workout_date"],
            }
        )

    async def get_active_schedule(self, user_id: int) -> Optional[ScheduleResponse]:
        """Get user's current schedule (active or paused)."""
        record = await self.plan_repo.get_current_by_user(user_id)
        if not record:
            return None
        return await self._to_response(record)

    async def list_schedules(self, user_id: int) -> list[ScheduleResponse]:
        """List all schedules for a user."""
        records = await self.plan_repo.list_by_user(user_id)
        return [await self._to_response(record) for record in records]

    async def toggle_schedule_status(
        self, user_id: int, schedule_id: int, is_active: bool
    ) -> ScheduleResponse:
        """Toggle schedule status between active and paused.

        Only 1 schedule can be active per user at a time.

        Args:
            user_id: User ID
            schedule_id: Schedule ID to update
            is_active: True to activate, False to pause

        Returns:
            Updated schedule response
        """
        # Get schedule by ID
        record = await self.plan_repo.get_by_id(schedule_id)
        if not record or record["deleted_at"] is not None:
            raise ResourceNotFoundException(
                message="Schedule not found",
                details={"schedule_id": schedule_id},
            )

        # Verify ownership
        if record["user_id"] != user_id:
            raise ResourceNotFoundException(
                message="Schedule not found",
                details={"schedule_id": schedule_id},
            )

        # Only allow toggling active or paused schedules
        if record["status"] not in ("active", "paused"):
            raise ResourceNotFoundException(
                message="Schedule not found",
                details={"schedule_id": schedule_id},
            )

        current_status = record["status"]
        new_status = "active" if is_active else "paused"

        # No change needed
        if current_status == new_status:
            return await self._to_response(record)

        if is_active:
            # Activating: schedule notifications for the week
            weekly_plan = record["weekly_plan"]
            if isinstance(weekly_plan, str):
                weekly_plan = json.loads(weekly_plan)

            notifications = schedule_notifications_for_week(
                plan_id=schedule_id,
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

            logger.info(
                f"Schedule activated for user {user_id}, scheduled {len(notifications or [])} notifications"
            )
        else:
            # Pausing: cancel all pending notifications
            await self.notification_repo.delete_by_plan(schedule_id)
            logger.info(
                f"Schedule paused for user {user_id}, cancelled pending notifications"
            )

        # Update status by schedule ID
        updated_record = await self.plan_repo.update_status(schedule_id, new_status)
        if not updated_record:
            raise ResourceNotFoundException(
                message="Failed to update schedule status",
                details={"schedule_id": schedule_id},
            )

        return await self._to_response(updated_record)

    async def deactivate_schedule(self, user_id: int) -> bool:
        """Deactivate user's schedule and cancel pending notifications."""
        record = await self.plan_repo.get_current_by_user(user_id)
        if not record:
            raise ResourceNotFoundException(
                message="No schedule found",
                details={"user_id": user_id},
            )

        # Delete pending notifications
        await self.notification_repo.delete_by_plan(record["id"])

        # Deactivate plan
        return await self.plan_repo.deactivate(user_id)

    async def regenerate_plan(self, user_id: int) -> ScheduleResponse:
        """Regenerate AI plan without changing schedule config."""
        record = await self.plan_repo.get_current_by_user(user_id)
        if not record:
            raise ResourceNotFoundException(
                message="No schedule found",
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
            fixed_start_time=str(record["fixed_start_time"])
            if record["fixed_start_time"]
            else None,
            fixed_end_time=str(record["fixed_end_time"])
            if record["fixed_end_time"]
            else None,
            flexible_periods=record["flexible_periods"],
            sports=list(record["sports_predefined"])
            + list(record["sports_custom"] or []),
            health_warnings=record["health_warnings"],
        )

        record = await self.plan_repo.update_weekly_plan(record["id"], weekly_plan)

        # Reschedule notifications only if schedule is active
        if record["status"] == "active":
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

        return await self._to_response(record)

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

    async def _to_response(self, record: asyncpg.Record) -> ScheduleResponse:
        """Convert DB record to response with notification statuses."""
        weekly_plan = record["weekly_plan"]
        if isinstance(weekly_plan, str):
            weekly_plan = json.loads(weekly_plan)

        # Merge notification statuses into weekly plan
        if weekly_plan:
            weekly_plan = await self._merge_notification_statuses(
                record, weekly_plan
            )

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

    async def _merge_notification_statuses(
        self, record: asyncpg.Record, weekly_plan: Dict[str, Any]
    ) -> Dict[str, WorkoutPlan]:
        """Merge notification statuses and workout times into the weekly plan."""
        plan_id = record["id"]
        notifications = await self.notification_repo.get_by_plan_id(plan_id)

        # Build a map of workout_day -> latest notification status
        day_status_map: Dict[str, Dict[str, Any]] = {}
        for notif in notifications:
            day = notif["workout_day"]
            # Keep the latest notification for each day (they're ordered by date)
            day_status_map[day] = {
                "status": notif["status"],
                "error_message": notif["error_message"],
            }

        # Get workout times based on schedule mode
        schedule_mode = record["schedule_mode"]
        fixed_start_time = record["fixed_start_time"]
        fixed_end_time = record["fixed_end_time"]
        flexible_periods = record["flexible_periods"]
        if isinstance(flexible_periods, str):
            flexible_periods = json.loads(flexible_periods)

        # Merge statuses into weekly plan
        result = {}
        for day, plan_data in weekly_plan.items():
            status_info = day_status_map.get(day, {})
            notif_status = status_info.get("status", "pending")

            # Map notification status to WorkoutStatus
            workout_status = WorkoutStatus.PENDING
            if notif_status == "sent":
                workout_status = WorkoutStatus.SENT
            elif notif_status == "completed":
                workout_status = WorkoutStatus.COMPLETED
            elif notif_status == "skipped":
                workout_status = WorkoutStatus.SKIPPED
            elif notif_status == "failed":
                workout_status = WorkoutStatus.FAILED

            # Determine workout times based on schedule mode
            workout_start_time = None
            workout_end_time = None

            if schedule_mode == "fixed":
                # Fixed mode: same time for all days
                workout_start_time = str(fixed_start_time) if fixed_start_time else None
                workout_end_time = str(fixed_end_time) if fixed_end_time else None
            elif schedule_mode == "flexible" and flexible_periods:
                # Flexible mode: get time period for this specific day
                day_periods = flexible_periods.get(day, [])
                if day_periods and len(day_periods) > 0:
                    # Use the first time period for the day
                    first_period = day_periods[0]
                    workout_start_time = first_period.get("startTime")
                    workout_end_time = first_period.get("endTime")

            result[day] = WorkoutPlan(
                exercise=plan_data.get("exercise", ""),
                duration_minutes=plan_data.get("duration_minutes", 0),
                estimated_calories=plan_data.get("estimated_calories", 0),
                description=plan_data.get("description", ""),
                workout_start_time=workout_start_time,
                workout_end_time=workout_end_time,
                status=workout_status,
                error_message=status_info.get("error_message")
                if workout_status == WorkoutStatus.FAILED
                else None,
            )

        return result

    def _parse_time(self, time_str: Optional[str]):
        """Parse time string to time object."""
        if not time_str:
            return None
        parts = str(time_str).split(":")
        return time(
            int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
        )
