"""
Q&A Service using SBERT and OpenRouter AI.
"""

import pandas as pd
from sentence_transformers import SentenceTransformer, util
import os
import requests
import re
import logging
from typing import Dict, List, Set
from app.utils.storage import StorageManager

logger = logging.getLogger(__name__)


class QAService:
    """Service for handling health-related Q&A using semantic search."""

    def __init__(self, settings):
        """Initialize Q&A service with model and data from GCS."""
        self.settings = settings

        # Initialize GCS storage manager
        if not settings.qa_gcs_bucket:
            raise ValueError("qa_gcs_bucket is required for Q&A service")

        self.storage = StorageManager(
            storage_type="gcs",
            gcs_bucket=settings.qa_gcs_bucket,
            local_cache_dir=settings.qa_local_cache_dir,
        )
        logger.info(
            f"Storage manager initialized with GCS bucket: {settings.qa_gcs_bucket}"
        )

        # File paths (will be resolved by storage manager)
        self.model_path_remote = settings.qa_model_path
        self.data_path_remote = settings.qa_data_path
        self.vocab_path_remote = settings.qa_vocab_path

        # Load components
        self.vocab = self._load_vocab()
        self.model = self._load_model()
        self.df, self.question_embeddings = self._load_data()

        # OpenRouter configuration
        self.openrouter_api_key = settings.openrouter_api_key or os.getenv(
            "OPENROUTER_API_KEY"
        )
        self.openrouter_model = settings.openrouter_model
        self.openrouter_timeout = settings.openrouter_timeout
        self.openrouter_url = "https://openrouter.ai/api/v1/chat/completions"

    def _load_vocab(self) -> Set[str]:
        """Load vocabulary from file."""
        try:
            # Get local path (downloads from GCS if needed)
            vocab_path = self.storage.get_file_path(self.vocab_path_remote)
            logger.info(f"Loading vocabulary from: {vocab_path}")

            with open(vocab_path, "r", encoding="utf-8") as f:
                vocab = set(line.strip().lower() for line in f if line.strip())
            logger.info(f"Loaded {len(vocab)} words from vocabulary")
            return vocab
        except FileNotFoundError:
            logger.warning(f"Vocabulary file not found: {self.vocab_path_remote}")
            return set()
        except Exception as e:
            logger.error(f"Error loading vocabulary: {e}")
            return set()

    def _load_model(self) -> SentenceTransformer:
        """Load SBERT model from GCS storage."""
        try:
            # Get model from GCS storage
            model_path = self.storage.get_directory_path(self.model_path_remote)
            logger.info(f"Loading SBERT model from GCS: {model_path}")
            return SentenceTransformer(model_path)
        except Exception as e:
            logger.error(f"Error loading model from GCS: {e}")
            logger.error("Please ensure the model files are uploaded to GCS bucket")
            raise

    def _load_data(self):
        """Load and preprocess dataset."""
        try:
            # Get local path (downloads from GCS if needed)
            data_path = self.storage.get_file_path(self.data_path_remote)
            logger.info(f"Loading dataset from: {data_path}")

            df = pd.read_excel(data_path)
            required_cols = ["Question", "Answer", "Keywords", "Field"]

            for col in required_cols:
                if col not in df.columns:
                    raise ValueError(f"Column '{col}' not found in dataset")

            # Preprocess questions
            df["question_clean"] = (
                df["Question"].astype(str).apply(self.preprocess_text)
            )

            logger.info(f"Creating embeddings for {len(df)} questions...")
            question_embeddings = self.model.encode(
                df["question_clean"].tolist(),
                convert_to_tensor=True,
                show_progress_bar=True,
            )

            logger.info("Data loaded and embeddings created successfully")
            return df, question_embeddings

        except Exception as e:
            logger.error(f"Error loading data: {e}")
            raise

    def preprocess_text(self, text: str) -> str:
        """Preprocess text."""
        text = text.lower()
        text = re.sub(r"[^a-z0-9\u00C0-\u017F\s]", " ", text)
        words = text.split()

        if self.vocab:
            words = [w for w in words if w in self.vocab]

        return " ".join(words)

    def summarize_with_ai(
        self, user_question: str, collected_answers: List[str]
    ) -> str:
        """Summarize answers using OpenRouter AI."""
        if not collected_answers:
            return "Sorry, no data available to summarize."

        if not self.openrouter_api_key:
            logger.warning("OpenRouter API key not configured")
            return "AI summarization is unavailable (missing API key)."

        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
        }

        prompt = (
            f"User question: {user_question}\n\n"
            f"Answers from data:\n- "
            + "\n- ".join(collected_answers)
            + "\n\nPlease summarize concisely and clearly, keeping important information. Respond in Vietnamese."
        )

        payload = {
            "model": self.openrouter_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a healthcare expert. Please rephrase the answer in an easy-to-understand way. Always respond in Vietnamese.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.5,
            "max_tokens": 400,
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
            return "Unable to summarize due to timeout."
        except Exception as e:
            logger.error(f"Error calling AI: {e}")
            return f"Error during summarization: {str(e)}"

    def ask_question(
        self, user_question: str, threshold: float = None, top_k: int = None
    ) -> Dict:
        """Process user question and return relevant answers."""
        if not user_question.strip():
            raise ValueError("Question is empty")

        # Use default values from settings if not provided
        if threshold is None:
            threshold = self.settings.qa_threshold
        if top_k is None:
            top_k = self.settings.qa_top_k

        cleaned_question = self.preprocess_text(user_question)
        if not cleaned_question:
            cleaned_question = user_question.lower()

        user_emb = self.model.encode(cleaned_question, convert_to_tensor=True)
        cos_scores = util.cos_sim(user_emb, self.question_embeddings)[0]

        top_idx_scores = sorted(
            [(i, score.item()) for i, score in enumerate(cos_scores)],
            key=lambda x: x[1],
            reverse=True,
        )[:top_k]

        top_idx_scores = [(i, s) for i, s in top_idx_scores if s >= threshold]

        if not top_idx_scores:
            return {
                "question": user_question,
                "answers": {
                    "Not Found": ["Sorry, no data available for this question yet."]
                },
                "summary": "",
            }

        result = {}
        collected_answers = []
        MAX_PER_FIELD = 5

        for idx, score in top_idx_scores:
            row = self.df.iloc[idx]
            q_text = str(row["Question"]).strip()
            a_text = str(row["Answer"]).strip()
            field = str(row["Field"]).strip()

            if not a_text or a_text.lower() == "nan":
                continue

            field_name = field if field and field.lower() != "nan" else "Uncategorized"
            full_text = f"Q: {q_text}\nA: {a_text} ({field_name})"
            collected_answers.append(a_text)

            if field not in result:
                result[field] = []
            if len(result[field]) < MAX_PER_FIELD:
                result[field].append(full_text)

        summary = self.summarize_with_ai(user_question, collected_answers)

        return {"question": user_question, "answers": result, "summary": summary}
