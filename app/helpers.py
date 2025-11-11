"""
Utility functions for the application.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict
from passlib.context import CryptContext
from jose import JWTError, jwt
import hashlib
from app.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    import bcrypt

    # Ensure password fits bcrypt's 72-byte limit
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]

    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    import bcrypt

    try:
        # Ensure password fits bcrypt's 72-byte limit
        password_bytes = plain_password.encode("utf-8")
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]

        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded_jwt


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode a JWT access token."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        return payload
    except JWTError:
        return None


def create_refresh_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT refresh token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )

    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded_jwt


def verify_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode a JWT refresh token."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )

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
    email: str, token_type: str = "email_verification"
) -> str:
    """Create a token for email verification or password reset."""
    expire_minutes = (
        settings.email_verification_expire_minutes
        if token_type == "email_verification"
        else settings.password_reset_expire_minutes
    )

    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    to_encode = {
        "sub": email,
        "exp": expire,
        "type": token_type,
    }

    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded_jwt


def verify_verification_token(token: str, expected_type: str) -> Optional[str]:
    """Verify email verification or password reset token."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )

        # Check token type
        if payload.get("type") != expected_type:
            return None

        # Return email from token
        return payload.get("sub")
    except JWTError:
        return None
