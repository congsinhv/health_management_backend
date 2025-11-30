"""
SBERT model loading and management for Q&A service with ONNX optimization.
from app.core.shared.exceptions import (
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
with proper error handling, multiple fallback sources, and ONNX optimization.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Tuple, Union

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

try:
    import torch
    import numpy as np
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

from app.core.qa_constants import DEFAULT_MODEL_NAME, REQUIRED_MODEL_FILES
from app.config import settings

logger = logging.getLogger(__name__)


class ModelLoader:
    """Load and manage SBERT model for Vietnamese Q&A with ONNX support."""

    def __init__(self, model_path: Optional[str] = None, use_onnx: bool = False):
        """
        Initialize model loader.

        Args:
            model_path: Path to save/load the model
            use_onnx: Whether to use ONNX runtime for inference
        """
        self.model_path = model_path or settings.qa_model_path
        self.use_onnx = use_onnx and ONNX_AVAILABLE
        self.model = None
        self.onnx_session = None
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
        """Load model from local storage with ONNX optimization."""
        try:
            model_path = Path(self.model_path)

            # Check if ONNX model exists and ONNX is enabled
            if self.use_onnx:
                onnx_model_path = model_path / "model.onnx"
                if onnx_model_path.exists():
                    logger.info(f"Loading ONNX model from local: {onnx_model_path}")
                    self.onnx_session = self._load_onnx_model(onnx_model_path)
                    if self.onnx_session is not None:
                        self.model_loaded = True
                        return True
                logger.warning("ONNX model not found, falling back to PyTorch")

            # Check if PyTorch model is complete
            if model_path.exists() and self._is_model_complete():
                logger.info(f"Loading SBERT model from local: {model_path}")
                self.model = SentenceTransformer(str(model_path))

                # Try to optimize to ONNX if enabled
                if self.use_onnx and ONNX_AVAILABLE:
                    self._try_optimize_to_onnx(self.model, model_path)

                self.model_loaded = True
                return True
        except Exception as e:
            logger.error(f"Failed to load local model: {e}")
        return False

    def _load_onnx_model(self, onnx_path: Path) -> Optional[any]:
        """Load ONNX model for inference."""
        try:
            # Configure ONNX Runtime session
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            if TORCH_AVAILABLE and torch.cuda.is_available():
                logger.info("ONNX Runtime: Using CUDA")
                providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            else:
                logger.info("ONNX Runtime: Using CPU")

            try:
                import onnxruntime as ort
                session = ort.InferenceSession(str(onnx_path), providers=providers)
            except ImportError:
                logger.error("onnxruntime not available")
                return None

            # Test the model with dummy input
            input_name = session.get_inputs()[0].name
            dummy_input = {"input_ids": [[1, 2, 3, 4, 5]],
                          "attention_mask": [[1, 1, 1, 1, 1]]}
            _ = session.run(None, dummy_input)

            logger.info(f"ONNX model loaded successfully from: {onnx_path}")
            return session
        except Exception as e:
            logger.error(f"Failed to load ONNX model: {e}")
            return None

    def _try_optimize_to_onnx(self, model: SentenceTransformer, model_path: Path) -> bool:
        """Try to convert PyTorch model to ONNX format."""
        if not ONNX_AVAILABLE:
            logger.warning("ONNX Runtime not available, skipping optimization")
            return False

        try:
            onnx_path = model_path / "model.onnx"
            if onnx_path.exists():
                logger.info("ONNX model already exists, skipping conversion")
                return True

            logger.info("Converting PyTorch model to ONNX format...")

            # Prepare dummy input for export
            tokenizer = model.tokenizer
            dummy_text = "This is a dummy sentence for ONNX export."
            inputs = tokenizer(dummy_text, return_tensors="pt",
                              padding=True, truncation=True, max_length=128)

            # Export to ONNX
            torch.onnx.export(
                model.model,
                (inputs["input_ids"], inputs["attention_mask"]),
                str(onnx_path),
                input_names=["input_ids", "attention_mask"],
                output_names=["last_hidden_state"],
                dynamic_axes={
                    "input_ids": {0: "batch_size", 1: "sequence"},
                    "attention_mask": {0: "batch_size", 1: "sequence"},
                    "last_hidden_state": {0: "batch_size", 1: "sequence"}
                },
                opset_version=14
            )

            logger.info(f"ONNX model saved to: {onnx_path}")
            return True
        except Exception as e:
            logger.warning(f"Failed to convert model to ONNX: {e}")
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

            # Try to optimize to ONNX if enabled
            if self.use_onnx and ONNX_AVAILABLE:
                model_path = Path(self.model_path)
                self._try_optimize_to_onnx(self.model, model_path)

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
        if not self.model_loaded:
            return {
                "loaded": False,
                "path": self.model_path,
                "model_name": DEFAULT_MODEL_NAME,
                "onnx_enabled": self.use_onnx,
                "onnx_available": ONNX_AVAILABLE,
            }

        info = {
            "loaded": True,
            "path": self.model_path,
            "model_name": DEFAULT_MODEL_NAME,
            "onnx_enabled": self.use_onnx,
            "onnx_available": ONNX_AVAILABLE,
            "onnx_loaded": self.onnx_session is not None,
        }

        if self.model is not None:
            info["max_seq_length"] = getattr(self.model, "max_seq_length", None)
            info["dimension"] = getattr(
                self.model.get_sentence_embedding_dimension(), "unknown"
            )

        return info

    def is_model_available(self) -> bool:
        """Check if model is loaded and ready."""
        if self.use_onnx:
            return self.onnx_session is not None
        else:
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
            if self.use_onnx and self.onnx_session is not None:
                return self._get_embeddings_onnx(sentences)
            else:
                return self.model.encode(sentences)
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    def _get_embeddings_onnx(self, sentences: list[str]) -> list:
        """Generate embeddings using ONNX Runtime."""
        try:
            if not self.model:
                raise RuntimeError("PyTorch model not available for tokenization")

            # Tokenize sentences
            tokenizer = self.model.tokenizer
            inputs = tokenizer(
                sentences,
                return_tensors="np",
                padding=True,
                truncation=True,
                max_length=128
            )

            # Run inference with ONNX
            outputs = self.onnx_session.run(
                None,
                {
                    "input_ids": inputs["input_ids"],
                    "attention_mask": inputs["attention_mask"]
                }
            )

            # Apply mean pooling (same as SentenceTransformer)
            last_hidden_state = outputs[0]
            attention_mask = inputs["attention_mask"]

            # Mean pooling
            input_mask_expanded = attention_mask[..., np.newaxis]
            sum_embeddings = np.sum(last_hidden_state * input_mask_expanded, axis=1)
            sum_mask = np.sum(input_mask_expanded, axis=1)
            sum_mask = np.clip(sum_mask, a_min=1e-9, a_max=None)
            mean_embeddings = sum_embeddings / sum_mask

            return mean_embeddings
        except Exception as e:
            logger.error(f"Failed to generate ONNX embeddings: {e}")
            # Fall back to PyTorch if ONNX fails
            if self.model is not None:
                logger.info("Falling back to PyTorch for embeddings")
                return self.model.encode(sentences)
            raise