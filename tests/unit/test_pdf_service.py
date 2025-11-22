"""
Unit tests for PDF service.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
from app.services.pdf_service import PDFService


@pytest.fixture
def sample_prediction_data():
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
            "paragraphs": ["Phân tích sức khỏe 1", "Phân tích sức khỏe 2"]
        },
        "dietPlan": {
            "weeklyPlans": [
                {
                    "day": 1,
                    "breakfast": [
                        {"name": "Bánh mì", "calories": 200, "count": 2, "unit": "cái"}
                    ],
                    "lunch": [
                        {"name": "Cơm gạo", "calories": 300, "count": 1, "unit": "bát"}
                    ],
                    "dinner": [
                        {"name": "Salad", "calories": 150, "count": 1, "unit": "tô"}
                    ],
                    "recommendedFoods": "Rau xanh, trái cây",
                    "foodsToLimit": "Đồ ngọt, đồ chiên rán",
                }
            ]
        },
        "workoutPlan": {
            "weeklyPlans": [
                {
                    "name": "Tập cardio",
                    "day": 1,
                    "exercises": [
                        {
                            "name": "Chạy bộ",
                            "duration": 30,
                            "unit": "phút",
                            "description": "Chạy bộ nhẹ nhàng",
                            "sets": None,
                            "reps": None,
                        },
                        {
                            "name": "Hít đất",
                            "duration": None,
                            "unit": None,
                            "description": "Hít đất cơ bản",
                            "sets": 3,
                            "reps": 15,
                        },
                    ],
                }
            ]
        },
    }


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


class TestPDFService:
    """Test PDF service functionality."""

    def test_pdf_service_init_without_templates(self):
        """Test PDF service initialization when templates directory doesn't exist."""
        with patch("app.services.pdf_service.Path.exists", return_value=False):
            service = PDFService()
            assert service.jinja_env is None

    @patch("app.services.pdf_service.Path.exists")
    @patch("app.services.pdf_service.Environment")
    @patch("app.services.pdf_service.settings")
    def test_pdf_service_init_with_templates(
        self, mock_settings, mock_jinja_env, mock_path_exists
    ):
        """Test PDF service initialization when templates directory exists."""
        # Setup mocks
        mock_path_exists.return_value = True
        mock_settings.gcp_public_bucket = "test-bucket"
        mock_settings.gcp_project_id = "test-project"

        # Mock GCS uploader
        with patch("app.services.pdf_service.GCSUploader") as mock_gcs_uploader:
            service = PDFService()
            mock_jinja_env.assert_called_once()
            mock_gcs_uploader.assert_called_once()

    @patch("app.services.pdf_service.Path.exists")
    @patch("app.services.pdf_service.Environment")
    @patch("app.services.pdf_service.settings")
    @patch("app.services.pdf_service.GCSUploader")
    async def test_generate_prediction_pdf_success(
        self,
        mock_gcs_uploader_class,
        mock_settings,
        mock_jinja_env_class,
        mock_path_exists,
        sample_prediction_data,
        sample_user_input,
    ):
        """Test successful PDF generation and upload."""
        # Setup mocks
        mock_path_exists.return_value = True
        mock_settings.gcp_public_bucket = "test-bucket"
        mock_settings.gcp_project_id = "test-project"

        # Mock Jinja2 template
        mock_template = Mock()
        mock_template.render.return_value = "<html>Test content</html>"
        mock_jinja_env = Mock()
        mock_jinja_env.get_template.return_value = mock_template
        mock_jinja_env_class.return_value = mock_jinja_env

        # Mock GCS uploader
        mock_gcs_uploader = Mock()
        mock_gcs_uploader.upload_file.return_value = "https://example.com/test.pdf"
        mock_gcs_uploader_class.return_value = mock_gcs_uploader

        # Mock WeasyPrint HTML to PDF conversion
        with patch("app.services.pdf_service.HTML") as mock_html:
            mock_html_doc = Mock()
            mock_html.return_value = mock_html_doc
            mock_html_doc.write_pdf.return_value = b"PDF content"

            service = PDFService()
            pdf_url = await service.generate_prediction_pdf(
                prediction_data=sample_prediction_data, user_input=sample_user_input
            )

        # Verify
        assert pdf_url == "https://example.com/test.pdf"
        mock_template.render.assert_called_once()
        mock_gcs_uploader.upload_file.assert_called_once()

    @patch("app.services.pdf_service.Path.exists")
    @patch("app.services.pdf_service.Environment")
    async def test_generate_pdf_without_jinja_env(
        self,
        mock_jinja_env_class,
        mock_path_exists,
        sample_prediction_data,
        sample_user_input,
    ):
        """Test PDF generation when Jinja environment is not initialized."""
        # Setup mocks
        mock_path_exists.return_value = False

        service = PDFService()
        pdf_url = await service.generate_prediction_pdf(
            prediction_data=sample_prediction_data, user_input=sample_user_input
        )

        # Verify
        assert pdf_url is None

    @patch("app.services.pdf_service.Path.exists")
    @patch("app.services.pdf_service.Environment")
    @patch("app.services.pdf_service.settings")
    @patch("app.services.pdf_service.GCSUploader")
    async def test_generate_pdf_without_gcs_uploader(
        self,
        mock_gcs_uploader_class,
        mock_settings,
        mock_jinja_env_class,
        mock_path_exists,
        sample_prediction_data,
        sample_user_input,
    ):
        """Test PDF generation when GCS uploader is not available."""
        # Setup mocks
        mock_path_exists.return_value = True
        mock_settings.gcp_public_bucket = None  # No bucket configured

        mock_jinja_env = Mock()
        mock_jinja_env_class.return_value = mock_jinja_env

        service = PDFService()
        pdf_url = await service.generate_prediction_pdf(
            prediction_data=sample_prediction_data, user_input=sample_user_input
        )

        # Verify
        assert pdf_url is None
        mock_gcs_uploader_class.assert_not_called()

    @patch("app.services.pdf_service.Path.exists")
    @patch("app.services.pdf_service.Environment")
    @patch("app.services.pdf_service.settings")
    @patch("app.services.pdf_service.GCSUploader")
    async def test_generate_pdf_template_render_error(
        self,
        mock_gcs_uploader_class,
        mock_settings,
        mock_jinja_env_class,
        mock_path_exists,
        sample_prediction_data,
        sample_user_input,
    ):
        """Test PDF generation when template rendering fails."""
        # Setup mocks
        mock_path_exists.return_value = True
        mock_settings.gcp_public_bucket = "test-bucket"
        mock_settings.gcp_project_id = "test-project"

        # Mock Jinja2 template to raise exception
        mock_template = Mock()
        mock_template.render.side_effect = Exception("Template render error")
        mock_jinja_env = Mock()
        mock_jinja_env.get_template.return_value = mock_template
        mock_jinja_env_class.return_value = mock_jinja_env

        mock_gcs_uploader = Mock()
        mock_gcs_uploader_class.return_value = mock_gcs_uploader

        service = PDFService()
        pdf_url = await service.generate_prediction_pdf(
            prediction_data=sample_prediction_data, user_input=sample_user_input
        )

        # Verify
        assert pdf_url is None
        mock_gcs_uploader.upload_file.assert_not_called()

    @patch("app.services.pdf_service.Path.exists")
    @patch("app.services.pdf_service.Environment")
    @patch("app.services.pdf_service.settings")
    @patch("app.services.pdf_service.GCSUploader")
    async def test_generate_pdf_weasyprint_error(
        self,
        mock_gcs_uploader_class,
        mock_settings,
        mock_jinja_env_class,
        mock_path_exists,
        sample_prediction_data,
        sample_user_input,
    ):
        """Test PDF generation when WeasyPrint fails."""
        # Setup mocks
        mock_path_exists.return_value = True
        mock_settings.gcp_public_bucket = "test-bucket"
        mock_settings.gcp_project_id = "test-project"

        # Mock Jinja2 template
        mock_template = Mock()
        mock_template.render.return_value = "<html>Test content</html>"
        mock_jinja_env = Mock()
        mock_jinja_env.get_template.return_value = mock_template
        mock_jinja_env_class.return_value = mock_jinja_env

        mock_gcs_uploader = Mock()
        mock_gcs_uploader_class.return_value = mock_gcs_uploader

        # Mock WeasyPrint to raise exception
        with patch("app.services.pdf_service.HTML") as mock_html:
            mock_html.side_effect = Exception("WeasyPrint error")

            service = PDFService()
            pdf_url = await service.generate_prediction_pdf(
                prediction_data=sample_prediction_data, user_input=sample_user_input
            )

        # Verify
        assert pdf_url is None
        mock_gcs_uploader.upload_file.assert_not_called()

    @patch("app.services.pdf_service.Path.exists")
    @patch("app.services.pdf_service.Environment")
    @patch("app.services.pdf_service.settings")
    @patch("app.services.pdf_service.GCSUploader")
    async def test_generate_pdf_gcs_upload_error(
        self,
        mock_gcs_uploader_class,
        mock_settings,
        mock_jinja_env_class,
        mock_path_exists,
        sample_prediction_data,
        sample_user_input,
    ):
        """Test PDF generation when GCS upload fails."""
        # Setup mocks
        mock_path_exists.return_value = True
        mock_settings.gcp_public_bucket = "test-bucket"
        mock_settings.gcp_project_id = "test-project"

        # Mock Jinja2 template
        mock_template = Mock()
        mock_template.render.return_value = "<html>Test content</html>"
        mock_jinja_env = Mock()
        mock_jinja_env.get_template.return_value = mock_template
        mock_jinja_env_class.return_value = mock_jinja_env

        # Mock GCS uploader to raise exception
        mock_gcs_uploader = Mock()
        mock_gcs_uploader.upload_file.side_effect = Exception("Upload failed")
        mock_gcs_uploader_class.return_value = mock_gcs_uploader

        # Mock WeasyPrint HTML to PDF conversion
        with patch("app.services.pdf_service.HTML") as mock_html:
            mock_html_doc = Mock()
            mock_html.return_value = mock_html_doc
            mock_html_doc.write_pdf.return_value = b"PDF content"

            service = PDFService()
            pdf_url = await service.generate_prediction_pdf(
                prediction_data=sample_prediction_data, user_input=sample_user_input
            )

        # Verify
        assert pdf_url is None
        mock_gcs_uploader.upload_file.assert_called_once()

    @patch("app.services.pdf_service.Path.exists")
    @patch("app.services.pdf_service.Environment")
    def test_render_template_success(
        self,
        mock_jinja_env_class,
        mock_path_exists,
        sample_prediction_data,
        sample_user_input,
    ):
        """Test successful template rendering."""
        # Setup mocks
        mock_path_exists.return_value = True

        # Mock Jinja2 template
        mock_template = Mock()
        expected_html = "<html>Rendered content</html>"
        mock_template.render.return_value = expected_html
        mock_jinja_env = Mock()
        mock_jinja_env.get_template.return_value = mock_template
        mock_jinja_env_class.return_value = mock_jinja_env

        service = PDFService()
        html_content = service._render_template(
            prediction_data=sample_prediction_data, user_input=sample_user_input
        )

        # Verify
        assert html_content == expected_html
        mock_jinja_env.get_template.assert_called_with("prediction_report.html")

        # Verify template context
        call_args = mock_template.render.call_args[1]
        assert "prediction" in call_args
        assert "user_input" in call_args
        assert "generated_at" in call_args
        assert "title" in call_args
        assert call_args["title"] == "Báo Cáo Sức Khỏe"

    @patch("app.services.pdf_service.Path.exists")
    @patch("app.services.pdf_service.Environment")
    def test_render_template_error(
        self,
        mock_jinja_env_class,
        mock_path_exists,
        sample_prediction_data,
        sample_user_input,
    ):
        """Test template rendering when error occurs."""
        # Setup mocks
        mock_path_exists.return_value = True

        # Mock Jinja2 environment to raise exception
        mock_jinja_env = Mock()
        mock_jinja_env.get_template.side_effect = Exception("Template error")
        mock_jinja_env_class.return_value = mock_jinja_env

        service = PDFService()
        html_content = service._render_template(
            prediction_data=sample_prediction_data, user_input=sample_user_input
        )

        # Verify
        assert html_content is None

    def test_html_to_pdf_success(self):
        """Test successful HTML to PDF conversion."""
        html_content = "<html><body>Test content</body></html>"

        # Mock WeasyPrint
        with patch("app.services.pdf_service.HTML") as mock_html, patch(
            "app.services.pdf_service.CSS"
        ) as mock_css:
            mock_html_doc = Mock()
            mock_html.return_value = mock_html_doc
            mock_html_doc.write_pdf.return_value = b"PDF content"

            mock_css_doc = Mock()
            mock_css.return_value = mock_css_doc

            service = PDFService()
            pdf_bytes = service._html_to_pdf(html_content)

            # Verify
            assert pdf_bytes == b"PDF content"
            mock_html.assert_called_once_with(string=html_content)
            mock_css.assert_called_once()

    def test_html_to_pdf_error(self):
        """Test HTML to PDF conversion when error occurs."""
        html_content = "<html><body>Test content</body></html>"

        # Mock WeasyPrint to raise exception
        with patch("app.services.pdf_service.HTML") as mock_html:
            mock_html.side_effect = Exception("Conversion error")

            service = PDFService()
            pdf_bytes = service._html_to_pdf(html_content)

            # Verify
            assert pdf_bytes is None

    async def test_get_pdf_url_placeholder(self):
        """Test get_pdf_url method (placeholder)."""
        service = PDFService()
        pdf_url = await service.get_pdf_url(prediction_id=1, user_id=1)
        assert pdf_url is None  # Placeholder implementation returns None
