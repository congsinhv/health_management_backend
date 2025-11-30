"""Prediction API endpoints."""
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging

from app.services.predict_service import PredictService
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predict", tags=["Predictions"])


class UserInput(BaseModel):
    """User input for prediction."""
    age: int
    gender: str
    height: float
    weight: float
    family_history: Optional[bool] = False
    FAVC: Optional[str] = "no"
    FCVC: Optional[float] = 2.0
    NCP: Optional[int] = 3
    CAEC: Optional[str] = "Sometimes"
    CH2O: Optional[float] = 2.0
    FAF: Optional[float] = 1.0
    TUE: Optional[float] = 2.0
    CALC: Optional[str] = "Sometimes"
    MTRANS: Optional[str] = "Automobile"


class PredictionResponse(BaseModel):
    """Prediction response from service."""
    obesity_level: str
    bmi: float
    metabolic_age: int
    diet_plan: Dict[str, Any]
    workout_plan: Dict[str, Any]
    raw_prediction: list
    input_data: Dict[str, Any]


def get_predict_service(request: Request) -> PredictService:
    """Get prediction service from app state."""
    return request.app.state.predict_service


@router.post("/", response_model=PredictionResponse)
async def predict(
    user_input: UserInput,
    predict_service = Depends(get_predict_service)
):
    """Generate health prediction."""
    try:
        prediction = await predict_service.predict(user_input.dict())
        return prediction
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Prediction service error: {str(e)}"
        )


@router.get("/health")
async def health_check(predict_service = Depends(get_predict_service)):
    """Check prediction service health."""
    try:
        model_loaded = predict_service.is_model_loaded()
        return {
            "status": "healthy",
            "service": "prediction",
            "model_loaded": model_loaded,
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "prediction",
            "error": str(e),
            "version": "1.0.0"
        }


@router.get("/info")
async def service_info(predict_service = Depends(get_predict_service)):
    """Get prediction service information."""
    try:
        model_info = predict_service.model_loader.get_model_info() if predict_service.model_loader else {"loaded": False}
        return {
            "service": "VHealth Prediction Service",
            "version": "1.0.0",
            "model": model_info,
            "endpoints": {
                "predict": "/api/v1/predict/",
                "health": "/api/v1/predict/health",
                "info": "/api/v1/predict/info"
            }
        }
    except Exception as e:
        logger.error(f"Service info failed: {e}")
        return {
            "service": "VHealth Prediction Service",
            "version": "1.0.0",
            "error": str(e)
        }