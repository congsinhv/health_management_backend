"""
Integration tests for Chat AI microservice communication and end-to-end workflows.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient
import json

# Import from parent directory
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.main import create_qa_app
from app.api.qa import create_qa_app as create_qa_router
from app.core.shared.http_client import ServiceClient
from app.core.shared.exceptions import (
    ServiceUnavailableException,
    AIServiceException,
    OpenAIException,
)


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""

    @pytest.fixture
    def full_app_with_services(self, mock_qa_service, mock_openai_client):
        """Create app with fully mocked services."""
        app = create_qa_app()

        # Setup complete service stack
        app.state.qa_service = mock_qa_service
        app.state.qa_service.ai_summarizer.openai_client = mock_openai_client

        return app

    @pytest.fixture
    def client(self, full_app_with_services):
        """Create test client."""
        return TestClient(full_app_with_services)

    @pytest.fixture
    async def async_client(self, full_app_with_services):
        """Create async client for streaming tests."""
        from httpx import AsyncClient, ASGITransport

        client = AsyncClient(
            transport=ASGITransport(app=full_app_with_services), base_url="http://test"
        )
        yield client

    def test_complete_qa_workflow(self, client, mock_qa_service):
        """Test complete Q&A workflow from question to answer."""
        # Setup realistic mock responses
        mock_qa_service.find_similar_questions.return_value = [
            {
                "question": "What is diabetes?",
                "answer": "Diabetes is a metabolic disease that affects blood sugar levels.",
                "similarity": 0.92,
                "field": "health",
            },
            {
                "question": "What are diabetes symptoms?",
                "answer": "Common symptoms include increased thirst, frequent urination.",
                "similarity": 0.87,
                "field": "health",
            },
        ]

        # Make request
        request_data = {
            "question": "Tell me about diabetes",
            "threshold": 0.7,
            "top_k": 3,
        }

        response = client.post("/api/v1/qa/ask", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert data["question"] == request_data["question"]
        assert "answers" in data
        assert "summary" in data

        # Verify service methods were called
        mock_qa_service.find_similar_questions.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_streaming_workflow(self, async_client, mock_qa_service):
        """Test complete streaming Q&A workflow."""

        # Setup realistic streaming response
        async def mock_stream():
            yield {
                "event": "question_received",
                "data": {"question": "Tell me about diabetes"},
            }
            yield {
                "event": "answers_found",
                "data": {"count": 2, "similarity_threshold": 0.7},
            }
            yield "Diabetes is a metabolic disease"
            yield " that affects blood sugar levels."
            yield "It requires proper management through diet, exercise, and medication."
            yield {
                "event": "stream_complete",
                "data": {"total_tokens": 25, "duration": 1.2},
            }

        mock_qa_service.ask_question_stream.return_value = mock_stream()

        # Make streaming request
        request_data = {
            "question": "Tell me about diabetes",
            "threshold": 0.7,
            "top_k": 3,
        }

        response = await async_client.post("/api/v1/qa/ask-stream", json=request_data)
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Read streaming response
        content = response.text
        assert "event: question_received" in content
        assert "event: answers_found" in content
        assert "Diabetes is a metabolic disease" in content
        assert "event: stream_complete" in content

    def test_health_check_workflow(self, client, mock_qa_service):
        """Test complete health check workflow."""
        # Mock comprehensive health status
        mock_qa_service.get_health_check.return_value = {
            "status": "healthy",
            "components": {
                "model_loaded": True,
                "embeddings_ready": True,
                "dataset_loaded": True,
                "ai_available": True,
            },
            "metrics": {
                "total_questions": 1000,
                "avg_response_time": 0.8,
                "cache_hit_rate": 0.85,
            },
        }

        # Test health endpoint
        health_response = client.get("/api/v1/qa/health")
        assert health_response.status_code == 200

        health_data = health_response.json()
        assert health_data["status"] == "healthy"
        assert health_data["model_loaded"] is True
        assert health_data["openai_configured"] is True

        # Test detailed status endpoint
        status_response = client.get("/api/v1/qa/status")
        assert status_response.status_code == 200

        status_data = status_response.json()
        assert status_data["status"] == "healthy"
        assert status_data["service"] == "chat_ai_service"
        assert "timestamp" in status_data

    def test_error_recovery_workflow(self, client, mock_qa_service):
        """Test error recovery workflow."""
        # Simulate service error
        mock_qa_service.ask_question_stream.side_effect = AIServiceException(
            "AI service temporarily unavailable"
        )

        request_data = {
            "question": "Tell me about diabetes",
            "threshold": 0.7,
            "top_k": 3,
        }

        response = client.post("/api/v1/qa/ask", json=request_data)
        assert response.status_code == 503

        data = response.json()
        assert data["error"] == "ServiceUnavailable"
        assert "temporarily unavailable" in data["message"]


class TestServiceToServiceCommunication:
    """Test service-to-service communication patterns."""

    @pytest.fixture
    def mock_service_client(self):
        """Mock service client for inter-service communication."""
        client = AsyncMock()
        client.post = AsyncMock(
            return_value=MagicMock(
                status_code=200,
                json=lambda: {
                    "question": "What is diabetes?",
                    "answers": {"health": ["Diabetes is a metabolic disease..."]},
                    "summary": "Diabetes is a metabolic disease affecting blood sugar levels.",
                },
            )
        )
        return client

    @pytest.fixture
    def main_api_app(self):
        """Mock main API application for integration testing."""
        from fastapi import FastAPI
        from fastapi import APIRouter

        app = FastAPI(title="VHealth Main API")
        router = APIRouter()

        @router.post("/api/v1/qa/ask")
        async def proxy_qa_request(request_data: dict):
            """Proxy Q&A request to Chat AI service."""
            # This would normally use ServiceClient to call Chat AI service
            client = MagicMock()
            response = client.post("/api/v1/qa/ask", json=request_data)
            return response.json()

        app.include_router(router)
        return app

    @pytest.mark.asyncio
    async def test_main_api_proxy_flow(self, mock_service_client):
        """Test main API proxying requests to Chat AI service."""
        # Mock ServiceClient
        with patch("app.core.shared.http_client.ServiceClient") as mock_client_class:
            mock_client_class.return_value = mock_service_client

            # Simulate main API calling Chat AI service
            client = mock_service_client
            request_data = {
                "question": "What is diabetes?",
                "threshold": 0.7,
                "top_k": 3,
            }

            response = await client.post(
                "/api/v1/qa/ask",
                json=request_data,
                headers={"Authorization": "Bearer service-token"},
            )

            assert response.status_code == 200
            mock_service_client.post.assert_called_once()

            # Verify request was properly formatted
            call_args = mock_service_client.post.call_args
            assert "json" in call_args.kwargs
            assert call_args.kwargs["json"]["question"] == request_data["question"]

    @pytest.mark.asyncio
    async def test_iam_authentication_flow(self):
        """Test IAM authentication between services."""
        # Mock IAM token generation
        with patch("app.core.shared.http_client.generate_iam_token") as mock_iam:
            mock_iam.return_value = "iam-token-123"

            with patch("app.core.shared.http_client.ServiceClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client_instance.post.return_value = MagicMock(status_code=200)
                mock_client.return_value = mock_client_instance

                # Create service client with IAM
                from app.core.shared.http_client import ServiceClient

                client = ServiceClient("https://chat-ai-service.com", use_iam=True)

                # Make request
                await client.post("/api/v1/qa/ask", json={"question": "Test"})

                # Verify IAM token was generated
                mock_iam.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_discovery_flow(self):
        """Test service discovery and load balancing."""
        # Mock service discovery
        mock_services = [
            "https://chat-ai-1.example.com",
            "https://chat-ai-2.example.com",
            "https://chat-ai-3.example.com",
        ]

        with patch(
            "app.core.shared.http_client.discover_chat_ai_services"
        ) as mock_discover:
            mock_discover.return_value = mock_services

            # Mock client selection and request
            with patch("app.core.shared.http_client.ServiceClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client_instance.post.return_value = MagicMock(status_code=200)
                mock_client.return_value = mock_client_instance

                # Simulate load-balanced request
                client = ServiceClient(
                    mock_services[0]
                )  # Round-robin would select first

                await client.post("/api/v1/qa/ask", json={"question": "Test"})

                # Should have called the first service
                assert client.base_url == mock_services[0]

    @pytest.mark.asyncio
    async def test_circuit_breaker_pattern(self):
        """Test circuit breaker pattern for service resilience."""
        # Mock circuit breaker state
        with patch("app.core.shared.http_client.CircuitBreaker") as mock_breaker:
            mock_breaker_instance = MagicMock()
            mock_breaker_instance.is_open.return_value = False
            mock_breaker_instance.call = AsyncMock(
                return_value=MagicMock(status_code=200)
            )
            mock_breaker.return_value = mock_breaker_instance

            # Mock service client with circuit breaker
            with patch("app.core.shared.http_client.ServiceClient") as mock_client:
                mock_client_instance = AsyncMock()
                mock_client.return_value = mock_client_instance

                # Simulate request with circuit breaker
                client = mock_client_instance

                # Circuit breaker should be used
                mock_breaker_instance.call.assert_called()


class TestPerformanceAndScalability:
    """Test performance characteristics and scalability."""

    @pytest.fixture
    def performance_qa_service(self, mock_qa_service):
        """Create QA service with performance monitoring."""
        # Add performance metrics
        mock_qa_service.metrics = {
            "total_requests": 0,
            "total_response_time": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        # Wrap methods to track performance
        original_ask_stream = mock_qa_service.ask_question_stream

        async def tracked_ask_stream(*args, **kwargs):
            start_time = time.time()
            mock_qa_service.metrics["total_requests"] += 1

            async for result in original_ask_stream(*args, **kwargs):
                yield result

            end_time = time.time()
            mock_qa_service.metrics["total_response_time"] += end_time - start_time

        mock_qa_service.ask_question_stream = tracked_ask_stream

        return mock_qa_service

    @pytest.mark.asyncio
    async def test_concurrent_request_handling(self, performance_qa_service):
        """Test handling multiple concurrent requests."""

        # Mock streaming response
        async def mock_response():
            await asyncio.sleep(0.1)  # Simulate processing time
            yield "Test response"

        performance_qa_service.ask_question_stream.return_value = mock_response()

        # Create concurrent requests
        async def make_request(i):
            async for chunk in performance_qa_service.ask_question_stream(
                f"Question {i}", threshold=0.7, top_k=3
            ):
                pass

        # Run 10 concurrent requests
        tasks = [make_request(i) for i in range(10)]
        start_time = time.time()
        await asyncio.gather(*tasks)
        end_time = time.time()

        # Should complete faster than sequential processing
        duration = end_time - start_time
        assert duration < 1.0  # Should be much faster than 10 * 0.1 = 1.0 second

        # Verify metrics
        assert performance_qa_service.metrics["total_requests"] == 10

    @pytest.mark.asyncio
    async def test_response_time_sla(self, performance_qa_service):
        """Test response time meets SLA requirements."""

        # Mock fast streaming response
        async def mock_response():
            yield "Quick response"

        performance_qa_service.ask_question_stream.return_value = mock_response()

        # Make request and measure time
        start_time = time.time()
        events = []
        async for chunk in performance_qa_service.ask_question_stream(
            "Test question", threshold=0.7, top_k=3
        ):
            events.append(chunk)
        end_time = time.time()

        response_time = end_time - start_time

        # Should meet SLA (less than 100ms for simple requests)
        assert response_time < 0.1
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_memory_usage_under_load(self, performance_qa_service):
        """Test memory usage doesn't grow excessively under load."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Mock streaming response
        async def mock_response():
            # Simulate some memory usage
            data = ["x" * 1000 for _ in range(100)]  # 100KB of data
            yield "Response with data"

        performance_qa_service.ask_question_stream.return_value = mock_response()

        # Make many requests
        for i in range(100):
            async for chunk in performance_qa_service.ask_question_stream(
                f"Question {i}", threshold=0.7, top_k=3
            ):
                pass

            # Check memory every 10 requests
            if i % 10 == 0:
                current_memory = process.memory_info().rss
                memory_growth = current_memory - initial_memory

                # Memory growth should be reasonable (less than 50MB)
                assert memory_growth < 50 * 1024 * 1024

    @pytest.mark.asyncio
    async def test_graceful_degradation_under_load(self, performance_qa_service):
        """Test graceful degradation when system is under load."""

        # Simulate degraded performance
        async def slow_response():
            await asyncio.sleep(0.5)  # Slow response
            yield "Slow response due to load"

        performance_qa_service.ask_question_stream.return_value = slow_response()

        # Make request and verify it completes even with delay
        start_time = time.time()
        events = []
        async for chunk in performance_qa_service.ask_question_stream(
            "Test question", threshold=0.7, top_k=3
        ):
            events.append(chunk)
        end_time = time.time()

        response_time = end_time - start_time
        assert response_time >= 0.5  # Should take at least 0.5 seconds
        assert len(events) == 1

        # Service should still return response, not time out
        assert events[0] == "Slow response due to load"


