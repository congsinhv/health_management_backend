"""
Email service package with decomposed components.
from app.exceptions import (
    EmailException,
    EmailConfigurationException,
    EmailSendException,
    EmailTemplateException,
    ServiceUnavailableException,
)
from app.core.error_context import ErrorContext

This package provides a clean EmailService facade that internally
uses specialized components for SMTP, template rendering, and email sending.
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional

from .smtp_client import SMTPClient
from .template_renderer import EmailTemplateRenderer
from .email_sender import EmailSender
from .email_types import EmailVerificationData, PasswordResetData, TokenData

import logging

logger = logging.getLogger(__name__)


class EmailService:
    """
    Email service facade that provides backward compatibility while using
    decomposed components internally.
    """

    def __init__(self):
        """Initialize email service with decomposed components."""
        try:
            self.smtp_client = SMTPClient()
            self.template_renderer = EmailTemplateRenderer()
            self.email_sender = EmailSender(self.smtp_client, self.template_renderer)
            logger.info(
                "Email service initialized successfully with decomposed components"
            )
        except Exception as e:
            logger.error(f"Failed to initialize email service: {e}")
            self.smtp_client = None
            self.template_renderer = None
            self.email_sender = None

    def _is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return (
            self.smtp_client is not None
            and self.template_renderer is not None
            and self.email_sender is not None
            and self.smtp_client.is_configured
        )

    def _render_template(self, template_name: str, **context) -> str:
        """Render email template with context."""
        if not self.template_renderer:
            raise RuntimeError("Template renderer not initialized")

        return self.template_renderer.render_template(template_name, **context)

    async def send_email_verification(
        self,
        email: str,
        first_name: str,
        verification_token: str,
        base_url: str = "http://localhost:3000",
    ) -> bool:
        """Send email verification email."""
        if not self._is_configured():
            logger.warning(
                f"Email service not configured. Verification token for {email}: {verification_token}"
            )
            return False

        return await self.email_sender.send_email_verification(
            email=email,
            first_name=first_name,
            verification_token=verification_token,
            base_url=base_url,
        )

    async def send_password_reset(
        self,
        email: str,
        first_name: str,
        reset_token: str,
        base_url: str = "http://localhost:3000",
    ) -> bool:
        """Send password reset email."""
        if not self._is_configured():
            logger.warning(
                f"Email service not configured. Reset token for {email}: {reset_token}"
            )
            return False

        return await self.email_sender.send_password_reset(
            email=email,
            first_name=first_name,
            reset_token=reset_token,
            base_url=base_url,
        )

    def generate_secure_token(self, length: int = 32) -> str:
        """Generate a cryptographically secure token."""
        return secrets.token_urlsafe(length)

    def generate_password_reset_token(self, email: str) -> str:
        """Generate a secure password reset token."""
        timestamp = str(int(datetime.now().timestamp()))
        signature = secrets.token_urlsafe(16)
        return f"{timestamp}.{signature}.{secrets.token_hex(8)}"

    def get_service_status(self) -> dict:
        """Get comprehensive status of the email service."""
        if not self._is_configured():
            return {
                "configured": False,
                "components": {
                    "smtp_client": self.smtp_client is not None,
                    "template_renderer": self.template_renderer is not None,
                    "email_sender": self.email_sender is not None,
                },
            }

        return {
            "configured": True,
            "components": {
                "smtp_client": self.smtp_client is not None,
                "template_renderer": self.template_renderer is not None,
                "email_sender": self.email_sender is not None,
            },
            "smtp_info": self.smtp_client.get_configuration_info(),
            "available_templates": self.template_renderer.get_available_templates(),
        }


# Create global email service instance for backward compatibility
email_service = EmailService()
