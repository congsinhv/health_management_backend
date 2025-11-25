"""
Email data types and schemas for the email service.
"""

from typing import Optional
from pydantic import BaseModel, EmailStr


class EmailMessage(BaseModel):
    """Email message data structure."""

    subject: str
    recipients: list[EmailStr]
    body: str
    subtype: str = "html"


class EmailVerificationData(BaseModel):
    """Data for email verification emails."""

    email: str
    first_name: str
    verification_token: str
    base_url: str = "http://localhost:3000"
    verification_url: Optional[str] = None
    expiry_minutes: int


class PasswordResetData(BaseModel):
    """Data for password reset emails."""

    email: str
    first_name: str
    reset_token: str
    base_url: str = "http://localhost:3000"
    reset_url: Optional[str] = None
    expiry_minutes: int


class TokenData(BaseModel):
    """Token generation data."""

    email: str
    timestamp: str
    signature: str
    checksum: str
