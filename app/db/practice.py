"""
Practice database operations using raw SQL queries with custom exception handling.
"""

import asyncpg
from typing import Optional, List
from datetime import datetime, time
from app.db.database import BaseRepository
from app.utils.timezone import get_vietnam_now
from app.exceptions import (
    ResourceNotFoundException,
    DatabaseException,
    DatabaseConstraintException,
    DuplicateResourceException,
)


class PracticeRepository(BaseRepository):
    """Repository for practice database operations."""

    async def create_practice(
        self,
        user_id: int,
        day_of_week: int,
        start_time: time,
        end_time: time,
        exercises: List[str],
        notes: Optional[str] = None,
    ) -> asyncpg.Record:
        """Create a new practice schedule."""
        now = get_vietnam_now()
        query = """
            INSERT INTO practice (
                user_id, day_of_week, start_time, end_time, 
                exercises, notes, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $7)
            RETURNING id, user_id, day_of_week, start_time, end_time,
                      exercises, notes, created_at, updated_at
        """
        try:
            result = await self.fetch_one(
                query,
                user_id,
                day_of_week,
                start_time,
                end_time,
                exercises,
                notes,
                now,
            )
            if not result:
                raise DatabaseException(
                    "Failed to create practice schedule",
                    details={"user_id": user_id, "day_of_week": day_of_week},
                )
            return result
        except asyncpg.ForeignKeyViolationError as e:
            raise ResourceNotFoundException(
                message="User not found",
                details={"user_id": user_id, "constraint": str(e)},
            )
        except asyncpg.CheckViolationError as e:
            raise DatabaseConstraintException(
                message="Invalid day_of_week value (must be 1-7)",
                details={"day_of_week": day_of_week, "constraint": str(e)},
            )
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while creating practice schedule",
                details={"user_id": user_id, "error": str(e)},
            )

    async def get_practice_by_id(self, practice_id: int) -> asyncpg.Record:
        """Get practice schedule by ID."""
        query = """
            SELECT id, user_id, day_of_week, start_time, end_time,
                   exercises, notes, created_at, updated_at
            FROM practice
            WHERE id = $1 AND deleted_at IS NULL
        """
        try:
            result = await self.fetch_one(query, practice_id)
            if not result:
                raise ResourceNotFoundException(
                    message="Practice schedule not found",
                    details={"practice_id": practice_id},
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching practice by ID",
                details={"practice_id": practice_id, "error": str(e)},
            )

    async def get_practices_by_user(
        self, user_id: int, limit: int = 100, offset: int = 0
    ) -> List[asyncpg.Record]:
        """Get all practice schedules for a user."""
        query = """
            SELECT id, user_id, day_of_week, start_time, end_time,
                   exercises, notes, created_at, updated_at
            FROM practice
            WHERE user_id = $1 AND deleted_at IS NULL
            ORDER BY day_of_week, start_time
            LIMIT $2 OFFSET $3
        """
        try:
            return await self.fetch_many(query, user_id, limit, offset)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching user practices",
                details={"user_id": user_id, "error": str(e)},
            )

    async def get_practices_by_user_and_day(
        self, user_id: int, day_of_week: int
    ) -> List[asyncpg.Record]:
        """Get practice schedules for a specific day of week."""
        query = """
            SELECT id, user_id, day_of_week, start_time, end_time,
                   exercises, notes, created_at, updated_at
            FROM practice
            WHERE user_id = $1 AND day_of_week = $2 AND deleted_at IS NULL
            ORDER BY start_time
        """
        try:
            return await self.fetch_many(query, user_id, day_of_week)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching practices by day",
                details={
                    "user_id": user_id,
                    "day_of_week": day_of_week,
                    "error": str(e),
                },
            )

    async def update_practice(
        self,
        practice_id: int,
        day_of_week: Optional[int] = None,
        start_time: Optional[time] = None,
        end_time: Optional[time] = None,
        exercises: Optional[List[str]] = None,
        notes: Optional[str] = None,
    ) -> asyncpg.Record:
        """Update practice schedule information."""
        now = get_vietnam_now()
        query = """
            UPDATE practice
            SET day_of_week = COALESCE($2, day_of_week),
                start_time = COALESCE($3, start_time),
                end_time = COALESCE($4, end_time),
                exercises = COALESCE($5, exercises),
                notes = COALESCE($6, notes),
                updated_at = $7
            WHERE id = $1 AND deleted_at IS NULL
            RETURNING id, user_id, day_of_week, start_time, end_time,
                      exercises, notes, created_at, updated_at
        """
        try:
            result = await self.fetch_one(
                query,
                practice_id,
                day_of_week,
                start_time,
                end_time,
                exercises,
                notes,
                now,
            )
            if not result:
                raise ResourceNotFoundException(
                    message="Practice schedule not found or update failed",
                    details={"practice_id": practice_id},
                )
            return result
        except asyncpg.CheckViolationError as e:
            raise DatabaseConstraintException(
                message="Invalid day_of_week value (must be 1-7)",
                details={"day_of_week": day_of_week, "constraint": str(e)},
            )
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while updating practice schedule",
                details={"practice_id": practice_id, "error": str(e)},
            )

    async def delete_practice(self, practice_id: int) -> asyncpg.Record:
        """Soft delete practice schedule."""
        now = get_vietnam_now()
        query = """
            UPDATE practice
            SET deleted_at = $2, updated_at = $2
            WHERE id = $1 AND deleted_at IS NULL
            RETURNING id
        """
        try:
            result = await self.fetch_one(query, practice_id, now)
            if not result:
                raise ResourceNotFoundException(
                    message="Practice schedule not found for deletion",
                    details={"practice_id": practice_id},
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while deleting practice schedule",
                details={"practice_id": practice_id, "error": str(e)},
            )

    async def delete_practices_by_user(self, user_id: int) -> int:
        """Soft delete all practice schedules for a user."""
        now = get_vietnam_now()
        query = """
            UPDATE practice
            SET deleted_at = $2, updated_at = $2
            WHERE user_id = $1 AND deleted_at IS NULL
        """
        try:
            result = await self.execute(query, user_id, now)
            # Extract number from result string like "UPDATE 5"
            try:
                return int(result.split()[-1]) if result.split()[-1].isdigit() else 0
            except (IndexError, ValueError):
                return 0
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while deleting user practices",
                details={"user_id": user_id, "error": str(e)},
            )

    async def count_practices_by_user(self, user_id: int) -> int:
        """Count total practice schedules for a user."""
        query = """
            SELECT COUNT(*) FROM practice 
            WHERE user_id = $1 AND deleted_at IS NULL
        """
        try:
            result = await self.fetch_one(query, user_id)
            return result["count"] if result else 0
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while counting user practices",
                details={"user_id": user_id, "error": str(e)},
            )

    async def get_all_practices(
        self, limit: int = 100, offset: int = 0
    ) -> List[asyncpg.Record]:
        """Get all practice schedules with pagination."""
        query = """
            SELECT id, user_id, day_of_week, start_time, end_time,
                   exercises, notes, created_at, updated_at
            FROM practice
            WHERE deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """
        try:
            return await self.fetch_many(query, limit, offset)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching all practices",
                details={"limit": limit, "offset": offset, "error": str(e)},
            )
