"""
Constants for prediction service.

This module contains configuration constants, model settings,
and other values used by the prediction service.
"""

# File paths
TEMPLATE_DIR = "app/templates"  # PDF templates directory
FONT_DIR = "app/static/fonts"  # Custom fonts directory

# Default template name
DEFAULT_TEMPLATE_NAME = "prediction_template.html"

# Font configuration
DEFAULT_FONT_FAMILY = "SVN-Gilroy"
FALLBACK_FONT_FAMILY = "DejaVu Sans"

# Vietnamese character range for text processing
VIETNAMESE_UNICODE_RANGE = "U+00C0-U+017F"

# Gender mappings
GENDER_MALE_VARIANTS = ["male", "m", "nam", "đực"]
GENDER_FEMALE_VARIANTS = ["female", "f", "nữ", "cái"]

# PDF generation settings
PDF_PAGE_SIZE = "A4"
PDF_MARGIN = "2cm"
PDF_ENCODING = "UTF-8"
