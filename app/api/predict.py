"""Prediction API - Proxy to Prediction service + DB persistence."""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any
import logging
import uuid
from datetime import datetime, timezone

from app.schemas.predict import UserInput, PredictionResponse
from app.clients.prediction_client import prediction_client
from app.services.predict_service import ObesityPredictorComplete
from app.db.prediction import PredictionRepository
from app.db.database import get_database_pool
from app.auth.dependencies import get_current_user
from app.core.shared.exceptions import (
    PredictionException,
    ValidationException,
    ServiceUnavailableException,
)
from app.core.error_context import ErrorContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/predict", tags=["Predictions"])


@router.post("/", response_model=PredictionResponse)
async def predict(
    user_input: UserInput,
    current_user=Depends(get_current_user),
    pool=Depends(get_database_pool),
):
    """Generate health prediction (proxied + persisted)."""
    try:
        with ErrorContext(
            "predict_obesity",
            {"user_id": current_user.id, "operation": "prediction_request"},
        ):
            # 1. Call Prediction service
            prediction_data = await prediction_client.predict(user_input.dict())

            # 2. Persist to database
            prediction_repo = PredictionRepository(pool)
            prediction_id = str(uuid.uuid4())

            await prediction_repo.create_prediction(
                prediction_id=prediction_id,
                user_id=current_user.id,
                user_input=user_input.dict(),
                prediction_data=prediction_data,
            )

            # 3. Return with ID
            return PredictionResponse(
                id=prediction_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                userInput=user_input,
                prediction=prediction_data.get("prediction", {}),
                healthMetrics=prediction_data.get("healthMetrics", {}),
                healthAnalysis=prediction_data.get("healthAnalysis", {}),
                dietPlan=prediction_data.get("dietPlan", {}),
                workoutPlan=prediction_data.get("workoutPlan", {}),
                raw_prediction=prediction_data.get("raw_prediction", []),
            )

    except ValidationException as e:
        logger.error(f"Prediction validation failed: {e}")
        raise HTTPException(status_code=422, detail=f"Invalid input: {str(e)}")
    except ServiceUnavailableException as e:
        logger.error(f"Prediction service unavailable: {e}")
        raise HTTPException(
            status_code=503, detail=f"Prediction service unavailable: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")


@router.post("/{prediction_id}/pdf")
async def generate_pdf(
    prediction_id: str,
    current_user=Depends(get_current_user),
    pool=Depends(get_database_pool),
):
    """Generate PDF report for prediction."""
    try:
        # This stays in Main API - uses existing PDF service (in Main API)
        from app.services.pdf_service import PdfGeneratorService

        pdf_service = PdfGeneratorService(pool)

        # Get prediction from database
        prediction_repo = PredictionRepository(pool)
        prediction = await prediction_repo.get_prediction(prediction_id)

        if not prediction:
            raise HTTPException(status_code=404, detail="Prediction not found")

        # Check if prediction belongs to current user
        if prediction.get("user_id") != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Generate and upload PDF
        pdf_url = await pdf_service.generate_and_upload_pdf(prediction)

        return {"pdf_url": pdf_url, "prediction_id": prediction_id}

    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")
