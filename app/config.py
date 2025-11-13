"""
Configuration settings for the Health Management application.
"""

from typing import Optional, List
from pydantic import Field, model_validator, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        protected_namespaces=("settings_",),
    )

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
    allowed_hosts: List[str] = ["*"]

    custom_domain: Optional[str] = Field(None, description="Custom domain")

    # CORS settings
    cors_origins: List[str] = Field(
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
            "https://localhost:3000",
            "https://localhost:3001",
            "https://localhost:8080",
            "https://127.0.0.1:3000",
            "https://127.0.0.1:3001",
            "https://127.0.0.1:8080",
            "https://192.168.1.3:3000",
            "https://192.168.1.3:3001",
            "https://192.168.1.3:8080",
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

    # OpenRouter AI settings
    openrouter_api_key: Optional[str] = Field(
        default=None, description="OpenRouter API key for AI summarization"
    )
    openrouter_model: str = Field(
        default="openai/gpt-4o-mini", description="OpenRouter model to use"
    )
    openrouter_timeout: int = Field(
        default=30, description="OpenRouter API timeout in seconds"
    )
    openrouter_temperature: float = Field(
        default=0.5,
        ge=0.0,
        le=2.0,
        description="Temperature for OpenRouter AI responses",
    )
    openrouter_max_tokens: int = Field(
        default=400, ge=1, le=4096, description="Maximum tokens for AI responses"
    )

    # Rate limiting (configuration only, implementation in future PR)
    qa_rate_limit_requests: int = Field(
        default=10, ge=1, description="Max requests per time window"
    )
    qa_rate_limit_window: int = Field(
        default=60, ge=1, description="Rate limit time window in seconds"
    )

    # Conversation Features settings
    # ========================================
    conversation_max_pinned: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of pinned conversations per user",
    )
    conversation_auto_title: bool = Field(
        default=True, description="Auto-generate titles from first Q&A"
    )
    conversation_title_max_length: int = Field(
        default=60,
        ge=10,
        le=255,
        description="Maximum characters for auto-generated title",
    )

    # Search Configuration
    search_results_per_page: int = Field(
        default=20, ge=1, le=100, description="Number of search results per page"
    )
    search_max_results: int = Field(
        default=100, ge=1, le=1000, description="Maximum search results to return"
    )
    search_cache_ttl: int = Field(
        default=180, ge=0, description="Search cache TTL in seconds"
    )

    # Performance settings
    enable_redis_cache: bool = Field(
        default=False, description="Enable Redis caching for performance"
    )
    redis_url: str = Field(
        default="redis://localhost:6379/0", description="Redis connection URL"
    )
    cache_conversation_list_ttl: int = Field(
        default=300, ge=0, description="Cache TTL for conversation list (seconds)"
    )
    cache_conversation_detail_ttl: int = Field(
        default=600, ge=0, description="Cache TTL for conversation detail (seconds)"
    )
    cache_search_results_ttl: int = Field(
        default=180, ge=0, description="Cache TTL for search results (seconds)"
    )

    # Version History settings
    message_version_limit: int = Field(
        default=50, ge=1, le=100, description="Maximum versions per message"
    )
    auto_version_on_edit: bool = Field(
        default=True, description="Track edits automatically as versions"
    )


# Global settings instance
settings = Settings()
