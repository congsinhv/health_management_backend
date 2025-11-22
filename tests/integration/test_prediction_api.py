"""
Integration tests for prediction API endpoints.
"""

import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from app.main import app
from app.schemas.user import UserInDB


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_current_user():
    """Mock current user for authentication."""
    return UserInDB(
        id=1,
        email="test@example.com",
        hashed_password="hashed_password",
        full_name="Test User",
        is_active=True,
        is_superuser=False,
    )


@pytest.fixture
def sample_user_input():
    """Sample user input data."""
    return {
        "name": "Test User",
        "gender": "Male",
        "age": 30.0,
        "height": 1.75,
        "weight": 70.0,
        "family_history": False,
        "FAF": 1.0,
        "TUE": 1.0,
        "NCP": 3,
        "FCVC": 2.0,
        "CH2O": 2.0,
        "FAVC": 0,
        "CALC": 0,
        "CAEC": 2,
        "MTRANS_Calorie": 1,
    }


@pytest.fixture
def sample_prediction_response():
    """Sample prediction response data."""
    return {
        "id": "test-prediction-id",
        "timestamp": "2025-11-22T17:30:00",
        "userInput": {
            "name": "Test User",
            "gender": "Male",
            "age": 30.0,
            "height": 1.75,
            "weight": 70.0,
            "familyHistory": "Không",
            "highCalorieFood": "Không",
            "vegetableFrequency": "Thường xuyên",
            "waterIntake": "1-2L",
            "mainMeals": 3,
            "snackFrequency": "Không",
            "physicalActivity": "1-2 ngày",
            "screenTime": "0-2h",
            "transportation": "Xe máy",
            "smoking": "Không",
            "alcohol": "Không",
        },
        "prediction": {
            "level": "Normal_Weight",
            "confidence": 85.5,
            "bmi": 22.86,
            "status": "Bình thường",
            "reliability": "high",
        },
        "healthMetrics": {
            "weight": {"label": "Cân nặng", "value": 70.0, "unit": "kg"},
            "bmi": {"label": "BMI", "value": 22.86, "unit": ""},
            "height": {"label": "Chiều cao", "value": 1.75, "unit": "m"},
        },
        "healthAnalysis": {
            "paragraphs": [
                "Test health analysis paragraph 1",
                "Test health analysis paragraph 2",
            ]
        },
        "dietPlan": {"weeklyPlans": []},
        "workoutPlan": {"weeklyPlans": []},
    }