class TestResilienceAndErrorHandling:
    """Test resilience patterns and error handling."""

    @pytest.mark.asyncio
    async def test_service_timeout_handling(self):
        """Test timeout handling when Chat AI service is slow."""

        # Mock slow service
        async def slow_service():
            await asyncio.sleep(5.0)  # Very slow
            yield "Delayed response"

        mock_qa_service = AsyncMock()
        mock_qa_service.ask_question_stream.return_value = slow_service()

        # Test with timeout
        try:
            async for chunk in asyncio.wait_for(
                mock_qa_service.ask_question_stream("Test", 0.7, 3),
                timeout=1.0,  # 1 second timeout
            ):
                pass
            assert False, "Should have timed out"
        except asyncio.TimeoutError:
            pass  # Expected

    @pytest.mark.asyncio
    async def test_service_unavailable_fallback(self):
        """Test fallback behavior when Chat AI service is unavailable."""
        # Mock unavailable service
        with patch("app.core.shared.http_client.ServiceClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.side_effect = Exception("Service unavailable")
            mock_client.return_value = mock_client_instance

            # Test fallback behavior
            client = mock_client_instance

            with pytest.raises(ServiceUnavailableException):
                await client.post("/api/v1/qa/ask", json={"question": "Test"})

    @pytest.mark.asyncio
    async def test_partial_service_degradation(self):
        """Test behavior when service is partially degraded."""
        # Mock partially working service
        mock_qa_service = AsyncMock()

        # AI summarizer is unavailable, but search works
        async def degraded_stream():
            # Found answers but can't summarize
            yield "AI summarizer is temporarily unavailable. Here are some relevant answers:"
            yield "Diabetes is a metabolic disease that affects blood sugar levels."
            yield "It requires proper management through diet and exercise."

        mock_qa_service.ask_question_stream.return_value = degraded_stream()
        mock_qa_service.get_health_check.return_value = {
            "status": "degraded",
            "components": {
                "model_loaded": True,
                "embeddings_ready": True,
                "ai_available": False,
            },
        }

        # Service should still provide basic functionality
        events = []
        async for event in mock_qa_service.ask_question_stream("Test", 0.7, 3):
            events.append(event)

        assert len(events) == 3
        assert any("unavailable" in event for event in events)

    @pytest.mark.asyncio
    async def test_retry_mechanism(self):
        """Test retry mechanism for transient failures."""
        # Mock service that fails then succeeds
        call_count = 0

        async def flaky_service():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient failure")
            yield "Success after retries"

        mock_qa_service = AsyncMock()
        mock_qa_service.ask_question_stream.side_effect = flaky_service()

        # Test with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                events = []
                async for event in mock_qa_service.ask_question_stream("Test", 0.7, 3):
                    events.append(event)
                assert len(events) == 1
                assert events[0] == "Success after retries"
                break
            except Exception:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(0.1)  # Brief delay before retry
        else:
            assert False, "Should have succeeded after retries"

    def test_error_context_propagation(self):
        """Test that error context is properly propagated through service calls."""
        from app.core.error_context import ErrorContext

        # Set up error context
        request_id = ErrorContext.set_request_id()
        ErrorContext.add_context("user_id", 123)
        ErrorContext.add_context("operation", "qa_request")

        # Verify context is maintained
        context = ErrorContext.get_all()
        assert "request_id" in context
        assert context["user_id"] == 123
        assert context["operation"] == "qa_request"
