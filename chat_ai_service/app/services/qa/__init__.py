"""
Q&A service package with decomposed components.
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

This package provides a clean QAService facade that internally
uses specialized components for model loading, dataset management,
search, and AI summarization.
"""

import logging
from typing import List, Dict, Optional, Tuple, Iterator

from .model_loader import ModelLoader
from .dataset_loader import DatasetLoader
from .question_hasher import (
    hash_question,
    hash_content_for_summary,
    create_cache_key,
    create_summary_cache_key,
)
from .ai_summarizer import AISummarizer
from app.core.qa_constants import (
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TOP_K,
    ANSWER_CACHE_TTL,
    SUMMARY_CACHE_TTL,
)

logger = logging.getLogger(__name__)


class QAService:
    """
    Q&A service facade that provides backward compatibility while using
    decomposed components internally.
    """

    def __init__(self, settings, cache_service=None):
        """
        Initialize Q&A service with decomposed components.

        Args:
            settings: Application settings
            cache_service: Optional cache service for caching results
        """
        self.settings = settings
        self.cache_service = cache_service
        self.max_per_field = getattr(settings, "qa_max_per_field", 5)

        # Initialize components
        self.model_loader = ModelLoader(settings.qa_model_path)
        self.dataset_loader = DatasetLoader(
            settings.qa_data_path, settings.qa_vocab_path
        )
        self.ai_summarizer = AISummarizer()

        # Lazy-loaded components
        self.vocab = None
        self.model = None
        self.df = None
        self.question_embeddings = None

        logger.info("QA Service initialized with decomposed components")

    async def initialize(self) -> None:
        """Initialize components that require async operations."""
        try:
            # Load model
            self.model = self.model_loader.load_model()
            if self.model is None:
                logger.error("Failed to load SBERT model")
                return

            # Load vocabulary
            self.vocab = self.dataset_loader.load_vocabulary()

            # Load dataset
            self.df = self.dataset_loader.load_dataset()
            if self.df is None:
                logger.error("Failed to load Q&A dataset")
                return

            # Pre-compute embeddings
            self.question_embeddings = self._compute_embeddings()

            logger.info("QA Service initialization completed successfully")

        except Exception as e:
            logger.error(f"QA Service initialization failed: {e}")

    def _compute_embeddings(self) -> List:
        """Compute embeddings for all questions in dataset."""
        try:
            questions = self.df["question"].tolist()
            embeddings = self.model_loader.get_embeddings(questions)
            logger.info(f"Computed embeddings for {len(questions)} questions")
            return embeddings
        except Exception as e:
            logger.error(f"Error computing embeddings: {e}")
            return []

    async def ask_question_stream(
        self,
        question: str,
        threshold: Optional[float] = None,
        top_k: Optional[int] = None,
    ) -> Iterator[str]:
        """
        Ask a question with streaming AI response.

        Args:
            question: User's question
            threshold: Similarity threshold
            top_k: Maximum results to return

        Yields:
            Streaming response chunks
        """
        if not self._is_ready():
            yield "Sorry, Q&A service is currently unavailable."
            return

        try:
            # Use defaults if not provided
            threshold = threshold or DEFAULT_SIMILARITY_THRESHOLD
            top_k = top_k or DEFAULT_TOP_K

            # Search for relevant answers
            answers = await self._search_similar_answers(question, threshold, top_k)

            if not answers:
                yield "Tôi không tìm thấy thông tin phù hợp cho câu hỏi của bạn."
                return

            # Generate AI summary stream
            summary_stream = self.ai_summarizer.generate_summary_stream(
                question, answers
            )
            async for chunk in summary_stream:
                yield chunk

        except Exception as e:
            logger.error(f"Error in ask_question_stream: {e}")
            yield "Xin lỗi, đã xảy ra lỗi khi xử lý câu hỏi của bạn."

    def _search_similar_answers(
        self, question: str, threshold: float, top_k: int
    ) -> List[Dict[str, any]]:
        """
        Search for similar answers using semantic search.

        Args:
            question: User's question
            threshold: Similarity threshold
            top_k: Maximum results

        Returns:
            List of similar answers with metadata
        """
        if not self._is_ready():
            return []

        try:
            # Generate question embedding
            question_embedding = self.model_loader.get_embeddings([question])[0]

            # Calculate similarities
            import torch
            from sentence_transformers import util

            similarities = util.cos_sim(question_embedding, self.question_embeddings)[0]

            # Filter by threshold
            valid_indices = (similarities >= threshold).nonzero(as_tuple=True)[0]
            if len(valid_indices) == 0:
                return []

            # Get top results
            top_scores = similarities[valid_indices]
            sorted_indices = top_scores.argsort(descending=True)[:top_k]
            top_indices = valid_indices[sorted_indices]

            # Format results with field grouping
            return self._format_search_results(top_indices, top_scores, top_k)

        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []

    def _format_search_results(
        self, indices, scores, top_k: int
    ) -> List[Dict[str, any]]:
        """Format search results with field grouping and limits."""
        try:
            results = []
            field_counts = {}

            for idx, score in zip(indices, scores):
                if len(results) >= top_k:
                    break

                row = self.df.iloc[idx]
                field = row["field"]

                # Check per-field limits
                if field not in field_counts:
                    field_counts[field] = 0
                if field_counts[field] >= self.max_per_field:
                    continue

                # Add result
                result = {
                    "answer": row["answer"],
                    "field": field,
                    "score": float(score),
                    "metadata": row.get("metadata", {}),
                }
                results.append(result)
                field_counts[field] += 1

            return results

        except Exception as e:
            logger.error(f"Error formatting search results: {e}")
            return []

    def _is_ready(self) -> bool:
        """Check if service is ready for use."""
        return (
            self.model is not None
            and self.df is not None
            and self.question_embeddings is not None
            and self.ai_summarizer.is_available()
        )

    def get_service_status(self) -> Dict[str, any]:
        """Get comprehensive status of the Q&A service."""
        return {
            "initialized": self._is_ready(),
            "model_info": self.model_loader.get_model_info()
            if self.model_loader
            else None,
            "dataset_info": self.dataset_loader.get_dataset_info()
            if self.dataset_loader
            else None,
            "ai_info": self.ai_summarizer.get_model_info()
            if self.ai_summarizer
            else None,
            "vocab_loaded": len(self.vocab) > 0 if self.vocab else False,
            "dataset_rows": len(self.df) if self.df is not None else 0,
            "embeddings_computed": self.question_embeddings is not None,
        }

    def get_health_check(self) -> Dict[str, any]:
        """Health check for monitoring."""
        status = "healthy" if self._is_ready() else "unhealthy"

        return {
            "status": status,
            "components": {
                "model_loaded": self.model is not None,
                "dataset_loaded": self.df is not None,
                "embeddings_ready": self.question_embeddings is not None,
                "ai_available": self.ai_summarizer.is_available()
                if self.ai_summarizer
                else False,
                "cache_available": self.cache_service is not None,
            },
        }

    # Maintain backward compatibility for hash functions
    def __hash_question(self, question: str) -> str:
        """Legacy hash_question method for backward compatibility."""
        return hash_question(question)

    def __hash_content_for_summary(self, question: str, answers: List[Dict]) -> str:
        """Legacy hash_content_for_summary method for backward compatibility."""
        return hash_content_for_summary(question, answers)


# Global QA service instance for backward compatibility
qa_service = None


def create_qa_service(settings, cache_service=None) -> QAService:
    """Factory function to create QA service instance."""
    return QAService(settings, cache_service)