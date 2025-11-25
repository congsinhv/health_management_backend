"""
Email template rendering with Jinja2.

This module handles the rendering of email templates using Jinja2
with proper error handling and template management.
"""

from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateError
from pathlib import Path
from typing import Dict, Any
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class EmailTemplateRenderer:
    """Render email templates using Jinja2."""

    def __init__(self):
        """Initialize the template renderer with email templates directory."""
        template_dir = Path(__file__).parent.parent.parent / "templates" / "email"

        if not template_dir.exists():
            raise FileNotFoundError(
                f"Email templates directory not found: {template_dir}"
            )

        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        logger.info(
            f"Email template renderer initialized with templates from: {template_dir}"
        )

    def render_verification_email(
        self, verification_url: str, first_name: str, expiration_minutes: int
    ) -> str:
        """
        Render email verification template.

        Args:
            verification_url: URL for email verification
            first_name: User's first name
            expiration_minutes: Expiration time in minutes

        Returns:
            Rendered HTML content
        """
        try:
            template = self.env.get_template("verification.html")
            return template.render(
                verification_url=verification_url,
                first_name=first_name,
                expiry_minutes=expiration_minutes,
            )
        except TemplateError as e:
            logger.error(f"Error rendering verification email template: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error rendering verification email: {e}")
            raise

    def render_password_reset_email(
        self, reset_url: str, first_name: str, expiration_minutes: int
    ) -> str:
        """
        Render password reset template.

        Args:
            reset_url: URL for password reset
            first_name: User's first name
            expiration_minutes: Expiration time in minutes

        Returns:
            Rendered HTML content
        """
        try:
            template = self.env.get_template("password_reset.html")
            return template.render(
                reset_url=reset_url,
                first_name=first_name,
                expiry_minutes=expiration_minutes,
            )
        except TemplateError as e:
            logger.error(f"Error rendering password reset email template: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error rendering password reset email: {e}")
            raise

    def render_template(self, template_name: str, **context: Dict[str, Any]) -> str:
        """
        Render any email template with provided context.

        Args:
            template_name: Name of the template file
            **context: Template context variables

        Returns:
            Rendered HTML content
        """
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except TemplateError as e:
            logger.error(f"Error rendering template '{template_name}': {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error rendering template '{template_name}': {e}")
            raise

    def get_available_templates(self) -> list[str]:
        """
        Get list of available email templates.

        Returns:
            List of template names
        """
        try:
            return self.env.list_templates()
        except Exception as e:
            logger.error(f"Error listing templates: {e}")
            return []
