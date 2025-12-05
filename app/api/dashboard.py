from app.db.database import get_database_pool
from fastapi import APIRouter, Depends, status, Query, HTTPException
from app.services.dashboard import DashboardService
from app.db.dashboard import DashboardRepository
from app.schemas.user_profile import UserProfileResponse
from app.exceptions import ResourceNotFoundException, DatabaseException
from typing import Dict, Any, List
import logging
from app.schemas.dashboard import (
    HealthOverviewResponse,
    
)

logger = logging.getLogger(__name__)
router = APIRouter()

def get_dashboard_service(pool = Depends(get_database_pool)):
    repo = DashboardRepository(pool)
    return DashboardService(repo)

@router.get(
    "/profile/{user_id}",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
)
async def get_dashboard_profile(
    user_id: int,
    service: DashboardService = Depends(get_dashboard_service),
):
    """
    Get user profile for dashboard
    """
    try:
        return await service.get_user_profile(user_id)
    except ResourceNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e.message) if hasattr(e, 'message') else "User profile not found"
        )
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Biểu đồ hoạt động hằng ngày
@router.get(
    "/daily-activity/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=List[Dict[str, Any]],
)
async def get_daily_activity(
    user_id: int,
    service: DashboardService = Depends(get_dashboard_service),
):
    """
    Get daily activity data for charts
    """
    try:
        return await service.get_daily_activity(user_id)
    except Exception as e:
        logger.error(f"Error getting daily activity: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Biểu đồ hoạt động hằng tuần
@router.get(
    "/weekly-activity/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=List[Dict[str, Any]],
)
async def get_weekly_activity(
    user_id: int,
    service: DashboardService = Depends(get_dashboard_service),
):
    """
    Get weekly activity data for charts
    """
    try:
        return await service.get_weekly_activity(user_id)
    except Exception as e:
        logger.error(f"Error getting weekly activity: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Biểu đồ hoạt động hằng tháng
@router.get(
    "/monthly-activity/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=List[Dict[str, Any]],
)
async def get_monthly_activity(
    user_id: int,
    service: DashboardService = Depends(get_dashboard_service),
):
    """
    Get monthly activity data for charts
    """
    try:
        return await service.get_monthly_activity(user_id)
    except Exception as e:
        logger.error(f"Error getting monthly activity: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

# Health summary với AI
@router.get(
    "/health-summary/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=Dict[str, str],
)
async def generate_personal_health_summary(
    user_id: int,
    service: DashboardService = Depends(get_dashboard_service),
):
    """
    Generate personalized health summary using AI
    """
    try:
        # First, get the user profile
        profile = await service.get_user_profile(user_id)
        
        # Then generate the health summary
        summary = await service.generate_personal_health_summary(profile)
        
        return {"summary": summary}
        
    except ResourceNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e.message) if hasattr(e, 'message') else "User profile not found"
        )
    except DatabaseException as e:
        logger.error(f"Database error generating health summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating health summary"
        )
    except Exception as e:
        logger.error(f"Error generating health summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
    
    
# Endpoint tổng quan
@router.get(
    "/overview/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=HealthOverviewResponse,
    summary="Tổng quan sức khỏe",
    description="Lấy thông tin tổng quan về sức khỏe người dùng"
)
async def get_health_overview(
    user_id: int,
    service: DashboardService = Depends(get_dashboard_service),
):
    """
    Get comprehensive health overview for dashboard
    """
    try:
        overview = await service.get_health_overview(user_id)
        return overview
        
    except ResourceNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e.message) if hasattr(e, 'message') else "User profile not found"
        )
    except DatabaseException as e:
        logger.error(f"Database error getting health overview: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error getting health overview"
        )
    except Exception as e:
        logger.error(f"Error getting health overview: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )