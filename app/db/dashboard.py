import asyncpg
from typing import Optional, List, Dict, Any
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
    async def get_daily_activity(self, user_id: int) -> List[asyncpg.Record]:
        query = """
        SELECT 
            DATE(date) AS date,
            COALESCE(SUM(exercise_minutes), 0) AS exercise_minutes,
            COALESCE(SUM(calories), 0) AS calories
        FROM user_exercise_logs
        WHERE user_id = $1
        GROUP BY DATE(date)
        ORDER BY date DESC
        LIMIT 11;
        """
        try:
            return await self.fetch_many(query, user_id)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching daily activity",
                details={"user_id": user_id, "error": str(e)},
            )

    # Biểu đồ hoạt động hằng tuần
    async def get_weekly_activity(self, user_id: int) -> List[asyncpg.Record]:
        query = """
        SELECT 
            TO_CHAR(date, 'Day') AS day_name,
            EXTRACT(DOW FROM date) AS day_of_week,
            COALESCE(SUM(exercise_minutes), 0) AS total_minutes
        FROM user_exercise_logs
        WHERE user_id = $1
            AND date >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY TO_CHAR(date, 'Day'), EXTRACT(DOW FROM date)
        ORDER BY EXTRACT(DOW FROM date);
        """
        
        # Alternative query if you want Vietnamese day names:
        query_vn = """
        SELECT 
            CASE EXTRACT(DOW FROM date)
                WHEN 1 THEN 'Thứ Hai'
                WHEN 2 THEN 'Thứ Ba'
                WHEN 3 THEN 'Thứ Tư'
                WHEN 4 THEN 'Thứ Năm'
                WHEN 5 THEN 'Thứ Sáu'
                WHEN 6 THEN 'Thứ Bảy'
                WHEN 0 THEN 'Chủ Nhật'
            END AS day,
            COALESCE(SUM(exercise_minutes), 0) AS total_minutes
        FROM user_exercise_logs
        WHERE user_id = $1
            AND date >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY EXTRACT(DOW FROM date)
        ORDER BY EXTRACT(DOW FROM date);
        """
        try:
            return await self.fetch_many(query_vn, user_id)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching weekly activity",
                details={"user_id": user_id, "error": str(e)},
            )

    # Biểu đồ hoạt động hằng tháng
    async def get_monthly_activity(self, user_id: int) -> List[asyncpg.Record]:
        query = """
        SELECT 
            TO_CHAR(date, 'YYYY-MM') AS month_year,
            EXTRACT(MONTH FROM date) AS month_number,
            COALESCE(AVG(exercise_minutes), 0) AS avg_exercise,
            COALESCE(SUM(exercise_minutes), 0) AS total_exercise
        FROM user_exercise_logs
        WHERE user_id = $1
            AND date >= CURRENT_DATE - INTERVAL '12 months'
        GROUP BY TO_CHAR(date, 'YYYY-MM'), EXTRACT(MONTH FROM date)
        ORDER BY TO_CHAR(date, 'YYYY-MM');
        """
        
        # Alternative query if you want Vietnamese month names:
        query_vn = """
        SELECT 
            CASE EXTRACT(MONTH FROM date)
                WHEN 1 THEN 'Tháng 1'
                WHEN 2 THEN 'Tháng 2'
                WHEN 3 THEN 'Tháng 3'
                WHEN 4 THEN 'Tháng 4'
                WHEN 5 THEN 'Tháng 5'
                WHEN 6 THEN 'Tháng 6'
                WHEN 7 THEN 'Tháng 7'
                WHEN 8 THEN 'Tháng 8'
                WHEN 9 THEN 'Tháng 9'
                WHEN 10 THEN 'Tháng 10'
                WHEN 11 THEN 'Tháng 11'
                WHEN 12 THEN 'Tháng 12'
            END AS month,
            COALESCE(AVG(exercise_minutes), 0) AS avg_exercise,
            COALESCE(SUM(exercise_minutes), 0) AS total_exercise
        FROM user_exercise_logs
        WHERE user_id = $1
            AND date >= CURRENT_DATE - INTERVAL '12 months'
        GROUP BY EXTRACT(MONTH FROM date)
        ORDER BY EXTRACT(MONTH FROM date);
        """
        try:
            return await self.fetch_many(query_vn, user_id)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching monthly activity",
                details={"user_id": user_id, "error": str(e)},
            )