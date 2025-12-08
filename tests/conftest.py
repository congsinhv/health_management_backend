"""
Pytest configuration and fixtures for chat system tests.
"""

import pytest
import asyncpg
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, time, date
import uuid
import os
from types import SimpleNamespace
from app.main import app


from app.db.database import database


@pytest.fixture(autouse=True)
def override_database(mock_database_pool):
    """Override database pool for all tests."""
    original_pool = database.pool
    database.pool = mock_database_pool
    yield
    database.pool = original_pool


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


@pytest.fixture
def test_user(sample_user):
    """Test user object with attribute access."""
    return SimpleNamespace(**sample_user)


@pytest.fixture
def db_pool(mock_database_pool):
    """Alias for mock_database_pool to match test plan."""
    return mock_database_pool


@pytest.fixture
def auth_token():
    """Test auth token."""
    return "test-token-jwt"


@pytest.fixture
async def client(async_client):
    """Alias for async_client."""
    yield async_client


@pytest.fixture
async def test_schedule_plan(db_pool, test_user):
    """Create test schedule plan."""
    return {
        "id": 1,
        "user_id": test_user.id,
        "goal": "maintain",
        "schedule_mode": "fixed",
        "selected_days": ["monday", "wednesday"],
        "fixed_start_time": time(7, 0),
        "fixed_end_time": time(8, 0),
        "sports_predefined": ["gym"],
        "weekly_plan": {
            "monday": {"exercise": "Gym", "duration": 45},
            "wednesday": {"exercise": "Running", "duration": 30},
        },
        "status": "active",
    }


@pytest.fixture
async def test_device(db_pool, test_user):
    """Create test device."""
    return {
        "user_id": test_user.id,
        "fcm_token": f"test-token-{uuid.uuid4()}",
        "device_type": "android",
        "device_name": "Test Phone",
        "is_active": True,
    }


@pytest.fixture
def mock_cloud_tasks_service():
    """Mock Cloud Tasks service."""
    service = MagicMock()
    service.create_notification_task = AsyncMock(return_value="task-123")
    service.delete_task = AsyncMock(return_value=None)
    service.get_queue_stats = AsyncMock(
        return_value={
            "name": "projects/vhealth-dev/locations/asia-southeast1/queues/workout-notifications",
            "state": "RUNNING",
            "rate_limits": {
                "max_dispatches_per_second": 500.0,
                "max_burst_size": 100,
                "max_concurrent_dispatches": 1000,
            },
            "retry_config": {"max_attempts": 3},
        }
    )
    service.pause_queue = AsyncMock(return_value=True)
    service.resume_queue = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_fcm_service():
    """Mock FCM service."""
    service = MagicMock()
    service.send_notification.return_value = {"success_count": 1, "failure_count": 0}
    return service


@pytest.fixture
def mock_scheduler_auth():
    """Mock Cloud Scheduler auth for testing."""
    os.environ["NOTIFICATION_BATCH_API_KEY"] = "test-key-for-scheduler"
    yield
    if "NOTIFICATION_BATCH_API_KEY" in os.environ:
        del os.environ["NOTIFICATION_BATCH_API_KEY"]
