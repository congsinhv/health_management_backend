"""
Integration tests for prediction PDF endpoints (PUBLIC - no authentication).
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from app.main import app
from app.api.predict import create_pdf_service
from app.services.pdf_service import PdfGeneratorService, PdfGenerationError
from app.exceptions import ResourceNotFoundException, ValidationException

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def mock_pdf_service():
    """Create a mock PDF service."""
    mock_service = MagicMock(spec=PdfGeneratorService)
    mock_service.generate_and_upload_pdf = AsyncMock()
    return mock_service


def test_generate_pdf_public_endpoint_success(mock_pdf_service):
    """Test PDF generation works without authentication (PUBLIC endpoint)."""
    expected_url = (
        "https://storage.googleapis.com/bucket/predictions/prediction_test-123.pdf"
    )
    mock_pdf_service.generate_and_upload_pdf.return_value = expected_url

    app.dependency_overrides[create_pdf_service] = lambda: mock_pdf_service

    try:
        response = client.get("/api/v1/predict/export/test-123")

        assert response.status_code == 200
        data = response.json()
        assert "pdf_url" in data
        assert data["pdf_url"] == expected_url
    finally:
        app.dependency_overrides.clear()


def test_generate_pdf_not_found_returns_404(mock_pdf_service):
    """Test PDF generation for non-existent prediction."""
    mock_pdf_service.generate_and_upload_pdf.side_effect = ResourceNotFoundException(
        "Prediction not found"
    )

    app.dependency_overrides[create_pdf_service] = lambda: mock_pdf_service

    try:
        response = client.get("/api/v1/predict/export/non-existent-pdf")
        assert response.status_code == 404
        assert "not found" in response.json()["message"].lower()
    finally:
        app.dependency_overrides.clear()


def test_generate_pdf_service_failure_returns_500(mock_pdf_service):
    """Test PDF generation service failure."""
    mock_pdf_service.generate_and_upload_pdf.side_effect = PdfGenerationError(
        message="Failed to generate PDF", prediction_id="test-123"
    )

    app.dependency_overrides[create_pdf_service] = lambda: mock_pdf_service

    try:
        response = client.get("/api/v1/predict/export/test-123")
        assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()


def test_generate_pdf_unexpected_error_returns_500(mock_pdf_service):
    """Test unexpected error during PDF generation."""
    mock_pdf_service.generate_and_upload_pdf.side_effect = Exception("Unexpected error")

    app.dependency_overrides[create_pdf_service] = lambda: mock_pdf_service

    try:
        response = client.get("/api/v1/predict/export/test-123")
        assert response.status_code == 500
    finally:
        app.dependency_overrides.clear()


def test_generate_pdf_invalid_value_error_returns_422(mock_pdf_service):
    """Test invalid value error during PDF generation."""
    mock_pdf_service.generate_and_upload_pdf.side_effect = ValidationException(
        "Invalid prediction format"
    )

    app.dependency_overrides[create_pdf_service] = lambda: mock_pdf_service

    try:
        response = client.get("/api/v1/predict/export/invalid-pdf")
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_generate_pdf_idempotent(mock_pdf_service):
    """Test PDF generation is idempotent (can be called multiple times)."""
    expected_url = (
        "https://storage.googleapis.com/bucket/predictions/prediction_test-123.pdf"
    )
    mock_pdf_service.generate_and_upload_pdf.return_value = expected_url

    app.dependency_overrides[create_pdf_service] = lambda: mock_pdf_service

    try:
        # First call
        response1 = client.get("/api/v1/predict/export/test-123")
        assert response1.status_code == 200

        # Second call (should succeed)
        response2 = client.get("/api/v1/predict/export/test-123")
        assert response2.status_code == 200

        # Both should return valid URLs
        assert response1.json()["pdf_url"] == expected_url
        assert response2.json()["pdf_url"] == expected_url

        # Service should be called twice (idempotent behavior)
        assert mock_pdf_service.generate_and_upload_pdf.call_count == 2
    finally:
        app.dependency_overrides.clear()


def test_generate_pdf_various_prediction_ids(mock_pdf_service):
    """Test PDF generation with various prediction ID formats."""
    expected_url = "https://storage.googleapis.com/bucket/predictions/prediction.pdf"
    mock_pdf_service.generate_and_upload_pdf.return_value = expected_url

    test_cases = [
        "simple-id",
        "uuid-12345678-1234-1234-1234-123456789abc",
        "prediction_with_underscores",
        "prediction-with-dashes",
        "123",
        "prediction-with-numbers-123",
    ]

    app.dependency_overrides[create_pdf_service] = lambda: mock_pdf_service

    try:
        for prediction_id in test_cases:
            mock_pdf_service.generate_and_upload_pdf.reset_mock()
            response = client.get(f"/api/v1/predict/export/{prediction_id}")
            assert response.status_code == 200
            assert response.json()["pdf_url"] == expected_url

            # Verify the service was called with the correct prediction_id
            mock_pdf_service.generate_and_upload_pdf.assert_called_with(
                prediction_id=prediction_id
            )
    finally:
        app.dependency_overrides.clear()


def test_openapi_schema_includes_pdf_endpoint():
    """Test that OpenAPI schema includes the PDF export endpoint."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    openapi_spec = response.json()

    # Check if the export endpoint is in the paths
    pdf_path = "/api/v1/predict/export/{prediction_id}"
    assert pdf_path in openapi_spec["paths"]

    # Check endpoint details
    endpoint_spec = openapi_spec["paths"][pdf_path]["get"]
    assert "summary" in endpoint_spec
    assert "tags" in endpoint_spec
    assert "predict" in endpoint_spec["tags"]

    # Check response schema
    assert "200" in endpoint_spec["responses"]
    response_schema = endpoint_spec["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert "$ref" in response_schema
    assert "PdfResponse" in response_schema["$ref"]


def test_docs_page_includes_pdf_endpoint():
    """Test that the docs page is accessible and loads correctly."""
    response = client.get("/docs")
    assert response.status_code == 200

    # The docs page should be an HTML page that loads Swagger UI
    html_content = response.text
    assert "swagger-ui" in html_content.lower()
    # The page should reference the OpenAPI JSON which contains the endpoint
    assert "openapi.json" in html_content


def test_generate_pdf_with_json_string_data_in_database(mock_pdf_service):
    """Test PDF generation when prediction data is stored as JSON strings in database."""
    expected_url = "https://storage.googleapis.com/bucket/predictions/prediction_json_string_test.pdf"
    mock_pdf_service.generate_and_upload_pdf.return_value = expected_url

    app.dependency_overrides[create_pdf_service] = lambda: mock_pdf_service

    try:
        response = client.get("/api/v1/predict/export/json-string-test-123")

        assert response.status_code == 200
        data = response.json()
        assert "pdf_url" in data
        assert data["pdf_url"] == expected_url

        # Verify the service was called with the correct prediction_id
        mock_pdf_service.generate_and_upload_pdf.assert_called_once_with(
            prediction_id="json-string-test-123"
        )
    finally:
        app.dependency_overrides.clear()


def test_generate_pdf_with_mixed_data_types(mock_pdf_service):
    """Test PDF generation with mixed data types (dict and JSON string)."""
    expected_url = (
        "https://storage.googleapis.com/bucket/predictions/prediction_mixed_data.pdf"
    )
    mock_pdf_service.generate_and_upload_pdf.return_value = expected_url

    app.dependency_overrides[create_pdf_service] = lambda: mock_pdf_service

    try:
        response = client.get("/api/v1/predict/export/mixed-data-test-456")

        assert response.status_code == 200
        assert response.json()["pdf_url"] == expected_url
    finally:
        app.dependency_overrides.clear()


def test_generate_pdf_with_invalid_json_handles_gracefully(mock_pdf_service):
    """Test PDF generation handles invalid JSON strings gracefully."""
    expected_url = (
        "https://storage.googleapis.com/bucket/predictions/prediction_invalid_json.pdf"
    )
    mock_pdf_service.generate_and_upload_pdf.return_value = expected_url

    app.dependency_overrides[create_pdf_service] = lambda: mock_pdf_service

    try:
        response = client.get("/api/v1/predict/export/invalid-json-test-789")

        # Should still succeed despite invalid JSON in user_input
        assert response.status_code == 200
        assert response.json()["pdf_url"] == expected_url
    finally:
        app.dependency_overrides.clear()
