"""
Shared authentication utilities for VHealth microservices.

Provides functions for:
- Password hashing and verification using bcrypt
- JWT access and refresh token creation and verification
- Email verification token generation and validation
- Token hashing for secure storage

Usage:
    from app.core.shared.auth import (
        hash_password, verify_password,
        create_access_token, verify_access_token,
        create_refresh_token, verify_refresh_token
    )
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from jose import JWTError, jwt
import hashlib

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: Dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=30)  # Default 30 minutes

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt


def verify_access_token(
    token: str, secret_key: str, algorithm: str = "HS256"
) -> Optional[Dict[str, Any]]:
    """Verify and decode a JWT access token."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except JWTError:
        return None


def create_refresh_token(
    data: Dict[str, Any],
    secret_key: str,
    algorithm: str = "HS256",
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=30)  # Default 30 days

    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt


def verify_refresh_token(
    token: str, secret_key: str, algorithm: str = "HS256"
) -> Optional[Dict[str, Any]]:
    """Verify and decode a JWT refresh token."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])

        # Check if this is a refresh token
        if payload.get("type") != "refresh":
            return None

        return payload
    except JWTError:
        return None


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token for secure database storage using SHA256.

    Uses SHA256 (deterministic) instead of bcrypt so we can verify tokens
    by comparing hashes directly.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def create_verification_token(
    email: str,
    secret_key: str,
    algorithm: str = "HS256",
    token_type: str = "email_verification",
    expire_minutes: Optional[int] = None,
) -> str:
    """Create a token for email verification or password reset."""
    if expire_minutes is None:
        expire_minutes = 60 if token_type == "email_verification" else 30

    expire = datetime.utcnow() + timedelta(minutes=expire_minutes)
    to_encode = {
        "sub": email,
        "exp": expire,
        "type": token_type,
    }

    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt


def verify_verification_token(
    token: str,
    secret_key: str,
    algorithm: str = "HS256",
    expected_type: str = "email_verification",
) -> Optional[str]:
    """Verify email verification or password reset token."""
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])

        # Check token type
        if payload.get("type") != expected_type:
            return None

        # Return email from token
        return payload.get("sub")
    except JWTError:
        return None
