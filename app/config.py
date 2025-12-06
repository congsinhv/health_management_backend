"""
Configuration settings for the Health Management application.
"""

from typing import Optional, List
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
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
    database_query_timeout: float = Field(
        default=30.0, description="Query execution timeout in seconds (default: 30.0)"
    )
    database_connection_timeout: float = Field(
        default=10.0,
        description="Connection acquisition timeout in seconds (default: 10.0)",
    )

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
    allowed_hosts: List[str] = ["*"]

    custom_domain: Optional[str] = Field(None, description="Custom domain")

    # CORS settings - stored as comma-separated string in env var
    # Using str type to prevent pydantic-settings from trying to parse as JSON
    cors_origins_str: str = Field(
        default="http://localhost:3000,http://localhost:3001,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:8080,http://192.168.1.3:3000,http://192.168.1.3:3001,http://192.168.1.3:8080",
        alias="CORS_ORIGINS",
    )

    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if not self.cors_origins_str:
            return []
        # Try JSON first (for backward compatibility), then comma-separated
        if self.cors_origins_str.startswith("["):
            import json

            try:
                return json.loads(self.cors_origins_str)
            except json.JSONDecodeError:
                pass
        # Handle comma-separated string from environment variable
        return [
            origin.strip()
            for origin in self.cors_origins_str.split(",")
            if origin.strip()
        ]

    @model_validator(mode="after")
    def add_custom_domain_to_cors(self):
        """Add custom domain to CORS origins if provided."""
        if self.custom_domain:
            origin = f"https://{self.custom_domain}"
            # Check if origin is already in the string
            if origin not in self.cors_origins_str:
                self.cors_origins_str = f"{self.cors_origins_str},{origin}"
        return self

    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    cors_allow_headers: List[str] = [
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

    # ONNX optimization settings
    qa_model_format: str = Field(
        default="auto",
        description="Model format: auto (detect), pytorch, onnx",
    )
    qa_onnx_provider: str = Field(
        default="CPUExecutionProvider",
        description="ONNX execution provider (CPUExecutionProvider, CUDAExecutionProvider)",
    )

    # Lazy loading settings (Phase 2)
    qa_lazy_loading: bool = Field(
        default=True,
        description="Lazy load Q&A model on first request (faster startup)",
    )

    # Obesity Prediction Model settings
    obesity_model_dir: str = Field(
        default="/tmp/models_obesity",
        description="Path to obesity prediction models directory (writable cache)",
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
        default="vhealth-test-public",
        description="GCS bucket name for public file uploads (e.g., vhealth-test-public)",
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

    # Redis Cache settings
    # ========================================
    enable_redis_cache: bool = Field(
        default=False, description="Enable Redis caching for performance optimization"
    )
    redis_host: Optional[str] = Field(
        None, description="Redis host (from GCP Memorystore)"
    )
    redis_port: int = Field(default=6379, description="Redis port")
    redis_password: Optional[str] = Field(
        None, description="Redis password (from Secret Manager)"
    )
    redis_db: int = Field(default=0, description="Redis database number")
    redis_ssl: bool = Field(
        default=True, description="Use SSL/TLS for Redis connection"
    )
    redis_max_connections: int = Field(
        default=20, description="Maximum Redis connection pool size"
    )
    redis_connection_timeout: int = Field(
        default=5, description="Redis connection timeout in seconds"
    )

    # TTL settings for different cache types (in seconds)
    cache_ttl_qa_answer: int = Field(
        default=1800, description="TTL for Q&A answers (30 minutes)"
    )
    cache_ttl_qa_summary: int = Field(
        default=1800, description="TTL for Q&A AI summaries (30 minutes)"
    )
    cache_ttl_qa_embedding: int = Field(
        default=86400, description="TTL for Q&A embeddings (24 hours)"
    )
    cache_ttl_conversation_list: int = Field(
        default=300, description="TTL for conversation list (5 minutes)"
    )
    cache_ttl_conversation_detail: int = Field(
        default=600, description="TTL for conversation detail (10 minutes)"
    )
    cache_ttl_user_profile: int = Field(
        default=600, description="TTL for user profile (10 minutes)"
    )
    cache_ttl_message_list: int = Field(
        default=180, description="TTL for message list (3 minutes)"
    )

    # Cache warming settings (Phase 3)
    qa_cache_warmup_enabled: bool = Field(
        default=True, description="Pre-warm embedding cache at startup"
    )
    qa_cache_warmup_questions_file: str = Field(
        default="data/top_questions.txt",
        description="File with top questions for cache warming",
    )

    @property
    def redis_url(self) -> Optional[str]:
        """Construct Redis URL from configuration."""
        if not self.enable_redis_cache or not self.redis_host:
            return None

        # Build authentication part
        auth_part = ""
        if self.redis_password:
            auth_part = f":{self.redis_password}@"

        # Build URL with SSL requirement
        url = f"redis://{auth_part}{self.redis_host}:{self.redis_port}/{self.redis_db}"

        if self.redis_ssl:
            url += "?ssl_cert_reqs=required"

        return url

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Avoid Pydantic protected namespace warning for model_* fields
        protected_namespaces=(),
        # Don't try to parse env vars as JSON for complex types
        # This allows our field_validator to handle the parsing
        env_parse_none_str="None",
    )


# Global settings instance
settings = Settings()
