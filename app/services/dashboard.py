from app.db.dashboard import DashboardRepository
from app.schemas.user_profile import UserProfileResponse
from app.exceptions import (
    ResourceNotFoundException,
    DatabaseException,
)
from app.core.error_context import ErrorContext


class DashboardService:
    def __init__(self, repository: DashboardRepository):
        self.repository = repository

    async def get_user_profile(self, user_id: int) -> UserProfileResponse:
        try:
            record = await self.repository.get_profile_by_user_id(user_id)

            # Nếu record là asyncpg.Record → convert sang dict
            record_dict = dict(record)

            return UserProfileResponse(**record_dict)

        except ResourceNotFoundException:
            # Ném lại để FastAPI handler convert thành response JSON
            raise

        except DatabaseException:
            raise

        except Exception as e:
            raise DatabaseException(
                message="Unexpected error in DashboardService.get_user_profile",
                details={"error": str(e)},
            )
        
    # Bieu do hoat dong hang ngay
    async def get_daily_activity(self, user_id: int):
        try:
            records = await self.repository.get_daily_activity(user_id)
            result = []
            for record in records:
                result.append({
                    "date": record["date"],
                    "exercise_minutes": record["exercise_minutes"],
                    "calories": record["calories"]
                })
            return result
        except DatabaseException:
            raise
        except Exception as e:
            raise DatabaseException(
                message="Unexpected error in DashboardService.get_daily_activity",
                details={"error": str(e)},
            )
    # Bieu do hoat dong hang tuan
    async def get_weekly_activity(self, user_id: int):
        try:
            records = await self.repository.get_weekly_activity(user_id)
            result = []
            for record in records:
                result.append({
                    "day": record["day"],
                    "total_minutes": record["total_minutes"],
                })
            return result
        except DatabaseException:
            raise
        except Exception as e:
            raise DatabaseException(
                message="Unexpected error in DashboardService.get_weekly_activity",
                details={"error": str(e)},
            )
        
    # Bieu do hoat dong hang thang
    async def get_monthly_activity(self, user_id: int):
        try:
            records = await self.repository.get_monthly_activity(user_id)
            result = []
            for record in records:
                result.append({
                    "month": record["month"],
                    "avg_exercise": record["avg_exercise"],
                })
            return result
        except DatabaseException:
            raise
        except Exception as e:
            raise DatabaseException(
                message="Unexpected error in DashboardService.get_monthly_activity",
                details={"error": str(e)},
            )