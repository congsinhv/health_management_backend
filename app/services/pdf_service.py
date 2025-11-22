"""
PDF generation service using WeasyPrint.
"""

import logging
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from functools import partial
import asyncpg
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from app.config import settings
from app.utils.gcs_uploader import GCSUploader
from app.db.prediction import PredictionRepository

logger = logging.getLogger(__name__)

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
FONT_DIR = Path(__file__).parent.parent / "static" / "fonts"


class PdfGeneratorService:
    """Service for generating prediction PDFs (PUBLIC - no auth)."""

    def __init__(self, pool: Optional[asyncpg.Pool] = None):
        self.pool = pool
        self.prediction_repo = PredictionRepository(pool) if pool else None
        self.jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

        # GCS uploader (only if configured)
        if hasattr(settings, "gcp_public_bucket") and settings.gcp_public_bucket:
            self.gcs_uploader = GCSUploader(
                bucket_name=settings.gcp_public_bucket,
                project_id=getattr(settings, "gcp_project_id", None),
            )
        else:
            self.gcs_uploader = None
            logger.warning("GCS configuration not found - PDF upload disabled")

    async def generate_and_upload_pdf(self, prediction_id: str) -> Optional[str]:
        """
        Generate PDF for prediction and upload to GCS.

        Args:
            prediction_id: External prediction ID from PredictionResponse.id

        Returns:
            Public GCS URL or None if failed

        Raises:
            ValueError: If prediction not found
        """
        if not self.prediction_repo:
            logger.warning("Prediction repository not available")
            return None

        # 1. Fetch prediction from database (PUBLIC - no user check)
        prediction_record = await self.prediction_repo.get_prediction_by_prediction_id(
            prediction_id
        )

        if not prediction_record:
            raise ValueError(f"Prediction not found: {prediction_id}")

        # 2. Generate PDF bytes
        pdf_bytes = await self._generate_pdf_bytes(prediction_record)

        if not pdf_bytes:
            logger.error(f"Failed to generate PDF for prediction {prediction_id}")
            return None

        # 3. Upload to GCS if available
        if self.gcs_uploader:
            filename = (
                f"prediction_{prediction_id}_{int(datetime.utcnow().timestamp())}.pdf"
            )
            folder = "predictions"

            try:
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
                    f"Generated and uploaded PDF for prediction {prediction_id}: {pdf_url}"
                )
                return pdf_url

            except Exception as e:
                logger.error(
                    f"Failed to upload PDF for prediction {prediction_id}: {e}"
                )
                return None
        else:
            logger.warning("GCS uploader not available - cannot upload PDF")
            return None

    async def _generate_pdf_bytes(
        self, prediction_record: asyncpg.Record
    ) -> Optional[bytes]:
        """
        Generate PDF bytes from prediction record.

        Args:
            prediction_record: Database prediction record

        Returns:
            PDF bytes or None if failed
        """
        try:
            # 1. Prepare template context
            context = self._prepare_template_context(prediction_record)

            # 2. Render HTML
            html_string = self._render_html("prediction_pdf.html", context)

            # 3. Convert to PDF (run in executor - WeasyPrint is synchronous)
            loop = asyncio.get_event_loop()
            pdf_bytes = await loop.run_in_executor(
                None, partial(self._html_to_pdf, html_string)
            )

            return pdf_bytes

        except Exception as e:
            logger.error(f"Error generating PDF: {e}", exc_info=True)
            return None

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

        # Extract health metrics
        health_metrics = prediction_data.get("healthMetrics", {})

        # Map gender for display
        gender_display = "Nam" if user_input.get("gender") == "male" else "Nữ"

        # Map family history for display
        family_history_display = "Có" if user_input.get("family_history") else "Không"

        # Determine status class for CSS styling
        bmi = prediction_data.get("prediction", {}).get("bmi", 0)
        if bmi < 18.5:
            status_class = "warning"  # Underweight
        elif bmi < 25:
            status_class = "normal"  # Normal
        elif bmi < 30:
            status_class = "warning"  # Overweight
        else:
            status_class = "danger"  # Obese

        # Prepare user input display values
        user_input_display = {
            "name": user_input.get("name", "User"),
            "gender": gender_display,
            "age": user_input.get("age", 0),
            "height": user_input.get("height", 0),
            "weight": user_input.get("weight", 0),
            "familyHistory": family_history_display,
            "highCalorieFood": user_input.get("highCalorieFood", "Không có"),
            "vegetableFrequency": user_input.get("vegetableFrequency", "Không có"),
            "waterIntake": user_input.get("waterIntake", "Không có"),
            "mainMeals": user_input.get("mainMeals", 3),
            "snackFrequency": user_input.get("snackFrequency", "Không có"),
            "alcohol": user_input.get("alcohol", "Không có"),
            "physicalActivity": user_input.get("physicalActivity", "Không có"),
            "screenTime": user_input.get("screenTime", "Không có"),
            "transportation": user_input.get("transportation", "Không có"),
            "smoking": user_input.get("smoking", "Không có"),
        }

        return {
            "prediction_id": prediction_record["prediction_id"],
            "created_at": prediction_record["created_at"].strftime("%d/%m/%Y %H:%M"),
            "user_input": user_input_display,
            "prediction": prediction_data.get("prediction", {}),
            "health_analysis": prediction_data.get("healthAnalysis", {}).get(
                "paragraphs", []
            ),
            "diet_plan": prediction_data.get("dietPlan", {}).get("weeklyPlans", []),
            "workout_plan": prediction_data.get("workoutPlan", {}).get(
                "weeklyPlans", []
            ),
            "health_metrics": health_metrics,
            "status_class": status_class,
            "font_path": str(FONT_DIR / "NotoSans-Regular.ttf"),
        }

    def _render_html(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render HTML template with context.

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
        Convert HTML string to PDF bytes using WeasyPrint.

        Args:
            html_string: HTML content

        Returns:
            PDF bytes
        """
        html = HTML(string=html_string)
        return html.write_pdf()
