"""
Integration tests for prediction API.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.services.predict_service import ObesityPredictorComplete

client = TestClient(app)


@pytest.mark.asyncio
async def test_predict_public_endpoint_success():
    """Test public prediction endpoint works without authentication."""
    # Mock the prediction service to avoid model loading
    mock_prediction_response = {
        "id": "test-prediction-id",
        "timestamp": "2025-11-22T18:00:00Z",
        "userInput": {
            "name": "Test User",
            "gender": "male",
            "age": 30.0,
            "height": 1.75,
            "weight": 75.0,
            "familyHistory": "Không có",
            "highCalorieFood": "Thỉnh thoảng",
            "vegetableFrequency": "Hàng ngày",
            "waterIntake": "Đủ",
            "mainMeals": 3,
            "snackFrequency": "Thỉnh thoảng",
            "physicalActivity": "Vừa phải",
            "screenTime": "Ít",
            "transportation": "Đi bộ",
            "smoking": "Không",
            "alcohol": "Thỉnh thoảng",
        },
        "prediction": {
            "level": "Normal_Weight",
            "confidence": 85.0,
            "bmi": 24.5,
            "status": "Bình thường",
            "reliability": "high",
        },
        "healthMetrics": {
            "weight": {"label": "Cân nặng", "value": 75.0, "unit": "kg"},
            "bmi": {"label": "BMI", "value": 24.5, "unit": ""},
            "height": {"label": "Chiều cao", "value": 1.75, "unit": "m"},
        },
        "healthAnalysis": {"paragraphs": ["Test analysis"]},
        "dietPlan": {"weeklyPlans": []},
        "workoutPlan": {"weeklyPlans": []},
    }

    with patch("app.api.predict.get_predict_service") as mock_get_service:
        # Create a mock service
        mock_service = AsyncMock()
        mock_service.predict_obesity_ai.return_value = mock_prediction_response
        mock_get_service.return_value = mock_service

        # Test the endpoint
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
        assert "timestamp" in data
        assert "userInput" in data
        assert "prediction" in data
        assert data["prediction"]["level"] == "Normal_Weight"


def test_predict_endpoint_handles_service_unavailable():
    """Test prediction endpoint when service is unavailable."""
    with patch("app.api.predict.get_predict_service") as mock_get_service:
        # Mock service unavailable
        mock_get_service.side_effect = Exception("Service unavailable")

        response = client.post(
            "/api/v1/predict/",
            json={"gender": "male", "age": 30, "height": 1.75, "weight": 75},
        )

        assert response.status_code == 503
        assert "Prediction service unavailable" in response.json()["detail"]


def test_predict_endpoint_validation_error():
    """Test prediction endpoint with invalid data."""
    response = client.post(
        "/api/v1/predict/",
        json={
            "gender": "invalid_gender",
            "age": -5,  # Invalid age
            "height": 0,  # Invalid height
            "weight": 0,  # Invalid weight
        },
    )

    # Should return validation error (422)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_predict_saves_to_database():
    """Test prediction saves to database when service is available."""
    mock_prediction_response = {
        "id": "test-prediction-id",
        "timestamp": "2025-11-22T18:00:00Z",
        "userInput": {"name": "Test User", "gender": "male"},
        "prediction": {"level": "Normal_Weight", "confidence": 85.0, "bmi": 24.5},
        "healthMetrics": {"weight": {"label": "Cân nặng", "value": 75.0, "unit": "kg"}},
        "healthAnalysis": {"paragraphs": ["Test"]},
        "dietPlan": {"weeklyPlans": []},
        "workoutPlan": {"weeklyPlans": []},
    }

    with patch("app.api.predict.get_predict_service") as mock_get_service:
        mock_service = AsyncMock()
        mock_service.predict_obesity_ai.return_value = mock_prediction_response
        mock_get_service.return_value = mock_service

        response = client.post(
            "/api/v1/predict/",
            json={"gender": "male", "age": 30, "height": 1.75, "weight": 75},
        )

        assert response.status_code == 200

        # Verify the service was called with save_to_db=True
        mock_service.predict_obesity_ai.assert_called_once()
        call_args = mock_service.predict_obesity_ai.call_args
        assert call_args.kwargs["save_to_db"] is True
