from fastapi import APIRouter, Depends, status, HTTPException
from typing import Annotated, List, Optional
import asyncpg
import logging
from pydantic import BaseModel
from app.schemas.predict import UserInput, PredictionResponse, PdfResponse
from app.schemas.schedule import RegeneratePlanRequest_predict
from app.schemas.user import UserInDB
from app.services.predict_service import ObesityPredictorComplete
from app.services.pdf_service import PdfGeneratorService, PdfGenerationError
from app.db.database import get_database_pool
from app.core.error_context import ErrorContext
from app.exceptions import (
    ServiceUnavailableException,
    ValidationException,
    ResourceNotFoundException,
    FileNotFoundException,
    StorageException,
    PredictionException,
)
from app.db.prediction import PredictionRepository
from app.auth.dependencies import get_current_active_user

logger = logging.getLogger(__name__)
router = APIRouter()


# Request schemas
class RegeneratePlanRequest(BaseModel):
    """Request body for regenerating weekly plan from prediction."""

    prediction_id: str
    user_id: int
    goal: str  # "lose", "gain", "maintain"
    selected_days: List[str]  # ["monday", "tuesday", ...]
    workout_start_time: str = "08:00:00"
    timezone: str = "Asia/Ho_Chi_Minh"
    schedule_mode: str = "fixed"


# Dependency functions
def create_predict_service(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ObesityPredictorComplete:
    """Dependency to get prediction service with database connection."""
    try:
        return ObesityPredictorComplete(pool=db_pool)
    except Exception as e:
        logger.warning(f"Failed to initialize prediction service with database: {e}")
        try:
            return ObesityPredictorComplete(pool=None)
        except Exception as fallback_error:
            logger.error(f"Failed to initialize prediction service: {fallback_error}")
            raise ServiceUnavailableException(
                "Prediction service unavailable - models not loaded"
            )


def create_pdf_service(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> PdfGeneratorService:
    """Dependency to get PDF generator service."""
    return PdfGeneratorService(db_pool)


# Endpoints
@router.post("/", response_model=PredictionResponse, status_code=status.HTTP_200_OK)
async def predict_obesity(
    data: UserInput,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    predict_service: ObesityPredictorComplete = Depends(create_predict_service),
):
    """
    Generate obesity prediction (PUBLIC endpoint - no authentication required).

    **Request Body**:
    - User demographic and lifestyle data

    **Response**:
    - Comprehensive prediction with health analysis, diet plan, workout plan
    - Includes prediction_id for PDF generation
    """
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "predict_obesity")
    ErrorContext.add_context("operation", "obesity_prediction")

    with ErrorContext(
        "predict_obesity",
        {
            "has_data": bool(data),
            "age": data.age if hasattr(data, "age") else None,
            "gender": data.gender if hasattr(data, "gender") else None,
        },
    ):
        if predict_service is None:
            raise ServiceUnavailableException(
                "Prediction service unavailable - models not loaded"
            )

        prediction = await predict_service.predict_obesity_ai(
            data=data, save_to_db=True, user_id=current_user.id
        )

        ErrorContext.add_context("prediction_id", prediction.id)
        return prediction


@router.get(
    "/{prediction_id}",
    response_model=PredictionResponse,
    status_code=status.HTTP_200_OK,
)
async def get_prediction_by_prediction_id(
    prediction_id: str,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    predict_service: ObesityPredictorComplete = Depends(create_predict_service),
):
    """Get prediction by prediction_id."""
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "get_prediction_by_prediction_id")
    ErrorContext.add_context("operation", "prediction_retrieval")
    ErrorContext.add_context("prediction_id", prediction_id)
    ErrorContext.add_context("user_id", current_user.id)
    with ErrorContext(
        "get_prediction_by_prediction_id", {"prediction_id": prediction_id}
    ):
        prediction = await predict_service.get_prediction_by_prediction_id(
            prediction_id
        )
        return prediction


@router.get(
    "/export/{prediction_id}",
    response_model=PdfResponse,
    status_code=status.HTTP_200_OK,
)
async def export_prediction_pdf(
    prediction_id: str,
    pdf_service: PdfGeneratorService = Depends(create_pdf_service),
):
    """
    Export prediction as PDF (PUBLIC endpoint - no authentication required).

    **Path Parameters**:
    - prediction_id: External prediction ID from PredictionResponse.id

    **Response**:
    - PDF public URL
    """
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "export_prediction_pdf")
    ErrorContext.add_context("operation", "pdf_generation")
    ErrorContext.add_context("prediction_id", prediction_id)

    with ErrorContext("export_prediction_pdf", {"prediction_id": prediction_id}):
        pdf_url = await pdf_service.generate_and_upload_pdf(prediction_id=prediction_id)

        logger.info(f"Generated PDF for prediction {prediction_id}")
        ErrorContext.add_context("pdf_url", pdf_url)

        return PdfResponse(pdf_url=pdf_url)


@router.post(
    "/regenerate_weekly_plan", response_model=dict, status_code=status.HTTP_200_OK
)
async def regenerate_weekly_plan(
    request_data: RegeneratePlanRequest_predict,
    predict_service: ObesityPredictorComplete = Depends(create_predict_service),
):
    """
    Regenerate weekly workout plan based on existing prediction.

    **Request Body**:
    - prediction_id: External prediction ID from PredictionResponse.id
    - user_id: ID of the user
    - schedule: Schedule configuration (mode, selected_days, times)
    - timezone: User's timezone (default: Asia/Ho_Chi_Minh)

    **Response**:
    - Schedule record with weekly plan and notifications
    """
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "regenerate_weekly_plan")
    ErrorContext.add_context("operation", "regenerate_workout_plan")
    ErrorContext.add_context("prediction_id", request_data.prediction_id)

    with ErrorContext(
        "regenerate_weekly_plan",
        {
            "user_id": request_data.user_id,
            "prediction_id": request_data.prediction_id,
        },
    ):
        if predict_service is None:
            raise ServiceUnavailableException(
                "Prediction service unavailable - models not loaded"
            )

        # Lấy prediction hiện tại để có weekly plans
        existing_prediction = await predict_service.get_prediction_by_id(
            request_data.prediction_id
        )

        if not existing_prediction:
            raise ResourceNotFoundException(
                message="Prediction not found for regenerating plan",
                details={"prediction_id": request_data.prediction_id},
            )

        if not existing_prediction.workoutPlan.weeklyPlans:
            raise ValidationException(
                "Prediction has no weekly plans to regenerate from"
            )

        # Generate và trả về schedule record trực tiếp
        schedule_response = (
            await predict_service.generate_weekly_schedule_from_prediction(
                weeklyPlans=existing_prediction.workoutPlan.weeklyPlans,
                user_id=request_data.user_id,
                schedule=request_data.schedule,
                timezone=request_data.timezone or "Asia/Ho_Chi_Minh",
            )
        )

        ErrorContext.add_context("schedule_id", schedule_response.id)

        return schedule_response.model_dump()
