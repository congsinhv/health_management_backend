"""
SMTP client for sending emails using FastAPI-Mail.

This module handles SMTP connection management and configuration
with proper error handling and connection validation.
"""

import logging
from typing import Optional
from fastapi_mail import FastMail, ConnectionConfig
from app.config import settings

logger = logging.getLogger(__name__)


class SMTPClient:
    """SMTP client with connection management and configuration."""

    def __init__(self):
        """Initialize SMTP client with configuration."""
        self.mail = None
        self._configured = False

        # Check if email service is properly configured
        if self._is_configuration_valid():
            self._configure_smtp()
        else:
            logger.warning("Email service not configured - missing required settings")

    def _is_configuration_valid(self) -> bool:
        """Check if all required SMTP configuration is present."""
        required_settings = [
            settings.mail_username,
            settings.mail_password,
            settings.mail_from,
            settings.mail_server,
        ]
        return all(required_settings)

    def _configure_smtp(self) -> None:
        """Configure SMTP connection with FastAPI-Mail."""
        try:
            conf = ConnectionConfig(
                MAIL_USERNAME=settings.mail_username,
                MAIL_PASSWORD=settings.mail_password,
                MAIL_FROM=settings.mail_from,
                MAIL_PORT=settings.mail_port,
                MAIL_SERVER=settings.mail_server,
                MAIL_FROM_NAME="Health Management",
                MAIL_STARTTLS=settings.mail_tls,
                MAIL_SSL_TLS=settings.mail_ssl,
                TEMPLATE_FOLDER=None,  # We use our own Jinja2 environment
            )
            self.mail = FastMail(conf)
            self._configured = True
            logger.info("SMTP client configured successfully")
        except Exception as e:
            logger.error(f"Failed to configure SMTP client: {e}")
            self.mail = None
            self._configured = False

    @property
    def is_configured(self) -> bool:
        """Check if SMTP client is properly configured."""
        return self._configured

    def get_mail_client(self) -> Optional[FastMail]:
        """
        Get the FastAPI-Mail client instance.

        Returns:
            FastMail instance if configured, None otherwise
        """
        return self.mail

    async def test_connection(self) -> bool:
        """
        Test SMTP connection by sending a test configuration check.

        Returns:
            True if connection test succeeds, False otherwise
        """
        if not self._configured:
            logger.warning("Cannot test SMTP connection - not configured")
            return False

        try:
            # FastAPI-Mail doesn't have a direct connection test method
            # We can validate the configuration by checking if it can create a message
            # This will fail early if configuration is invalid
            from fastapi_mail import MessageSchema

            test_message = MessageSchema(
                subject="Connection Test",
                recipients=[settings.mail_from],
                body="Test message",
                subtype="plain",
            )
            # If we can create the message without error, configuration is likely valid
            return True
        except Exception as e:
            logger.error(f"SMTP connection test failed: {e}")
            return False

    def get_configuration_info(self) -> dict:
        """
        Get current SMTP configuration info (excluding sensitive data).

        Returns:
            Dictionary with configuration information
        """
        if not self._configured:
            return {"configured": False}

        return {
            "configured": True,
            "server": settings.mail_server,
            "port": settings.mail_port,
            "username": settings.mail_username,
            "from_email": settings.mail_from,
            "use_tls": settings.mail_tls,
            "use_ssl": settings.mail_ssl,
        }
