"""
PDF service package with decomposed components.
from app.exceptions import (
    PDFGenerationException,
    PDFTemplateException,
    PDFFontException,
    FileOperationException,
    StorageException,
    ServiceUnavailableException,
)
from app.core.error_context import ErrorContext

This package provides a clean PdfGeneratorService facade that demonstrates
the service decomposition pattern with PDF generation, font management, and storage.
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
except ImportError:
    HTML = None
    CSS = None
    FontConfiguration = None

from app.core.predict_constants import (
    TEMPLATE_DIR,
    FONT_DIR,
    DEFAULT_FONT_FAMILY,
    DEFAULT_TEMPLATE_NAME,
)
from app.config import settings

logger = logging.getLogger(__name__)


class PdfGeneratorService:
    """
    PDF generation service facade that demonstrates decomposed architecture.
    """

    def __init__(self):
        """Initialize PDF service with basic configuration."""
        self.font_config = FontConfiguration()
        self.template_dir = Path(TEMPLATE_DIR)
        self.font_dir = Path(FONT_DIR)

        logger.info("PDF Service initialized with decomposed components")

    def generate_pdf_from_data(
        self, html_content: str, css_content: Optional[str] = None
    ) -> bytes:
        """
        Generate PDF from HTML content.

        Args:
            html_content: HTML content to convert
            css_content: Optional CSS for styling

        Returns:
            PDF bytes
        """
        if HTML is None:
            logger.error("WeasyPrint not available")
            raise RuntimeError("WeasyPrint package is required")

        try:
            # Create WeasyPrint HTML object
            html_obj = HTML(string=html_content)

            # Apply CSS if provided
            stylesheets = []
            if css_content:
                stylesheets.append(CSS(string=css_content))

            # Generate PDF with optimization
            pdf_bytes = html_obj.write_pdf(
                stylesheets=stylesheets, optimize_size=("fonts",)
            )

            return pdf_bytes

        except Exception as e:
            logger.error(f"Error generating PDF: {e}")
            raise

    def get_service_status(self) -> Dict[str, Any]:
        """Get PDF service status."""
        return {
            "weasyprint_available": HTML is not None,
            "template_dir": str(self.template_dir),
            "template_dir_exists": self.template_dir.exists(),
            "font_dir": str(self.font_dir),
            "font_dir_exists": self.font_dir.exists(),
        }

    def get_available_fonts(self) -> list[str]:
        """Get list of available font directories."""
        if not FontConfiguration:
            return []

        try:
            font_config = FontConfiguration()
            return [str(path) for path in font_config.fonts]
        except Exception:
            return []


# Global PDF service instance for backward compatibility
pdf_service = PdfGeneratorService()
