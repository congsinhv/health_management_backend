"""
Pytest configuration and fixtures for chat system tests.
"""

import pytest
import asyncio
import asyncpg
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_database_pool():
    """Mock database connection pool."""
    pool = AsyncMock()
    return pool


@pytest.fixture
def mock_connection():
    """Mock database connection."""
    connection = AsyncMock()
    return connection


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