class TestPredictionAPI:
    """Test prediction API endpoints."""

    def test_predict_obesity_unauthorized(self, client, sample_user_input):
        """Test prediction endpoint without authentication."""
        response = client.post("/api/v1/predict/", json=sample_user_input)
        assert response.status_code == 401

    @patch("app.api.predict.get_current_active_user")
    @patch("app.api.predict.get_predict_service")
    @patch("app.api.predict.PredictionRepository")
    @patch("app.api.predict.get_database_pool")
    def test_predict_obesity_success(
        self,
        mock_get_db_pool,
        mock_prediction_repo_class,
        mock_get_predict_service,
        mock_get_current_user,
        client,
        sample_user_input,
        sample_prediction_response,
        mock_current_user,
    ):
        """Test successful prediction creation."""
        # Setup mocks
        mock_get_current_user.return_value = mock_current_user

        # Mock prediction service
        mock_predict_service = Mock()
        mock_predict_service.predict_obesity_ai = AsyncMock(
            return_value=sample_prediction_response
        )
        mock_get_predict_service.return_value = mock_predict_service

        # Mock database pool
        mock_pool = Mock()
        mock_get_db_pool.return_value = mock_pool

        # Mock prediction repository
        mock_repo = Mock()
        mock_prediction_record = {
            "id": 1,
            "user_id": 1,
            "user_input": sample_user_input,
            "prediction_data": sample_prediction_response,
            "pdf_url": None,
            "created_at": "2025-11-22T17:30:00",
            "updated_at": "2025-11-22T17:30:00",
            "deleted_at": None,
        }
        mock_repo.create = AsyncMock(return_value=mock_prediction_record)
        mock_prediction_repo_class.return_value = mock_repo

        # Make request
        response = client.post(
            "/api/v1/predict/",
            json=sample_user_input,
            headers={"Authorization": "Bearer test_token"},
        )

        # Verify response
        assert response.status_code == 200
        response_data = response.json()
        assert "prediction_data" in response_data
        assert response_data["prediction_data"]["id"] == "test-prediction-id"
        assert response_data["pdf_url"] is None

    @patch("app.api.predict.get_current_active_user")
    @patch("app.api.predict.get_predict_service")
    def test_predict_obesity_service_unavailable(
        self,
        mock_get_predict_service,
        mock_get_current_user,
        client,
        sample_user_input,
        mock_current_user,
    ):
        """Test prediction when service is unavailable."""
        # Setup mocks
        mock_get_current_user.return_value = mock_current_user
        mock_get_predict_service.return_value = None

        # Make request
        response = client.post(
            "/api/v1/predict/",
            json=sample_user_input,
            headers={"Authorization": "Bearer test_token"},
        )

        # Verify response
        assert response.status_code == 503
        assert "Prediction service unavailable" in response.json()["detail"]

    @patch("app.api.predict.get_current_active_user")
    @patch("app.api.predict.PredictionRepository")
    @patch("app.api.predict.get_database_pool")
    def test_generate_pdf_success(
        self,
        mock_get_db_pool,
        mock_prediction_repo_class,
        mock_get_current_user,
        client,
        mock_current_user,
    ):
        """Test successful PDF generation."""
        # Setup mocks
        mock_get_current_user.return_value = mock_current_user

        # Mock database pool
        mock_pool = Mock()
        mock_get_db_pool.return_value = mock_pool

        # Mock prediction repository
        mock_repo = Mock()
        prediction_record = {
            "id": 1,
            "user_id": 1,
            "user_input": {"name": "Test User"},
            "prediction_data": {"id": "test-prediction"},
            "pdf_url": None,
            "created_at": "2025-11-22T17:30:00",
        }
        mock_repo.get_by_id_and_user = AsyncMock(return_value=prediction_record)
        mock_repo.update_pdf_url = AsyncMock(
            return_value={**prediction_record, "pdf_url": "https://example.com/pdf.pdf"}
        )
        mock_prediction_repo_class.return_value = mock_repo

        # Mock PDF service
        with patch("app.api.predict.get_pdf_service") as mock_get_pdf_service:
            mock_pdf_service = Mock()
            mock_pdf_service.generate_prediction_pdf = AsyncMock(
                return_value="https://example.com/pdf.pdf"
            )
            mock_get_pdf_service.return_value = mock_pdf_service

            # Make request
            response = client.post(
                "/api/v1/predict/1/pdf", headers={"Authorization": "Bearer test_token"}
            )

        # Verify response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["pdf_url"] == "https://example.com/pdf.pdf"
        assert response_data["prediction_id"] == 1

    @patch("app.api.predict.get_current_active_user")
    @patch("app.api.predict.PredictionRepository")
    @patch("app.api.predict.get_database_pool")
    def test_generate_pdf_already_exists(
        self,
        mock_get_db_pool,
        mock_prediction_repo_class,
        mock_get_current_user,
        client,
        mock_current_user,
    ):
        """Test PDF generation when PDF already exists."""
        # Setup mocks
        mock_get_current_user.return_value = mock_current_user

        # Mock database pool
        mock_pool = Mock()
        mock_get_db_pool.return_value = mock_pool

        # Mock prediction repository with existing PDF
        mock_repo = Mock()
        prediction_record = {
            "id": 1,
            "user_id": 1,
            "user_input": {"name": "Test User"},
            "prediction_data": {"id": "test-prediction"},
            "pdf_url": "https://example.com/existing.pdf",
            "created_at": "2025-11-22T17:30:00",
        }
        mock_repo.get_by_id_and_user = AsyncMock(return_value=prediction_record)
        mock_prediction_repo_class.return_value = mock_repo

        # Make request
        response = client.post(
            "/api/v1/predict/1/pdf", headers={"Authorization": "Bearer test_token"}
        )

        # Verify response - should return existing PDF URL
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["pdf_url"] == "https://example.com/existing.pdf"
        assert response_data["prediction_id"] == 1

    @patch("app.api.predict.get_current_active_user")
    @patch("app.api.predict.PredictionRepository")
    @patch("app.api.predict.get_database_pool")
    def test_generate_pdf_not_found(
        self,
        mock_get_db_pool,
        mock_prediction_repo_class,
        mock_get_current_user,
        client,
        mock_current_user,
    ):
        """Test PDF generation for non-existent prediction."""
        # Setup mocks
        mock_get_current_user.return_value = mock_current_user

        # Mock database pool
        mock_pool = Mock()
        mock_get_db_pool.return_value = mock_pool

        # Mock prediction repository
        mock_repo = Mock()
        mock_repo.get_by_id_and_user = AsyncMock(return_value=None)
        mock_prediction_repo_class.return_value = mock_repo

        # Make request
        response = client.post(
            "/api/v1/predict/999/pdf", headers={"Authorization": "Bearer test_token"}
        )

        # Verify response
        assert response.status_code == 404
        assert "Prediction not found" in response.json()["detail"]

    @patch("app.api.predict.get_current_active_user")
    @patch("app.api.predict.PredictionRepository")
    @patch("app.api.predict.get_database_pool")
    def test_get_prediction_success(
        self,
        mock_get_db_pool,
        mock_prediction_repo_class,
        mock_get_current_user,
        client,
        mock_current_user,
    ):
        """Test getting prediction details."""
        # Setup mocks
        mock_get_current_user.return_value = mock_current_user

        # Mock database pool
        mock_pool = Mock()
        mock_get_db_pool.return_value = mock_pool

        # Mock prediction repository
        mock_repo = Mock()
        prediction_record = {
            "id": 1,
            "user_id": 1,
            "user_input": {"name": "Test User"},
            "prediction_data": {
                "id": "test-prediction",
                "prediction": {"level": "Normal_Weight"},
            },
            "pdf_url": "https://example.com/pdf.pdf",
            "created_at": "2025-11-22T17:30:00",
        }
        mock_repo.get_by_id_and_user = AsyncMock(return_value=prediction_record)
        mock_prediction_repo_class.return_value = mock_repo

        # Make request
        response = client.get(
            "/api/v1/predict/1", headers={"Authorization": "Bearer test_token"}
        )

        # Verify response
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["prediction_data"]["id"] == "test-prediction"
        assert response_data["pdf_url"] == "https://example.com/pdf.pdf"

    @patch("app.api.predict.get_current_active_user")
    @patch("app.api.predict.PredictionRepository")
    @patch("app.api.predict.get_database_pool")
    def test_get_prediction_not_found(
        self,
        mock_get_db_pool,
        mock_prediction_repo_class,
        mock_get_current_user,
        client,
        mock_current_user,
    ):
        """Test getting non-existent prediction."""
        # Setup mocks
        mock_get_current_user.return_value = mock_current_user

        # Mock database pool
        mock_pool = Mock()
        mock_get_db_pool.return_value = mock_pool

        # Mock prediction repository
        mock_repo = Mock()
        mock_repo.get_by_id_and_user = AsyncMock(return_value=None)
        mock_prediction_repo_class.return_value = mock_repo

        # Make request
        response = client.get(
            "/api/v1/predict/999", headers={"Authorization": "Bearer test_token"}
        )

        # Verify response
        assert response.status_code == 404
        assert "Prediction not found" in response.json()["detail"]

    def test_prediction_endpoints_unauthorized(self, client):
        """Test all prediction endpoints without authentication."""
        endpoints = [
            (
                "/api/v1/predict/",
                "post",
                {
                    "name": "Test",
                    "gender": "Male",
                    "age": 30,
                    "height": 1.75,
                    "weight": 70,
                },
            ),
            ("/api/v1/predict/1", "get"),
            ("/api/v1/predict/1/pdf", "post"),
        ]

        for endpoint, method, *data in endpoints:
            if method == "post" and data:
                response = client.post(endpoint, json=data[0])
            else:
                response = client.request(method, endpoint)
            assert response.status_code == 401
