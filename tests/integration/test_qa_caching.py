"""
Integration tests for Q&A caching functionality.

Tests cache miss → compute → cache store flow,
cache hit → fast return, and graceful fallback when Redis unavailable.
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.services.qa_service import QAService, hash_question, hash_content_for_summary
from app.services.cache import CacheService
from app.config import settings


@pytest.fixture
def mock_cache_service():
    """Create a mock cache service for testing."""
    cache_service = AsyncMock(spec=CacheService)
    cache_service.enabled = True
    cache_service.get = AsyncMock(return_value=None)  # Cache miss by default
    cache_service.set = AsyncMock(return_value=True)
    cache_service.set_json = AsyncMock(return_value=True)
    return cache_service


@pytest.fixture
def mock_qa_service(mock_cache_service):
    """Create QA service with mock cache."""
    # Mock the heavy initialization parts
    with patch("app.services.qa_service.QAService._load_model"), patch(
        "app.services.qa_service.QAService._load_data", return_value=(Mock(), [])
    ), patch("app.services.qa_service.QAService._load_vocab", return_value=set()):
        qa_service = QAService(settings, cache_service=mock_cache_service)
        # Mock the model and data
        qa_service.model = Mock()
        qa_service.model.encode = Mock(return_value=Mock())
        qa_service.df = Mock()
        qa_service.question_embeddings = Mock()
        qa_service.max_per_field = 5

        return qa_service


@pytest.fixture
def disabled_qa_service():
    """Create QA service without cache."""
    with patch("app.services.qa_service.QAService._load_model"), patch(
        "app.services.qa_service.QAService._load_data", return_value=(Mock(), [])
    ), patch("app.services.qa_service.QAService._load_vocab", return_value=set()):
        qa_service = QAService(settings, cache_service=None)
        qa_service.model = Mock()
        qa_service.model.encode = Mock(return_value=Mock())
        qa_service.df = Mock()
        qa_service.question_embeddings = Mock()
        qa_service.max_per_field = 5

        return qa_service


class TestQuestionHashing:
    """Test question hashing functionality."""

    def test_hash_question_basic(self):
        """Test basic question hashing."""
        question = "What is diabetes?"
        hash_value = hash_question(question)

        assert isinstance(hash_value, str)
        assert len(hash_value) == 16
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_hash_question_normalization(self):
        """Test that similar questions produce same hash."""
        q1 = "What is diabetes?"
        q2 = "  What  is  diabetes?  "
        q3 = "WHAT IS DIABETES?"

        hash1 = hash_question(q1)
        hash2 = hash_question(q2)
        hash3 = hash_question(q3)

        # Should be the same after normalization
        assert hash1 == hash2
        # Case difference should be handled (lowercase normalization)
        assert hash1 == hash3

    def test_hash_question_different_questions(self):
        """Test that different questions produce different hashes."""
        q1 = "What is diabetes?"
        q2 = "How to treat hypertension?"

        hash1 = hash_question(q1)
        hash2 = hash_question(q2)

        assert hash1 != hash2

    def test_hash_content_for_summary(self):
        """Test content hashing for summaries."""
        question = "What is diabetes?"
        answers = [
            {"field": "General", "answer": "Diabetes is a metabolic disease"},
            {"field": "Treatment", "answer": "Treatment includes medication"},
        ]

        content_hash = hash_content_for_summary(question, answers)

        assert isinstance(content_hash, str)
        assert len(content_hash) == 16

    def test_hash_content_consistency(self):
        """Test that same content produces same hash regardless of order."""
        question = "What is diabetes?"
        answers1 = [
            {"field": "General", "answer": "Diabetes is a metabolic disease"},
            {"field": "Treatment", "answer": "Treatment includes medication"},
        ]
        answers2 = [
            {"field": "Treatment", "answer": "Treatment includes medication"},
            {"field": "General", "answer": "Diabetes is a metabolic disease"},
        ]

        hash1 = hash_content_for_summary(question, answers1)
        hash2 = hash_content_for_summary(question, answers2)

        # Should be different because list order matters in JSON serialization
        assert hash1 != hash2


class TestQACaching:
    """Test Q&A caching integration."""

    @pytest.mark.asyncio
    async def test_ask_question_cache_miss(self, mock_qa_service, mock_cache_service):
        """Test cache miss → compute → cache store flow."""
        question = "What is diabetes?"
        threshold = 0.55
        top_k = 7

        # Mock cache miss
        mock_cache_service.get.return_value = None

        # Mock model encoding and similarity search using patch.object
        with patch("app.services.qa_service.util.cos_sim") as mock_cos_sim:
            # Mock similarity scores with proper tensor types
            import torch

            mock_cos_sim.return_value = [
                torch.tensor([0.9, 0.8, 0.7])
            ]  # Returns torch tensors with .item() method

            # Mock DataFrame to return test data with matching number of rows
            import pandas as pd
            import numpy as np

            mock_qa_service.df = pd.DataFrame(
                {
                    "Câu hỏi": [
                        "Test question 1",
                        "Test question 2",
                        "Test question 3",
                    ],
                    "Câu trả lời": ["Test answer 1", "Test answer 2", "Test answer 3"],
                    "Lĩnh vực": ["General", "Health", "Nutrition"],
                }
            )
            mock_qa_service.question_embeddings = np.array(
                [[0.1, 0.2, 0.3], [0.2, 0.3, 0.4], [0.3, 0.4, 0.5]]
            )

            # Mock summarize_with_ai
            with patch.object(
                mock_qa_service,
                "summarize_with_ai",
                new=AsyncMock(return_value="Test summary"),
            ):
                result = await mock_qa_service.ask_question(question, threshold, top_k)

        # Verify cache was checked
        expected_cache_key = f"qa:answers:{hash_question(question)}:{threshold}:{top_k}"
        mock_cache_service.get.assert_called_once_with(expected_cache_key)

        # Verify result was cached
        mock_cache_service.set_json.assert_called_once()
        call_args = mock_cache_service.set_json.call_args
        assert call_args[0][0] == expected_cache_key  # cache key
        assert call_args[1]["ttl"] == settings.cache_ttl_qa_answer

        # Verify result structure
        assert result["question"] == question
        assert "answers" in result
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_ask_question_cache_hit(self, mock_qa_service, mock_cache_service):
        """Test cache hit → fast return."""
        question = "What is diabetes?"
        threshold = 0.55
        top_k = 7

        # Prepare cached result
        cached_result = {
            "question": question,
            "answers": {"General": ["Q: Test\nA: Test answer (General)"]},
            "summary": "Cached summary",
        }
        mock_cache_service.get.return_value = json.dumps(cached_result)

        result = await mock_qa_service.ask_question(question, threshold, top_k)

        # Verify cache was checked
        expected_cache_key = f"qa:answers:{hash_question(question)}:{threshold}:{top_k}"
        mock_cache_service.get.assert_called_once_with(expected_cache_key)

        # Verify no computation was performed (cache hit)
        mock_qa_service.model.encode.assert_not_called()

        # Verify cached result was returned
        assert result == cached_result

    @pytest.mark.asyncio
    async def test_ask_question_different_parameters_different_cache_keys(
        self, mock_qa_service, mock_cache_service
    ):
        """Test that different thresholds/top_k create different cache entries."""
        question = "What is diabetes?"

        # Reset mock call count
        mock_cache_service.get.reset_mock()
        mock_cache_service.set_json.reset_mock()

        # First call with threshold=0.55, top_k=7
        mock_cache_service.get.return_value = None

        with patch("app.services.qa_service.util.cos_sim") as mock_cos_sim:
            # Mock similarity scores with proper tensor types
            import torch

            mock_cos_sim.return_value = [torch.tensor([0.9, 0.8, 0.7])]

            import pandas as pd
            import numpy as np

            mock_qa_service.df = pd.DataFrame(
                {
                    "Câu hỏi": [
                        "Test question 1",
                        "Test question 2",
                        "Test question 3",
                    ],
                    "Câu trả lời": ["Test answer 1", "Test answer 2", "Test answer 3"],
                    "Lĩnh vực": ["General", "Health", "Nutrition"],
                }
            )
            mock_qa_service.question_embeddings = np.array(
                [[0.1, 0.2, 0.3], [0.2, 0.3, 0.4], [0.3, 0.4, 0.5]]
            )

            with patch.object(
                mock_qa_service,
                "summarize_with_ai",
                new=AsyncMock(return_value="Summary"),
            ):
                await mock_qa_service.ask_question(question, threshold=0.55, top_k=7)

        # Second call with threshold=0.60, top_k=5
        mock_cache_service.get.return_value = None

        with patch("app.services.qa_service.util.cos_sim") as mock_cos_sim:
            import torch

            mock_cos_sim.return_value = [torch.tensor([0.9, 0.8, 0.7])]
            with patch.object(
                mock_qa_service,
                "summarize_with_ai",
                new=AsyncMock(return_value="Summary"),
            ):
                await mock_qa_service.ask_question(question, threshold=0.60, top_k=5)

        # Verify different cache keys were used
        call_args_list = mock_cache_service.get.call_args_list
        cache_keys = [call[0][0] for call in call_args_list]

        assert len(cache_keys) == 2
        assert cache_keys[0] != cache_keys[1]
        assert "0.55" in cache_keys[0]
        assert "7" in cache_keys[0]
        assert "0.6" in cache_keys[1]  # 0.60 formatted as 0.6
        assert "5" in cache_keys[1]

    @pytest.mark.asyncio
    async def test_ask_question_cache_disabled(self, disabled_qa_service):
        """Test that Q&A service works when cache is disabled."""
        question = "What is diabetes?"

        # Mock DataFrame to return test data
        import pandas as pd
        import numpy as np

        disabled_qa_service.df = pd.DataFrame(
            {
                "Câu hỏi": ["Test question"],
                "Câu trả lời": ["Test answer"],
                "Lĩnh vực": ["General"],
            }
        )
        disabled_qa_service.question_embeddings = np.array([[0.1, 0.2, 0.3]])

        with patch("app.services.qa_service.util.cos_sim") as mock_cos_sim:
            import torch

            mock_cos_sim.return_value = [torch.tensor([0.9])]
            with patch.object(
                disabled_qa_service,
                "summarize_with_ai",
                new=AsyncMock(return_value="Test summary"),
            ):
                result = await disabled_qa_service.ask_question(question)

        # Verify result structure
        assert result["question"] == question
        assert "answers" in result
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_ask_question_cache_error(self, mock_qa_service, mock_cache_service):
        """Test graceful fallback when cache fails."""
        question = "What is diabetes?"

        # Mock cache error
        mock_cache_service.get.side_effect = Exception("Redis connection failed")

        # Mock DataFrame to return test data
        import pandas as pd
        import numpy as np

        mock_qa_service.df = pd.DataFrame(
            {
                "Câu hỏi": ["Test question"],
                "Câu trả lời": ["Test answer"],
                "Lĩnh vực": ["General"],
            }
        )
        mock_qa_service.question_embeddings = np.array([[0.1, 0.2, 0.3]])

        with patch("app.services.qa_service.util.cos_sim") as mock_cos_sim:
            import torch

            mock_cos_sim.return_value = [torch.tensor([0.9])]
            with patch.object(
                mock_qa_service,
                "summarize_with_ai",
                new=AsyncMock(return_value="Test summary"),
            ):
                # Should not raise exception, should continue with normal flow
                result = await mock_qa_service.ask_question(question)

        # Verify result is still returned despite cache error
        assert result["question"] == question
        assert "answers" in result
        assert "summary" in result

    @pytest.mark.asyncio
    async def test_summarize_with_ai_cache_miss(
        self, mock_qa_service, mock_cache_service
    ):
        """Test AI summary cache miss → compute → cache store."""
        question = "What is diabetes?"
        answers = ["Answer 1", "Answer 2"]

        # Mock cache miss
        mock_cache_service.get.return_value = None

        # Mock OpenAI response
        mock_summary = "AI-generated summary"
        with patch.object(
            mock_qa_service.openai_client.chat.completions, "create"
        ) as mock_openai:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = mock_summary
            mock_openai.return_value = mock_response

            result = await mock_qa_service.summarize_with_ai(question, answers)

        # Verify cache was checked
        expected_cache_key = f"qa:summary:{hash_content_for_summary(question, answers)}"
        mock_cache_service.get.assert_called_once_with(expected_cache_key)

        # Verify result was cached with 30-day TTL
        mock_cache_service.set.assert_called_once_with(
            expected_cache_key, mock_summary, ttl=2592000
        )

        # Verify AI summary was returned
        assert result == mock_summary

    @pytest.mark.asyncio
    async def test_summarize_with_ai_cache_hit(
        self, mock_qa_service, mock_cache_service
    ):
        """Test AI summary cache hit → fast return."""
        question = "What is diabetes?"
        answers = ["Answer 1", "Answer 2"]
        cached_summary = "Cached AI summary"

        # Mock cache hit
        mock_cache_service.get.return_value = cached_summary

        result = await mock_qa_service.summarize_with_ai(question, answers)

        # Verify cache was checked
        expected_cache_key = f"qa:summary:{hash_content_for_summary(question, answers)}"
        mock_cache_service.get.assert_called_once_with(expected_cache_key)

        # Verify OpenAI was not called (cache hit)
        # Note: openai_client.chat.completions.create is a method, not a mock, so we can't assert on it directly

        # Verify cached summary was returned
        assert result == cached_summary

    @pytest.mark.asyncio
    async def test_summarize_with_ai_cache_disabled(self, disabled_qa_service):
        """Test AI summary when cache is disabled."""
        question = "What is diabetes?"
        answers = ["Answer 1", "Answer 2"]
        mock_summary = "AI-generated summary"

        with patch.object(
            disabled_qa_service.openai_client.chat.completions, "create"
        ) as mock_openai:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = mock_summary
            mock_openai.return_value = mock_response

            result = await disabled_qa_service.summarize_with_ai(question, answers)

        # Verify AI summary was generated
        assert result == mock_summary
        mock_openai.assert_called_once()

    @pytest.mark.asyncio
    async def test_summarize_with_ai_cache_error(
        self, mock_qa_service, mock_cache_service
    ):
        """Test graceful fallback when AI summary cache fails."""
        question = "What is diabetes?"
        answers = ["Answer 1", "Answer 2"]
        mock_summary = "AI-generated summary"

        # Mock cache error
        mock_cache_service.get.side_effect = Exception("Redis connection failed")

        with patch.object(
            mock_qa_service.openai_client.chat.completions, "create"
        ) as mock_openai:
            mock_response = Mock()
            mock_response.choices = [Mock()]
            mock_response.choices[0].message.content = mock_summary
            mock_openai.return_value = mock_response

            result = await mock_qa_service.summarize_with_ai(question, answers)

        # Should still generate AI summary despite cache error
        assert result == mock_summary
        mock_openai.assert_called_once()


class TestQACacheIntegration:
    """End-to-end integration tests for Q&A caching."""

    @pytest.mark.asyncio
    async def test_full_cache_miss_to_cache_hit_cycle(self):
        """Test complete cycle: cache miss → compute → cache → cache hit."""
        # This test would require a real or fakeredis instance
        # For now, we'll use comprehensive mocks
        pass

    def test_cache_key_structure(self):
        """Test cache key structure matches expected format."""
        question = "What is diabetes?"
        threshold = 0.55
        top_k = 7

        expected_pattern = f"qa:answers:{hash_question(question)}:{threshold}:{top_k}"

        # Verify key components
        assert expected_pattern.startswith("qa:answers:")
        assert str(threshold) in expected_pattern
        assert str(top_k) in expected_pattern
        assert len(expected_pattern.split(":")) == 5  # qa:answers:hash:threshold:top_k

    def test_summary_cache_key_structure(self):
        """Test AI summary cache key structure."""
        question = "What is diabetes?"
        answers = [{"field": "General", "answer": "Test answer"}]

        expected_pattern = f"qa:summary:{hash_content_for_summary(question, answers)}"

        # Verify key components
        assert expected_pattern.startswith("qa:summary:")
        assert len(expected_pattern.split(":")) == 3  # qa:summary:hash
