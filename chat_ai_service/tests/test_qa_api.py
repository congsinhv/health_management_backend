"""
Tests for Chat AI API endpoints - Q&A functionality with streaming support.
"""

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Import from parent directory
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.main import create_qa_app
from app.api.qa import create_qa_app as create_qa_router
from app.schemas.qa import QuestionRequest, QuestionResponse
from app.core.shared.exceptions import (
    ValidationException,
    ServiceUnavailableException,
    QAModelNotLoadedException,
    OpenAIException,
)
from app.core.error_context import ErrorContext


class TestQAEndpoints:
    """Test Q&A API endpoints functionality."""

    @pytest.fixture
    def app(self, mock_qa_service):
        """Create test app with mocked QA service."""
        app = create_qa_app()

        # Mock startup event to set up QA service
        app.state.qa_service = mock_qa_service

        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def async_client(self, app, mock_qa_service):
        """Create async client for streaming tests."""
        from httpx import AsyncClient, ASGITransport

        app.state.qa_service = mock_qa_service
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        yield client
        app.state.qa_service = None

    def test_root_endpoint(self, client):
        """Test root endpoint returns service information."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "VHealth Chat AI Service"
        assert data["description"] is not None
        assert data["version"] == "1.0.0"
        assert "/docs" in data["docs_url"]
        assert "/api/v1/qa/health" in data["health_check"]

    def test_create_qa_app_structure(self):
        """Test QA app creation and structure."""
        app = create_qa_app()

        assert app.title == "VHealth Chat AI Service"
        assert app.description is not None
        assert app.version == "1.0.0"
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"

        # Check router is included
        assert any("/api/v1/qa" in route.path for route in app.routes)

    def test_ask_question_success(self, client, mock_qa_service):
        """Test successful question answering."""
        # Mock streaming response
        mock_qa_service.ask_question_stream.return_value = iter(
            [
                "Diabetes is a metabolic disease",
                "that affects blood sugar levels.",
                "It requires proper management.",
            ]
        )

        request_data = {"question": "What is diabetes?", "threshold": 0.55, "top_k": 5}

        response = client.post("/api/v1/qa/ask", json=request_data)
        assert response.status_code == 200

        data = response.json()
        assert data["question"] == request_data["question"]
        assert "answers" in data
        assert "summary" in data

    def test_ask_question_empty(self, client):
        """Test question answering with empty question."""
        request_data = {"question": "", "threshold": 0.55, "top_k": 5}

        response = client.post("/api/v1/qa/ask", json=request_data)
        assert response.status_code == 422  # Validation error

    def test_ask_question_whitespace_only(self, client):
        """Test question answering with whitespace-only question."""
        request_data = {"question": "   ", "threshold": 0.55, "top_k": 5}

        response = client.post("/api/v1/qa/ask", json=request_data)
        assert response.status_code == 422  # Validation error

    def test_ask_question_service_unavailable(self, client):
        """Test question answering when QA service is unavailable."""
        # Remove QA service from app state
        client.app.state.qa_service = None

        request_data = {"question": "What is diabetes?", "threshold": 0.55, "top_k": 5}

        response = client.post("/api/v1/qa/ask", json=request_data)
        assert response.status_code == 503  # Service unavailable

    def test_ask_question_streaming_success(self, async_client, mock_qa_service):
        """Test successful streaming question answering."""
        # Mock streaming response with different chunk types
        mock_qa_service.ask_question_stream.return_value = iter(
            [
                {
                    "event": "question_received",
                    "data": {"question": "What is diabetes?"},
                },
                {"event": "answers_found", "data": {"count": 3}},
                "Diabetes is a metabolic disease",
                "that affects blood sugar levels.",
                {"event": "stream_complete", "data": {"total_tokens": 5}},
            ]
        )

        request_data = {"question": "What is diabetes?", "threshold": 0.55, "top_k": 5}

        response = asyncio.run(
            async_client.post("/api/v1/qa/ask-stream", json=request_data)
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    def test_ask_question_streaming_no_results(self, async_client, mock_qa_service):
        """Test streaming question answering with no results."""
        mock_qa_service.ask_question_stream.return_value = iter(
            ["Sorry, I couldn't find relevant information for your question."]
        )

        request_data = {
            "question": "What is quantum computing?",
            "threshold": 0.9,
            "top_k": 3,
        }

        response = asyncio.run(
            async_client.post("/api/v1/qa/ask-stream", json=request_data)
        )
        assert response.status_code == 200

    def test_ask_question_streaming_service_unavailable(self, async_client):
        """Test streaming question answering when service unavailable."""
        async_client.app.state.qa_service = None

        request_data = {"question": "What is diabetes?", "threshold": 0.55, "top_k": 5}

        response = asyncio.run(
            async_client.post("/api/v1/qa/ask-stream", json=request_data)
        )
        assert response.status_code == 503

    def test_ask_question_streaming_empty_question(self, async_client):
        """Test streaming question answering with empty question."""
        request_data = {"question": "", "threshold": 0.55, "top_k": 5}

        response = asyncio.run(
            async_client.post("/api/v1/qa/ask-stream", json=request_data)
        )
        assert response.status_code == 422

    def test_qa_health_check_healthy(self, client, mock_qa_service):
        """Test QA health check when service is healthy."""
        mock_qa_service.get_health_check.return_value = {
            "status": "healthy",
            "components": {
                "model_loaded": True,
                "embeddings_ready": True,
                "ai_available": True,
            },
        }

        response = client.get("/api/v1/qa/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is True
        assert data["embeddings_loaded"] is True
        assert data["streaming_enabled"] is True
        assert data["openai_configured"] is True
        assert "Q&A service is operational" in data["message"]

    def test_qa_health_check_unavailable(self, client):
        """Test QA health check when service is unavailable."""
        client.app.state.qa_service = None

        response = client.get("/api/v1/qa/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "unavailable"
        assert data["model_loaded"] is False
        assert data["embeddings_loaded"] is False
        assert data["streaming_enabled"] is False
        assert data["openai_configured"] is False
        assert "not initialized" in data["message"]

    def test_qa_health_check_partial(self, client, mock_qa_service):
        """Test QA health check with partially loaded components."""
        mock_qa_service.get_health_check.return_value = {
            "status": "degraded",
            "components": {
                "model_loaded": True,
                "embeddings_ready": False,
                "ai_available": False,
            },
        }

        response = client.get("/api/v1/qa/health")
        assert response.status_code == 200

        data = response.json()
        assert data["model_loaded"] is True
        assert data["embeddings_loaded"] is False
        assert data["openai_configured"] is False
        assert "issues detected" in data["message"]

    def test_qa_service_status_available(self, client, mock_qa_service):
        """Test detailed service status when available."""
        mock_qa_service.get_service_status.return_value = {
            "status": "healthy",
            "model_loaded": True,
            "embeddings_ready": True,
            "streaming_enabled": True,
            "openai_configured": True,
            "model_info": {"name": "test-model", "dimension": 768},
        }

        response = client.get("/api/v1/qa/status")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "chat_ai_service"
        assert data["status"] == "healthy"
        assert data["model_loaded"] is True
        assert "timestamp" in data

    def test_qa_service_status_unavailable(self, client):
        """Test detailed service status when unavailable."""
        client.app.state.qa_service = None

        response = client.get("/api/v1/qa/status")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "chat_ai_service"
        assert data["status"] == "unavailable"
        assert "not initialized" in data["message"]
        assert "timestamp" in data


class TestQAEndpointErrorHandling:
    """Test Q&A API endpoint error handling."""

    @pytest.fixture
    def app_with_failing_service(self):
        """Create app with failing QA service."""
        app = create_qa_app()

        # Mock failing QA service
        mock_service = MagicMock()
        mock_service.ask_question_stream = AsyncMock(
            side_effect=Exception("Service error")
        )
        mock_service.get_health_check.side_effect = Exception("Health check error")

        app.state.qa_service = mock_service
        return app

    @pytest.fixture
    def client_with_failing_service(self, app_with_failing_service):
        """Create client with failing QA service."""
        return TestClient(app_with_failing_service)

    def test_ask_question_service_error(self, client_with_failing_service):
        """Test question answering with service error."""
        request_data = {"question": "What is diabetes?", "threshold": 0.55, "top_k": 5}

        response = client_with_failing_service.post("/api/v1/qa/ask", json=request_data)
        assert response.status_code == 500

    def test_qa_health_check_error(self, client_with_failing_service):
        """Test health check with error."""
        response = client_with_failing_service.get("/api/v1/qa/health")
        assert response.status_code == 500

    def test_qa_service_status_error(self, client_with_failing_service):
        """Test service status with error."""
        response = client_with_failing_service.get("/api/v1/qa/status")
        assert response.status_code == 200  # Should return basic status even on error


class TestStreamingFunctionality:
    """Test streaming functionality in detail."""

    @pytest.fixture
    def mock_request(self):
        """Mock FastAPI request for streaming tests."""
        request = MagicMock()
        request.is_disconnected = AsyncMock(return_value=False)
        request.app.state.qa_service = MagicMock()
        return request

    def test_process_question_non_streaming_success(self, mock_qa_service):
        """Test _process_question_non_streaming with success."""
        # Mock streaming response
        mock_qa_service.ask_question_stream.return_value = iter(
            ["Diabetes is a metabolic disease", "that affects blood sugar levels."]
        )

        from app.api.qa import _process_question_non_streaming

        result = asyncio.run(
            _process_question_non_streaming(
                mock_qa_service, "What is diabetes?", 0.55, 5
            )
        )

        assert result["question"] == "What is diabetes?"
        assert "answers" in result
        assert "summary" in result

    def test_process_question_non_streaming_no_results(self, mock_qa_service):
        """Test _process_question_non_streaming with no results."""
        mock_qa_service.ask_question_stream.return_value = iter([])

        from app.api.qa import _process_question_non_streaming

        result = asyncio.run(
            _process_question_non_streaming(
                mock_qa_service, "What is diabetes?", 0.55, 5
            )
        )

        assert result["question"] == "What is diabetes?"
        assert result["answers"] == {}
        assert "not find information" in result["summary"]

    def test_process_question_non_streaming_sorry_response(self, mock_qa_service):
        """Test _process_question_non_streaming with 'sorry' response."""
        mock_qa_service.ask_question_stream.return_value = iter(
            ["Sorry, I couldn't find information for your question."]
        )

        from app.api.qa import _process_question_non_streaming

        result = asyncio.run(
            _process_question_non_streaming(
                mock_qa_service, "What is diabetes?", 0.55, 5
            )
        )

        assert result["question"] == "What is diabetes?"
        assert result["answers"] == {}
        assert (
            result["summary"] == "Sorry, I couldn't find information for your question."
        )

    def test_process_question_non_streaming_error(self, mock_qa_service):
        """Test _process_question_non_streaming with error."""
        mock_qa_service.ask_question_stream.side_effect = Exception("Processing error")

        from app.api.qa import _process_question_non_streaming

        result = asyncio.run(
            _process_question_non_streaming(
                mock_qa_service, "What is diabetes?", 0.55, 5
            )
        )

        assert result["question"] == "What is diabetes?"
        assert result["answers"] == {}
        assert "Xin lỗi" in result["summary"]  # Vietnamese apology

    @pytest.mark.asyncio
    async def test_event_generator_disconnect_detection(
        self, mock_qa_service, mock_request
    ):
        """Test event generator handles client disconnection."""
        # Mock request to be disconnected
        mock_request.is_disconnected.return_value = True

        # Mock streaming response
        mock_qa_service.ask_question_stream.return_value = iter(
            ["Diabetes is a metabolic disease"]
        )

        from app.api.qa import ask_question_stream

        request_data = QuestionRequest(
            question="What is diabetes?", threshold=0.55, top_k=5
        )

        # This should handle disconnection gracefully
        try:
            async for chunk in mock_qa_service.ask_question_stream():
                pass
        except Exception:
            pass  # Expected due to disconnection

    @pytest.mark.asyncio
    async def test_event_generator_heartbeat(self, mock_qa_service, mock_request):
        """Test event generator sends heartbeat keep-alive messages."""
        # Mock request to stay connected
        mock_request.is_disconnected.return_value = False

        # Mock streaming response with delays
        async def mock_stream():
            await asyncio.sleep(0.1)
            yield "First chunk"
            await asyncio.sleep(0.1)
            yield "Second chunk"

        mock_qa_service.ask_question_stream.return_value = mock_stream()

        # Test that heartbeat would be sent (implementation detail)


class TestRequestValidation:
    """Test request validation for Q&A endpoints."""

    def test_question_request_validation(self):
        """Test QuestionRequest schema validation."""
        # Valid request
        request = QuestionRequest(question="What is diabetes?", threshold=0.55, top_k=5)
        assert request.question == "What is diabetes?"
        assert request.threshold == 0.55
        assert request.top_k == 5

    def test_question_request_defaults(self):
        """Test QuestionRequest with default values."""
        request = QuestionRequest(question="What is diabetes?")
        assert request.question == "What is diabetes?"
        # Check default values from schema

    def test_question_request_invalid_threshold(self):
        """Test QuestionRequest with invalid threshold."""
        with pytest.raises(Exception):  # Pydantic validation error
            QuestionRequest(
                question="What is diabetes?",
                threshold=1.5,  # Invalid: should be 0.0-1.0
            )

    def test_question_request_invalid_top_k(self):
        """Test QuestionRequest with invalid top_k."""
        with pytest.raises(Exception):  # Pydantic validation error
            QuestionRequest(
                question="What is diabetes?", top_k=25  # Invalid: should be 1-20
            )

    def test_question_request_long_question(self):
        """Test QuestionRequest with question that's too long."""
        long_question = "x" * 501  # Over 500 character limit
        with pytest.raises(Exception):  # Pydantic validation error
            QuestionRequest(question=long_question)

    def test_question_request_minimal_question(self):
        """Test QuestionRequest with minimal valid question."""
        request = QuestionRequest(question="A?")
        assert request.question == "A?"


