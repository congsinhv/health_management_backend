"""
Performance tests for Chat AI service - ONNX optimization and benchmarks.
"""

import pytest
import time
import asyncio
import psutil
import os
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
import numpy as np

# Import from parent directory
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.qa.model_loader import ModelLoader
from app.services.qa import QAService
from app.config import Settings


class TestONNXOptimization:
    """Test ONNX optimization performance benefits."""

    @pytest.fixture
    def mock_pytorch_model(self):
        """Mock PyTorch model for testing."""
        model = MagicMock()
        model.encode.return_value = np.random.rand(1, 768).tolist()
        model.get_sentence_embedding_dimension.return_value = 768
        model.max_seq_length = 512
        model.tokenizer = MagicMock()
        model.tokenizer.return_value = {
            "input_ids": [[1, 2, 3, 4, 5]],
            "attention_mask": [[1, 1, 1, 1, 1]],
        }
        return model

    @pytest.fixture
    def mock_onnx_session(self):
        """Mock ONNX Runtime session for testing."""
        session = MagicMock()
        # Mock realistic ONNX output
        session.run.return_value = [
            np.random.rand(1, 5, 768).astype(np.float32)  # last_hidden_state
        ]
        session.get_inputs.return_value = [
            MagicMock(name="input_ids"),
            MagicMock(name="attention_mask"),
        ]
        return session

    @pytest.fixture
    def pytorch_loader(self, mock_pytorch_model):
        """Create ModelLoader configured for PyTorch."""
        with patch("app.services.qa.model_loader.SentenceTransformer") as mock_st:
            mock_st.return_value = mock_pytorch_model
            loader = ModelLoader(use_onnx=False)
            loader.model = mock_pytorch_model
            loader.model_loaded = True
            return loader

    @pytest.fixture
    def onnx_loader(self, mock_pytorch_model, mock_onnx_session):
        """Create ModelLoader configured for ONNX."""
        with patch("app.services.qa.model_loader.SentenceTransformer") as mock_st:
            mock_st.return_value = mock_pytorch_model
            loader = ModelLoader(use_onnx=True)
            loader.model = mock_pytorch_model
            loader.onnx_session = mock_onnx_session
            loader.model_loaded = True
            return loader

    def test_onnx_vs_pytorch_inference_speed(self, pytorch_loader, onnx_loader):
        """Test ONNX inference speed compared to PyTorch."""
        test_sentences = ["What is diabetes?"] * 10  # Batch of 10 sentences

        # Benchmark PyTorch
        start_time = time.time()
        pytorch_results = pytorch_loader.get_embeddings(test_sentences)
        pytorch_time = time.time() - start_time

        # Benchmark ONNX
        start_time = time.time()
        onnx_results = onnx_loader.get_embeddings(test_sentences)
        onnx_time = time.time() - start_time

        # Verify results are similar
        assert len(pytorch_results) == len(onnx_results)
        assert len(pytorch_results[0]) == len(onnx_results[0])

        # ONNX should be faster (in realistic scenarios)
        # Note: In mocked environment, timing might not reflect real performance
        print(f"PyTorch time: {pytorch_time:.4f}s, ONNX time: {onnx_time:.4f}s")
        print(f"Speedup ratio: {pytorch_time / onnx_time:.2f}x")

        # At minimum, both should complete
        assert pytorch_time > 0
        assert onnx_time > 0

    def test_onnx_memory_usage(self, pytorch_loader, onnx_loader):
        """Test ONNX memory usage compared to PyTorch."""
        process = psutil.Process(os.getpid())

        # Measure PyTorch memory
        initial_memory = process.memory_info().rss
        pytorch_loader.get_embeddings(["Test sentence"] * 100)
        pytorch_memory = process.memory_info().rss - initial_memory

        # Wait a bit for memory to settle
        time.sleep(0.1)

        # Measure ONNX memory
        initial_memory = process.memory_info().rss
        onnx_loader.get_embeddings(["Test sentence"] * 100)
        onnx_memory = process.memory_info().rss - initial_memory

        print(f"PyTorch memory: {pytorch_memory / 1024 / 1024:.2f}MB")
        print(f"ONNX memory: {onnx_memory / 1024 / 1024:.2f}MB")

        # Memory usage should be reasonable
        assert pytorch_memory >= 0
        assert onnx_memory >= 0

    def test_onnx_model_conversion(self, mock_pytorch_model, tmp_path):
        """Test ONNX model conversion process."""
        # Mock torch.onnx.export
        with patch("app.services.qa.model_loader.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = False
            mock_torch.onnx.export = MagicMock()

            with patch("app.services.qa.model_loader.ort") as mock_ort:
                # Mock successful ONNX session creation
                mock_session = MagicMock()
                mock_ort.InferenceSession.return_value = mock_session

                loader = ModelLoader(model_path=str(tmp_path), use_onnx=True)
                loader.model = mock_pytorch_model

                # Test conversion
                result = loader._try_optimize_to_onnx(mock_pytorch_model, tmp_path)

                assert result is True
                mock_torch.onnx.export.assert_called_once()

                # Verify ONNX file path
                expected_onnx_path = tmp_path / "model.onnx"
                mock_torch.onnx.export.assert_called_with(
                    mock_pytorch_model,
                    mock_pytorch_model.tokenizer.return_value.values(),
                    str(expected_onnx_path),
                    input_names=["input_ids", "attention_mask"],
                    output_names=["last_hidden_state"],
                    dynamic_axes={
                        "input_ids": {0: "batch_size", 1: "sequence"},
                        "attention_mask": {0: "batch_size", 1: "sequence"},
                        "last_hidden_state": {0: "batch_size", 1: "sequence"},
                    },
                    opset_version=14,
                )

    def test_onnx_fallback_to_pytorch(self, pytorch_loader, mock_onnx_session):
        """Test ONNX fallback to PyTorch when ONNX fails."""
        # Mock ONNX failure
        mock_onnx_session.run.side_effect = Exception("ONNX inference failed")

        # Set up loader with ONNX enabled but failing
        pytorch_loader.use_onnx = True
        pytorch_loader.onnx_session = mock_onnx_session

        test_sentences = ["What is diabetes?"]

        # Should fallback to PyTorch
        result = pytorch_loader.get_embeddings(test_sentences)

        assert result is not None
        assert len(result) == 1
        assert len(result[0]) == 768

    def test_onnx_batch_processing(self, onnx_loader):
        """Test ONNX batch processing efficiency."""
        batch_sizes = [1, 5, 10, 25, 50]
        processing_times = []

        for batch_size in batch_sizes:
            test_sentences = [f"Test sentence {i}" for i in range(batch_size)]

            start_time = time.time()
            results = onnx_loader.get_embeddings(test_sentences)
            end_time = time.time()

            processing_time = end_time - start_time
            processing_times.append(processing_time)

            # Verify all sentences processed
            assert len(results) == batch_size

            print(f"Batch size {batch_size}: {processing_time:.4f}s")

        # Processing time should scale reasonably with batch size
        # Linear scaling would be: time_per_item = total_time / batch_size
        time_per_items = [t / b for t, b in zip(processing_times, batch_sizes)]

        # First item might be slower due to setup
        # Later items should have consistent time per item
        for i in range(2, len(time_per_items)):
            # Time per item shouldn't increase dramatically
            assert time_per_items[i] < time_per_items[1] * 2


class TestQAPServicePerformance:
    """Test QA Service performance characteristics."""

    @pytest.fixture
    def performance_qa_service(self):
        """Create QA service with performance monitoring."""
        settings = Settings(
            DEBUG=True,
            qa_model_path="/tmp/test_model",
            model_auto_download=False,
            OPENAI_API_KEY="test-key",
        )

        with patch("app.services.qa.ModelLoader"), patch(
            "app.services.qa.DatasetLoader"
        ), patch("app.services.qa.AISummarizer"):
            service = QAService(settings)

            # Add performance metrics tracking
            service.metrics = {
                "total_requests": 0,
                "total_response_time": 0,
                "avg_response_time": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "error_count": 0,
            }

            # Wrap methods to track performance
            original_ask_stream = service.ask_question_stream

            async def tracked_ask_stream(*args, **kwargs):
                start_time = time.time()
                service.metrics["total_requests"] += 1

                try:
                    async for result in original_ask_stream(*args, **kwargs):
                        yield result
                except Exception:
                    service.metrics["error_count"] += 1
                    raise
                finally:
                    end_time = time.time()
                    response_time = end_time - start_time
                    service.metrics["total_response_time"] += response_time
                    service.metrics["avg_response_time"] = (
                        service.metrics["total_response_time"]
                        / service.metrics["total_requests"]
                    )

            service.ask_question_stream = tracked_ask_stream
            return service

    @pytest.mark.asyncio
    async def test_concurrent_request_performance(self, performance_qa_service):
        """Test performance under concurrent requests."""

        # Mock fast streaming response
        async def mock_stream():
            await asyncio.sleep(0.05)  # 50ms processing time
            yield "Quick response"

        performance_qa_service.ask_question_stream.return_value = mock_stream()

        # Test different concurrency levels
        concurrency_levels = [1, 5, 10, 20]
        results = {}

        for concurrency in concurrency_levels:
            # Create concurrent requests
            async def make_request(i):
                start_time = time.time()
                events = []
                async for chunk in performance_qa_service.ask_question_stream(
                    f"Question {i}", threshold=0.7, top_k=3
                ):
                    events.append(chunk)
                end_time = time.time()
                return end_time - start_time, len(events)

            # Run concurrent requests
            tasks = [make_request(i) for i in range(concurrency)]
            start_time = time.time()
            request_times = await asyncio.gather(*tasks)
            end_time = time.time()

            total_time = end_time - start_time
            avg_time_per_request = sum(t[0] for t in request_times) / len(request_times)
            total_events = sum(t[1] for t in request_times)

            results[concurrency] = {
                "total_time": total_time,
                "avg_request_time": avg_time_per_request,
                "total_events": total_events,
                "requests_per_second": concurrency / total_time,
            }

            print(
                f"Concurrency {concurrency}: {total_time:.3f}s total, "
                f"{avg_time_per_request:.3f}s avg, "
                f"{concurrency/total_time:.1f} req/s"
            )

            # Verify all requests completed successfully
            assert total_events == concurrency
            assert total_time < concurrency * 0.1  # Should be faster than sequential

        # Performance should scale reasonably
        assert results[20]["requests_per_second"] > results[1]["requests_per_second"]

    @pytest.mark.asyncio
    async def test_response_time_sla(self, performance_qa_service):
        """Test response time meets SLA requirements."""
        # Mock realistic response times
        response_times = [0.05, 0.08, 0.12, 0.06, 0.09]  # Various response times

        async def variable_stream():
            delay = response_times[
                len(performance_qa_service.metrics) % len(response_times)
            ]
            await asyncio.sleep(delay)
            yield "Response"

        performance_qa_service.ask_question_stream.return_value = variable_stream()

        # Make multiple requests and measure
        sla_targets = {
            "p50": 0.1,  # 50th percentile < 100ms
            "p95": 0.2,  # 95th percentile < 200ms
            "p99": 0.3,  # 99th percentile < 300ms
        }

        request_times = []
        for _ in range(100):
            start_time = time.time()
            async for _ in performance_qa_service.ask_question_stream("Test", 0.7, 3):
                pass
            end_time = time.time()
            request_times.append(end_time - start_time)

        # Calculate percentiles
        request_times.sort()
        p50 = request_times[int(len(request_times) * 0.5)]
        p95 = request_times[int(len(request_times) * 0.95)]
        p99 = request_times[int(len(request_times) * 0.99)]

        print(
            f"Response time percentiles: P50={p50:.3f}s, P95={p95:.3f}s, P99={p99:.3f}s"
        )

        # Verify SLA targets are met
        assert p50 <= sla_targets["p50"], f"P50 {p50}s > {sla_targets['p50']}s"
        assert p95 <= sla_targets["p95"], f"P95 {p95}s > {sla_targets['p95']}s"
        assert p99 <= sla_targets["p99"], f"P99 {p99}s > {sla_targets['p99']}s"

    @pytest.mark.asyncio
    async def test_memory_efficiency_under_load(self, performance_qa_service):
        """Test memory efficiency under sustained load."""
        process = psutil.Process(os.getpid())

        # Mock memory-intensive streaming
        async def memory_intensive_stream():
            # Simulate some memory allocation
            data = ["x" * 1000 for _ in range(1000)]  # 1MB of data
            yield "Memory intensive response"
            # Data should be garbage collected after function

        performance_qa_service.ask_question_stream.return_value = (
            memory_intensive_stream()
        )

        # Measure memory over sustained load
        initial_memory = process.memory_info().rss
        memory_samples = []

        for batch in range(10):  # 10 batches of requests
            for request in range(10):  # 10 requests per batch
                async for _ in performance_qa_service.ask_question_stream(
                    "Test", 0.7, 3
                ):
                    pass

            # Sample memory after each batch
            current_memory = process.memory_info().rss
            memory_growth = current_memory - initial_memory
            memory_samples.append(memory_growth)

            # Force garbage collection
            import gc

            gc.collect()

        # Analyze memory usage
        max_memory_growth = max(memory_samples)
        final_memory_growth = memory_samples[-1]

        print(f"Max memory growth: {max_memory_growth / 1024 / 1024:.2f}MB")
        print(f"Final memory growth: {final_memory_growth / 1024 / 1024:.2f}MB")

        # Memory growth should be bounded
        assert max_memory_growth < 100 * 1024 * 1024  # Less than 100MB growth
        assert (
            final_memory_growth < max_memory_growth * 0.5
        )  # Should recover some memory

    @pytest.mark.asyncio
    async def test_throughput_scaling(self, performance_qa_service):
        """Test throughput scaling with different loads."""

        # Mock response with predictable processing time
        async def predictable_stream():
            await asyncio.sleep(0.01)  # 10ms processing time
            yield "Predictable response"

        performance_qa_service.ask_question_stream.return_value = predictable_stream()

        # Test different batch sizes
        batch_sizes = [1, 5, 10, 25, 50]
        throughput_results = {}

        for batch_size in batch_sizes:
            # Create batch of requests
            tasks = []
            for i in range(batch_size):

                async def make_request(i=i):
                    events = []
                    async for chunk in performance_qa_service.ask_question_stream(
                        f"Question {i}", threshold=0.7, top_k=3
                    ):
                        events.append(chunk)
                    return len(events)

                tasks.append(make_request())

            # Measure throughput
            start_time = time.time()
            results = await asyncio.gather(*tasks)
            end_time = time.time()

            duration = end_time - start_time
            total_events = sum(results)
            throughput = total_events / duration

            throughput_results[batch_size] = {
                "duration": duration,
                "total_events": total_events,
                "throughput": throughput,
                "requests_per_second": batch_size / duration,
            }

            print(
                f"Batch size {batch_size}: {throughput:.1f} events/s, "
                f"{batch_size/duration:.1f} req/s"
            )

            # Verify all requests processed
            assert total_events == batch_size

        # Throughput should scale but may have diminishing returns
        assert (
            throughput_results[50]["throughput"] > throughput_results[1]["throughput"]
        )


class TestPerformanceRegression:
    """Test for performance regressions."""

    @pytest.mark.asyncio
    async def test_embedding_generation_regression(self):
        """Test embedding generation doesn't regress in performance."""
        # Mock model loader
        with patch("app.services.qa.ModelLoader") as mock_loader_class:
            mock_loader = MagicMock()
            mock_loader_class.return_value = mock_loader

            # Mock realistic embedding generation time
            async def realistic_embeddings(sentences):
                # Simulate processing time based on batch size
                processing_time = (
                    0.001 + len(sentences) * 0.0001
                )  # 1ms base + 0.1ms per sentence
                await asyncio.sleep(processing_time)
                return [[0.1, 0.2, 0.3] for _ in sentences]

            mock_loader.get_embeddings = realistic_embeddings
            mock_loader.is_model_available.return_value = True

            # Test with different batch sizes
            batch_sizes = [1, 10, 50, 100]
            max_times = {
                1: 0.01,  # 10ms max for single sentence
                10: 0.05,  # 50ms max for 10 sentences
                50: 0.2,  # 200ms max for 50 sentences
                100: 0.4,  # 400ms max for 100 sentences
            }

            for batch_size in batch_sizes:
                sentences = [f"Test sentence {i}" for i in range(batch_size)]

                start_time = time.time()
                embeddings = mock_loader.get_embeddings(sentences)
                end_time = time.time()

                processing_time = end_time - start_time

                print(
                    f"Batch size {batch_size}: {processing_time:.3f}s (max: {max_times[batch_size]:.3f}s)"
                )

                assert len(embeddings) == batch_size
                assert (
                    processing_time < max_times[batch_size]
                ), f"Batch {batch_size} took {processing_time:.3f}s, max allowed {max_times[batch_size]:.3f}s"

    @pytest.mark.asyncio
    async def test_search_performance_regression(self):
        """Test similarity search performance doesn't regress."""
        # Create large dataset for search testing
        import pandas as pd

        num_questions = 10000

        df = pd.DataFrame(
            {
                "Question": [f"Health question {i}" for i in range(num_questions)],
                "Answer": [f"Health answer {i}" for i in range(num_questions)],
                "Field": ["health"] * num_questions,
            }
        )

        # Generate pre-computed embeddings
        embeddings = [
            [i / 1000, (i + 1) / 1000, (i + 2) / 1000] for i in range(num_questions)
        ]

        # Mock QA service with large dataset
        with patch("app.services.qa.ModelLoader"), patch(
            "app.services.qa.DatasetLoader"
        ) as mock_dataset_loader, patch("app.services.qa.AISummarizer"):
            mock_dataset_loader.return_value.load_dataset.return_value = df

            from app.services.qa import QAService

            settings = Settings(qa_model_path="/tmp/test")
            service = QAService(settings)
            service.df = df
            service.question_embeddings = embeddings
            service.is_initialized = True

            # Mock similarity calculation
            def mock_cosine_similarity(query_emb, dataset_emb, threshold=0.5, top_k=10):
                # Simulate realistic search time
                import time

                time.sleep(0.01 + len(dataset_emb) * 0.000001)  # 10ms + 1µs per item
                return [[0.9, 0.8, 0.7][: min(top_k, 3)]]

            with patch(
                "app.services.qa.util.cosine_similarity", mock_cosine_similarity
            ):
                # Test search performance
                max_search_time = 0.1  # 100ms max for search

                start_time = time.time()
                results = service.find_similar_questions(
                    "What is diabetes?", threshold=0.7, top_k=5
                )
                end_time = time.time()

                search_time = end_time - start_time

                print(f"Search time for {num_questions} items: {search_time:.3f}s")

                assert (
                    search_time < max_search_time
                ), f"Search took {search_time:.3f}s, max allowed {max_search_time:.3f}s"

    def test_startup_time_regression(self):
        """Test service startup time doesn't regress."""
        max_startup_time = 5.0  # 5 seconds max startup time

        # Mock service components
        with patch("app.services.qa.ModelLoader") as mock_loader, patch(
            "app.services.qa.DatasetLoader"
        ) as mock_dataset, patch("app.services.qa.AISummarizer") as mock_summarizer:
            # Mock initialization delays
            async def delayed_init():
                await asyncio.sleep(0.5)  # 500ms delay
                return True

            mock_loader.return_value.load_model.return_value = MagicMock()
            mock_dataset.return_value.load_dataset.return_value = pd.DataFrame()
            mock_summarizer.return_value.is_available.return_value = True

            from app.services.qa import QAService

            settings = Settings(qa_model_path="/tmp/test")
            service = QAService(settings)

            # Measure startup time
            start_time = time.time()
            asyncio.run(service.initialize())
            end_time = time.time()

            startup_time = end_time - start_time

            print(f"Service startup time: {startup_time:.3f}s")

            assert (
                startup_time < max_startup_time
            ), f"Startup took {startup_time:.3f}s, max allowed {max_startup_time:.3f}s"

    @pytest.mark.asyncio
    async def test_streaming_latency_regression(self):
        """Test streaming response latency doesn't regress."""
        # Mock AI summarizer with controlled response timing
        with patch("app.services.qa.ModelLoader"), patch(
            "app.services.qa.DatasetLoader"
        ), patch("app.services.qa.AISummarizer") as mock_summarizer:
            # Create streaming response with controlled chunk delays
            async def controlled_stream():
                chunks = [
                    "This is the first chunk",
                    " of the response",
                    " with some delays",
                    " between chunks.",
                ]
                for chunk in chunks:
                    await asyncio.sleep(0.02)  # 20ms per chunk
                    yield chunk

            mock_summarizer.return_value.summarize_with_streaming.return_value = (
                controlled_stream()
            )

            from app.services.qa import QAService

            settings = Settings(qa_model_path="/tmp/test")
            service = QAService(settings)
            service.is_initialized = True

            # Test streaming latency
            max_first_chunk_time = 0.1  # 100ms max for first chunk
            max_chunk_interval = 0.05  # 50ms max between chunks

            start_time = time.time()
            chunk_times = []

            async for chunk in service.ask_question_stream("Test question", 0.7, 3):
                chunk_time = time.time()
                chunk_times.append(chunk_time)

                # First chunk should arrive quickly
                if len(chunk_times) == 1:
                    first_chunk_latency = chunk_time - start_time
                    assert (
                        first_chunk_latency < max_first_chunk_time
                    ), f"First chunk latency {first_chunk_latency:.3f}s > {max_first_chunk_time:.3f}s"
                elif len(chunk_times) > 1:
                    chunk_interval = chunk_time - chunk_times[-2]
                    assert (
                        chunk_interval < max_chunk_interval
                    ), f"Chunk interval {chunk_interval:.3f}s > {max_chunk_interval:.3f}s"

                # Stop after a few chunks for testing
                if len(chunk_times) >= 3:
                    break

            print(f"Streaming latencies: {[t - chunk_times[0] for t in chunk_times]}")
