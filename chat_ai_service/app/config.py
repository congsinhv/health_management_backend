"""
Configuration for Chat AI microservice.

Uses Pydantic BaseSettings for environment variable management
with validation and type safety.
"""

import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings for Chat AI microservice."""

    # Application settings
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    SECRET_KEY: str = Field(default="dev-secret-key", description="Secret key for security")
    PORT: int = Field(default=8080, description="Server port")
    HOST: str = Field(default="0.0.0.0", description="Server host")

    # CORS settings
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        description="Allowed CORS origins"
    )

    # Q&A Service settings
    QA_ENABLED: bool = Field(default=True, description="Enable Q&A service")
    QA_MODEL_PATH: str = Field(
        default="./models/qa",
        description="Path to SBERT model"
    )
    QA_DATA_PATH: str = Field(
        default="./data/qa/data.xlsx",
        description="Path to Q&A dataset"
    )
    QA_VOCAB_PATH: str = Field(
        default="./data/qa/tuvung.txt",
        description="Path to vocabulary file"
    )
    QA_THRESHOLD: float = Field(default=0.55, description="Default similarity threshold")
    QA_TOP_K: int = Field(default=7, description="Default number of top results")
    QA_MAX_PER_FIELD: int = Field(default=5, description="Maximum answers per field")

    # Model settings
    MODEL_AUTO_DOWNLOAD: bool = Field(
        default=True,
        description="Auto-download model if not found locally"
    )
    MODEL_DOWNLOAD_TIMEOUT: int = Field(
        default=300,
        description="Model download timeout in seconds"
    )

    # Google Cloud Platform settings (optional)
    GCP_PROJECT_ID: Optional[str] = Field(
        default=None,
        description="Google Cloud project ID"
    )
    GCP_MODEL_BUCKET: Optional[str] = Field(
        default=None,
        description="GCS bucket for model storage"
    )
    GCP_MODEL_BLOB_PATH: Optional[str] = Field(
        default=None,
        description="GCS path prefix for model files"
    )
    GCP_DATA_BLOB_PATH: Optional[str] = Field(
        default=None,
        description="GCS path prefix for data files"
    )

    # OpenAI settings
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key"
    )
    OPENAI_SERVICE_URL: Optional[str] = Field(
        default=None,
        description="OpenAI service URL (for service-to-service communication)"
    )
    OPENAI_TEMPERATURE: float = Field(
        default=0.7,
        description="OpenAI temperature setting"
    )
    OPENAI_MAX_TOKENS: int = Field(
        default=150,
        description="OpenAI max tokens for summaries"
    )

    # ONNX settings
    USE_ONNX: bool = Field(
        default=False,
        description="Enable ONNX runtime for model optimization"
    )
    ONNX_PROVIDERS: List[str] = Field(
        default=["CPUExecutionProvider"],
        description="ONNX runtime providers"
    )

    # Redis caching settings (optional)
    ENABLE_REDIS_CACHE: bool = Field(
        default=False,
        description="Enable Redis caching"
    )
    REDIS_URL: Optional[str] = Field(
        default=None,
        description="Redis connection URL"
    )
    CACHE_TTL_QA_ANSWER: int = Field(
        default=1800,  # 30 minutes
        description="Cache TTL for Q&A answers in seconds"
    )
    CACHE_TTL_SUMMARY: int = Field(
        default=2592000,  # 30 days
        description="Cache TTL for AI summaries in seconds"
    )

    # Monitoring and metrics
    METRICS_ENABLED: bool = Field(
        default=True,
        description="Enable metrics collection"
    )
    METRICS_PORT: int = Field(
        default=9090,
        description="Metrics server port"
    )

    # Rate limiting settings
    ENABLE_RATE_LIMITING: bool = Field(
        default=True,
        description="Enable rate limiting"
    )
    MAX_CONCURRENT_REQUESTS: int = Field(
        default=10,
        description="Maximum concurrent requests per user"
    )
    MAX_REQUESTS_PER_MINUTE: int = Field(
        default=30,
        description="Maximum requests per minute per user"
    )

    # Service-to-service communication
    MAIN_SERVICE_URL: Optional[str] = Field(
        default=None,
        description="Main service URL for data synchronization"
    )
    SERVICE_TIMEOUT: int = Field(
        default=30,
        description="Timeout for service-to-service requests"
    )

    # Deployment settings
    DEPLOYMENT_ENV: str = Field(
        default="development",
        description="Deployment environment (development/staging/production)"
    )
    INSTANCE_ID: Optional[str] = Field(
        default=None,
        description="Service instance ID for logging"
    )

    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()

# QA constants
QA_VOCAB_FILE = "tuvung.txt"
DEFAULT_MODEL_NAME = "keepitreal/vietnamese-sbert"
DEFAULT_SIMILARITY_THRESHOLD = 0.55
DEFAULT_TOP_K = 7
ANSWER_CACHE_TTL = 1800  # 30 minutes
SUMMARY_CACHE_TTL = 2592000  # 30 days

# Required model files for validation
REQUIRED_MODEL_FILES = [
    "config.json",
    "modules.json",
    "sentence_bert_config.json",
    "config_sentence_transformers.json",
    "1_Pooling/config.json",
]

# Standard messages for responses
class Messages:
    """Standard HTTP-compliant response messages."""

    # 400 Bad Request errors
    EMPTY_QUESTION = "Bad Request: Question cannot be empty"
    INVALID_THRESHOLD = "Bad Request: Similarity threshold must be between 0.0 and 1.0"
    INVALID_TOP_K = "Bad Request: Top k must be between 1 and 20"

    # 503 Service Unavailable errors
    AI_NOT_AVAILABLE = (
        "Service Unavailable: AI summarization is not available (missing API key)"
    )
    MODEL_NOT_LOADED = "Service Unavailable: Q&A model is not loaded"
    DATASET_NOT_LOADED = "Service Unavailable: Q&A dataset is not loaded"
    SERVICE_UNAVAILABLE = "Service Unavailable: Q&A service is temporarily unavailable"

    # 204 No Content (no data available)
    NO_RESULTS_FOUND = "No Results Found"
    NO_DATA_TO_SUMMARIZE = "No Content: No data available for summarization"

    # Response data messages
    UNCLASSIFIED_FIELD = "Unclassified"
    PROCESSING_ERROR = "Internal Server Error: Error processing question"

    # Success messages
    SERVICE_HEALTHY = "Q&A service is operational"
    SERVICE_UNHEALTHY = "Q&A service is experiencing issues"