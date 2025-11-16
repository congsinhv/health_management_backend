"""
Configuration settings for the Health Management application.
"""

from typing import Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings
import logging

logger = logging.getLogger(__name__)


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

    custom_domain: Optional[str] = Field(None, description="Custom domain")

    # CORS settings
    cors_origins: list[str] = Field(
        default_factory=lambda: [
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
    )

    @model_validator(mode="after")
    def add_custom_domain_to_cors(self):
        """Add custom domain to CORS origins if provided."""
        if self.custom_domain:
            origin = f"https://{self.custom_domain}"
            if origin not in self.cors_origins:
                self.cors_origins.append(origin)
        return self

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
    # Q&A Service settings
    # ========================================
    qa_enabled: bool = Field(default=True, description="Enable/disable Q&A service")

    # Local paths (used as cache directory when downloading from GCS)
    qa_model_path: str = Field(
        default="./models/vietnamese-sbert",
        description="Path to SBERT model directory (local cache)",
    )
    qa_data_path: str = Field(
        default="data.xlsx", description="Path to Q&A dataset Excel file"
    )
    qa_vocab_path: str = Field(
        default="tuvung.txt", description="Path to Vietnamese vocabulary file"
    )

    # GCS Storage settings
    gcp_project_id: Optional[str] = Field(
        default=None, description="GCP project ID for GCS access"
    )
    gcp_model_bucket: Optional[str] = Field(
        default=None,
        description="GCS bucket name for models (e.g., vhealth-dev-models)",
    )
    gcp_model_blob_path: str = Field(
        default="models/vietnamese-sbert/",
        description="Path to model files within GCS bucket",
    )
    gcp_data_blob_path: str = Field(
        default="data/", description="Path to data files within GCS bucket"
    )
    model_auto_download: bool = Field(
        default=True, description="Automatically download models from GCS if not local"
    )
    model_download_timeout: int = Field(
        default=600, description="Timeout for model download from GCS (seconds)"
    )
    gcp_public_bucket: Optional[str] = Field(
        default="vhealth-dev-public",
        description="GCS bucket name for public file uploads (e.g., vhealth-dev-public)",
    )

    # Q&A behavior settings
    openai_api_key: str = Field(
        default="openai_api_key", description="OpenAI API key for AI summarization"
    )
    qa_threshold: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold for answers",
    )
    qa_top_k: int = Field(
        default=7, ge=1, le=20, description="Maximum number of top results to return"
    )
    qa_max_per_field: int = Field(
        default=5, ge=1, le=10, description="Maximum answers per field category"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
