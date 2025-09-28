"""
Configuration settings for the Health Management application.
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application settings
    app_name: str = "Health Management API"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database settings
    database_url: str = Field(..., description="PostgreSQL database URL")
    database_pool_min_size: int = 1
    database_pool_max_size: int = 20
    database_pool_timeout: float = 30.0

    # Security settings
    secret_key: str = Field(..., description="Secret key for JWT token signing")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # Email verification and password reset
    email_verification_expire_minutes: int = 60
    password_reset_expire_minutes: int = 30

    # OAuth settings
    google_client_id: Optional[str] = Field(None, description="Google OAuth client ID")
    google_client_secret: Optional[str] = Field(
        None, description="Google OAuth client secret"
    )
    google_redirect_uri: Optional[str] = Field(
        None, description="Google OAuth redirect URI"
    )

    # Email settings
    mail_username: Optional[str] = Field(None, description="Email username")
    mail_password: Optional[str] = Field(None, description="Email password")
    mail_from: Optional[str] = Field(None, description="From email address")
    mail_port: int = 587
    mail_server: Optional[str] = Field(None, description="SMTP server")
    mail_tls: bool = True
    mail_ssl: bool = False
    use_credentials: bool = True
    validate_certs: bool = True
    webui_url: Optional[str] = Field(None, description="WebUI URL")

    # API settings
    api_v1_prefix: str = "/api/v1"
    allowed_hosts: list[str] = ["*"]

    # CORS settings
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:8080",
        "http://192.168.1.3:3000",
        "http://192.168.1.3:3001",
        "http://192.168.1.3:8080",
    ]
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    cors_allow_headers: list[str] = [
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
        "Cookie",
        "Set-Cookie",
    ]

    # Logging
    log_level: str = "INFO"

    # Documentation settings
    docs_enabled: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
