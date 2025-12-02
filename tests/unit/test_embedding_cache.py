"""
Test embedding cache functionality (Phase 3).

Tests embedding serialization, cache hit/miss behavior, cache warming,
and performance requirements (<5ms cache hits).
"""
import pytest
import numpy as np
import time
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.cache import CacheService, create_cache_service
from app.services.qa_service import QAService
from app.config import settings


class TestEmbeddingSerialization:
    """Test msgpack-numpy serialization of embeddings."""

    @pytest.mark.asyncio
    async def test_embedding_roundtrip(self):
        """Test that embeddings can be cached and retrieved without data loss."""
        # Create test embedding (768-dim SBERT vector)
        original_embedding = np.random.rand(768).astype(np.float32)

        # Mock Redis client
        mock_redis = AsyncMock()
        stored_data = None

        async def mock_setex(key, ttl, data):
            nonlocal stored_data
            stored_data = data
            return True

        async def mock_get(key):
            return stored_data

        mock_redis.setex = mock_setex
        mock_redis.get = mock_get

        # Create cache service with mock
        cache_service = CacheService(mock_redis)

        # Cache embedding
        success = await cache_service.set_embedding("test:embedding", original_embedding)
        assert success is True

        # Retrieve embedding
        retrieved_embedding = await cache_service.get_embedding("test:embedding")

        # Verify data integrity
        assert retrieved_embedding is not None
        assert isinstance(retrieved_embedding, np.ndarray)
        assert retrieved_embedding.shape == original_embedding.shape
        assert np.allclose(retrieved_embedding, original_embedding, atol=1e-6)

    @pytest.mark.asyncio
    async def test_embedding_serialization_size(self):
        """Test that serialization is efficient (<10KB for 768-dim vector)."""
        import msgpack
        import msgpack_numpy as m

        # Create 768-dim embedding
        embedding = np.random.rand(768).astype(np.float32)

        # Serialize
        serialized = msgpack.packb(embedding, default=m.encode)

        # Verify size is reasonable (should be ~6KB for float32)
        assert len(serialized) < 10_000, f"Serialized size too large: {len(serialized)} bytes"
        assert len(serialized) > 3_000, f"Serialized size too small: {len(serialized)} bytes"


class TestEmbeddingCacheIntegration:
    """Test embedding cache integration with QA service."""

    @pytest.mark.asyncio
    async def test_cache_miss_then_hit(self):
        """Test that first request caches, second request hits cache."""
        # Skip if Redis not configured
        if not settings.enable_redis_cache:
            pytest.skip("Redis cache not enabled")

        # Create real cache service
        cache_service = await create_cache_service()

        if not cache_service.enabled:
            pytest.skip("Redis connection failed")

        # Clear any existing test cache
        await cache_service.delete("qa:embedding:*")

        # Mock QA service with embedding computation tracking
        qa_service = MagicMock()
        qa_service.cache_service = cache_service
        qa_service.settings = settings

        # Track inference calls
        inference_calls = []

        async def mock_get_question_embedding(question):
            """Mock that simulates actual embedding computation."""
            from app.services.qa_service import _hash_question
            import torch

            # Preprocess (same as actual)
            cleaned = question.lower().strip()

            # Check cache
            if qa_service.cache_service and qa_service.cache_service.enabled:
                question_hash = _hash_question(question)
                cache_key = f"qa:embedding:{question_hash}"

                cached = await qa_service.cache_service.get_embedding(cache_key)
                if cached is not None:
                    return torch.from_numpy(cached)

            # Simulate inference
            inference_calls.append(question)
            embedding = np.random.rand(768).astype(np.float32)

            # Cache if available
            if qa_service.cache_service and qa_service.cache_service.enabled:
                question_hash = _hash_question(question)
                cache_key = f"qa:embedding:{question_hash}"
                await qa_service.cache_service.set_embedding(cache_key, embedding)

            return torch.from_numpy(embedding)

        # Test question
        test_question = "Làm thế nào để giảm cân?"

        # First call: cache miss
        emb1 = await mock_get_question_embedding(test_question)
        assert len(inference_calls) == 1, "First call should trigger inference"

        # Second call: cache hit
        emb2 = await mock_get_question_embedding(test_question)
        assert len(inference_calls) == 1, "Second call should NOT trigger inference (cache hit)"

        # Embeddings should match
        assert torch.allclose(emb1, emb2, atol=1e-5)

    @pytest.mark.asyncio
    async def test_cache_hit_performance(self):
        """Test that cache hits return in <5ms."""
        if not settings.enable_redis_cache:
            pytest.skip("Redis cache not enabled")

        cache_service = await create_cache_service()

        if not cache_service.enabled:
            pytest.skip("Redis connection failed")

        # Cache a test embedding
        test_embedding = np.random.rand(768).astype(np.float32)
        await cache_service.set_embedding("test:perf", test_embedding)

        # Measure retrieval time (10 iterations for stable measurement)
        times = []
        for _ in range(10):
            start = time.time()
            retrieved = await cache_service.get_embedding("test:perf")
            elapsed_ms = (time.time() - start) * 1000
            times.append(elapsed_ms)

            assert retrieved is not None

        # Average should be <5ms
        avg_time = sum(times) / len(times)
        assert avg_time < 5.0, f"Cache hit took {avg_time:.2f}ms (expected <5ms)"

        # Cleanup
        await cache_service.delete("test:perf")


