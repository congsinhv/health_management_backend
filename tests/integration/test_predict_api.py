"""
Integration tests for prediction API.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.api.predict import create_predict_service
from app.services.predict_service import ObesityPredictorComplete
from app.exceptions import ServiceUnavailableException
from app.schemas.predict import (
    PredictionResponse,
    UserInputResponse,
    PredictionDetail,
    HealthMetrics,
    Metric,
    HealthAnalysis,
    DietPlan,
    WorkoutPlan,
)

client = TestClient(app, raise_server_exceptions=False)


def create_mock_prediction_response():
    """Create a valid mock prediction response."""
    return PredictionResponse(
        id="test-prediction-id",
        timestamp="2025-11-22T18:00:00Z",
        userInput=UserInputResponse(
            name="Test User",
            gender="male",
            age=30.0,
            height=1.75,
            weight=75.0,
            familyHistory="Không có",
            highCalorieFood="Thỉnh thoảng",
            vegetableFrequency="Hàng ngày",
            waterIntake="Đủ",
            mainMeals=3,
            snackFrequency="Thỉnh thoảng",
            physicalActivity="Vừa phải",
            screenTime="Ít",
            transportation="Đi bộ",
            smoking="Không",
            alcohol="Thỉnh thoảng",
        ),
        prediction=PredictionDetail(
            level="Normal_Weight",
            confidence=85.0,
            bmi=24.5,
            status="Bình thường",
            reliability="high",
        ),
        healthMetrics=HealthMetrics(
            weight=Metric(label="Cân nặng", value=75.0, unit="kg"),
            bmi=Metric(label="BMI", value=24.5, unit=""),
            height=Metric(label="Chiều cao", value=1.75, unit="m"),
        ),
        healthAnalysis=HealthAnalysis(paragraphs=["Test analysis"]),
        dietPlan=DietPlan(weeklyPlans=[]),
        workoutPlan=WorkoutPlan(weeklyPlans=[]),
    )


@pytest.fixture
def mock_predict_service():
    """Create a mock prediction service."""
    mock_service = MagicMock(spec=ObesityPredictorComplete)
    mock_service.predict_obesity_ai = AsyncMock()
    return mock_service


def test_predict_public_endpoint_success(mock_predict_service):
    """Test public prediction endpoint works without authentication."""
    mock_predict_service.predict_obesity_ai.return_value = (
        create_mock_prediction_response()
    )

    # Override the dependency
    app.dependency_overrides[create_predict_service] = lambda: mock_predict_service

    try:
        response = client.post(
            "/api/v1/predict/",
            json={
                "name": "Test User",
                "gender": "male",
                "age": 30,
                "height": 1.75,
                "weight": 75,
                "family_history": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["id"] == "test-prediction-id"
        # Verify the service was called with save_to_db=True
        mock_predict_service.predict_obesity_ai.assert_called_once()
        call_args = mock_predict_service.predict_obesity_ai.call_args
        assert call_args.kwargs["save_to_db"] is True
    finally:
        app.dependency_overrides.clear()


def test_predict_endpoint_handles_service_unavailable():
    """Test prediction endpoint when service is unavailable."""
    mock_service = MagicMock(spec=ObesityPredictorComplete)
    mock_service.predict_obesity_ai = AsyncMock(
        side_effect=ServiceUnavailableException("Prediction service unavailable")
    )

    # Override the dependency to return a mock that raises exception when called
    app.dependency_overrides[create_predict_service] = lambda: mock_service

    try:
        response = client.post(
            "/api/v1/predict/",
            json={"gender": "male", "age": 30, "height": 1.75, "weight": 75},
        )

        assert response.status_code == 503
        # The exception handler returns a generic message for security
        assert "unavailable" in response.json()["message"].lower()
    finally:
        app.dependency_overrides.clear()


def test_predict_endpoint_validation_error(mock_predict_service):
    """Test prediction endpoint with invalid data."""
    # Override the dependency
    app.dependency_overrides[create_predict_service] = lambda: mock_predict_service

    try:
        # Missing required fields (gender, age, height, weight) should trigger 422
        response = client.post(
            "/api/v1/predict/",
            json={
                "name": "Test",
                # Missing: gender, age, height, weight
            },
        )

        # Should return validation error (422) for missing required fields
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_predict_saves_to_database(mock_predict_service):
    """Test prediction saves to database when service is available."""
    mock_predict_service.predict_obesity_ai.return_value = (
        create_mock_prediction_response()
    )

    # Override the dependency
    app.dependency_overrides[create_predict_service] = lambda: mock_predict_service

    try:
        response = client.post(
            "/api/v1/predict/",
            json={"gender": "male", "age": 30, "height": 1.75, "weight": 75},
        )

        assert response.status_code == 200

        # Verify the service was called with save_to_db=True
        mock_predict_service.predict_obesity_ai.assert_called_once()
        call_args = mock_predict_service.predict_obesity_ai.call_args
        assert call_args.kwargs["save_to_db"] is True
    finally:
        app.dependency_overrides.clear()
