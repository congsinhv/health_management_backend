"""
Exercise Log repository for database operations.
"""

from typing import Optional, List, Dict, Any
import asyncpg
from datetime import date

from app.config import logger
from app.db.database import BaseRepository
from app.exceptions import DatabaseException


class ExerciseLogRepository(BaseRepository):
    """Repository for user exercise log operations."""

    async def create(self, data: Dict[str, Any]) -> asyncpg.Record:
        """Create new exercise log."""
        query = """
            INSERT INTO user_exercise_logs (
                user_id, scheduled_notification_id,
                exercise_minutes, calories, date
            ) VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """
        try:
            return await self.fetch_one(
                query,
                data.get("user_id"),
                data.get("scheduled_notification_id"),
                data.get("exercise_minutes"),
                data.get("calories"),
                data.get("date"),
            )
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error creating exercise log",
                details={"user_id": data.get("user_id"), "error": str(e)},
            )

    async def get_by_user_and_date(
        self, user_id: int, log_date: date
    ) -> List[asyncpg.Record]:
        """Get exercise logs for a user on a specific date."""
        query = """
            SELECT * FROM user_exercise_logs
            WHERE user_id = $1 AND date = $2
            ORDER BY created_at DESC
        """
        try:
            return await self.fetch_many(query, user_id, log_date)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error fetching exercise logs",
                details={"user_id": user_id, "date": str(log_date), "error": str(e)},
            )
