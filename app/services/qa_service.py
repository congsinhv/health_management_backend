"""
Q&A Service using SBERT and OpenRouter AI.
"""

import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd
import requests
from sentence_transformers import SentenceTransformer, util

from app.utils.gcs_downloader import GCSDownloader

logger = logging.getLogger(__name__)


class QAService:
    """Service for handling health-related Q&A using semantic search."""

    # Required model files for SBERT
    REQUIRED_MODEL_FILES = [
        "config.json",
        "modules.json",
        "sentence_bert_config.json",
        "config_sentence_transformers.json",
        "1_Pooling/config.json",
    ]

    def __init__(self, settings):
        """Initialize Q&A service with model and data."""
        self.settings = settings
        self.model_path = settings.qa_model_path
        self.data_path = settings.qa_data_path
        self.vocab_path = settings.qa_vocab_path

        # Ensure models are available (download from GCS if needed)
        if settings.model_auto_download:
            self._ensure_model_and_data_exist()

        # Load components
        self.vocab = self._load_vocab()
        self.model = self._load_model()
        self.df, self.question_embeddings = self._load_data()

        # OpenRouter configuration
        # Note: Only use from settings, don't fallback to os.getenv for security
        self.openrouter_api_key = settings.openrouter_api_key
        if not self.openrouter_api_key:
            logger.warning(
                "OpenRouter API key not configured - AI summarization will not be available"
            )

        self.openrouter_model = settings.openrouter_model
        self.openrouter_timeout = settings.openrouter_timeout
        self.openrouter_temperature = settings.openrouter_temperature
        self.openrouter_max_tokens = settings.openrouter_max_tokens
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"

        # Q&A behavior settings
        self.max_per_field = settings.qa_max_per_field

    def _ensure_model_and_data_exist(self) -> None:
        """
        Ensure model and data files exist locally, download from GCS if needed.

        This method checks if the model is complete locally. If not, it attempts
        to download from GCS. If GCS is not configured, it will fall back to
        Hugging Face download in _load_model().
        """
        # Check if model is already complete locally
        if self._is_model_complete():
            logger.info("Model files found locally and complete")
            return

        # Try to download from GCS if configured
        if not self.settings.gcp_model_bucket:
            logger.info(
                "GCS bucket not configured, will attempt Hugging Face download if needed"
            )
            return

        logger.info("Model not found locally, attempting download from GCS...")
        try:
            self._download_from_gcs()
        except Exception as e:
            logger.warning(
                f"Failed to download from GCS: {e}. Will attempt Hugging Face download if needed."
            )

    def _is_model_complete(self) -> bool:
        """
        Check if all required model files exist locally.

        Returns:
            True if all required files exist, False otherwise
        """
        model_dir = Path(self.model_path)
        if not model_dir.exists():
            return False

        # Check for required config files
        for required_file in self.REQUIRED_MODEL_FILES:
            if not (model_dir / required_file).exists():
                logger.debug(f"Missing required model file: {required_file}")
                return False

        # Check for model weights file (required for model to load)
        # Modern models use model.safetensors, older ones use pytorch_model.bin
        has_weights = (
            (model_dir / "model.safetensors").exists()
            or (model_dir / "pytorch_model.bin").exists()
            or (model_dir / "1_Pooling" / "model.safetensors").exists()
            or (model_dir / "1_Pooling" / "pytorch_model.bin").exists()
        )

        if not has_weights:
            logger.debug("Missing model weights file (model.safetensors or pytorch_model.bin)")
            return False

        return True

    def _download_from_gcs(self) -> None:
        """
        Download model and data files from GCS.

        Raises:
            Exception: If download fails or GCS is not properly configured
        """
        if not self.settings.gcp_model_bucket:
            raise ValueError("GCS bucket not configured")

        logger.info(
            f"Downloading from GCS bucket: {self.settings.gcp_model_bucket}"
        )

        downloader = GCSDownloader(
            bucket_name=self.settings.gcp_model_bucket,
            project_id=self.settings.gcp_project_id,
            timeout=self.settings.model_download_timeout,
        )

        # Download model files
        logger.info("Downloading model files...")
        success, failed = downloader.download_directory(
            blob_prefix=self.settings.gcp_model_blob_path,
            local_dir=self.model_path,
            force=False,
        )

        if failed > 0 or success == 0:
            raise RuntimeError(
                f"Failed to download model files: {success} succeeded, {failed} failed"
            )

        logger.info(f"Successfully downloaded {success} model files")

        # Validate model is complete
        if not self._is_model_complete():
            model_dir = Path(self.model_path)
            # Check which weight file is missing
            missing_weights = []
            if not (model_dir / "model.safetensors").exists():
                missing_weights.append("model.safetensors")
            if not (model_dir / "pytorch_model.bin").exists():
                missing_weights.append("pytorch_model.bin")

            error_msg = (
                f"Downloaded model is incomplete - missing model weights file. "
                f"Expected one of: model.safetensors or pytorch_model.bin. "
                f"Please ensure the model weights file is uploaded to GCS bucket "
                f"{self.settings.gcp_model_bucket} at path {self.settings.gcp_model_blob_path}"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # Download data files if configured
        if self.settings.gcp_data_blob_path:
            try:
                logger.info("Downloading data files...")

                # Download data.xlsx
                data_blob = (
                    f"{self.settings.gcp_data_blob_path}data.xlsx"
                    if self.settings.gcp_data_blob_path.endswith("/")
                    else f"{self.settings.gcp_data_blob_path}/data.xlsx"
                )
                downloader.download_file(data_blob, self.data_path, force=False)

                # Download tuvung.txt
                vocab_blob = (
                    f"{self.settings.gcp_data_blob_path}tuvung.txt"
                    if self.settings.gcp_data_blob_path.endswith("/")
                    else f"{self.settings.gcp_data_blob_path}/tuvung.txt"
                )
                downloader.download_file(vocab_blob, self.vocab_path, force=False)

                logger.info("Data files downloaded successfully")
            except Exception as e:
                logger.warning(f"Failed to download data files from GCS: {e}")
                # Don't fail if data files can't be downloaded, they might be local

    def _load_vocab(self) -> Set[str]:
        """Load vocabulary from file."""
        if not os.path.exists(self.vocab_path):
            logger.warning(
                f"Vocabulary file not found: {self.vocab_path}. "
                "Proceeding without vocabulary filtering."
            )
            return set()

        try:
            with open(self.vocab_path, "r", encoding="utf-8") as f:
                vocab = set(line.strip().lower() for line in f if line.strip())
            logger.info(f"Loaded {len(vocab)} words from vocabulary")
            return vocab
        except Exception as e:
            logger.error(f"Error loading vocabulary: {e}")
            return set()

    def _load_model(self) -> SentenceTransformer:
        """
        Load or download SBERT model.

        First attempts to load from local path. If not found and GCS download
        failed, falls back to Hugging Face download.

        Returns:
            Loaded SentenceTransformer model

        Raises:
            Exception: If model cannot be loaded from any source
        """
        try:
            if os.path.exists(self.model_path) and self._is_model_complete():
                logger.info("Loading SBERT model from local cache...")
                return SentenceTransformer(self.model_path)
            else:
                logger.info(
                    "Model not found locally, downloading from Hugging Face..."
                )
                model = SentenceTransformer(
                    "keepitreal/vietnamese-sbert", cache_folder=None
                )

                # Save for future use
                try:
                    os.makedirs(self.model_path, exist_ok=True)
                    model.save(self.model_path)
                    logger.info(f"Model saved to {self.model_path}")
                except Exception as e:
                    logger.warning(f"Failed to save model locally: {e}")

                return model
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise RuntimeError(f"Failed to load Q&A model: {e}") from e

    def _load_data(self) -> tuple[pd.DataFrame, any]:
        """
        Load and preprocess dataset.

        Returns:
            Tuple of (DataFrame, question_embeddings)

        Raises:
            FileNotFoundError: If dataset file not found
            ValueError: If required columns are missing
        """
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(
                f"Dataset not found: {self.data_path}. "
                "Please ensure data.xlsx is available locally or in GCS."
            )

        try:
            df = pd.read_excel(self.data_path)
            required_cols = ["Câu hỏi", "Câu trả lời", "Từ khóa", "Lĩnh vực"]

            for col in required_cols:
                if col not in df.columns:
                    raise ValueError(f"Column '{col}' not found in dataset")

            # Preprocess questions
            df["Câu hỏi_clean"] = df["Câu hỏi"].astype(str).apply(
                self.preprocess_text
            )

            logger.info(f"Creating embeddings for {len(df)} questions...")
            question_embeddings = self.model.encode(
                df["Câu hỏi_clean"].tolist(),
                convert_to_tensor=True,
                show_progress_bar=True,
            )

            logger.info("Data loaded and embeddings created successfully")
            return df, question_embeddings

        except Exception as e:
            logger.error(f"Error loading data: {e}")
            raise

    def preprocess_text(self, text: str) -> str:
        """
        Preprocess text for semantic search.

        Args:
            text: Raw text to preprocess

        Returns:
            Preprocessed text with only alphanumeric and Vietnamese characters
        """
        text = text.lower()
        # Keep Vietnamese characters (U+00C0 to U+017F)
        text = re.sub(r"[^a-z0-9\u00C0-\u017F\s]", " ", text)
        words = text.split()

        # Filter by vocabulary if available
        if self.vocab:
            words = [w for w in words if w in self.vocab]

        return " ".join(words)

    def summarize_with_ai(
        self, user_question: str, collected_answers: List[str]
    ) -> str:
        """
        Summarize answers using OpenRouter AI.

        Args:
            user_question: The user's original question
            collected_answers: List of answers to summarize

        Returns:
            AI-generated summary or error message
        """
        if not collected_answers:
            return "Xin lỗi, chưa có dữ liệu để tóm tắt."

        if not self.openrouter_api_key:
            logger.warning("OpenRouter API key not configured")
            return "AI summarization không khả dụng (thiếu API key)."

        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
        }

        prompt = (
            f"Người dùng hỏi: {user_question}\n\n"
            f"Các câu trả lời từ dữ liệu:\n- "
            + "\n- ".join(collected_answers)
            + "\n\nHãy tóm tắt ngắn gọn, dễ hiểu, giữ đúng thông tin quan trọng, bằng tiếng Việt."
        )

        payload = {
            "model": self.openrouter_model,
            "messages": [
                {
                    "role": "system",
                    "content": "Bạn là chuyên gia y tế, hãy diễn đạt lại câu trả lời sao cho dễ hiểu.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": self.openrouter_temperature,
            "max_tokens": self.openrouter_max_tokens,
        }

        try:
            response = requests.post(
                self.openrouter_url,
                headers=headers,
                json=payload,
                timeout=self.openrouter_timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except requests.exceptions.Timeout:
            logger.error("OpenRouter API timeout")
            return "Không thể tóm tắt do timeout."
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling OpenRouter API: {e}")
            return f"Lỗi khi tóm tắt: {str(e)}"
        except (KeyError, IndexError) as e:
            logger.error(f"Unexpected API response format: {e}")
            return "Lỗi khi xử lý phản hồi từ AI."

    def ask_question(
        self, user_question: str, threshold: Optional[float] = None, top_k: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Process user question and return relevant answers.

        Args:
            user_question: The question to answer
            threshold: Minimum similarity score (uses config default if None)
            top_k: Maximum results to return (uses config default if None)

        Returns:
            Dictionary with question, answers by field, and AI summary

        Raises:
            ValueError: If question is empty
        """
        if not user_question or not user_question.strip():
            raise ValueError("Câu hỏi trống")

        # Use default values from settings if not provided
        if threshold is None:
            threshold = self.settings.qa_threshold
        if top_k is None:
            top_k = self.settings.qa_top_k

        # Preprocess question
        cleaned_question = self.preprocess_text(user_question)
        if not cleaned_question:
            # If preprocessing removes everything, use original lowercased
            cleaned_question = user_question.lower()

        # Generate embedding and compute similarity
        user_emb = self.model.encode(cleaned_question, convert_to_tensor=True)
        cos_scores = util.cos_sim(user_emb, self.question_embeddings)[0]

        # Get top scoring results
        top_idx_scores = sorted(
            [(i, score.item()) for i, score in enumerate(cos_scores)],
            key=lambda x: x[1],
            reverse=True,
        )[:top_k]

        # Filter by threshold
        top_idx_scores = [(i, s) for i, s in top_idx_scores if s >= threshold]

        if not top_idx_scores:
            return {
                "question": user_question,
                "answers": {
                    "Không tìm thấy": [
                        "Xin lỗi, dữ liệu chưa được cập nhật cho câu hỏi này."
                    ]
                },
                "summary": "",
            }

        # Collect answers by field
        result = {}
        collected_answers = []

        for idx, score in top_idx_scores:
            row = self.df.iloc[idx]
            q_text = str(row["Câu hỏi"]).strip()
            a_text = str(row["Câu trả lời"]).strip()
            field = str(row["Lĩnh vực"]).strip()

            # Skip invalid answers
            if not a_text or a_text.lower() == "nan":
                continue

            field_name = (
                field if field and field.lower() != "nan" else "Chưa phân loại"
            )
            full_text = f"Q: {q_text}\nA: {a_text} ({field_name})"
            collected_answers.append(a_text)

            # Group by field with limit per field
            if field not in result:
                result[field] = []
            if len(result[field]) < self.max_per_field:
                result[field].append(full_text)

        # Generate AI summary
        summary = self.summarize_with_ai(user_question, collected_answers)

        return {"question": user_question, "answers": result, "summary": summary}
