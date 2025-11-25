"""
Email sending functionality using SMTP client and template renderer.

This module handles the composition and sending of emails with proper
error handling, logging, and fallback mechanisms.
"""

import logging
from typing import Optional
from fastapi_mail import MessageSchema
from .smtp_client import SMTPClient
from .template_renderer import EmailTemplateRenderer
from .email_types import EmailMessage
from app.config import settings

logger = logging.getLogger(__name__)


class EmailSender:
    """Email sending with SMTP client and template rendering."""

    def __init__(
        self, smtp_client: SMTPClient, template_renderer: EmailTemplateRenderer
    ):
        """
        Initialize email sender with required dependencies.

        Args:
            smtp_client: Configured SMTP client
            template_renderer: Template renderer for email content
        """
        self.smtp_client = smtp_client
        self.template_renderer = template_renderer

    async def send_email(self, message: EmailMessage) -> bool:
        """
        Send an email message.

        Args:
            message: Email message to send

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.smtp_client.is_configured:
            logger.warning("Cannot send email - SMTP client not configured")
            return False

        try:
            mail_client = self.smtp_client.get_mail_client()
            if not mail_client:
                logger.error("Failed to get mail client instance")
                return False

            # Convert to FastAPI-Mail MessageSchema
            fastmail_message = MessageSchema(
                subject=message.subject,
                recipients=message.recipients,
                body=message.body,
                subtype=message.subtype,
            )

            await mail_client.send_message(fastmail_message)
            logger.info(
                f"Email sent successfully to {len(message.recipients)} recipients"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    async def send_email_verification(
        self,
        email: str,
        first_name: str,
        verification_token: str,
        base_url: str = "http://localhost:3000",
    ) -> bool:
        """
        Send email verification email.

        Args:
            email: Recipient email address
            first_name: User's first name
            verification_token: Verification token
            base_url: Base URL for verification link

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Build verification URL
            verification_url = (
                f"{base_url}/auth/verify-email?token={verification_token}"
            )

            # Render email template
            html_content = self.template_renderer.render_verification_email(
                verification_url=verification_url,
                first_name=first_name,
                expiration_minutes=settings.email_verification_expire_minutes,
            )

            # Create email message
            message = EmailMessage(
                subject="Verify Your Email - Health Management",
                recipients=[email],
                body=html_content,
                subtype="html",
            )

            return await self.send_email(message)

        except Exception as e:
            logger.error(f"Failed to send verification email to {email}: {e}")
            return False

    async def send_password_reset(
        self,
        email: str,
        first_name: str,
        reset_token: str,
        base_url: str = "http://localhost:3000",
    ) -> bool:
        """
        Send password reset email.

        Args:
            email: Recipient email address
            first_name: User's first name
            reset_token: Password reset token
            base_url: Base URL for reset link

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Build reset URL
            reset_url = f"{base_url}/auth/reset-password?token={reset_token}"

            # Render email template
            html_content = self.template_renderer.render_password_reset_email(
                reset_url=reset_url,
                first_name=first_name,
                expiration_minutes=settings.password_reset_expire_minutes,
            )

            # Create email message
            message = EmailMessage(
                subject="Reset Your Password - Health Management",
                recipients=[email],
                body=html_content,
                subtype="html",
            )

            return await self.send_email(message)

        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {e}")
            return False

    async def send_custom_email(
        self, subject: str, recipients: list[str], template_name: str, **context
    ) -> bool:
        """
        Send custom email using specified template.

        Args:
            subject: Email subject
            recipients: List of recipient email addresses
            template_name: Name of the template to use
            **context: Template context variables

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Render custom template
            html_content = self.template_renderer.render_template(
                template_name=template_name, **context
            )

            # Create email message
            message = EmailMessage(
                subject=subject,
                recipients=recipients,
                body=html_content,
                subtype="html",
            )

            return await self.send_email(message)

        except Exception as e:
            logger.error(
                f"Failed to send custom email with template '{template_name}': {e}"
            )
            return False

    def get_sender_info(self) -> dict:
        """
        Get information about the email sender configuration.

        Returns:
            Dictionary with sender configuration info
        """
        return {
            "smtp_configured": self.smtp_client.is_configured,
            "smtp_info": self.smtp_client.get_configuration_info(),
            "available_templates": self.template_renderer.get_available_templates(),
        }
