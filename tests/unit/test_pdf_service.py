"""
Tests for PDF generation service.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from app.services.pdf_service import PdfGeneratorService


@pytest.fixture
def pdf_service(mock_database_pool):
    """Create PdfGeneratorService with mock pool."""
    return PdfGeneratorService(mock_database_pool)


@pytest.fixture
def pdf_service_no_gcs(mock_database_pool):
    """Create PdfGeneratorService without GCS uploader."""
    with patch("app.services.pdf_service.settings") as mock_settings:
        mock_settings.gcp_public_bucket = None
        return PdfGeneratorService(mock_database_pool)


@pytest.mark.asyncio
async def test_prepare_template_context(pdf_service):
    """Test template context preparation."""
    mock_record = Mock()
    mock_record.__getitem__ = lambda self, key: {
        "prediction_id": "test-prediction-123",
        "created_at": Mock(strftime=lambda fmt: "22/11/2025 18:00"),
        "user_input": {"name": "Test User", "gender": "male", "family_history": True},
        "prediction_data": {
            "userInput": {"name": "Test User"},
            "prediction": {"bmi": 22.5, "level": "Normal_Weight", "confidence": 85.0},
            "healthAnalysis": {"paragraphs": ["Good health analysis"]},
            "healthMetrics": {
                "weight": {"value": 75.0, "unit": "kg"},
                "bmi": {"value": 22.5, "unit": ""},
                "height": {"value": 1.75, "unit": "m"},
            },
        },
    }[key]

    context = pdf_service._prepare_template_context(mock_record)

    assert context["prediction_id"] == "test-prediction-123"
    assert "user_input" in context
    assert context["status_class"] == "normal"
    assert context["user_input"]["gender"] == "Nam"
    assert context["user_input"]["familyHistory"] == "Có"


@pytest.mark.asyncio
async def test_prepare_template_context_different_bmi(pdf_service):
    """Test template context with different BMI values."""
    mock_record = Mock()
    mock_record.__getitem__ = lambda self, key: {
        "prediction_id": "test-prediction-123",
        "created_at": Mock(strftime=lambda fmt: "22/11/2025 18:00"),
        "user_input": {"name": "Test User"},
        "prediction_data": {
            "prediction": {"bmi": 32.0},  # Obese
        },
    }[key]

    context = pdf_service._prepare_template_context(mock_record)
    assert context["status_class"] == "danger"


@pytest.mark.asyncio
async def test_render_html(pdf_service):
    """Test HTML rendering."""
    context = {
        "prediction_id": "test-123",
        "created_at": "22/11/2025",
        "user_input": {"name": "Test User", "gender": "Nam"},
        "prediction": {"bmi": 22.5},
        "health_analysis": [],
        "diet_plan": [],
        "workout_plan": [],
        "health_metrics": {},
        "status_class": "normal",
        "fonts": {
            "regular": "/path/to/SVN-Gilroy-Regular.otf",
            "medium": "/path/to/SVN-Gilroy-Medium.otf",
            "semibold": "/path/to/SVN-Gilroy-SemiBold.otf",
            "bold": "/path/to/SVN-Gilroy-Bold.otf",
        },
    }

    html = pdf_service._render_html("prediction_pdf.html", context)

    assert isinstance(html, str)
    # Template renders user info and health content
    assert "VHealth" in html or "Kết quả dự đoán" in html


@pytest.mark.asyncio
async def test_generate_and_upload_pdf_success(pdf_service, mock_connection):
    """Test successful PDF generation and upload."""
    # Mock prediction retrieval
    mock_connection.fetchrow.return_value = {
        "prediction_id": "test-prediction-123",
        "user_input": {"name": "Test User"},
        "prediction_data": {"prediction": {"bmi": 22.5}},
        "created_at": "2025-11-22 10:00:00",
    }

    # Mock PDF generation
    with patch.object(
        pdf_service, "_generate_pdf_bytes", new_callable=AsyncMock
    ) as mock_gen:
        mock_gen.return_value = b"PDF content"

        # Mock GCS upload
        with patch.object(pdf_service.gcs_uploader, "upload_file") as mock_upload:
            mock_upload.return_value = "https://storage.googleapis.com/bucket/file.pdf"

            url = await pdf_service.generate_and_upload_pdf("test-prediction-123")

            assert url is not None
            assert "pdf" in url
            mock_gen.assert_called_once()
            mock_upload.assert_called_once()


@pytest.mark.asyncio
async def test_generate_and_upload_pdf_not_found(pdf_service):
    """Test PDF generation for non-existent prediction."""
    from app.core.shared.exceptions import ResourceNotFoundException
    from app.services.pdf_service import PdfGenerationError

    # Mock the prediction repository to raise ResourceNotFoundException
    pdf_service.prediction_repo = AsyncMock()
    pdf_service.prediction_repo.get_prediction_by_prediction_id.side_effect = (
        ResourceNotFoundException(
            "Prediction not found", details={"prediction_id": "non-existent-prediction"}
        )
    )

    # Service catches all exceptions and re-raises as PdfGenerationError
    with pytest.raises(PdfGenerationError):
        await pdf_service.generate_and_upload_pdf("non-existent-prediction")


@pytest.mark.asyncio
async def test_generate_and_upload_pdf_no_gcs(pdf_service_no_gcs):
    """Test PDF generation when GCS is not configured."""
    from app.services.pdf_service import PdfGenerationError
    from datetime import datetime

    # Mock the prediction repository
    pdf_service_no_gcs.prediction_repo = AsyncMock()
    pdf_service_no_gcs.prediction_repo.get_prediction_by_prediction_id.return_value = {
        "prediction_id": "test-prediction-123",
        "user_input": {},
        "prediction_data": {"prediction": {"bmi": 22.5}},
        "created_at": datetime.now(),
    }

    # Mock PDF generation
    with patch.object(
        pdf_service_no_gcs, "_generate_pdf_bytes", new_callable=AsyncMock
    ) as mock_gen:
        mock_gen.return_value = b"PDF content"

        # Should raise PdfGenerationError when GCS is not available
        with pytest.raises(PdfGenerationError) as exc_info:
            await pdf_service_no_gcs.generate_and_upload_pdf("test-prediction-123")

        assert "GCS uploader not available" in str(exc_info.value)


@pytest.mark.asyncio
async def test_generate_pdf_bytes_success(pdf_service):
    """Test successful PDF bytes generation."""
    from datetime import datetime

    mock_record = Mock()
    mock_record.__getitem__ = lambda self, key: {
        "prediction_id": "test-123",
        "created_at": datetime.now(),
        "user_input": {"name": "Test User"},
        "prediction_data": {
            "userInput": {"name": "Test User"},
            "prediction": {"bmi": 22.5},
            "healthAnalysis": {"paragraphs": []},
            "healthMetrics": {},
        },
    }[key]

    # Mock HTML to PDF conversion using the optimized method
    with patch.object(pdf_service, "_html_to_pdf_optimized") as mock_pdf:
        mock_pdf.return_value = b"PDF bytes"

        result = await pdf_service._generate_pdf_bytes(mock_record)

        assert result == b"PDF bytes"
        mock_pdf.assert_called_once()


@pytest.mark.asyncio
async def test_generate_pdf_bytes_failure(pdf_service):
    """Test PDF generation failure handling."""
    from datetime import datetime
    from app.services.pdf_service import PdfGenerationError

    mock_record = Mock()
    mock_record.__getitem__ = lambda self, key: {
        "prediction_id": "test-123",
        "created_at": datetime.now(),
        "user_input": {"name": "Test User"},
        "prediction_data": {
            "userInput": {"name": "Test User"},
            "prediction": {"bmi": 22.5},
            "healthAnalysis": {"paragraphs": []},
            "healthMetrics": {},
        },
    }[key]

    # Mock HTML to PDF conversion to raise exception
    with patch.object(pdf_service, "_html_to_pdf_optimized") as mock_pdf:
        mock_pdf.side_effect = Exception("PDF generation failed")

        # Should raise PdfGenerationError on failure
        with pytest.raises(PdfGenerationError):
            await pdf_service._generate_pdf_bytes(mock_record)


def test_html_to_pdf(pdf_service):
    """Test HTML to PDF conversion."""
    html_string = """
    <!DOCTYPE html>
    <html>
    <head><title>Test</title></head>
    <body><h1>Test PDF</h1></body>
    </html>
    """

    with patch("app.services.pdf_service.HTML") as mock_html:
        mock_html_instance = Mock()
        mock_html.return_value = mock_html_instance
        mock_html_instance.write_pdf.return_value = b"PDF content"

        result = pdf_service._html_to_pdf(html_string)

        assert result == b"PDF content"
        mock_html.assert_called_once_with(string=html_string)
        mock_html_instance.write_pdf.assert_called_once()


@pytest.mark.asyncio
async def test_prepare_template_context_with_json_strings(pdf_service):
    """Test template context preparation with JSON string data (database storage fix)."""
    mock_record = Mock()
    mock_record.__getitem__ = lambda self, key: {
        "prediction_id": "test-prediction-123",
        "created_at": Mock(strftime=lambda fmt: "22/11/2025 18:00"),
        "user_input": '{"name": "Test User", "gender": "male", "family_history": true, "age": 30}',
        "prediction_data": '{"prediction": {"bmi": 22.5, "level": "Normal_Weight", "confidence": 85.0}, "healthAnalysis": {"paragraphs": ["Good health analysis"]}, "healthMetrics": {"weight": {"value": 75.0, "unit": "kg"}, "bmi": {"value": 22.5, "unit": ""}, "height": {"value": 1.75, "unit": "m"}}}',
    }[key]

    context = pdf_service._prepare_template_context(mock_record)

    assert context["prediction_id"] == "test-prediction-123"
    assert context["user_input"]["name"] == "Test User"
    assert context["user_input"]["gender"] == "Nam"
    assert context["user_input"]["familyHistory"] == "Có"
    assert context["user_input"]["age"] == 30
    assert context["status_class"] == "normal"
    assert context["prediction"]["bmi"] == 22.5
    assert context["health_metrics"]["weight"]["value"] == 75.0


@pytest.mark.asyncio
async def test_prepare_template_context_mixed_data_types(pdf_service):
    """Test template context preparation with mixed data types (dict and JSON string)."""
    mock_record = Mock()
    mock_record.__getitem__ = lambda self, key: {
        "prediction_id": "test-prediction-123",
        "created_at": Mock(strftime=lambda fmt: "22/11/2025 18:00"),
        "user_input": {"name": "Test User", "gender": "male", "age": 30},  # Dictionary
        "prediction_data": '{"prediction": {"bmi": 25.5, "level": "Over_Weight"}, "healthAnalysis": {"paragraphs": []}, "healthMetrics": {}}',  # JSON string
    }[key]

    context = pdf_service._prepare_template_context(mock_record)

    assert context["user_input"]["name"] == "Test User"
    assert context["user_input"]["age"] == 30
    assert context["prediction"]["bmi"] == 25.5
    assert context["status_class"] == "warning"  # BMI 25.5 = overweight


@pytest.mark.asyncio
async def test_prepare_template_context_invalid_json_strings(pdf_service, caplog):
    """Test template context preparation with invalid JSON strings (error handling)."""
    mock_record = Mock()
    mock_record.__getitem__ = lambda self, key: {
        "prediction_id": "test-prediction-123",
        "created_at": Mock(strftime=lambda fmt: "22/11/2025 18:00"),
        "user_input": '{"name": "Test User", "gender": "male"',  # Invalid JSON - missing closing brace
        "prediction_data": '{"prediction": {"bmi": 22.5}}',  # Valid JSON
    }[key]

    # Should not raise exception, but handle gracefully
    context = pdf_service._prepare_template_context(mock_record)

    assert context["prediction_id"] == "test-prediction-123"
    # When JSON parsing fails, error should be logged
    assert any(
        "Failed to parse user_input as JSON" in record.message
        for record in caplog.records
    )
    # user_input is transformed later in the method with default values
    assert isinstance(context["user_input"], dict)
    assert context["prediction"]["bmi"] == 22.5


@pytest.mark.asyncio
async def test_prepare_template_context_both_invalid_json(pdf_service, caplog):
    """Test template context preparation with both user_input and prediction_data as invalid JSON."""
    mock_record = Mock()
    mock_record.__getitem__ = lambda self, key: {
        "prediction_id": "test-prediction-123",
        "created_at": Mock(strftime=lambda fmt: "22/11/2025 18:00"),
        "user_input": "not json at all",  # Invalid JSON
        "prediction_data": '{"prediction": invalid json',  # Invalid JSON
    }[key]

    # Should handle both errors gracefully
    context = pdf_service._prepare_template_context(mock_record)

    assert context["prediction_id"] == "test-prediction-123"
    # Both errors should be logged
    assert any(
        "Failed to parse user_input as JSON" in record.message
        for record in caplog.records
    )
    assert any(
        "Failed to parse prediction_data as JSON" in record.message
        for record in caplog.records
    )
    # user_input is transformed with default values
    assert isinstance(context["user_input"], dict)
    # When prediction_data fails, it should not crash the context preparation
    assert "prediction" in context


@pytest.mark.asyncio
async def test_prepare_template_context_empty_json_strings(pdf_service):
    """Test template context preparation with empty JSON strings."""
    mock_record = Mock()
    mock_record.__getitem__ = lambda self, key: {
        "prediction_id": "test-prediction-123",
        "created_at": Mock(strftime=lambda fmt: "22/11/2025 18:00"),
        "user_input": "{}",  # Empty JSON object as string
        "prediction_data": '{"prediction": {"bmi": 22.5}, "healthAnalysis": {"paragraphs": []}, "healthMetrics": {}}',
    }[key]

    context = pdf_service._prepare_template_context(mock_record)

    assert context["prediction_id"] == "test-prediction-123"
    # Empty dict is valid JSON, user_input is transformed with default values
    assert isinstance(context["user_input"], dict)
    assert context["prediction"]["bmi"] == 22.5
    assert context["status_class"] == "normal"


@pytest.mark.asyncio
async def test_prepare_template_context_null_values(pdf_service):
    """Test template context preparation with null values."""
    mock_record = Mock()
    mock_record.__getitem__ = lambda self, key: {
        "prediction_id": "test-prediction-123",
        "created_at": Mock(strftime=lambda fmt: "22/11/2025 18:00"),
        "user_input": None,  # Null value
        "prediction_data": '{"prediction": {"bmi": 22.5}, "healthAnalysis": {"paragraphs": []}, "healthMetrics": {}}',
    }[key]

    context = pdf_service._prepare_template_context(mock_record)

    assert context["prediction_id"] == "test-prediction-123"
    # Should handle None values gracefully - user_input becomes empty dict
    assert context["user_input"] == {} or isinstance(context["user_input"], dict)
    assert context["prediction"]["bmi"] == 22.5


@pytest.mark.asyncio
async def test_generate_pdf_bytes_with_json_string_data(pdf_service):
    """Test _generate_pdf_bytes method with JSON string data."""
    from datetime import datetime

    # Mock database record with JSON strings
    mock_record = Mock()
    mock_record.__getitem__ = lambda self, key: {
        "prediction_id": "test-prediction-123",
        "created_at": datetime.now(),
        "user_input": '{"name": "John Doe", "gender": "male", "age": 35, "height": 1.80, "weight": 85, "family_history": true}',
        "prediction_data": '{"prediction": {"bmi": 26.2, "level": "Over_Weight", "confidence": 88.0}, "healthAnalysis": {"paragraphs": ["Health risk analysis paragraph"]}, "healthMetrics": {"weight": {"value": 85.0, "unit": "kg"}, "bmi": {"value": 26.2, "unit": ""}, "height": {"value": 1.80, "unit": "m"}}}',
    }[key]

    # Mock HTML to PDF conversion using the optimized method
    with patch.object(pdf_service, "_html_to_pdf_optimized") as mock_pdf:
        mock_pdf.return_value = b"PDF bytes from JSON string data"

        result = await pdf_service._generate_pdf_bytes(mock_record)

        assert result == b"PDF bytes from JSON string data"
        mock_pdf.assert_called_once()


@pytest.mark.asyncio
async def test_init_without_pool():
    """Test PdfGeneratorService initialization without pool."""
    service = PdfGeneratorService(pool=None)

    assert service.pool is None
    assert service.prediction_repo is None
    assert service.jinja_env is not None
