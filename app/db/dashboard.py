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

    # Lấy thông tin người dùng theo user_id
    async def get_profile_by_user_id(self, user_id: int) -> asyncpg.Record:
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
                    message="User profile not found",
                    details={"user_id": user_id},
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching user profile",
                details={"user_id": user_id, "error": str(e)},
            )

    # Biểu đồ hoạt động hằng ngày
    async def get_daily_activity(self, user_id: int):
        query = """
        SELECT 
            TO_CHAR(date, 'DD') AS date,
            exercise_minutes,
            calories
        FROM user_exercise_logs
        WHERE user_id = $1
        ORDER BY date DESC
        LIMIT 11;
        """
        return await self.fetch_many(query, user_id)

    # Biểu đồ hoạt động hằng tuần
    async def get_weekly_activity(self, user_id: int):
        query = """
            SELECT 
                CASE EXTRACT(DOW FROM date)
                    WHEN 1 THEN 'T2'
                    WHEN 2 THEN 'T3'
                    WHEN 3 THEN 'T4'
                    WHEN 4 THEN 'T5'
                    WHEN 5 THEN 'T6'
                    WHEN 6 THEN 'T7'
                    ELSE 'CN'
                END AS day,
                SUM(exercise_minutes) AS total_minutes
            FROM user_exercise_logs
            WHERE user_id = $1
            GROUP BY EXTRACT(DOW FROM date)
            ORDER BY EXTRACT(DOW FROM date);
        """
        return await self.fetch_many(query, user_id)
    # Bieu do hoat dong hang thang
    async def get_monthly_activity(self, user_id: int):
        query = """
            SELECT 
                'Th' || EXTRACT(MONTH FROM date)::TEXT AS month,
                AVG(exercise_minutes) AS avg_exercise
            FROM user_exercise_logs
            WHERE user_id = $1
            GROUP BY EXTRACT(MONTH FROM date)
            ORDER BY EXTRACT(MONTH FROM date);
        """
        return await self.fetch_many(query, user_id)
