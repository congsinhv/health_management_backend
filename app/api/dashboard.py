from app.db.database import get_database_pool
from fastapi import APIRouter, Depends, status, Query
from app.services.dashboard import DashboardService
from app.db.dashboard import DashboardRepository
from app.schemas.user_profile import UserProfileResponse
router = APIRouter()

def get_dashboard_service(pool = Depends(get_database_pool)):
    repo = DashboardRepository(pool)
    return DashboardService(repo)

@router.get(
    "/profile/{user_id}",
    response_model=UserProfileResponse
)
async def get_dashboard_profile(
    user_id: int,
    service: DashboardService = Depends(get_dashboard_service),
):
    return await service.get_user_profile(user_id)
# Bieu do hoat dong hang ngay
@router.get(
    "/daily-activity/{user_id}",
    status_code=status.HTTP_200_OK,
)
async def get_daily_activity(
    user_id: int,
    service: DashboardService = Depends(get_dashboard_service),
):
    return await service.get_daily_activity(user_id)

# Bieu do hoat dong hang tuan
@router.get(
    "/weekly-activity/{user_id}",
    status_code=status.HTTP_200_OK,
)
async def get_weekly_activity(
    user_id: int,
    service: DashboardService = Depends(get_dashboard_service),
):
    return await service.get_weekly_activity(user_id)

@router.get(
    "/monthly-activity/{user_id}",
    status_code=status.HTTP_200_OK,
)
async def get_monthly_activity(
    user_id: int,
    service: DashboardService = Depends(get_dashboard_service),
):
    return await service.get_monthly_activity(user_id)