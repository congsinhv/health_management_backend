"""
PDF generation service for health predictions.
"""

import os
import logging
import tempfile
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader
from app.config import settings
from app.utils.gcs_uploader import GCSUploader

logger = logging.getLogger(__name__)


class PDFService:
    """Service for generating PDF reports from prediction data."""

    def __init__(self):
        """Initialize PDF service."""
        self.template_dir = Path(__file__).parent.parent / "templates"
        self.fonts_dir = Path(__file__).parent.parent / "fonts"

        # Initialize Jinja2 environment
        if self.template_dir.exists():
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(self.template_dir)), autoescape=True
            )
        else:
            logger.error(f"Template directory not found: {self.template_dir}")
            self.jinja_env = None

        # Initialize GCS uploader
        self.gcs_uploader = None
        if settings.gcp_public_bucket:
            try:
                self.gcs_uploader = GCSUploader(
                    bucket_name=settings.gcp_public_bucket,
                    project_id=settings.gcp_project_id,
                )
                logger.info("GCS uploader initialized for PDF storage")
            except Exception as e:
                logger.error(f"Failed to initialize GCS uploader: {e}")
                self.gcs_uploader = None

    async def generate_prediction_pdf(
        self, prediction_data: Dict[str, Any], user_input: Dict[str, Any]
    ) -> Optional[str]:
        """
        Generate PDF report from prediction data and upload to GCS.

        Args:
            prediction_data: Prediction response data
            user_input: Original user input data

        Returns:
            Public URL of the uploaded PDF, or None if failed
        """
        try:
            if not self.jinja_env:
                logger.error("Jinja2 environment not initialized")
                return None

            # Render HTML template
            html_content = self._render_template(prediction_data, user_input)
            if not html_content:
                logger.error("Failed to render HTML template")
                return None

            # Generate PDF
            pdf_bytes = self._html_to_pdf(html_content)
            if not pdf_bytes:
                logger.error("Failed to generate PDF")
                return None

            # Upload to GCS
            if self.gcs_uploader:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"prediction_report_{timestamp}.pdf"

                pdf_url = self.gcs_uploader.upload_file(
                    file_content=pdf_bytes,
                    file_name=filename,
                    folder="predictions",
                    content_type="application/pdf",
                    make_public=True,
                )

                logger.info(f"PDF uploaded successfully: {pdf_url}")
                return pdf_url
            else:
                logger.error("GCS uploader not available")
                return None

        except Exception as e:
            logger.error(f"Error generating prediction PDF: {e}")
            return None

    def _render_template(
        self, prediction_data: Dict[str, Any], user_input: Dict[str, Any]
    ) -> Optional[str]:
        """Render HTML template with prediction data."""
        try:
            template = self.jinja_env.get_template("prediction_report.html")

            # Prepare template context
            context = {
                "prediction": prediction_data,
                "user_input": user_input,
                "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "title": "Báo Cáo Sức Khỏe",
            }

            html_content = template.render(**context)
            return html_content

        except Exception as e:
            logger.error(f"Error rendering template: {e}")
            return None

    def _html_to_pdf(self, html_content: str) -> Optional[bytes]:
        """Convert HTML content to PDF using WeasyPrint."""
        try:
            # Create CSS for Vietnamese font support
            css_content = """
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+:wght@400;500;600;700&display=swap');

            @page {
                size: A4;
                margin: 2cm;
            }

            body {
                font-family: 'Noto Sans', Arial, sans-serif;
                font-size: 12px;
                line-height: 1.6;
                color: #333;
            }

            .header {
                text-align: center;
                margin-bottom: 30px;
                border-bottom: 2px solid #4CAF50;
                padding-bottom: 20px;
            }

            .title {
                font-size: 24px;
                font-weight: bold;
                color: #2E7D32;
                margin-bottom: 10px;
            }

            .section {
                margin-bottom: 25px;
            }

            .section-title {
                font-size: 18px;
                font-weight: 600;
                color: #2E7D32;
                margin-bottom: 15px;
                border-left: 4px solid #4CAF50;
                padding-left: 10px;
            }

            .info-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 15px;
                margin-bottom: 20px;
            }

            .info-item {
                background: #f8f9fa;
                padding: 10px;
                border-radius: 5px;
                border-left: 3px solid #4CAF50;
            }

            .info-label {
                font-weight: 600;
                color: #555;
                margin-bottom: 3px;
            }

            .info-value {
                font-size: 14px;
            }

            .metric {
                background: #e8f5e8;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 10px;
                border: 1px solid #c8e6c9;
            }

            .metric-label {
                font-weight: 600;
                color: #2E7D32;
                display: block;
                margin-bottom: 5px;
            }

            .metric-value {
                font-size: 20px;
                font-weight: bold;
                color: #1B5E20;
            }

            .metric-unit {
                font-size: 14px;
                color: #666;
                margin-left: 5px;
            }

            .health-analysis {
                background: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 20px;
            }

            .analysis-paragraph {
                margin-bottom: 10px;
                text-align: justify;
            }

            .plan-section {
                margin-bottom: 20px;
            }

            .day-plan {
                background: #f0f8ff;
                border: 1px solid #bee5eb;
                border-radius: 8px;
                padding: 15px;
                margin-bottom: 15px;
            }

            .day-title {
                font-weight: 600;
                color: #0066cc;
                margin-bottom: 10px;
            }

            .meal-section {
                margin-bottom: 10px;
            }

            .meal-title {
                font-weight: 600;
                color: #495057;
                margin-bottom: 5px;
            }

            .food-item {
                margin-left: 20px;
                margin-bottom: 3px;
            }

            .exercise-item {
                margin-left: 20px;
                margin-bottom: 8px;
            }

            .exercise-name {
                font-weight: 600;
            }

            .exercise-details {
                color: #666;
                font-size: 11px;
            }

            .footer {
                margin-top: 30px;
                text-align: center;
                font-size: 10px;
                color: #666;
                border-top: 1px solid #ddd;
                padding-top: 15px;
            }

            .prediction-badge {
                background: #4CAF50;
                color: white;
                padding: 8px 16px;
                border-radius: 20px;
                font-weight: 600;
                display: inline-block;
                margin-bottom: 15px;
            }

            .confidence {
                background: #2196F3;
                color: white;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 11px;
                margin-left: 10px;
            }

            @media print {
                .page-break {
                    page-break-before: always;
                }
            }
            """

            # Create HTML document with CSS
            html_doc = HTML(string=html_content)
            css_doc = CSS(string=css_content)

            # Generate PDF
            pdf_bytes = html_doc.write_pdf(stylesheets=[css_doc])
            return pdf_bytes

        except Exception as e:
            logger.error(f"Error converting HTML to PDF: {e}")
            return None

    async def get_pdf_url(self, prediction_id: int, user_id: int) -> Optional[str]:
        """
        Get PDF URL for a prediction (placeholder - would need database integration).

        Args:
            prediction_id: ID of the prediction
            user_id: ID of the user requesting the PDF

        Returns:
            PDF URL if available, None otherwise
        """
        # This would typically query the database for the PDF URL
        # For now, return None as this is handled in the repository layer
        return None
