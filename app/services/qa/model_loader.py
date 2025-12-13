"""
SBERT model loading and management for Q&A service.
from app.exceptions import (
    QAServiceException,
    QAModelNotLoadedException,
    QADatasetException,
    QAModelException,
    AIServiceException,
    OpenAIException,
    ModelNotLoadedException,
    DataProcessingException,
    ServiceUnavailableException,
    DatabaseException,
)
from app.core.error_context import ErrorContext

This module handles loading, downloading, and managing the Vietnamese SBERT model
with proper error handling and multiple fallback sources.
"""

import os
import logging
from pathlib import Path
from typing import Optional

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

from google.api_core.exceptions import Forbidden, PermissionDenied, GoogleAPIError
from google.auth.exceptions import GoogleAuthError

from app.core.qa_constants import DEFAULT_MODEL_NAME, REQUIRED_MODEL_FILES
from app.config import settings
from app.utils.gcs_downloader import GCSDownloader

logger = logging.getLogger(__name__)


class ModelLoader:
    """Load and manage SBERT model for Vietnamese Q&A."""

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize model loader.

        Args:
            model_path: Path to save/load the model
        """
        self.model_path = model_path or settings.qa_model_path
        self.model = None
        self.model_loaded = False

    def load_model(self) -> Optional[SentenceTransformer]:
        """
        Load SBERT model, download from multiple sources if needed.

        Returns:
            Loaded SentenceTransformer model or None if unavailable

        Raises:
            ImportError: If sentence_transformers is not installed
            Exception: If model cannot be loaded from any source
        """
        if SentenceTransformer is None:
            raise ImportError(
                "sentence_transformers is required. Install with: "
                "pip install sentence-transformers"
            )

        if self.model_loaded and self.model is not None:
            return self.model

        try:
            # Try local model first
            if self._load_local_model():
                return self.model

            # Fall back to Hugging Face download
            if self._download_from_huggingface():
                return self.model

            # Fall back to GCS if auto-download is enabled
            if settings.model_auto_download:
                if self._download_from_gcs():
                    return self.model

            logger.error("Failed to load model from any source")
            return None

        except Exception as e:
            logger.error(f"Unexpected error loading model: {e}")
            return None

    def _load_local_model(self) -> bool:
        """Load model from local storage."""
        try:
            model_path = Path(self.model_path)
            if model_path.exists() and self._is_model_complete():
                logger.info(f"Loading SBERT model from local: {model_path}")
                self.model = SentenceTransformer(str(model_path))
                self.model_loaded = True
                return True
        except Exception as e:
            logger.error(f"Failed to load local model: {e}")
        return False

    def _download_from_huggingface(self) -> bool:
        """Download model from Hugging Face."""
        try:
            logger.info("Downloading SBERT model from Hugging Face...")
            self.model = SentenceTransformer(
                DEFAULT_MODEL_NAME, cache_folder=None  # Don't use default cache
            )

            # Save model locally for future use
            self._save_model_locally()
            self.model_loaded = True
            return True

        except Exception as e:
            logger.error(f"Failed to download from Hugging Face: {e}")
            return False

    def _download_from_gcs(self) -> bool:
        """Download model from Google Cloud Storage."""
        try:
            # This would implement GCS download logic
            # For now, fall back to Hugging Face
            logger.info("GCS download not implemented, falling back to Hugging Face")
            return self._download_from_huggingface()

        except Exception as e:
            logger.error(f"Failed to download from GCS: {e}")
            return False

    def _save_model_locally(self) -> bool:
        """Save model to local storage."""
        try:
            if self.model is None:
                return False

            model_path = Path(self.model_path)
            model_path.mkdir(parents=True, exist_ok=True)

            self.model.save(str(model_path))
            logger.info(f"Model saved to {model_path}")
            return True

        except Exception as e:
            logger.warning(f"Failed to save model locally: {e}")
            return False

    def _is_model_complete(self) -> bool:
        """Check if all required model files are present."""
        try:
            model_path = Path(self.model_path)
            if not model_path.exists():
                return False

            required_files = [model_path / file for file in REQUIRED_MODEL_FILES]
            return all(file.exists() for file in required_files)

        except Exception:
            return False

    def get_model_info(self) -> dict:
        """Get information about the loaded model."""
        if not self.model_loaded or self.model is None:
            return {
                "loaded": False,
                "path": self.model_path,
                "model_name": DEFAULT_MODEL_NAME,
            }

        return {
            "loaded": True,
            "path": self.model_path,
            "model_name": DEFAULT_MODEL_NAME,
            "max_seq_length": getattr(self.model, "max_seq_length", None),
            "dimension": getattr(
                self.model.get_sentence_embedding_dimension(), "unknown"
            ),
        }

    def is_model_available(self) -> bool:
        """Check if model is loaded and ready."""
        return self.model_loaded and self.model is not None

    def get_embeddings(self, sentences: list[str]) -> list:
        """
        Generate embeddings for given sentences.

        Args:
            sentences: List of text sentences to embed

        Returns:
            List of embedding vectors
        """
        if not self.is_model_available():
            raise QAModelException(message="Model not loaded. Call load_model() first.")

        try:
            return self.model.encode(sentences)
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
