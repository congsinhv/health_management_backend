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