class TestCacheWarming:
    """Test cache warming script."""

    @pytest.mark.asyncio
    async def test_load_questions_from_file(self):
        """Test loading questions from file."""
        from scripts.cache_warmer import load_top_questions
        from pathlib import Path

        # Create temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("Question 1\n")
            f.write("Question 2\n")
            f.write("\n")  # Empty line
            f.write("Question 3\n")
            temp_path = f.name

        try:
            questions = await load_top_questions(temp_path)
            assert len(questions) == 3
            assert questions[0] == "Question 1"
            assert questions[1] == "Question 2"
            assert questions[2] == "Question 3"
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_warm_cache_integration(self):
        """Test that cache warming actually caches embeddings."""
        if not settings.enable_redis_cache:
            pytest.skip("Redis cache not enabled")

        from scripts.cache_warmer import warm_cache

        cache_service = await create_cache_service()

        if not cache_service.enabled:
            pytest.skip("Redis connection failed")

        # Create mock QA service
        qa_service = MagicMock()
        qa_service.cache_service = cache_service
        qa_service.settings = settings

        cached_questions = []

        async def mock_get_question_embedding(question):
            """Mock embedding computation."""
            cached_questions.append(question)
            embedding = np.random.rand(768).astype(np.float32)
            # Actually cache it
            from app.services.qa_service import _hash_question
            cache_key = f"qa:embedding:{_hash_question(question)}"
            await cache_service.set_embedding(cache_key, embedding)
            return embedding

        qa_service._get_question_embedding = mock_get_question_embedding

        # Warm cache with test questions
        test_questions = [
            "Question 1",
            "Question 2",
            "Question 3",
        ]

        await warm_cache(qa_service, test_questions)

        # Verify all questions were processed
        assert len(cached_questions) == 3

        # Verify embeddings are actually cached
        from app.services.qa_service import _hash_question
        for q in test_questions:
            cache_key = f"qa:embedding:{_hash_question(q)}"
            cached = await cache_service.get_embedding(cache_key)
            assert cached is not None, f"Embedding for '{q}' not cached"


class TestCacheFallback:
    """Test graceful fallback when cache unavailable."""

    @pytest.mark.asyncio
    async def test_cache_disabled_still_works(self):
        """Test that QA service works when cache is disabled."""
        # Create cache service with Redis disabled
        cache_service = CacheService(None)

        assert cache_service.enabled is False

        # Should return None gracefully
        result = await cache_service.get_embedding("any:key")
        assert result is None

        # Should succeed silently
        success = await cache_service.set_embedding("any:key", np.random.rand(768))
        assert success is True  # Pass-through mode


# Pytest configuration
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