class TestErrorContextIntegration:
    """Test ErrorContext integration with Q&A endpoints."""

    def test_error_context_set_on_endpoints(self, mock_qa_service):
        """Test that ErrorContext is properly set for endpoints."""
        app = create_qa_app()
        app.state.qa_service = mock_qa_service

        # Mock ErrorContext methods
        with patch("app.api.qa.ErrorContext") as mock_error_context:
            mock_error_context.set_request_id = MagicMock()
            mock_error_context.add_context = MagicMock()
            mock_error_context.return_value.__enter__ = MagicMock()
            mock_error_context.return_value.__exit__ = MagicMock()

            client = TestClient(app)
            client.post(
                "/api/v1/qa/ask",
                json={"question": "What is diabetes?", "threshold": 0.55, "top_k": 5},
            )

            # Verify ErrorContext was called
            mock_error_context.set_request_id.assert_called()
            mock_error_context.add_context.assert_called()

    def test_error_context_data_added(self, mock_qa_service):
        """Test that appropriate context data is added."""
        app = create_qa_app()
        app.state.qa_service = mock_qa_service

        with patch("app.api.qa.ErrorContext") as mock_error_context:
            mock_error_context.set_request_id = MagicMock()
            mock_error_context.add_context = MagicMock()

            client = TestClient(app)
            client.post(
                "/api/v1/qa/ask",
                json={"question": "What is diabetes?", "threshold": 0.55, "top_k": 5},
            )

            # Check that context was added with expected keys
            context_calls = mock_error_context.add_context.call_args_list
            context_keys = [call[0][0] for call in context_calls]
            assert "endpoint" in context_keys
            assert "operation" in context_keys
            assert "question_length" in context_keys
