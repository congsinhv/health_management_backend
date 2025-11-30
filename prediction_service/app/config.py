"""Configuration settings for Prediction Service."""
from typing import Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Prediction Service settings loaded from environment variables."""

    # Application settings
    app_name: str = "VHealth Prediction Service"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, description="Enable debug mode")

    # Model settings
    model_path: str = Field(
        default="models/obesity_classifier.onnx", description="Path to ONNX model file"
    )
    label_encoder_path: str = Field(
        default="models/label_encoder.json",
        description="Path to label encoder JSON file",
    )

    # OpenAI settings
    openai_api_key: str = Field(
        ..., description="OpenAI API key for AI recommendations"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Log level")

    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:3001,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:8080",
        alias="CORS_ORIGINS",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from environment."""
        if not self.cors_origins:
            return []
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Global settings instance
settings = Settings()
