from typing import Annotated
import asyncpg
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.schemas.predict import UserInput, PredictionResponse
from app.services.predict_service import ObesityPredictorComplete
from app.services.pdf_service import PDFService
from app.db.prediction import PredictionRepository
from app.auth.dependencies import get_current_active_user
from app.db.database import get_database_pool
from app.schemas.user import UserInDB

router = APIRouter(prefix="/predict", tags=["Prediction"])

# Initialize services lazily to avoid import errors during testing
predict_service = None
pdf_service = None


def get_predict_service():
    global predict_service
    if predict_service is None:
        try:
            predict_service = ObesityPredictorComplete()
        except Exception as e:
            # Model files not available, return None
            predict_service = None
    return predict_service


def get_pdf_service():
    global pdf_service
    if pdf_service is None:
        try:
            pdf_service = PDFService()
        except Exception as e:
            pdf_service = None
    return pdf_service


class PDFResponse(BaseModel):
    """Response model for PDF generation."""

    pdf_url: str
    prediction_id: int


class PredictionResponse(BaseModel):
    """Response model for prediction with optional PDF URL."""

    prediction_data: dict
    pdf_url: str = None


@router.post("/", response_model=PredictionResponse)
async def predict_obesity(
    data: UserInput,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db_pool: Annotated[asyncpg.Pool, Depends(get_database_pool)],
):
    """Generate health prediction and save to database."""
    try:
        predict_service = get_predict_service()
        if predict_service is None:
            raise HTTPException(
                status_code=503,
                detail="Prediction service unavailable - models not loaded",
            )

        # Generate prediction
        prediction_response = await predict_service.predict_obesity_ai(data)

        # Save to database
        prediction_repo = PredictionRepository(db_pool)
        prediction_record = await prediction_repo.create(
            user_id=current_user.id,
            user_input=data.dict(),
            prediction_data=prediction_response.dict(),
        )

        if not prediction_record:
            # Log error but don't fail the request - prediction still works
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Failed to save prediction to database for user {current_user.id}"
            )

        return PredictionResponse(
            prediction_data=prediction_response.dict(),
            pdf_url=prediction_record.get("pdf_url") if prediction_record else None,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{prediction_id}/pdf", response_model=PDFResponse)
async def generate_prediction_pdf(
    prediction_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db_pool: Annotated[asyncpg.Pool, Depends(get_database_pool)],
):
    """Generate PDF for an existing prediction."""
    try:
        # Get prediction from database
        prediction_repo = PredictionRepository(db_pool)
        prediction_record = await prediction_repo.get_by_id_and_user(
            prediction_id=prediction_id, user_id=current_user.id
        )

        if not prediction_record:
            raise HTTPException(status_code=404, detail="Prediction not found")

        # Check if PDF already exists
        if prediction_record.get("pdf_url"):
            return PDFResponse(
                pdf_url=prediction_record["pdf_url"], prediction_id=prediction_id
            )

        # Generate PDF
        pdf_service_instance = get_pdf_service()
        if not pdf_service_instance:
            raise HTTPException(status_code=503, detail="PDF service unavailable")

        pdf_url = await pdf_service_instance.generate_prediction_pdf(
            prediction_data=prediction_record["prediction_data"],
            user_input=prediction_record["user_input"],
        )

        if not pdf_url:
            raise HTTPException(status_code=500, detail="Failed to generate PDF")

        # Update prediction record with PDF URL
        updated_prediction = await prediction_repo.update_pdf_url(
            prediction_id=prediction_id, user_id=current_user.id, pdf_url=pdf_url
        )

        return PDFResponse(pdf_url=pdf_url, prediction_id=prediction_id)

    except HTTPException:
        raise
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error generating PDF for prediction {prediction_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate PDF")


@router.get("/{prediction_id}", response_model=PredictionResponse)
async def get_prediction(
    prediction_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    db_pool: Annotated[asyncpg.Pool, Depends(get_database_pool)],
):
    """Get a specific prediction with PDF URL if available."""
    try:
        prediction_repo = PredictionRepository(db_pool)
        prediction_record = await prediction_repo.get_by_id_and_user(
            prediction_id=prediction_id, user_id=current_user.id
        )

        if not prediction_record:
            raise HTTPException(status_code=404, detail="Prediction not found")

        return PredictionResponse(
            prediction_data=prediction_record["prediction_data"],
            pdf_url=prediction_record.get("pdf_url"),
        )

    except HTTPException:
        raise
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error getting prediction {prediction_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get prediction")
