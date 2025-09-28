"""
Email service for sending verification and notification emails.
"""

import secrets
from typing import Optional
from datetime import datetime, timedelta
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from jinja2 import Environment, BaseLoader
from app.config import settings


# Email templates
EMAIL_VERIFICATION_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Verify Your Email - Health Management</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f4f4f4; }
        .container { max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; }
        .header { text-align: center; margin-bottom: 30px; }
        .logo { font-size: 28px; font-weight: bold; color: #2563eb; }
        .content { line-height: 1.6; color: #333; }
        .button { display: inline-block; padding: 12px 30px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
        .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🏥 Health Management</div>
        </div>
        <div class="content">
            <h2>Welcome, {{ first_name }}!</h2>
            <p>Thank you for registering with Health Management. To complete your registration and secure your account, please verify your email address by clicking the button below:</p>
            <a href="{{ verification_url }}" class="button">Verify Email Address</a>
            <p>If the button doesn't work, you can copy and paste this link into your browser:</p>
            <p><a href="{{ verification_url }}">{{ verification_url }}</a></p>
            <p><strong>This verification link will expire in {{ expiry_minutes }} minutes.</strong></p>
            <p>If you didn't create an account with us, please ignore this email.</p>
        </div>
        <div class="footer">
            <p>This is an automated email from Health Management. Please do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
"""

PASSWORD_RESET_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Password Reset - HealthCare Pro</title>
    <style>
      /* Reset and base styles */
      * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
      }

      body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
          Oxygen, Ubuntu, Cantarell, sans-serif;
        line-height: 1.6;
        color: #1a1a1a;
        background-color: #f8f9fa;
        margin: 0;
        padding: 0;
        -webkit-text-size-adjust: 100%;
        -ms-text-size-adjust: 100%;
      }

      /* Container */
      .email-container {
        max-width: 600px;
        margin: 0 auto;
        background-color: #ffffff;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1),
          0 2px 4px -1px rgba(0, 0, 0, 0.06);
      }

      /* Header */
      .header {
        background: linear-gradient(135deg, #0f766e 0%, #14b8a6 100%);
        padding: 32px 40px;
        text-align: center;
      }

      .logo {
        font-size: 28px;
        font-weight: 700;
        color: #ffffff;
        letter-spacing: -0.025em;
        margin-bottom: 8px;
      }

      .tagline {
        color: #a7f3d0;
        font-size: 14px;
        font-weight: 500;
        letter-spacing: 0.025em;
        text-transform: uppercase;
      }

      /* Content */
      .content {
        padding: 40px;
      }

      .content h1 {
        font-size: 24px;
        font-weight: 700;
        color: #1a1a1a;
        margin-bottom: 24px;
        letter-spacing: -0.025em;
        line-height: 1.3;
      }

      .greeting {
        font-size: 16px;
        color: #374151;
        margin-bottom: 20px;
        font-weight: 500;
      }

      .content p {
        font-size: 16px;
        color: #4b5563;
        margin-bottom: 20px;
        line-height: 1.7;
      }

      /* Button */
      .button-container {
        text-align: center;
        margin: 32px 0;
      }

      .button {
        display: inline-block;
        padding: 16px 32px;
        background: linear-gradient(135deg, #0f766e 0%, #14b8a6 100%);
        color: #ffffff;
        text-decoration: none;
        border-radius: 8px;
        font-weight: 600;
        font-size: 16px;
        letter-spacing: 0.025em;
        transition: all 0.2s ease;
        box-shadow: 0 4px 6px -1px rgba(15, 118, 110, 0.3);
      }

      .button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 8px -1px rgba(15, 118, 110, 0.4);
      }

      /* Link fallback */
      .link-fallback {
        background-color: #f0fdfa;
        border: 1px solid #a7f3d0;
        border-radius: 8px;
        padding: 16px;
        margin: 24px 0;
      }

      .link-fallback p {
        font-size: 14px;
        color: #065f46;
        margin-bottom: 8px;
      }

      .link-fallback a {
        color: #0f766e;
        word-break: break-all;
        font-size: 14px;
      }

      /* Warning box */
      .warning {
        background-color: #fef3c7;
        border: 1px solid #f59e0b;
        border-radius: 8px;
        padding: 16px;
        margin: 24px 0;
      }

      .warning p {
        color: #92400e;
        font-weight: 600;
        margin: 0;
        font-size: 14px;
      }

      /* Security notice */
      .security-notice {
        background-color: #f3f4f6;
        border-radius: 8px;
        padding: 20px;
        margin: 24px 0;
      }

      .security-notice p {
        color: #374151;
        font-size: 14px;
        margin: 0;
      }

      /* Footer */
      .footer {
        background-color: #f8f9fa;
        padding: 32px 40px;
        border-top: 1px solid #e5e7eb;
        text-align: center;
      }

      .footer p {
        font-size: 12px;
        color: #6b7280;
        margin: 0;
        line-height: 1.5;
      }

      .footer a {
        color: #0f766e;
        text-decoration: none;
      }

      /* Responsive design */
      @media only screen and (max-width: 600px) {
        .email-container {
          margin: 0;
          border-radius: 0;
        }

        .header,
        .content,
        .footer {
          padding: 24px 20px;
        }

        .content h1 {
          font-size: 20px;
        }

        .button {
          padding: 14px 24px;
          font-size: 15px;
        }
      }

      /* Dark mode support */
      @media (prefers-color-scheme: dark) {
        body {
          background-color: #111827;
        }

        .email-container {
          background-color: #1f2937;
        }

        .content h1 {
          color: #f9fafb;
        }

        .greeting {
          color: #d1d5db;
        }

        .content p {
          color: #9ca3af;
        }

        .footer {
          background-color: #111827;
          border-top-color: #374151;
        }
      }
    </style>
  </head>
  <body>
    <div style="padding: 20px 0">
      <div class="email-container">
        <!-- Header -->
        <div class="header">
          <div class="logo">HealthCare Pro</div>
          <div class="tagline">Secure Health Management</div>
        </div>

        <!-- Content -->
        <div class="content">
          <h1>Password Reset Request</h1>

          <div class="greeting">Hello {{ first_name }},</div>

          <p>
            We received a request to reset your password for your HealthCare Pro
            account. To ensure the security of your health information, we've
            generated a secure reset link for you.
          </p>

          <div class="button-container">
            <a href="{{ reset_url }}" class="button" role="button"
              >Reset Your Password</a
            >
          </div>

          <div class="link-fallback">
            <p>
              <strong>Button not working?</strong> If the button above doesn't
              work, please:
            </p>
            <ol
              style="
                color: #065f46;
                font-size: 14px;
                margin: 8px 0 0 20px;
                padding: 0;
              "
            >
              <li>Right-click the "Reset Your Password" button above</li>
              <li>Select "Copy link address" from the menu</li>
              <li>Paste the link into your browser's address bar</li>
            </ol>
            <p
              style="
                font-size: 12px;
                color: #065f46;
                margin-top: 12px;
                font-style: italic;
              "
            >
              For security reasons, we don't display the full reset link in this
              email.
            </p>
          </div>

          <div class="warning">
            <p>
              ⏰ This reset link will expire in {{ expiry_minutes }} minutes for
              your security.
            </p>
          </div>

          <div class="security-notice">
            <p>
              <strong>🔒 Security Notice:</strong> If you didn't request this
              password reset, please ignore this email and consider:
            </p>
            <ul
              style="
                margin: 8px 0 0 20px;
                padding: 0;
                color: #374151;
                font-size: 14px;
              "
            >
              <li>Checking if someone else has access to your email</li>
              <li>Reviewing recent login activity on your account</li>
              <li>Contacting our security team if you have concerns</li>
            </ul>
            <p style="margin-top: 12px">
              Your password will remain unchanged, and your account remains
              secure.
            </p>
          </div>

          <p>
            Need help? Contact our support team at
            <a href="mailto:support@healthcarepro.com" style="color: #0f766e"
              >support@healthcarepro.com</a
            >
            or call <strong>(555) 123-4567</strong> during business hours.
          </p>
        </div>

        <!-- Footer -->
        <div class="footer">
          <p>
            This is an automated security email from HealthCare Pro.<br />
            Please do not reply to this email address.
          </p>
          <p style="margin-top: 12px">
            <a href="#" style="margin: 0 8px">Privacy Policy</a> |
            <a href="#" style="margin: 0 8px">Security Center</a> |
            <a href="#" style="margin: 0 8px">Support</a> |
            <a href="#" style="margin: 0 8px">Contact Us</a>
          </p>
          <p style="margin-top: 16px; font-size: 11px; color: #9ca3af">
            HealthCare Pro, Inc. | 123 Medical Center Dr, Suite 100<br />
            Healthcare City, HC 12345 | © 2025 All rights reserved
          </p>
        </div>
      </div>
    </div>
  </body>
</html>
"""


class EmailService:
    """Service for sending emails."""

    def __init__(self):
        if not self._is_configured():
            self.mail = None
            return

        # Configure FastMail
        conf = ConnectionConfig(
            MAIL_USERNAME=settings.mail_username,
            MAIL_PASSWORD=settings.mail_password,
            MAIL_FROM=settings.mail_from,
            MAIL_PORT=settings.mail_port,
            MAIL_SERVER=settings.mail_server,
            MAIL_STARTTLS=settings.mail_tls,
            MAIL_SSL_TLS=settings.mail_ssl,
            USE_CREDENTIALS=settings.use_credentials,
            VALIDATE_CERTS=settings.validate_certs,
        )
        self.mail = FastMail(conf)
        self.template_env = Environment(loader=BaseLoader())

    def _is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return all(
            [
                settings.mail_username,
                settings.mail_password,
                settings.mail_from,
                settings.mail_server,
            ]
        )

    def _render_template(self, template: str, **context) -> str:
        """Render email template with context."""
        template_obj = self.template_env.from_string(template)
        return template_obj.render(**context)

    async def send_email_verification(
        self,
        email: str,
        first_name: str,
        verification_token: str,
        base_url: str = "http://localhost:3000",
    ) -> bool:
        """Send email verification email."""
        if not self.mail:
            print(
                f"Email service not configured. Verification token for {email}: {verification_token}"
            )
            return False

        try:
            verification_url = (
                f"{base_url}/auth/verify-email?token={verification_token}"
            )

            html_content = self._render_template(
                EMAIL_VERIFICATION_TEMPLATE,
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
            print(f"Failed to send email verification to {email}: {e}")
            return False

    async def send_password_reset(
        self,
        email: str,
        first_name: str,
        reset_token: str,
        base_url: str = "http://localhost:3000",
    ) -> bool:
        """Send password reset email."""
        if not self.mail:
            print(
                f"Email service not configured. Password reset token for {email}: {reset_token}"
            )
            return False

        try:
            reset_url = f"{base_url}/auth/reset-password?token={reset_token}"

            html_content = self._render_template(
                PASSWORD_RESET_TEMPLATE,
                first_name=first_name,
                reset_url=reset_url,
                expiry_minutes=settings.password_reset_expire_minutes,
            )

            message = MessageSchema(
                subject="Password Reset - Health Management",
                recipients=[email],
                body=html_content,
                subtype="html",
            )

            await self.mail.send_message(message)
            return True

        except Exception as e:
            print(f"Failed to send password reset email to {email}: {e}")
            return False

    def generate_verification_token(self) -> str:
        """Generate a secure verification token."""
        return secrets.token_urlsafe(32)

    def generate_reset_token(self) -> str:
        """Generate a secure password reset token."""
        return secrets.token_urlsafe(32)


# Global email service instance
email_service = EmailService()
