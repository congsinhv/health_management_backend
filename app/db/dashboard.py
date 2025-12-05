import asyncpg
from typing import Optional
from datetime import datetime
from decimal import Decimal
from app.db.database import BaseRepository
from app.schemas.user_profile import UserProfileCreate, UserProfileUpdate
from app.exceptions import (
    ResourceNotFoundException,
    DatabaseException,
    DatabaseConstraintException,
    DuplicateResourceException,
)

class DashboardRepository(BaseRepository):
    """Repository for dashboard-related database operations."""

    async def get_profile_by_user_id(self, user_id: int) -> asyncpg.Record:
        """Get user profile by user ID."""
        query = """
        SELECT id, user_id, first_name, last_name, avatar_url, gender,
            height_cm, weight_kg, date_of_birth, family_medical_history,
            goal, created_at, updated_at, heart_rate, exercise_minutes,
            age, sleep_hours, water_intake
        FROM user_profiles
        WHERE user_id = $1;
        """
        try:
            result = await self.fetch_one(query, user_id)
            if not result:
                raise ResourceNotFoundException(
                    message="User profile not found", details={"user_id": user_id}
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching user profile",
                details={"user_id": user_id, "error": str(e)},
            )