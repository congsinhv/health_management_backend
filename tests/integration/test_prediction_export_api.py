"""
Integration tests for consolidated prediction endpoints (PUBLIC - no authentication).
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app

client = TestClient(app)


def test_predict_endpoint_exists():
    """Test that the prediction endpoint still works."""
    response = client.post(
        "/api/v1/predict/",
        json={"gender": "male", "age": 30, "height": 1.75, "weight": 75},
    )

    # Should return 503 (service unavailable) since models aren't loaded,
    # but the endpoint should exist and be properly routed
    assert response.status_code in [503, 500]


def test_export_endpoint_exists():
    """Test that the export endpoint is properly configured."""
    with patch("app.services.pdf_service.PdfGeneratorService") as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.generate_and_upload_pdf = AsyncMock(
            side_effect=Exception("Service unavailable")
        )

        response = client.get("/api/v1/predict/export/test-prediction-123")

        # Should return 500 (service error) but endpoint should exist
        assert response.status_code == 500


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
        assert "Prediction" in predict_tags

    if export_path in openapi_spec["paths"]:
        export_tags = openapi_spec["paths"][export_path]["get"].get("tags", [])
        assert "Prediction" in export_tags


def test_no_redundant_prediction_pdf_endpoint():
    """Test that the old redundant endpoint no longer exists."""
    response = client.get("/api/v1/predictions/test-123/pdf")

    # Should return 404 since the redundant endpoint was removed
    assert response.status_code == 404
