"""
Dataset loading and preprocessing for Q&A service.
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

This module handles loading and preprocessing the Q&A dataset
with vocabulary filtering and data validation.
"""

import os
import json
import logging
import pandas as pd
from pathlib import Path
from typing import Tuple, Set, Optional, Dict, Any

from app.core.qa_constants import QA_VOCAB_FILE
from app.config import settings

logger = logging.getLogger(__name__)


class DatasetLoader:
    """Load and preprocess Q&A dataset for semantic search."""

    def __init__(
        self, data_path: Optional[str] = None, vocab_path: Optional[str] = None
    ):
        """
        Initialize dataset loader.

        Args:
            data_path: Path to Q&A data file
            vocab_path: Path to vocabulary file
        """
        self.data_path = data_path or settings.qa_data_path
        self.vocab_path = vocab_path or settings.qa_vocab_path
        self.vocab = set()
        self.data_loaded = False
        self.df = None
        self.question_embeddings = None

    def load_dataset(self) -> Optional[pd.DataFrame]:
        """
        Load Q&A dataset from file.

        Returns:
            Loaded DataFrame or None if loading fails
        """
        try:
            if not os.path.exists(self.data_path):
                logger.error(f"Dataset file not found: {self.data_path}")
                return None

            logger.info(f"Loading Q&A dataset from: {self.data_path}")

            # Try different file formats
            if self.data_path.endswith(".json"):
                df = self._load_json_dataset()
            elif self.data_path.endswith((".csv", ".xlsx", ".parquet")):
                df = self._load_tabular_dataset()
            else:
                # Default to JSON
                df = self._load_json_dataset()

            if df is not None and not df.empty:
                df = self._preprocess_dataset(df)
                self.df = df
                self.data_loaded = True
                logger.info(f"Dataset loaded successfully: {len(df)} rows")
                return df
            else:
                logger.error("No valid data found in dataset file")
                return None

        except Exception as e:
            logger.error(f"Error loading dataset: {e}")
            return None

    def _load_json_dataset(self) -> Optional[pd.DataFrame]:
        """Load dataset from JSON file."""
        try:
            with open(self.data_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                return pd.DataFrame(data)
            elif isinstance(data, dict) and "data" in data:
                return pd.DataFrame(data["data"])
            else:
                logger.error(f"Unexpected JSON structure in {self.data_path}")
                return None

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format in {self.data_path}: {e}")
            return None

    def _load_tabular_dataset(self) -> Optional[pd.DataFrame]:
        """Load dataset from CSV/Excel file."""
        try:
            if self.data_path.endswith(".csv"):
                return pd.read_csv(self.data_path)
            elif self.data_path.endswith(".xlsx"):
                return pd.read_excel(self.data_path)
            elif self.data_path.endswith(".parquet"):
                return pd.read_parquet(self.data_path)
            else:
                logger.error(f"Unsupported file format: {self.data_path}")
                return None

        except Exception as e:
            logger.error(f"Error loading tabular dataset: {e}")
            return None

    def _preprocess_dataset(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Preprocess the loaded dataset.

        Args:
            df: Raw DataFrame

        Returns:
            Preprocessed DataFrame
        """
        # Ensure required columns exist
        required_columns = ["question", "answer", "field"]
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            logger.error(f"Missing required columns: {missing_columns}")
            return pd.DataFrame()

        # Clean and validate data
        df = df.copy()
        df["question"] = df["question"].astype(str).str.strip()
        df["answer"] = df["answer"].astype(str).str.strip()
        df["field"] = df["field"].astype(str).str.strip()

        # Remove empty rows
        df = df[df["question"].str.len() > 0]
        df = df[df["answer"].str.len() > 0]
        df = df[df["field"].str.len() > 0]

        # Apply vocabulary filtering if available
        if self.vocab:
            df = self._filter_by_vocab(df)

        # Add metadata if not present
        if "metadata" not in df.columns:
            df["metadata"] = "{}"

        logger.info(f"Preprocessed dataset: {len(df)} valid rows")
        return df

    def _filter_by_vocab(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter dataset using vocabulary.

        Args:
            df: DataFrame to filter

        Returns:
            Filtered DataFrame
        """
        if not self.vocab:
            return df

        def contains_vocab_words(text: str) -> bool:
            """Check if text contains vocabulary words."""
            words = text.lower().split()
            return any(word in self.vocab for word in words)

        # Filter questions and answers
        valid_questions = df["question"].apply(contains_vocab_words)
        valid_answers = df["answer"].apply(contains_vocab_words)

        # Keep rows where either question or answer contains vocab words
        df_filtered = df[valid_questions | valid_answers]

        logger.info(f"Vocabulary filtering: {len(df)} -> {len(df_filtered)} rows")
        return df_filtered

    def load_vocabulary(self) -> Set[str]:
        """
        Load vocabulary from file.

        Returns:
            Set of vocabulary words
        """
        if not os.path.exists(self.vocab_path):
            logger.warning(
                f"Vocabulary file not found: {self.vocab_path}. "
                "Proceeding without vocabulary filtering."
            )
            return set()

        try:
            with open(self.vocab_path, "r", encoding="utf-8") as f:
                vocab = set(line.strip().lower() for line in f if line.strip())
            self.vocab = vocab
            logger.info(f"Loaded {len(vocab)} words from vocabulary")
            return vocab

        except Exception as e:
            logger.error(f"Error loading vocabulary: {e}")
            return set()

    def get_dataset_info(self) -> Dict[str, Any]:
        """
        Get information about the loaded dataset.

        Returns:
            Dictionary with dataset information
        """
        if not self.data_loaded or self.df is None:
            return {
                "loaded": False,
                "path": self.data_path,
                "vocab_loaded": len(self.vocab) > 0,
                "vocab_size": len(self.vocab),
            }

        info = {
            "loaded": True,
            "path": self.data_path,
            "vocab_loaded": len(self.vocab) > 0,
            "vocab_size": len(self.vocab),
            "total_rows": len(self.df),
            "columns": list(self.df.columns),
        }

        # Add field distribution
        if "field" in self.df.columns:
            info["field_distribution"] = self.df["field"].value_counts().to_dict()

        # Add basic statistics
        if "question" in self.df.columns:
            info["question_length_stats"] = {
                "min": self.df["question"].str.len().min(),
                "max": self.df["question"].str.len().max(),
                "mean": self.df["question"].str.len().mean(),
            }

        return info

    def get_sample_data(self, n: int = 5) -> pd.DataFrame:
        """
        Get sample rows from the dataset.

        Args:
            n: Number of sample rows

        Returns:
            DataFrame with sample data
        """
        if not self.data_loaded or self.df is None:
            return pd.DataFrame()

        return self.df.head(n)

    def is_dataset_loaded(self) -> bool:
        """Check if dataset is loaded and available."""
        return self.data_loaded and self.df is not None
