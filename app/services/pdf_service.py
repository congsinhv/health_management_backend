"""
PDF generation service using WeasyPrint.
"""

import logging
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Union
from functools import partial
from concurrent.futures import ThreadPoolExecutor
import asyncpg
from jinja2 import Environment, FileSystemLoader, TemplateError
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration
from app.config import settings
from app.utils.gcs_uploader import GCSUploader
from app.db.prediction import PredictionRepository

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
FONT_DIR = Path(__file__).parent.parent / "static" / "fonts"


class PdfGenerationError(Exception):
    """Custom exception for PDF generation errors."""

    def __init__(self, message: str, prediction_id: str, error_type: str = "general", context: Optional[Dict] = None):
        self.message = message
        self.prediction_id = prediction_id
        self.error_type = error_type
        self.context = context or {}
        super().__init__(self.message)


class PdfGeneratorService:
    """Enhanced service for generating prediction PDFs (PUBLIC - no auth)."""

    def __init__(self, pool: Optional[asyncpg.Pool] = None):
        self.pool = pool
        self.prediction_repo = PredictionRepository(pool) if pool else None
        self.jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

        # Thread pool for PDF generation (limit concurrent operations)
        self.executor_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="pdf_gen")

        # Font configuration for better font handling
        self.font_config = FontConfiguration()

        # GCS uploader (only if configured)
        if hasattr(settings, "gcp_public_bucket") and settings.gcp_public_bucket:
            self.gcs_uploader = GCSUploader(
                bucket_name=settings.gcp_public_bucket,
                project_id=getattr(settings, "gcp_project_id", None),
            )
        else:
            self.gcs_uploader = None
            logger.warning("GCS configuration not found - PDF upload disabled")

    async def generate_and_upload_pdf(self, prediction_id: str, template_version: str = "v2") -> Optional[str]:
        """
        Generate PDF for prediction and upload to GCS.

        Args:
            prediction_id: External prediction ID from PredictionResponse.id
            template_version: Template version to use ("v1" for original, "v2" for improved)

        Returns:
            Public GCS URL or None if failed

        Raises:
            ValueError: If prediction not found
            PdfGenerationError: If PDF generation fails
        """
        if not self.prediction_repo:
            raise PdfGenerationError(
                "Prediction repository not available",
                prediction_id,
                "infrastructure"
            )

        try:
            # 1. Fetch prediction from database (PUBLIC - no user check)
            prediction_record = await self.prediction_repo.get_prediction_by_prediction_id(
                prediction_id
            )

            if not prediction_record:
                raise PdfGenerationError(
                    f"Prediction not found: {prediction_id}",
                    prediction_id,
                    "not_found"
                )

            # 2. Generate PDF bytes with error handling
            pdf_bytes = await self._generate_pdf_bytes(prediction_record, template_version)

            if not pdf_bytes:
                raise PdfGenerationError(
                    "Failed to generate PDF bytes",
                    prediction_id,
                    "generation_failed"
                )

            # 3. Upload to GCS if available
            if self.gcs_uploader:
                timestamp = int(datetime.utcnow().timestamp())
                filename = f"prediction_{prediction_id}_{timestamp}.pdf"
                folder = "predictions"

                pdf_url = self.gcs_uploader.upload_file(
                    file_content=pdf_bytes,
                    file_name=filename,
                    folder=folder,
                    content_type="application/pdf",
                    make_public=True,
                )

                # 4. Update prediction record with PDF URL
                await self.prediction_repo.update_pdf_url(prediction_id, pdf_url)

                logger.info(
                    f"✅ Successfully generated and uploaded PDF for prediction {prediction_id}: {pdf_url}"
                )
                return pdf_url
            else:
                raise PdfGenerationError(
                    "GCS uploader not available - cannot upload PDF",
                    prediction_id,
                    "infrastructure"
                )

        except PdfGenerationError:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error in generate_and_upload_pdf for {prediction_id}: {e}", exc_info=True)
            raise PdfGenerationError(
                f"Unexpected error: {str(e)}",
                prediction_id,
                "unexpected",
                {"original_error": str(e)}
            )

    async def _generate_pdf_bytes(
        self, prediction_record: asyncpg.Record, template_version: str = "v2"
    ) -> Optional[bytes]:
        """
        Generate PDF bytes from prediction record.

        Args:
            prediction_record: Database prediction record
            template_version: Template version to use

        Returns:
            PDF bytes

        Raises:
            PdfGenerationError: If PDF generation fails
        """
        prediction_id = prediction_record["prediction_id"]

        try:
            # 1. Prepare template context with validation
            context = self._prepare_template_context(prediction_record)

            # 2. Determine template name
            template_name = "prediction_pdf_v2.html" if template_version == "v2" else "prediction_pdf.html"

            # 3. Render HTML with template validation
            html_string = await self._render_html_safe(template_name, context)

            # 4. Convert to PDF using thread pool (better performance and error handling)
            pdf_bytes = await asyncio.get_event_loop().run_in_executor(
                self.executor_pool,
                partial(self._html_to_pdf_optimized, html_string)
            )

            if not pdf_bytes:
                raise PdfGenerationError(
                    "PDF generation returned empty result",
                    prediction_id,
                    "generation_failed"
                )

            logger.info(f"✅ Successfully generated PDF bytes for {prediction_id} using {template_name}")
            return pdf_bytes

        except TemplateError as e:
            logger.error(f"Template error for {prediction_id}: {e}")
            raise PdfGenerationError(
                f"Template rendering failed: {str(e)}",
                prediction_id,
                "template_error",
                {"template_name": template_name}
            )
        except Exception as e:
            logger.error(f"Error generating PDF for {prediction_id}: {e}", exc_info=True)
            raise PdfGenerationError(
                f"PDF generation failed: {str(e)}",
                prediction_id,
                "generation_failed",
                {"error_type": type(e).__name__}
            )

    def _prepare_template_context(
        self, prediction_record: asyncpg.Record
    ) -> Dict[str, Any]:
        """
        Prepare Jinja2 template context from prediction record.

        Args:
            prediction_record: Database record

        Returns:
            Template context dict
        """
        user_input = prediction_record["user_input"]
        prediction_data = prediction_record["prediction_data"]

        # Handle JSON strings that might be stored in database
        if user_input is None:
            user_input = {}
        elif isinstance(user_input, str):
            try:
                user_input = json.loads(user_input)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse user_input as JSON: {user_input}")
                user_input = {"error": "Invalid user input data"}

        if prediction_data is None:
            prediction_data = {}
        elif isinstance(prediction_data, str):
            try:
                prediction_data = json.loads(prediction_data)
            except json.JSONDecodeError:
                logger.error(
                    f"Failed to parse prediction_data as JSON: {prediction_data}"
                )
                prediction_data = {"error": "Invalid prediction data"}

        # Extract health metrics with fallback to calculation
        health_metrics = prediction_data.get("health_metrics", prediction_data.get("healthMetrics", {}))
        if not health_metrics:
            # Calculate basic metrics if not available
            weight = user_input.get("weight", 0)
            height = user_input.get("height", 0)
            if weight and height:
                bmi = weight / (height ** 2)
                health_metrics = {
                    "weight": weight,
                    "height": height,
                    "bmi": round(bmi, 1)
                }

        # Enhanced gender mapping
        gender = user_input.get("gender", "male")
        if gender.lower() in ["male", "m", "nam"]:
            gender_display = "Nam"
        elif gender.lower() in ["female", "f", "nữ"]:
            gender_display = "Nữ"
        else:
            gender_display = gender

        # Enhanced family history mapping
        family_history = user_input.get("family_history")
        if isinstance(family_history, bool):
            family_history_display = "Có" if family_history else "Không"
        else:
            family_history_display = family_history or "Không"

        # Determine status class for CSS styling (optional, can be used for styling)
        # Safely extract BMI value with robust type checking
        bmi = None

        # Try to get BMI from health_metrics first
        if isinstance(health_metrics, dict):
            bmi_candidate = health_metrics.get("bmi")
            # Only set BMI if it's a valid type
            if isinstance(bmi_candidate, (int, float, str)):
                bmi = bmi_candidate
        elif isinstance(health_metrics, (int, float)):
            # If health_metrics itself is the BMI value
            bmi = health_metrics

        # If still no BMI, try to get from prediction_data
        if bmi is None:
            if isinstance(prediction_data, dict):
                prediction = prediction_data.get("prediction", {})
                if isinstance(prediction, dict):
                    bmi = prediction.get("bmi")

        # Convert to float if possible, default to 0
        if bmi is not None:
            # Check if BMI is a numeric type or string that can be converted
            if isinstance(bmi, (int, float)):
                bmi = float(bmi)
            elif isinstance(bmi, str):
                try:
                    bmi = float(bmi)
                except ValueError:
                    bmi = 0.0
            else:
                # BMI is not a valid type (dict, list, etc.), set to 0
                bmi = 0.0
        else:
            bmi = 0.0

        if bmi < 18.5:
            status_class = "warning"  # Underweight
        elif bmi < 25:
            status_class = "normal"  # Normal
        elif bmi < 30:
            status_class = "warning"  # Overweight
        else:
            status_class = "danger"  # Obese

        # Enhanced user input display values with better defaults
        user_input_display = {
            "name": user_input.get("name", "Người dùng"),
            "gender": gender_display,
            "age": user_input.get("age", 0),
            "height": user_input.get("height", 0),
            "weight": user_input.get("weight", 0),
            "familyHistory": family_history_display,
            "highCalorieFood": self._map_boolean_display(user_input.get("frequent_high_calorie"), "Có", "Không"),
            "vegetableFrequency": user_input.get("frequent_vegetables", "Thỉnh thoảng"),
            "waterIntake": user_input.get("daily_water", "1-2L"),
            "mainMeals": user_input.get("main_meals_daily", 3),
            "snackFrequency": self._map_boolean_display(user_input.get("snacks_between_meals"), "Có", "Không"),
            "alcohol": self._map_boolean_display(user_input.get("alcohol"), "Có", "Không"),
            "physicalActivity": self._map_boolean_display(user_input.get("frequent_exercise"), "Có", "Không"),
            "screenTime": user_input.get("screen_time_daily", "2-4h"),
            "transportation": user_input.get("main_transport", "Xe máy"),
            "smoking": self._map_boolean_display(user_input.get("smoking"), "Có", "Không"),
        }

        # Extract prediction data with fallbacks
        prediction = prediction_data.get("prediction", {})
        if not prediction:
            # Create basic prediction structure if missing
            prediction = {
                "prediction_level": "Bình thường",
                "confidence": 75.0,
                "bmi": health_metrics.get("bmi", 22.5),
                "risk_factors": [],
                "recommendations": []
            }

        # Extract health analysis with multiple fallback locations
        health_analysis = []
        if "health_analysis" in prediction_data:
            if isinstance(prediction_data["health_analysis"], list):
                health_analysis = prediction_data["health_analysis"]
        elif "healthAnalysis" in prediction_data:
            health_analysis_obj = prediction_data["healthAnalysis"]
            if isinstance(health_analysis_obj, dict) and "paragraphs" in health_analysis_obj:
                health_analysis = health_analysis_obj["paragraphs"]
            elif isinstance(health_analysis_obj, list):
                health_analysis = health_analysis_obj

        return {
            "prediction_id": prediction_record["prediction_id"],
            "created_at": prediction_record["created_at"].strftime("%d/%m/%Y %H:%M"),
            "user_input": user_input_display,
            "prediction": prediction,
            "health_analysis": health_analysis,
            "health_metrics": health_metrics,
            "status_class": status_class,
            "font_path": str(FONT_DIR / "NotoSans-Regular.ttf"),
        }

    def _map_boolean_display(self, value: Any, true_value: str = "Có", false_value: str = "Không") -> str:
        """Helper function to map boolean values to display strings."""
        if isinstance(value, bool):
            return true_value if value else false_value
        if isinstance(value, str):
            if value.lower() in ["true", "yes", "có", "1"]:
                return true_value
            elif value.lower() in ["false", "no", "không", "0"]:
                return false_value
        return str(value) if value is not None else false_value

    async def _render_html_safe(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render HTML template with context and error handling.

        Args:
            template_name: Template filename
            context: Template context

        Returns:
            Rendered HTML string

        Raises:
            TemplateError: If template rendering fails
        """
        try:
            template = self.jinja_env.get_template(template_name)
            return template.render(context)
        except Exception as e:
            logger.error(f"Failed to render template {template_name}: {e}")
            raise TemplateError(f"Template rendering failed: {str(e)}")

    def _html_to_pdf_optimized(self, html_string: str) -> bytes:
        """
        Convert HTML string to PDF bytes using WeasyPrint with optimizations.

        Args:
            html_string: HTML content

        Returns:
            PDF bytes

        Raises:
            Exception: If PDF generation fails
        """
        try:
            # Create HTML object with optimizations
            html = HTML(string=html_string)

            # Use optimized CSS for better PDF generation
            css = CSS(string="""
                @page {
                    margin: 1.5cm;
                    size: A4 portrait;
                }

                * {
                    -webkit-print-color-adjust: exact !important;
                    print-color-adjust: exact !important;
                }

                body {
                    font-family: "DejaVu Sans", "Noto Sans", sans-serif;
                }
            """)

            # Generate PDF with font configuration and CSS
            pdf_bytes = html.write_pdf(
                stylesheets=[css],
                font_config=self.font_config,
                optimize_images=True
            )

            return pdf_bytes

        except Exception as e:
            logger.error(f"Failed to convert HTML to PDF: {e}", exc_info=True)
            raise Exception(f"PDF conversion failed: {str(e)}")

    def _render_html(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render HTML template with context (legacy method for backward compatibility).

        Args:
            template_name: Template filename
            context: Template context

        Returns:
            Rendered HTML string
        """
        template = self.jinja_env.get_template(template_name)
        return template.render(context)

    def _html_to_pdf(self, html_string: str) -> bytes:
        """
        Convert HTML string to PDF bytes using WeasyPrint (legacy method).

        Args:
            html_string: HTML content

        Returns:
            PDF bytes
        """
        from weasyprint.text.fonts import FontConfiguration

        # Enable font configuration for better font handling
        font_config = FontConfiguration()
        html = HTML(string=html_string)
        return html.write_pdf(font_config=font_config)

    async def cleanup(self):
        """Clean up resources when the service is shut down."""
        if hasattr(self, 'executor_pool'):
            self.executor_pool.shutdown(wait=True)
        logger.info("PDF generator service cleaned up")
