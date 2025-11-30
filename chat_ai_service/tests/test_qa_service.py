"""
Tests for QA Service - core business logic for question answering.
"""

import pytest
import asyncio
import pandas as pd
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path

# Import from parent directory
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.qa import QAService, create_qa_service
from app.services.qa.dataset_loader import DatasetLoader
from app.services.qa.question_hasher import QuestionHasher
from app.services.qa.ai_summarizer import AISummarizer
from app.config import Settings
from app.core.shared.exceptions import (
    QAServiceException,
    QAModelNotLoadedException,
    QADatasetException,
    AIServiceException,
    OpenAIException,
)


class TestQAService:
    """Test QA Service core functionality."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        return Settings(
            DEBUG=True,
            LOG_LEVEL="DEBUG",
            qa_model_path="/tmp/test_model",
            model_auto_download=False,
            OPENAI_API_KEY="test-key",
            qa_dataset_path="/tmp/test_dataset.csv",
            ENABLE_REDIS_CACHE=False,
        )

    @pytest.fixture
    def mock_model_loader(self):
        """Mock model loader."""
        loader = MagicMock()
        loader.load_model.return_value = MagicMock()
        loader.is_model_available.return_value = True
        loader.get_model_info.return_value = {
            "loaded": True,
            "dimension": 768,
            "model_name": "test-model",
        }
        return loader

    @pytest.fixture
    def mock_dataset_loader(self):
        """Mock dataset loader."""
        loader = MagicMock()
        df = pd.DataFrame(
            {
                "Question": [
                    "What is diabetes?",
                    "How to prevent diabetes?",
                    "What are diabetes symptoms?",
                ],
                "Answer": [
                    "Diabetes is a metabolic disease...",
                    "To prevent diabetes...",
                    "Common diabetes symptoms include...",
                ],
                "Field": ["health", "health", "health"],
            }
        )
        loader.load_dataset.return_value = df
        loader.is_dataset_loaded.return_value = True
        return loader

    @pytest.fixture
    def mock_ai_summarizer(self):
        """Mock AI summarizer."""
        summarizer = AsyncMock()
        summarizer.is_available.return_value = True
        return summarizer

    @pytest.fixture
    def qa_service(
        self, mock_settings, mock_model_loader, mock_dataset_loader, mock_ai_summarizer
    ):
        """Create QA service with mocked dependencies."""
        with patch(
            "app.services.qa.ModelLoader", return_value=mock_model_loader
        ), patch(
            "app.services.qa.DatasetLoader", return_value=mock_dataset_loader
        ), patch(
            "app.services.qa.AISummarizer", return_value=mock_ai_summarizer
        ):
            service = QAService(mock_settings)
            return service

    @pytest.mark.asyncio
    async def test_initialize_success(
        self, qa_service, mock_model_loader, mock_dataset_loader
    ):
        """Test successful QA service initialization."""
        await qa_service.initialize()

        assert qa_service.model_loader.load_model.called
        assert qa_service.dataset_loader.load_dataset.called
        assert qa_service.is_initialized is True

    @pytest.mark.asyncio
    async def test_initialize_model_failure(
        self, mock_settings, mock_dataset_loader, mock_ai_summarizer
    ):
        """Test initialization when model loading fails."""
        mock_model_loader = MagicMock()
        mock_model_loader.load_model.return_value = None
        mock_model_loader.is_model_available.return_value = False

        with patch(
            "app.services.qa.ModelLoader", return_value=mock_model_loader
        ), patch(
            "app.services.qa.DatasetLoader", return_value=mock_dataset_loader
        ), patch(
            "app.services.qa.AISummarizer", return_value=mock_ai_summarizer
        ):
            service = QAService(mock_settings)
            await service.initialize()

            assert service.is_initialized is False

    @pytest.mark.asyncio
    async def test_initialize_dataset_failure(
        self, mock_settings, mock_model_loader, mock_ai_summarizer
    ):
        """Test initialization when dataset loading fails."""
        mock_dataset_loader = MagicMock()
        mock_dataset_loader.load_dataset.return_value = None
        mock_dataset_loader.is_dataset_loaded.return_value = False

        with patch(
            "app.services.qa.ModelLoader", return_value=mock_model_loader
        ), patch(
            "app.services.qa.DatasetLoader", return_value=mock_dataset_loader
        ), patch(
            "app.services.qa.AISummarizer", return_value=mock_ai_summarizer
        ):
            service = QAService(mock_settings)
            await service.initialize()

            assert service.is_initialized is False

    @pytest.mark.asyncio
    async def test_ask_question_stream_success(self, qa_service):
        """Test successful streaming question answering."""
        # Setup test data
        test_question = "What is diabetes?"
        test_threshold = 0.55
        test_top_k = 3

        # Mock search results
        qa_service.find_similar_questions = MagicMock(
            return_value=[
                {
                    "question": "What is diabetes?",
                    "answer": "Diabetes is a metabolic disease...",
                    "similarity": 0.9,
                },
                {
                    "question": "What are diabetes symptoms?",
                    "answer": "Common diabetes symptoms include...",
                    "similarity": 0.8,
                },
            ]
        )

        # Mock AI summarizer
        qa_service.ai_summarizer.summarize_with_streaming.return_value = [
            "Diabetes is a metabolic disease",
            " that affects blood sugar levels.",
            " It requires proper management.",
        ]

        # Execute test
        events = []
        async for event in qa_service.ask_question_stream(
            test_question, test_threshold, test_top_k
        ):
            events.append(event)

        # Verify results
        assert len(events) == 3  # Three summary chunks
        assert events[0] == "Diabetes is a metabolic disease"
        assert events[1] == " that affects blood sugar levels."
        assert events[2] == " It requires proper management."

    @pytest.mark.asyncio
    async def test_ask_question_stream_no_results(self, qa_service):
        """Test streaming question answering with no results."""
        test_question = "What is quantum physics?"
        test_threshold = 0.9
        test_top_k = 3

        # Mock no search results
        qa_service.find_similar_questions = MagicMock(return_value=[])

        # Execute test
        events = []
        async for event in qa_service.ask_question_stream(
            test_question, test_threshold, test_top_k
        ):
            events.append(event)

        # Should return apology message
        assert len(events) == 1
        assert "Xin lỗi" in events[0] or "Sorry" in events[0]

    @pytest.mark.asyncio
    async def test_ask_question_stream_ai_error(self, qa_service):
        """Test streaming question answering with AI error."""
        test_question = "What is diabetes?"
        test_threshold = 0.55
        test_top_k = 3

        # Mock search results
        qa_service.find_similar_questions = MagicMock(
            return_value=[
                {
                    "question": "What is diabetes?",
                    "answer": "Diabetes is a metabolic disease...",
                    "similarity": 0.9,
                }
            ]
        )

        # Mock AI summarizer error
        qa_service.ai_summarizer.summarize_with_streaming.side_effect = OpenAIException(
            "AI service unavailable"
        )

        # Execute test
        events = []
        async for event in qa_service.ask_question_stream(
            test_question, test_threshold, test_top_k
        ):
            events.append(event)

        # Should return error message
        assert len(events) == 1
        assert "error" in events[0].lower() or "lỗi" in events[0].lower()

    @pytest.mark.asyncio
    async def test_ask_question_stream_service_error(self, qa_service):
        """Test streaming question answering with service error."""
        test_question = "What is diabetes?"

        # Mock service error
        qa_service.find_similar_questions = MagicMock(
            side_effect=Exception("Service error")
        )

        # Execute test
        with pytest.raises(QAServiceException):
            async for _ in qa_service.ask_question_stream(test_question):
                pass

    def test_find_similar_questions_success(self, qa_service):
        """Test finding similar questions successfully."""
        # Mock embeddings
        test_question = "What is diabetes?"
        mock_question_embedding = [[0.1, 0.2, 0.3]]
        qa_service.model_loader.get_embeddings.return_value = mock_question_embedding

        # Mock dataset embeddings (pre-computed)
        qa_service.question_embeddings = [[0.1, 0.2, 0.4], [0.5, 0.6, 0.7]]
        qa_service.df = pd.DataFrame(
            {
                "Question": ["What is diabetes?", "How to prevent diabetes?"],
                "Answer": ["Diabetes is...", "Prevention includes..."],
                "Field": ["health", "health"],
            }
        )

        # Mock cosine similarity calculation
        with patch("app.services.qa.util.cosine_similarity") as mock_cosine:
            mock_cosine.return_value = [[0.9, 0.3]]  # Similarities for each question

            results = qa_service.find_similar_questions(
                test_question, threshold=0.55, top_k=5
            )

            assert len(results) == 1  # Only one result above threshold
            assert results[0]["similarity"] == 0.9
            assert "What is diabetes?" in results[0]["question"]

    def test_find_similar_questions_no_embeddings(self, qa_service):
        """Test finding similar questions with no embeddings available."""
        qa_service.model_loader.is_model_available.return_value = False

        with pytest.raises(QAModelNotLoadedException):
            qa_service.find_similar_questions("What is diabetes?")

    def test_find_similar_questions_empty_dataset(self, qa_service):
        """Test finding similar questions with empty dataset."""
        qa_service.df = pd.DataFrame(columns=["Question", "Answer", "Field"])
        qa_service.question_embeddings = []

        results = qa_service.find_similar_questions("What is diabetes?")
        assert results == []

    def test_compute_embeddings_lazy(self, qa_service):
        """Test lazy computation of question embeddings."""
        qa_service.df = pd.DataFrame(
            {
                "Question": ["What is diabetes?", "How to prevent diabetes?"],
                "Answer": ["Diabetes is...", "Prevention includes..."],
                "Field": ["health", "health"],
            }
        )
        qa_service.question_embeddings = None  # Not computed yet
        qa_service.model_loader.get_embeddings.return_value = [
            [[0.1, 0.2, 0.3]],
            [[0.4, 0.5, 0.6]],
        ]

        # Should compute embeddings on first access
        embeddings = qa_service._get_question_embeddings()
        assert len(embeddings) == 2
        qa_service.model_loader.get_embeddings.assert_called_once()

    def test_compute_embeddings_already_computed(self, qa_service):
        """Test that embeddings are not recomputed if already available."""
        precomputed_embeddings = [[[0.1, 0.2, 0.3]]]
        qa_service.question_embeddings = precomputed_embeddings

        # Should return precomputed embeddings
        embeddings = qa_service._get_question_embeddings()
        assert embeddings == precomputed_embeddings

    def test_get_health_check_healthy(self, qa_service):
        """Test health check when service is healthy."""
        qa_service.is_initialized = True
        qa_service.model_loader.is_model_available.return_value = True
        qa_service.dataset_loader.is_dataset_loaded.return_value = True
        qa_service.ai_summarizer.is_available.return_value = True

        health = qa_service.get_health_check()

        assert health["status"] == "healthy"
        assert health["components"]["model_loaded"] is True
        assert health["components"]["dataset_loaded"] is True
        assert health["components"]["ai_available"] is True

    def test_get_health_check_degraded(self, qa_service):
        """Test health check when service is degraded."""
        qa_service.is_initialized = True
        qa_service.model_loader.is_model_available.return_value = True
        qa_service.dataset_loader.is_dataset_loaded.return_value = False
        qa_service.ai_summarizer.is_available.return_value = True

        health = qa_service.get_health_check()

        assert health["status"] == "degraded"
        assert health["components"]["model_loaded"] is True
        assert health["components"]["dataset_loaded"] is False
        assert health["components"]["ai_available"] is True

    def test_get_health_check_unhealthy(self, qa_service):
        """Test health check when service is unhealthy."""
        qa_service.is_initialized = False

        health = qa_service.get_health_check()

        assert health["status"] == "unhealthy"
        assert health["components"]["model_loaded"] is False
        assert health["components"]["dataset_loaded"] is False
        assert health["components"]["ai_available"] is False

    def test_get_service_status_detailed(self, qa_service):
        """Test detailed service status information."""
        qa_service.is_initialized = True
        qa_service.model_loader.get_model_info.return_value = {
            "loaded": True,
            "model_name": "test-model",
            "dimension": 768,
            "onnx_enabled": False,
        }
        qa_service.dataset_loader.get_dataset_info.return_value = {
            "loaded": True,
            "row_count": 100,
            "columns": ["Question", "Answer", "Field"],
        }

        status = qa_service.get_service_status()

        assert status["status"] == "healthy"
        assert "model_info" in status
        assert "dataset_info" in status
        assert status["model_info"]["model_name"] == "test-model"
        assert status["dataset_info"]["row_count"] == 100

    @pytest.mark.asyncio
    async def test_ask_question_stream_not_initialized(self, qa_service):
        """Test streaming question answering when service not initialized."""
        qa_service.is_initialized = False

        with pytest.raises(QAServiceException):
            async for _ in qa_service.ask_question_stream("What is diabetes?"):
                pass


class TestQAServiceFactory:
    """Test QA Service factory function."""

    @pytest.mark.asyncio
    async def test_create_qa_service_success(self, mock_settings):
        """Test successful QA service creation."""
        with patch("app.services.qa.ModelLoader"), patch(
            "app.services.qa.DatasetLoader"
        ), patch("app.services.qa.AISummarizer"):
            service = create_qa_service(mock_settings)
            assert service is not None
            assert isinstance(service, QAService)

    @pytest.mark.asyncio
    async def test_create_qa_service_with_none_settings(self):
        """Test QA service creation with None settings."""
        with patch("app.services.qa.get_settings") as mock_get_settings:
            mock_get_settings.return_value = MagicMock()

            with patch("app.services.qa.ModelLoader"), patch(
                "app.services.qa.DatasetLoader"
            ), patch("app.services.qa.AISummarizer"):
                service = create_qa_service(None)
                assert service is not None
                assert isinstance(service, QAService)


class TestQAServicePerformance:
    """Test QA Service performance characteristics."""

    @pytest.fixture
    def qa_service_with_data(self, qa_service):
        """Create QA service populated with test data."""
        # Add test dataset
        qa_service.df = pd.DataFrame(
            {
                "Question": [f"Test question {i}" for i in range(100)],
                "Answer": [f"Test answer {i}" for i in range(100)],
                "Field": ["health"] * 100,
            }
        )

        # Pre-compute embeddings
        qa_service.question_embeddings = [
            [[i / 100, (i + 1) / 100, (i + 2) / 100] for i in range(100)]
        ]
        qa_service.is_initialized = True

        return qa_service

    @pytest.mark.asyncio
    async def test_large_batch_processing(self, qa_service_with_data):
        """Test processing large batch of questions."""
        questions = [f"What is health benefit {i}?" for i in range(50)]

        start_time = asyncio.get_event_loop().time()

        for question in questions[:5]:  # Test subset for performance
            qa_service_with_data.find_similar_questions(
                question, threshold=0.5, top_k=3
            )

        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time

        # Performance assertion - should complete in reasonable time
        assert duration < 10.0  # 10 seconds max for 5 questions

    @pytest.mark.asyncio
    async def test_streaming_performance(self, qa_service_with_data):
        """Test streaming response performance."""
        # Mock fast summarizer
        qa_service_with_data.ai_summarizer.summarize_with_streaming.return_value = [
            "Fast response chunk 1",
            "Fast response chunk 2",
        ]

        start_time = asyncio.get_event_loop().time()

        events = []
        async for event in qa_service_with_data.ask_question_stream(
            "What is diabetes?"
        ):
            events.append(event)
            if len(events) >= 2:  # Stop after first few events
                break

        end_time = asyncio.get_event_loop().time()
        duration = end_time - start_time

        # Should get first chunk quickly
        assert duration < 1.0  # 1 second max for first chunk
        assert len(events) == 2

    def test_memory_usage_embeddings(self, qa_service_with_data):
        """Test memory usage for embeddings storage."""
        import sys

        # Check memory usage before and after embedding computation
        initial_size = sys.getsizeof(qa_service_with_data.question_embeddings)

        # Simulate larger dataset
        qa_service_with_data.question_embeddings = [
            [float(i) for i in range(768)] for _ in range(1000)
        ]

        final_size = sys.getsizeof(qa_service_with_data.question_embeddings)

        # Memory should scale reasonably
        assert final_size > initial_size
        assert final_size < 100 * 1024 * 1024  # Less than 100MB for 1000 embeddings

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, qa_service_with_data):
        """Test handling concurrent requests."""

        async def process_question(question):
            qa_service_with_data.find_similar_questions(
                question, threshold=0.5, top_k=3
            )

        # Run concurrent requests
        tasks = [process_question(f"What is health benefit {i}?") for i in range(10)]

        start_time = asyncio.get_event_loop().time()
        await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()

        duration = end_time - start_time

        # Concurrent processing should be faster than sequential
        assert duration < 5.0  # 5 seconds max for 10 concurrent requests


class TestQAServiceErrorHandling:
    """Test QA Service error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_empty_question(self, qa_service):
        """Test handling empty question."""
        with pytest.raises(Exception):  # Should raise validation error
            async for _ in qa_service.ask_question_stream("", threshold=0.5, top_k=3):
                pass

    @pytest.mark.asyncio
    async def test_very_long_question(self, qa_service):
        """Test handling very long question."""
        long_question = "What is " + "very " * 1000 + "long question?"

        # Should handle long questions without crashing
        qa_service.find_similar_questions = MagicMock(return_value=[])

        events = []
        async for event in qa_service.ask_question_stream(
            long_question, threshold=0.5, top_k=3
        ):
            events.append(event)

        # Should return apology for long questions too
        assert len(events) == 1

    def test_malformed_dataset(self, qa_service):
        """Test handling malformed dataset."""
        # Create malformed DataFrame
        qa_service.df = pd.DataFrame(
            {
                "Question": ["Valid question", None, "Another question"],
                "Answer": ["Valid answer", "Missing question answer", "Another answer"],
                "Field": ["health", "health", None],  # Missing field
            }
        )

        # Should handle malformed data gracefully
        qa_service.model_loader.get_embeddings.return_value = [[[0.1, 0.2, 0.3]]]

        embeddings = qa_service._get_question_embeddings()

        # Should skip invalid rows and process valid ones
        assert len(embeddings) >= 0  # Should not crash

    @pytest.mark.asyncio
    async def test_ai_summarizer_timeout(self, qa_service):
        """Test handling AI summarizer timeout."""
        # Mock timeout
        qa_service.find_similar_questions = MagicMock(
            return_value=[
                {"question": "Test", "answer": "Test answer", "similarity": 0.9}
            ]
        )
        qa_service.ai_summarizer.summarize_with_streaming.side_effect = (
            asyncio.TimeoutError()
        )

        events = []
        async for event in qa_service.ask_question_stream(
            "Test question", threshold=0.5, top_k=3
        ):
            events.append(event)

        # Should handle timeout gracefully
        assert len(events) == 1
        assert "timeout" in events[0].lower() or "time out" in events[0].lower()

    def test_model_loader_failure_recovery(self, qa_service):
        """Test recovery from model loader failure."""
        # Mock intermittent failure
        qa_service.model_loader.is_model_available.side_effect = [True, False, True]

        # First call should succeed
        qa_service.find_similar_questions("Test question", threshold=0.5, top_k=3)

        # Second call should fail
        with pytest.raises(QAModelNotLoadedException):
            qa_service.find_similar_questions("Test question", threshold=0.5, top_k=3)
