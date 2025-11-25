"""
Email service for sending verification and notification emails.
"""

import secrets
from typing import Optional
from datetime import datetime, timedelta
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from jinja2 import Environment, FileSystemLoader
from app.config import settings


class EmailService:
    def __init__(self):
        # Check if email service is configured
        if all(
            [
                settings.mail_username,
                settings.mail_password,
                settings.mail_from,
                settings.mail_server,
            ]
        ):
            conf = ConnectionConfig(
                MAIL_USERNAME=settings.mail_username,
                MAIL_PASSWORD=settings.mail_password,
                MAIL_FROM=settings.mail_from,
                MAIL_PORT=settings.mail_port,
                MAIL_SERVER=settings.mail_server,
                MAIL_FROM_NAME="Health Management",  # Default from name
                MAIL_STARTTLS=settings.mail_tls,  # Use mail_tls setting
                MAIL_SSL_TLS=settings.mail_ssl,  # Use mail_ssl setting
                TEMPLATE_FOLDER=None,  # We'll use our own Jinja2 environment
            )
            self.mail = FastMail(conf)
        else:
            self.mail = None

        # Initialize Jinja2 environment with file system loader
        self.template_env = Environment(
            loader=FileSystemLoader(searchpath="app/templates/email")
        )

    def _is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return self.mail is not None

    def _render_template(self, template_name: str, **context) -> str:
        """Render email template with context."""
        template_obj = self.template_env.get_template(template_name)
        return template_obj.render(**context)

    async def send_email_verification(
        self,
        email: str,
        first_name: str,
        verification_token: str,
        base_url: str = "http://localhost:3000",
    ) -> bool:
        """Send email verification email."""
        if not self._is_configured():
            print(
                f"Email service not configured. Verification token for {email}: {verification_token}"
            )
            return False

        try:
            verification_url = (
                f"{base_url}/auth/verify-email?token={verification_token}"
            )

            html_content = self._render_template(
                "verification.html",
                first_name=first_name,
                verification_url=verification_url,
                expiry_minutes=settings.email_verification_expire_minutes,
            )

            message = MessageSchema(
                subject="Verify Your Email - Health Management",
                recipients=[email],
                body=html_content,
                subtype="html",
            )

            await self.mail.send_message(message)
            return True
        except Exception as e:
            print(f"Failed to send verification email to {email}: {e}")
            return False

    async def send_password_reset(
        self,
        email: str,
        first_name: str,
        reset_token: str,
        base_url: str = "http://localhost:3000",
    ) -> bool:
        """Send password reset email."""
        if not self._is_configured():
            print(
                f"Email service not configured. Reset token for {email}: {reset_token}"
            )
            return False

        try:
            reset_url = f"{base_url}/auth/reset-password?token={reset_token}"

            html_content = self._render_template(
                "password_reset.html",
                first_name=first_name,
                reset_url=reset_url,
                expiry_minutes=settings.password_reset_expire_minutes,
            )

            message = MessageSchema(
                subject="Reset Your Password - Health Management",
                recipients=[email],
                body=html_content,
                subtype="html",
            )

            await self.mail.send_message(message)
            return True
        except Exception as e:
            print(f"Failed to send password reset email to {email}: {e}")
            return False

    def generate_secure_token(self, length: int = 32) -> str:
        """Generate a cryptographically secure token."""
        return secrets.token_urlsafe(length)

    def generate_password_reset_token(self, email: str) -> str:
        """Generate a secure password reset token."""
        timestamp = str(int(datetime.now().timestamp()))
        signature = secrets.token_urlsafe(16)
        return f"{timestamp}.{signature}.{secrets.token_hex(8)}"


# Create a global email service instance
email_service = EmailService()
