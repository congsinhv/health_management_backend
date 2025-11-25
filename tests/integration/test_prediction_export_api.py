"""
Integration tests for consolidated prediction endpoints (PUBLIC - no authentication).
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from app.main import app
from app.api.predict import create_predict_service, create_pdf_service
from app.services.predict_service import ObesityPredictorComplete
from app.services.pdf_service import PdfGeneratorService
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

client = TestClient(app)


def create_mock_prediction_response():
    """Create a valid mock prediction response."""
    return PredictionResponse(
        id="test-id",
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


@pytest.fixture
def mock_pdf_service():
    """Create a mock PDF service."""
    mock_service = MagicMock(spec=PdfGeneratorService)
    mock_service.generate_and_upload_pdf = AsyncMock()
    return mock_service


def test_predict_endpoint_exists(mock_predict_service):
    """Test that the prediction endpoint still works."""
    mock_predict_service.predict_obesity_ai.return_value = (
        create_mock_prediction_response()
    )

    app.dependency_overrides[create_predict_service] = lambda: mock_predict_service

    try:
        response = client.post(
            "/api/v1/predict/",
            json={"gender": "male", "age": 30, "height": 1.75, "weight": 75},
        )

        # Should return 200 with mocked service
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_export_endpoint_exists(mock_pdf_service):
    """Test that the export endpoint is properly configured."""
    mock_pdf_service.generate_and_upload_pdf.return_value = (
        "https://example.com/test.pdf"
    )

    app.dependency_overrides[create_pdf_service] = lambda: mock_pdf_service

    try:
        response = client.get("/api/v1/predict/export/test-prediction-123")

        # Should return 200 with mocked service
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_openapi_schema_includes_export_endpoint():
    """Test that OpenAPI schema includes the export endpoint."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    openapi_spec = response.json()

    # Check if the export endpoint is in the paths
    export_path = "/api/v1/predict/export/{prediction_id}"
    assert export_path in openapi_spec["paths"]

    # Check endpoint details
    endpoint_spec = openapi_spec["paths"][export_path]["get"]
    assert "summary" in endpoint_spec
    assert "export" in endpoint_spec["summary"].lower()


def test_prediction_router_tag_is_correct():
    """Test that prediction endpoints have the correct tag."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    openapi_spec = response.json()

    # Find prediction endpoints and check tags
    predict_path = "/api/v1/predict/"
    export_path = "/api/v1/predict/export/{prediction_id}"

    if predict_path in openapi_spec["paths"]:
        predict_tags = openapi_spec["paths"][predict_path]["post"].get("tags", [])
        assert "predict" in predict_tags

    if export_path in openapi_spec["paths"]:
        export_tags = openapi_spec["paths"][export_path]["get"].get("tags", [])
        assert "predict" in export_tags


def test_no_redundant_prediction_pdf_endpoint():
    """Test that the old redundant endpoint no longer exists."""
    response = client.get("/api/v1/predictions/test-123/pdf")

    # Should return 404 since the redundant endpoint was removed
    assert response.status_code == 404
