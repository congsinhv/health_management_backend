"""
Pytest configuration and fixtures for chat system tests.
"""

import pytest
import asyncpg
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from app.main import app
from app.core.shared.http_client import ServiceClient
from app.core.shared.exceptions import VHealthException
from tests.shared_utils import create_mock_service_client


@pytest.fixture
def mock_connection():
    """Mock database connection with all required methods."""
    connection = AsyncMock()
    connection.fetchrow = AsyncMock(return_value=None)
    connection.fetch = AsyncMock(return_value=[])
    connection.fetchval = AsyncMock(return_value=None)
    connection.execute = AsyncMock(return_value=None)
    return connection


@pytest.fixture
def mock_database_pool(mock_connection):
    """Mock database connection pool with proper async context manager support."""
    pool = MagicMock()  # Use MagicMock, not AsyncMock

    # Create async context manager for acquire()
    class AsyncContextManager:
        async def __aenter__(self):
            return mock_connection

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    # Make acquire() return the async context manager directly (not a coroutine)
    pool.acquire = MagicMock(return_value=AsyncContextManager())
    return pool


@pytest.fixture
def sample_user():
    """Sample user data."""
    return {
        "id": 1,
        "email": "test@example.com",
        "password_hash": "hashed_password",
        "first_name": "Test",
        "last_name": "User",
        "is_active": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_conversation():
    """Sample conversation data."""
    return {
        "id": 1,
        "user_id": 1,
        "title": "Test Conversation",
        "is_pinned": False,
        "is_archived": False,
        "metadata": {"theme": "health"},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "deleted_at": None,
    }


@pytest.fixture
def sample_message():
    """Sample message data."""
    return {
        "id": 1,
        "conversation_id": 1,
        "user_id": 1,
        "content": "Hello, this is a test message",
        "content_type": "text",
        "metadata": {"source": "web"},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "deleted_at": None,
    }


@pytest.fixture
def sample_message_version():
    """Sample message version data."""
    return {
        "id": 1,
        "message_id": 1,
        "version_number": 1,
        "content": "Original message content",
        "metadata": {},
        "user_id": 1,
        "created_at": datetime.now(timezone.utc),
    }


def create_asyncpg_record(data_dict):
    """Create an asyncpg.Record from a dictionary."""

    class MockRecord(dict):
        def __init__(self, **kwargs):
            super().__init__(kwargs)
            for key, value in kwargs.items():
                self[key] = value

    return MockRecord(**data_dict)


@pytest.fixture
def asyncpg_record_factory():
    """Factory for creating asyncpg.Record objects."""
    return create_asyncpg_record


# SSE Streaming fixtures
@pytest.fixture
def async_client(mock_qa_service):
    """Create AsyncClient for testing SSE endpoints with mocked QA service."""
    # Set up the mock qa_service on app.state
    app.state.qa_service = mock_qa_service

    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    yield client

    # Cleanup
    app.state.qa_service = None


@pytest.fixture
def mock_qa_service():
    """Mock Q&A service for testing."""
    service = AsyncMock()
    service.model = MagicMock()
    service.question_embeddings = MagicMock()
    service.openai_client = MagicMock()
    service.df = MagicMock()
    return service


@pytest.fixture
def sample_question_request():
    """Sample question request data."""
    return {"question": "Làm sao để khỏe mạnh?", "threshold": 0.55, "top_k": 7}


@pytest.fixture
def mock_openai_stream():
    """Create mock OpenAI streaming responses."""

    def create_mock_stream(content_chunks):
        """Create a mock stream with given content chunks."""
        mock_chunks = []
        for chunk in content_chunks:
            mock_choice = MagicMock()
            mock_choice.delta.content = chunk
            mock_chunk = MagicMock()
            mock_chunk.choices = [mock_choice]
            mock_chunks.append(mock_chunk)

        # Add final chunk with None content (end signal)
        mock_choice = MagicMock()
        mock_choice.delta.content = None
        mock_chunk = MagicMock()
        mock_chunk.choices = [mock_choice]
        mock_chunks.append(mock_chunk)

        mock_stream = MagicMock()
        mock_stream.__iter__.return_value = iter(mock_chunks)
        return mock_stream

    return create_mock_stream


# New shared package fixtures for microservices testing


@pytest.fixture
def mock_service_client():
    """Mock service client for service-to-service communication."""
    return create_mock_service_client()


@pytest.fixture
def mock_vhealth_exception():
    """Mock VHealthException for testing."""
    return VHealthException(
        message="Test exception",
        details={"test_field": "test_value"},
        error_code="TestException"
    )


@pytest.fixture
def sample_qa_request():
    """Sample QA request for testing."""
    from app.interfaces.qa_interface import QARequest
    return QARequest(
        question="What is diabetes?",
        user_id=1,
        conversation_id=None,
        context=None,
        threshold=0.55
    )


@pytest.fixture
def sample_prediction_request():
    """Sample prediction request for testing."""
    from app.interfaces.predict_interface import PredictionRequest
    return PredictionRequest(
        age=30,
        gender="male",
        height=175.0,
        weight=70.0,
        activity_level="moderate",
        smoking_status="never",
        alcohol_consumption="moderate",
        systolic_bp=120.0,
        diastolic_bp=80.0,
        family_history_diabetes=False,
        family_history_heart_disease=False,
        user_id=1,
        prediction_type="general"
    )


@pytest.fixture
def async_service_client():
    """Async service client fixture with proper cleanup."""
    import asyncio

    async def client():
        client = ServiceClient("https://test-service.com")
        yield client
        await client.close()

    return asyncio.run(client.__aenter__())
