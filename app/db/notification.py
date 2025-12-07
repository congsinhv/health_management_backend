"""
Notification repository for database operations.
"""

import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import asyncpg

from app.config import logger
from app.db.database import BaseRepository
from app.exceptions import (
    ResourceNotFoundException,
    DatabaseException,
)


class NotificationRepository(BaseRepository):
    """Repository for scheduled notification database operations."""

    async def create(self, data: Dict[str, Any]) -> asyncpg.Record:
        """Create scheduled notification."""
        query = """
            INSERT INTO scheduled_notifications (
                schedule_plan_id, user_id, scheduled_at,
                workout_date, workout_day, workout_start_time, workout_end_time,
                title, body, data, status
            ) VALUES (
                $1, $2, $3,
                $4, $5, $6, $7,
                $8, $9, $10, 'pending'
            )
            RETURNING *
        """
        try:
            return await self.fetch_one(
                query,
                data.get("schedule_plan_id"),
                data.get("user_id"),
                data.get("scheduled_at"),
                data.get("workout_date"),
                data.get("workout_day"),
                data.get("workout_start_time"),
                data.get("workout_end_time"),
                data.get("title"),
                data.get("body"),
                json.dumps(data.get("data")) if data.get("data") else None,
            )
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error creating notification",
                details={"error": str(e)},
            )

    async def create_batch(self, notifications: List[Dict[str, Any]]) -> int:
        """Create multiple notifications in batch."""
        if not notifications:
            return 0

        values = []
        params = []
        param_idx = 1
        for n in notifications:
            values.append(f"(${param_idx}, ${param_idx+1}, ${param_idx+2}, "
                         f"${param_idx+3}, ${param_idx+4}, ${param_idx+5}, ${param_idx+6}, "
                         f"${param_idx+7}, ${param_idx+8}, ${param_idx+9}, 'pending')")
            params.extend([
                n.get("schedule_plan_id"),
                n.get("user_id"),
                n.get("scheduled_at"),
                n.get("workout_date"),
                n.get("workout_day"),
                n.get("workout_start_time"),
                n.get("workout_end_time"),
                n.get("title"),
                n.get("body"),
                json.dumps(n.get("data")) if n.get("data") else None,
            ])
            param_idx += 10

        query = f"""
            INSERT INTO scheduled_notifications (
                schedule_plan_id, user_id, scheduled_at,
                workout_date, workout_day, workout_start_time, workout_end_time,
                title, body, data, status
            ) VALUES {', '.join(values)}
        """
        try:
            result = await self.execute(query, *params)
            return int(result.split()[-1]) if result else 0
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error creating batch notifications",
                details={"count": len(notifications), "error": str(e)},
            )

    async def get_pending_in_window(
        self, window_start: datetime, window_end: datetime
    ) -> List[asyncpg.Record]:
        """Get pending notifications within time window."""
        query = """
            SELECT n.*, sp.timezone
            FROM scheduled_notifications n
            JOIN schedule_plans sp ON sp.id = n.schedule_plan_id
            WHERE n.status = 'pending'
              AND n.scheduled_at >= $1
              AND n.scheduled_at <= $2
            ORDER BY n.scheduled_at
        """
        try:
            return await self.fetch_many(query, window_start, window_end)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error fetching pending notifications",
                details={"error": str(e)},
            )

    async def update_status(
        self,
        notification_id: int,
        status: str,
        cloud_task_name: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> asyncpg.Record:
        """Update notification status."""
        query = """
            UPDATE scheduled_notifications
            SET status = $1,
            cloud_task_name = COALESCE($2, cloud_task_name),
            error_message = $3,
            sent_at = CASE WHEN $1 = 'sent' THEN NOW() ELSE sent_at END,
            retry_count = CASE WHEN $1 = 'failed' THEN retry_count + 1 ELSE retry_count END,
            updated_at = NOW()
            WHERE id = $4
            RETURNING *
        """
        try:
            result = await self.fetch_one(query, status, cloud_task_name, error_message, notification_id)
            if not result:
                raise ResourceNotFoundException(
                    message="Notification not found",
                    details={"notification_id": notification_id},
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error updating notification",
                details={"notification_id": notification_id, "error": str(e)},
            )

    async def get_by_id(self, notification_id: int) -> Optional[asyncpg.Record]:
        """Get notification by ID."""
        query = "SELECT * FROM scheduled_notifications WHERE id = $1"
        try:
            return await self.fetch_one(query, notification_id)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error fetching notification",
                details={"notification_id": notification_id, "error": str(e)},
            )

    async def delete_by_plan(self, schedule_plan_id: int) -> int:
        """Delete all notifications for a plan."""
        query = """
            DELETE FROM scheduled_notifications
            WHERE schedule_plan_id = $1 AND status = 'pending'
        """
        try:
            result = await self.execute(query, schedule_plan_id)
            return int(result.split()[-1]) if result else 0
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error deleting notifications",
                details={"schedule_plan_id": schedule_plan_id, "error": str(e)},
            )

    async def get_upcoming_by_user(
        self, user_id: int, limit: int = 10
    ) -> List[asyncpg.Record]:
        """Get upcoming notifications for user."""
        query = """
            SELECT * FROM scheduled_notifications
            WHERE user_id = $1 AND status = 'pending' AND scheduled_at > NOW()
            ORDER BY scheduled_at
            LIMIT $2
        """
        try:
            return await self.fetch_many(query, user_id, limit)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error fetching upcoming notifications",
                details={"user_id": user_id, "error": str(e)},
            )
