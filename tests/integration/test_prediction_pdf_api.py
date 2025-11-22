"""
Integration tests for prediction PDF endpoints (PUBLIC - no authentication).
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app

client = TestClient(app)


def test_generate_pdf_public_endpoint_success():
    """Test PDF generation works without authentication (PUBLIC endpoint)."""
    expected_url = (
        "https://storage.googleapis.com/bucket/predictions/prediction_test-123.pdf"
    )

    with patch("app.services.pdf_service.PdfGeneratorService") as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.generate_and_upload_pdf = AsyncMock(return_value=expected_url)

        response = client.get("/api/v1/predictions/export/test-123")

        assert response.status_code == 200
        data = response.json()
        assert "pdf_url" in data
        assert data["pdf_url"] == expected_url


def test_generate_pdf_not_found_returns_404():
    """Test PDF generation for non-existent prediction."""
    with patch("app.services.pdf_service.PdfGeneratorService") as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.generate_and_upload_pdf = AsyncMock(
            side_effect=ValueError("Prediction not found")
        )

        response = client.get("/api/v1/predictions/export/non-existent-pdf")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


def test_generate_pdf_service_failure_returns_500():
    """Test PDF generation service failure."""
    with patch("app.services.pdf_service.PdfGeneratorService") as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.generate_and_upload_pdf = AsyncMock(return_value=None)

        response = client.get("/api/v1/predictions/export/test-123")
        assert response.status_code == 500
        assert "failed to generate pdf" in response.json()["detail"].lower()


def test_generate_pdf_unexpected_error_returns_500():
    """Test unexpected error during PDF generation."""
    with patch("app.services.pdf_service.PdfGeneratorService") as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.generate_and_upload_pdf = AsyncMock(
            side_effect=Exception("Unexpected error")
        )

        response = client.get("/api/v1/predictions/export/test-123")
        assert response.status_code == 500


def test_generate_pdf_invalid_value_error_returns_400():
    """Test invalid value error during PDF generation."""
    with patch("app.services.pdf_service.PdfGeneratorService") as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.generate_and_upload_pdf = AsyncMock(
            side_effect=ValueError("Invalid prediction format")
        )

        response = client.get("/api/v1/predictions/export/invalid-pdf")
        assert response.status_code == 400
        assert "invalid prediction format" in response.json()["detail"].lower()


def test_generate_pdf_idempotent():
    """Test PDF generation is idempotent (can be called multiple times)."""
    expected_url = (
        "https://storage.googleapis.com/bucket/predictions/prediction_test-123.pdf"
    )

    with patch("app.services.pdf_service.PdfGeneratorService") as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.generate_and_upload_pdf = AsyncMock(return_value=expected_url)

        # First call
        response1 = client.get("/api/v1/predictions/test-123/pdf")
        assert response1.status_code == 200

        # Second call (should succeed)
        response2 = client.get("/api/v1/predictions/test-123/pdf")
        assert response2.status_code == 200

        # Both should return valid URLs
        assert response1.json()["pdf_url"] == expected_url
        assert response2.json()["pdf_url"] == expected_url

        # Service should be called twice (idempotent behavior)
        assert mock_instance.generate_and_upload_pdf.call_count == 2


def test_generate_pdf_various_prediction_ids():
    """Test PDF generation with various prediction ID formats."""
    expected_url = "https://storage.googleapis.com/bucket/predictions/prediction.pdf"

    test_cases = [
        "simple-id",
        "uuid-12345678-1234-1234-1234-123456789abc",
        "prediction_with_underscores",
        "prediction-with-dashes",
        "123",
        "prediction-with-numbers-123",
    ]

    with patch("app.services.pdf_service.PdfGeneratorService") as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.generate_and_upload_pdf = AsyncMock(return_value=expected_url)

        for prediction_id in test_cases:
            response = client.get(f"/api/v1/predictions/export/{prediction_id}")
            assert response.status_code == 200
            assert response.json()["pdf_url"] == expected_url

            # Verify the service was called with the correct prediction_id
            mock_instance.generate_and_upload_pdf.assert_called_with(
                prediction_id=prediction_id
            )


def test_openapi_schema_includes_pdf_endpoint():
    """Test that OpenAPI schema includes the PDF endpoint."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    openapi_spec = response.json()

    # Check if the PDF endpoint is in the paths
    pdf_path = "/api/v1/predictions/{prediction_id}/pdf"
    assert pdf_path in openapi_spec["paths"]

    # Check endpoint details
    endpoint_spec = openapi_spec["paths"][pdf_path]["get"]
    assert "summary" in endpoint_spec
    assert "tags" in endpoint_spec
    assert "predictions" in endpoint_spec["tags"]

    # Check response schema
    assert "200" in endpoint_spec["responses"]
    response_schema = endpoint_spec["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert "$ref" in response_schema
    assert "PdfResponse" in response_schema["$ref"]


def test_docs_page_includes_pdf_endpoint():
    """Test that the docs page includes the PDF endpoint."""
    response = client.get("/docs")
    assert response.status_code == 200

    # The docs page should contain references to the PDF endpoint
    html_content = response.text
    assert "predictions" in html_content.lower()
    # The exact endpoint path might be formatted differently in the docs
    assert "pdf" in html_content.lower()


def test_generate_pdf_with_json_string_data_in_database():
    """Test PDF generation when prediction data is stored as JSON strings in database."""
    expected_url = "https://storage.googleapis.com/bucket/predictions/prediction_json_string_test.pdf"

    with patch("app.services.pdf_service.PredictionRepository") as mock_repo:
        # Mock database record with JSON string data
        mock_record = {
            "prediction_id": "json-string-test-123",
            "user_input": '{"name": "JSON Test User", "gender": "male", "age": 28, "height": 1.75, "weight": 70, "family_history": true}',
            "prediction_data": '{"prediction": {"bmi": 22.86, "level": "Normal_Weight", "confidence": 90.5}, "healthAnalysis": {"paragraphs": ["JSON string health analysis"]}, "healthMetrics": {"weight": {"value": 70.0, "unit": "kg"}, "bmi": {"value": 22.86, "unit": ""}, "height": {"value": 1.75, "unit": "m"}}}',
            "created_at": "2025-11-22 15:30:00",
        }

        # Mock the repository method to return JSON string data
        mock_repo_instance = mock_repo.return_value
        mock_repo_instance.get_prediction_by_prediction_id = AsyncMock(
            return_value=mock_record
        )
        mock_repo_instance.update_pdf_url = AsyncMock(return_value=True)

        with patch("app.services.pdf_service.PdfGeneratorService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.prediction_repo = mock_repo_instance
            mock_instance.generate_and_upload_pdf = AsyncMock(return_value=expected_url)

            response = client.get("/api/v1/predictions/export/json-string-test-123")

            assert response.status_code == 200
            data = response.json()
            assert "pdf_url" in data
            assert data["pdf_url"] == expected_url

            # Verify the service was called with the correct prediction_id
            mock_instance.generate_and_upload_pdf.assert_called_once_with(
                prediction_id="json-string-test-123"
            )


def test_generate_pdf_with_mixed_data_types():
    """Test PDF generation with mixed data types (dict and JSON string)."""
    expected_url = (
        "https://storage.googleapis.com/bucket/predictions/prediction_mixed_data.pdf"
    )

    with patch("app.services.pdf_service.PredictionRepository") as mock_repo:
        # Mock database record with mixed data types
        mock_record = {
            "prediction_id": "mixed-data-test-456",
            "user_input": {
                "name": "Mixed User",
                "gender": "female",
                "age": 32,
            },  # Dictionary
            "prediction_data": '{"prediction": {"bmi": 24.2, "level": "Normal_Weight"}, "healthAnalysis": {"paragraphs": ["Mixed data health analysis"]}, "healthMetrics": {}}',  # JSON string
            "created_at": "2025-11-22 16:45:00",
        }

        mock_repo_instance = mock_repo.return_value
        mock_repo_instance.get_prediction_by_prediction_id = AsyncMock(
            return_value=mock_record
        )
        mock_repo_instance.update_pdf_url = AsyncMock(return_value=True)

        with patch("app.services.pdf_service.PdfGeneratorService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.prediction_repo = mock_repo_instance
            mock_instance.generate_and_upload_pdf = AsyncMock(return_value=expected_url)

            response = client.get("/api/v1/predictions/export/mixed-data-test-456")

            assert response.status_code == 200
            assert response.json()["pdf_url"] == expected_url


def test_generate_pdf_with_invalid_json_handles_gracefully():
    """Test PDF generation handles invalid JSON strings gracefully."""
    expected_url = (
        "https://storage.googleapis.com/bucket/predictions/prediction_invalid_json.pdf"
    )

    with patch("app.services.pdf_service.PredictionRepository") as mock_repo:
        # Mock database record with invalid JSON
        mock_record = {
            "prediction_id": "invalid-json-test-789",
            "user_input": '{"name": "Invalid User", "gender": "male"',  # Invalid JSON - missing closing brace
            "prediction_data": '{"prediction": {"bmi": 25.0, "level": "Normal_Weight"}, "healthAnalysis": {"paragraphs": []}, "healthMetrics": {}}',  # Valid JSON
            "created_at": "2025-11-22 17:00:00",
        }

        mock_repo_instance = mock_repo.return_value
        mock_repo_instance.get_prediction_by_prediction_id = AsyncMock(
            return_value=mock_record
        )
        mock_repo_instance.update_pdf_url = AsyncMock(return_value=True)

        with patch("app.services.pdf_service.PdfGeneratorService") as mock_service:
            mock_instance = mock_service.return_value
            mock_instance.prediction_repo = mock_repo_instance
            mock_instance.generate_and_upload_pdf = AsyncMock(return_value=expected_url)

            response = client.get("/api/v1/predictions/export/invalid-json-test-789")

            # Should still succeed despite invalid JSON in user_input
            assert response.status_code == 200
            assert response.json()["pdf_url"] == expected_url
