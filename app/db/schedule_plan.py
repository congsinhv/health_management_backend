"""
Schedule Plan repository for database operations.
"""

import json
from typing import Optional, List, Dict, Any
import asyncpg

from app.config import logger
from app.db.database import BaseRepository
from app.exceptions import (
    ResourceNotFoundException,
    DatabaseException,
    DuplicateResourceException,
)


class SchedulePlanRepository(BaseRepository):
    """Repository for schedule plan database operations."""

    async def create(self, data: Dict[str, Any]) -> asyncpg.Record:
        """Create new schedule plan."""
        query = """
            INSERT INTO schedule_plans (
                user_id, height_m, weight_kg, target_weight_kg, goal,
                schedule_mode, selected_days, timezone,
                fixed_start_time, fixed_end_time, flexible_periods,
                sports_predefined, sports_custom,
                personal_notes, health_warnings, status
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8,
                $9, $10, $11,
                $12, $13,
                $14, $15, 'active'
            )
            RETURNING *
        """
        try:
            result = await self.fetch_one(
                query,
                data.get("user_id"),
                data.get("height_m"),
                data.get("weight_kg"),
                data.get("target_weight_kg"),
                data.get("goal"),
                data.get("schedule_mode", "fixed"),
                data.get("selected_days"),
                data.get("timezone", "Asia/Ho_Chi_Minh"),
                data.get("fixed_start_time"),
                data.get("fixed_end_time"),
                json.dumps(data.get("flexible_periods"))
                if data.get("flexible_periods")
                else None,
                data.get("sports_predefined"),
                data.get("sports_custom"),
                data.get("personal_notes"),
                data.get("health_warnings"),
            )
            if not result:
                raise DatabaseException(
                    message="Failed to create schedule plan",
                    details={"user_id": data.get("user_id")},
                )
            return result
        except asyncpg.UniqueViolationError:
            raise DuplicateResourceException(
                message="User already has an active schedule plan",
                details={"user_id": data.get("user_id")},
            )
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error creating schedule plan",
                details={"error": str(e)},
            )

    async def get_active_by_user(self, user_id: int) -> Optional[asyncpg.Record]:
        """Get active schedule plan for user."""
        query = """
            SELECT * FROM schedule_plans
            WHERE user_id = $1 AND status = 'active' AND deleted_at IS NULL
        """
        try:
            return await self.fetch_one(query, user_id)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error fetching schedule plan",
                details={"user_id": user_id, "error": str(e)},
            )

    async def get_by_id(self, plan_id: int) -> Optional[asyncpg.Record]:
        """Get schedule plan by ID."""
        query = """
            SELECT * FROM schedule_plans
            WHERE id = $1
        """
        try:
            return await self.fetch_one(query, plan_id)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error fetching schedule plan",
                details={"plan_id": plan_id, "error": str(e)},
            )

    async def update_weekly_plan(
        self, plan_id: int, weekly_plan: Dict[str, Any]
    ) -> asyncpg.Record:
        """Update AI-generated weekly plan."""
        query = """
            UPDATE schedule_plans
            SET weekly_plan = $1, updated_at = NOW()
            WHERE id = $2 AND deleted_at IS NULL
            RETURNING *
        """
        try:
            result = await self.fetch_one(query, json.dumps(weekly_plan), plan_id)
            if not result:
                raise ResourceNotFoundException(
                    message="Schedule plan not found",
                    details={"plan_id": plan_id},
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error updating weekly plan",
                details={"plan_id": plan_id, "error": str(e)},
            )

    async def deactivate(self, user_id: int) -> bool:
        """Deactivate current plan - active or paused (soft delete + status change)."""
        query = """
            UPDATE schedule_plans
            SET status = 'superseded', deleted_at = NOW(), updated_at = NOW()
            WHERE user_id = $1 AND status IN ('active', 'paused') AND deleted_at IS NULL
        """
        try:
            result = await self.execute(query, user_id)
            return "UPDATE" in result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error deactivating schedule plan",
                details={"user_id": user_id, "error": str(e)},
            )

    async def deactivate_and_create(self, data: Dict[str, Any]) -> asyncpg.Record:
        """Atomically deactivate existing plan and create new one in a transaction."""
        user_id = data.get("user_id")
        deactivate_query = """
            UPDATE schedule_plans
            SET status = 'superseded', deleted_at = NOW(), updated_at = NOW()
            WHERE user_id = $1 AND status IN ('active', 'paused') AND deleted_at IS NULL
        """
        create_query = """
            INSERT INTO schedule_plans (
                user_id, height_m, weight_kg, target_weight_kg, goal,
                schedule_mode, selected_days, timezone,
                fixed_start_time, fixed_end_time, flexible_periods,
                sports_predefined, sports_custom,
                personal_notes, health_warnings, status
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8,
                $9, $10, $11,
                $12, $13,
                $14, $15, 'active'
            )
            RETURNING *
        """
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    # First deactivate any existing active/paused plans
                    await connection.execute(deactivate_query, user_id)
                    # Then create the new plan
                    result = await connection.fetchrow(
                        create_query,
                        user_id,
                        data.get("height_m"),
                        data.get("weight_kg"),
                        data.get("target_weight_kg"),
                        data.get("goal"),
                        data.get("schedule_mode", "fixed"),
                        data.get("selected_days"),
                        data.get("timezone", "Asia/Ho_Chi_Minh"),
                        data.get("fixed_start_time"),
                        data.get("fixed_end_time"),
                        json.dumps(data.get("flexible_periods"))
                        if data.get("flexible_periods")
                        else None,
                        data.get("sports_predefined"),
                        data.get("sports_custom"),
                        data.get("personal_notes"),
                        data.get("health_warnings"),
                    )
            if not result:
                raise DatabaseException(
                    message="Failed to create schedule plan",
                    details={"user_id": user_id},
                )
            return result
        except asyncpg.UniqueViolationError:
            raise DuplicateResourceException(
                message="User already has an active schedule plan",
                details={"user_id": user_id},
            )
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error creating schedule plan",
                details={"error": str(e)},
            )

    async def list_active_plans(
        self, limit: int = 100, offset: int = 0
    ) -> List[asyncpg.Record]:
        """List all active schedule plans (for batch processing)."""
        query = """
            SELECT * FROM schedule_plans
            WHERE status = 'active' AND deleted_at IS NULL
            ORDER BY id
            LIMIT $1 OFFSET $2
        """
        try:
            return await self.fetch_many(query, limit, offset)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error listing active plans",
                details={"error": str(e)},
            )

    async def update_status(
        self, schedule_id: int, new_status: str
    ) -> Optional[asyncpg.Record]:
        """Update schedule status by ID.

        Args:
            schedule_id: Schedule plan ID
            new_status: New status ('active' or 'paused')

        Returns:
            Updated record or None if no schedule found
        """
        query = """
            UPDATE schedule_plans
            SET status = $1, updated_at = NOW()
            WHERE id = $2 AND deleted_at IS NULL AND status IN ('active', 'paused')
            RETURNING *
        """
        try:
            return await self.fetch_one(query, new_status, schedule_id)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error updating schedule status",
                details={
                    "schedule_id": schedule_id,
                    "new_status": new_status,
                    "error": str(e),
                },
            )

    async def get_current_by_user(self, user_id: int) -> Optional[asyncpg.Record]:
        """Get current schedule plan for user (active or paused)."""
        query = """
            SELECT * FROM schedule_plans
            WHERE user_id = $1 AND status IN ('active', 'paused') AND deleted_at IS NULL
        """
        try:
            return await self.fetch_one(query, user_id)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error fetching schedule plan",
                details={"user_id": user_id, "error": str(e)},
            )

    async def get_by_user(self, user_id: int) -> Optional[asyncpg.Record]:
        """List all schedule plans for a user (excluding soft-deleted)."""
        query = """
            SELECT * FROM schedule_plans
            WHERE user_id = $1 AND deleted_at IS NULL
            AND status IN ('active')
        """
        try:
            return await self.fetch_one(query, user_id)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error listing schedule plans",
                details={"user_id": user_id, "error": str(e)},
            )
