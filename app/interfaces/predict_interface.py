"""
Prediction service interface contract.

Defines the abstract interface for health prediction service.
Implements the contract that all prediction service implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.shared.schemas import BaseResponse, ServiceRequest


class PredictionRequest(ServiceRequest):
    """Health prediction request model."""

    # Basic demographic information
    age: int = Field(..., ge=0, le=120, description="Age in years")
    gender: str = Field(..., pattern="^(male|female|other)$", description="Gender")
    height: float = Field(..., ge=50.0, le=250.0, description="Height in cm")
    weight: float = Field(..., ge=10.0, le=500.0, description="Weight in kg")

    # Lifestyle factors
    activity_level: str = Field(
        ...,
        pattern="^(sedentary|light|moderate|active|very_active)$",
        description="Physical activity level",
    )
    smoking_status: str = Field(
        ..., pattern="^(never|former|current)$", description="Smoking status"
    )
    alcohol_consumption: str = Field(
        ..., pattern="^(none|moderate|heavy)$", description="Alcohol consumption"
    )

    # Health indicators
    systolic_bp: Optional[float] = Field(
        None, ge=70.0, le=250.0, description="Systolic blood pressure"
    )
    diastolic_bp: Optional[float] = Field(
        None, ge=40.0, le=150.0, description="Diastolic blood pressure"
    )
    fasting_glucose: Optional[float] = Field(
        None, ge=50.0, le=500.0, description="Fasting blood glucose (mg/dL)"
    )
    cholesterol: Optional[float] = Field(
        None, ge=100.0, le=400.0, description="Total cholesterol (mg/dL)"
    )

    # Medical history
    family_history_diabetes: bool = Field(
        False, description="Family history of diabetes"
    )
    family_history_heart_disease: bool = Field(
        False, description="Family history of heart disease"
    )
    personal_history_diabetes: bool = Field(
        False, description="Personal history of diabetes"
    )
    personal_history_heart_disease: bool = Field(
        False, description="Personal history of heart disease"
    )

    # User context
    user_id: Optional[int] = Field(None, description="User ID for tracking")
    prediction_type: str = Field(
        "general",
        description="Type of prediction: general, obesity, diabetes, heart_disease",
    )


class RiskScore(BaseModel):
    """Individual risk factor score."""

    factor: str = Field(..., description="Risk factor name")
    score: float = Field(..., ge=0.0, le=1.0, description="Risk score (0-1)")
    level: str = Field(
        ..., pattern="^(low|moderate|high|very_high)$", description="Risk level"
    )
    contributing_factors: List[str] = Field(
        default_factory=list, description="Factors contributing to this risk"
    )


class Recommendation(BaseModel):
    """Health recommendation model."""

    category: str = Field(..., description="Recommendation category")
    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Detailed recommendation")
    priority: str = Field(
        ...,
        pattern="^(low|medium|high|critical)$",
        description="Recommendation priority",
    )
    action_items: List[str] = Field(
        default_factory=list, description="Specific action items"
    )


class PredictionResponse(BaseResponse):
    """Health prediction response model."""

    user_id: Optional[int] = Field(None, description="User ID from request")
    bmi: float = Field(..., ge=10.0, le=60.0, description="Calculated BMI")
    obesity_level: str = Field(
        ...,
        pattern="^(underweight|normal|overweight|obese|severely_obese)$",
        description="Obesity classification",
    )
    obesity_risk: RiskScore = Field(..., description="Obesity risk assessment")
    diabetes_risk: RiskScore = Field(..., description="Diabetes risk assessment")
    heart_disease_risk: RiskScore = Field(
        ..., description="Heart disease risk assessment"
    )
    recommendations: List[Recommendation] = Field(
        default_factory=list, description="Personalized recommendations"
    )
    model_version: str = Field(..., description="ML model version used")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Overall prediction confidence"
    )
    processing_time_ms: Optional[int] = Field(
        None, description="Processing time in milliseconds"
    )


class PredictionHistory(BaseModel):
    """Prediction history model."""

    id: int
    user_id: int
    prediction_data: PredictionRequest
    prediction_result: PredictionResponse
    created_at: datetime
    notes: Optional[str] = None


class PredictionHealthCheck(BaseResponse):
    """Prediction service health check model."""

    service: str = Field("prediction", description="Service name")
    models_loaded: Dict[str, bool] = Field(..., description="Loaded model status")
    database_connected: bool = Field(..., description="Whether database is connected")
    cache_status: str = Field(..., description="Cache service status")
    total_predictions: Optional[int] = Field(None, description="Total predictions made")


class IPredictionService(ABC):
    """Prediction service interface."""

    @abstractmethod
    async def predict_health(self, request: PredictionRequest) -> PredictionResponse:
        """
        Generate health prediction based on user data.

        Args:
            request: Health prediction request with user data

        Returns:
            PredictionResponse with BMI, risk scores, and recommendations

        Raises:
            ValidationException: If input data is invalid
            ModelNotLoadedException: If ML models are not loaded
            PredictionDataException: If data processing fails
            AIServiceException: If AI recommendations fail
        """
        pass

    @abstractmethod
    async def get_user_predictions(
        self, user_id: int, limit: int = 10, offset: int = 0
    ) -> List[PredictionHistory]:
        """
        Get prediction history for a user.

        Args:
            user_id: User ID
            limit: Maximum number of predictions to return
            offset: Number of predictions to skip

        Returns:
            List of user's prediction history

        Raises:
            DatabaseException: If database query fails
        """
        pass

    @abstractmethod
    async def save_prediction(
        self,
        user_id: int,
        request: PredictionRequest,
        response: PredictionResponse,
        notes: Optional[str] = None,
    ) -> PredictionHistory:
        """
        Save a prediction to user history.

        Args:
            user_id: User ID
            request: Original prediction request
            response: Prediction response
            notes: Optional notes about the prediction

        Returns:
            Saved prediction history record

        Raises:
            DatabaseException: If database insert fails
        """
        pass

    @abstractmethod
    async def get_prediction_by_id(
        self, prediction_id: int, user_id: int
    ) -> Optional[PredictionHistory]:
        """
        Get a specific prediction by ID.

        Args:
            prediction_id: Prediction ID
            user_id: User ID for authorization

        Returns:
            Prediction history record or None if not found

        Raises:
            AuthorizationException: If user doesn't own prediction
            DatabaseException: If database query fails
        """
        pass

    @abstractmethod
    async def delete_prediction(self, prediction_id: int, user_id: int) -> bool:
        """
        Delete a prediction from user history.

        Args:
            prediction_id: Prediction ID
            user_id: User ID for authorization

        Returns:
            True if deleted, False if not found

        Raises:
            AuthorizationException: If user doesn't own prediction
            DatabaseException: If database delete fails
        """
        pass

    @abstractmethod
    async def health_check(self) -> PredictionHealthCheck:
        """
        Check the health of the prediction service.

        Returns:
            PredictionHealthCheck with service status and model details
        """
        pass

    @abstractmethod
    async def get_prediction_statistics(
        self, user_id: Optional[int] = None, days: int = 30
    ) -> Dict[str, Any]:
        """
        Get prediction statistics.

        Args:
            user_id: Optional user ID for user-specific stats
            days: Number of days to include in statistics

        Returns:
            Dictionary with prediction statistics

        Raises:
            DatabaseException: If database query fails
        """
        pass

    @abstractmethod
    async def generate_pdf_report(self, prediction_id: int, user_id: int) -> str:
        """
        Generate PDF report for a prediction.

        Args:
            prediction_id: Prediction ID
            user_id: User ID for authorization

        Returns:
            Path or URL to generated PDF

        Raises:
            AuthorizationException: If user doesn't own prediction
            PDFGenerationException: If PDF generation fails
            DatabaseException: If database query fails
        """
        pass
