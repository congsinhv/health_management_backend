"""
Test configuration and fixtures for pytest.

This module provides all the necessary fixtures for testing the Health Management API,
including mocked databases, services, authentication, and test clients.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch
from io import BytesIO

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient
from jose import jwt
import fakeredis
import fakeredis.aioredis

os.environ.setdefault(
    "DATABASE_URL", "postgresql://test:test@localhost:5432/test_health_management"
)
os.environ.setdefault(
    "SECRET_KEY", "test-secret-key-for-testing-only-change-in-production"
)
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("QA_ENABLED", "false")
os.environ.setdefault("MAIL_USERNAME", "")
os.environ.setdefault("MAIL_PASSWORD", "")
os.environ.setdefault("MAIL_FROM", "")
os.environ.setdefault("MAIL_SERVER", "")
os.environ.setdefault("WEBUI_URL", "http://localhost:3000")
# Add Google OAuth configuration for tests
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
os.environ.setdefault("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/callback")

# Import app components - only what's needed to avoid import errors
try:
    from app.config import settings
except ImportError:
    # Mock settings if import fails
    class MockSettings:
        SECRET_KEY = "test-secret-key-for-testing-only"
        ALGORITHM = "HS256"
        conversation_max_pinned = 10

    settings = MockSettings()

# Import only database repositories - avoid service imports that may have dependency issues
try:
    from app.db.conversation import ConversationRepository
except ImportError:
    ConversationRepository = None

try:
    from app.db.message import MessageRepository
except ImportError:
    MessageRepository = None

try:
    from app.db.message_version import MessageVersionRepository
except ImportError:
    MessageVersionRepository = None

try:
    from app.db.optimization import DatabaseOptimizationRepository
except ImportError:
    DatabaseOptimizationRepository = None

try:
    from app.services.cache import CacheService, ConversationCacheService
except ImportError:
    CacheService = None
    ConversationCacheService = None


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

# ============================================================================
# DATABASE MOCKS
# ============================================================================


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg connection pool."""
    pool = MagicMock()

    # Mock connection that can be accessed and modified by tests
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock(return_value="SELECT 1")

    # Create an async context manager for acquire()
    class AsyncContextManagerMock:
        def __init__(self, connection):
            self.connection = connection

        async def __aenter__(self):
            return self.connection

        async def __aexit__(self, *args):
            return None

    # Store connection reference so tests can modify it
    pool._mock_connection = conn

    # Make pool.acquire() return our async context manager
    pool.acquire = MagicMock(return_value=AsyncContextManagerMock(conn))

    return pool


@pytest.fixture
def test_db_pool(mock_db_pool):
    """Alias for mock_db_pool to maintain compatibility with integration tests."""
    return mock_db_pool


@pytest.fixture
def mock_conversation_repo(mock_db_pool):
    """Mock ConversationRepository with common responses."""
    if ConversationRepository:
        repo = ConversationRepository(mock_db_pool)
    else:
        repo = MagicMock()

    # Mock common methods
    repo.create = AsyncMock()
    repo.get = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.list_conversations = AsyncMock(return_value=[])
    repo.count_conversations = AsyncMock(return_value=0)
    repo.pin = AsyncMock()
    repo.unpin = AsyncMock()
    repo.update_tags = AsyncMock()
    repo.create_conversation = AsyncMock()
    repo.get_conversation_by_user = AsyncMock()
    repo.update_conversation = AsyncMock()
    repo.delete_conversation = AsyncMock()
    repo.get_user_conversations = AsyncMock(return_value=[])
    repo.count_user_conversations = AsyncMock(return_value=0)
    repo.get_pinned_conversations = AsyncMock(return_value=[])
    repo.pin_conversation = AsyncMock()

    return repo


@pytest.fixture
def mock_message_repo(mock_db_pool):
    """Mock MessageRepository with common responses."""
    if MessageRepository:
        repo = MessageRepository(mock_db_pool)
    else:
        repo = MagicMock()

    # Mock common methods
    repo.create = AsyncMock()
    repo.get = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    repo.get_conversation_messages = AsyncMock(return_value=[])
    repo.count_messages = AsyncMock(return_value=0)
    repo.create_branch = AsyncMock()
    repo.get_conversation_tree = AsyncMock(return_value=[])
    repo.get_branch_path = AsyncMock(return_value=[])
    repo.get_message_children = AsyncMock(return_value=[])
    repo.create_message = AsyncMock()

    return repo


@pytest.fixture
def mock_version_repo(mock_db_pool):
    """Mock MessageVersionRepository with common responses."""
    if MessageVersionRepository:
        repo = MessageVersionRepository(mock_db_pool)
    else:
        repo = MagicMock()

    # Mock common methods
    repo.create_version = AsyncMock()
    repo.get_all_versions = AsyncMock(return_value=[])
    repo.get_version = AsyncMock()
    repo.get_latest_version = AsyncMock()
    repo.delete_version = AsyncMock()
    repo.cleanup_old_versions = AsyncMock()

    return repo


@pytest.fixture
def mock_optimization_repo(mock_db_pool):
    """Mock DatabaseOptimizationRepository with common responses."""
    if DatabaseOptimizationRepository:
        repo = DatabaseOptimizationRepository(mock_db_pool)
    else:
        repo = MagicMock()

    # Mock common methods
    repo.get_table_stats = AsyncMock(return_value=[])
    repo.get_slow_queries = AsyncMock(return_value=[])
    repo.get_index_usage = AsyncMock(return_value=[])
    repo.vacuum_analyze = AsyncMock()
    repo.get_cache_hit_ratio = AsyncMock(return_value=0.95)

    return repo


# ============================================================================
# REDIS & CACHE MOCKS
# ============================================================================


@pytest_asyncio.fixture
async def fake_redis():
    """FakeRedis instance for cache testing."""
    redis = fakeredis.FakeRedis(decode_responses=False)
    yield redis
    redis.flushall()
    redis.close()


@pytest_asyncio.fixture
async def mock_cache_service(fake_redis):
    """Cache service with FakeRedis backend."""
    if CacheService:
        with patch("app.services.cache.redis.from_url", return_value=fake_redis):
            with patch("app.services.cache.settings.enable_redis_cache", True):
                service = CacheService()
    else:
        service = MagicMock()
    yield service
    fake_redis.flushall()


@pytest_asyncio.fixture
async def mock_conversation_cache_service(fake_redis):
    """Conversation cache service with FakeRedis backend."""
    if CacheService and ConversationCacheService:
        with patch("app.services.cache.redis.from_url", return_value=fake_redis):
            with patch("app.services.cache.settings.enable_redis_cache", True):
                base_cache = CacheService()
                service = ConversationCacheService(base_cache)
    else:
        service = MagicMock()
    yield service
    fake_redis.flushall()


# ============================================================================
# SERVICE MOCKS
# ============================================================================


@pytest.fixture
def mock_qa_service():
    """Mock QA service with standard responses."""
    service = MagicMock()

    # Standard response
    service.ask_question = AsyncMock(
        return_value={
            "answer": "This is a test answer.",
            "confidence": 0.85,
            "sources": [
                {"title": "Test Document", "score": 0.9, "content": "Test content"}
            ],
        }
    )

    service.health_check = AsyncMock(return_value=True)

    return service


@pytest.fixture
def mock_gcs_uploader():
    """Mock Google Cloud Storage uploader."""
    uploader = MagicMock()

    uploader.upload_file = AsyncMock(
        return_value={
            "url": "https://storage.googleapis.com/test-bucket/test-file.jpg",
            "bucket": "test-bucket",
            "filename": "test-file.jpg",
            "size": 1024,
        }
    )

    uploader.delete_file = AsyncMock(return_value=True)
    uploader.get_signed_url = AsyncMock(
        return_value="https://storage.googleapis.com/test-bucket/test-file.jpg?signed=true"
    )

    return uploader


# ============================================================================
# AUTHENTICATION FIXTURES
# ============================================================================


@pytest.fixture
def test_user_id() -> int:
    """Test user ID."""
    return 123


@pytest.fixture
def test_user_email() -> str:
    """Test user email."""
    return "test@example.com"


@pytest.fixture
def admin_user_id() -> int:
    """Admin user ID."""
    return 456


@pytest.fixture
def admin_user_email() -> str:
    """Admin user email."""
    return "admin@example.com"


@pytest.fixture
def mock_jwt_token(test_user_id: str, test_user_email: str) -> str:
    """Generate a mock JWT token for testing."""
    payload = {
        "sub": test_user_id,
        "email": test_user_email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    # Support both Pydantic lowercase fields and legacy UPPERCASE
    secret = getattr(
        settings, "SECRET_KEY", getattr(settings, "secret_key", "test-secret-key")
    )
    alg = getattr(settings, "ALGORITHM", getattr(settings, "algorithm", "HS256"))
    token = jwt.encode(payload, secret, algorithm=alg)
    return token


@pytest.fixture
def admin_jwt_token(admin_user_id: str, admin_user_email: str) -> str:
    """Generate a mock JWT token for admin user."""
    payload = {
        "sub": admin_user_id,
        "email": admin_user_email,
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    secret = getattr(
        settings, "SECRET_KEY", getattr(settings, "secret_key", "test-secret-key")
    )
    alg = getattr(settings, "ALGORITHM", getattr(settings, "algorithm", "HS256"))
    token = jwt.encode(payload, secret, algorithm=alg)
    return token


@pytest.fixture
def auth_headers(mock_jwt_token: str) -> Dict[str, str]:
    """HTTP headers with authentication token."""
    return {"Authorization": f"Bearer {mock_jwt_token}"}


@pytest.fixture
def admin_auth_headers(admin_jwt_token: str) -> Dict[str, str]:
    """HTTP headers with admin authentication token."""
    return {"Authorization": f"Bearer {admin_jwt_token}"}


# ============================================================================
# TEST CLIENTS
# ============================================================================


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI application instance."""
    test_app = FastAPI(title="Test App")
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Unauthenticated test client."""
    return TestClient(app)


@pytest_asyncio.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """Async test client for testing async endpoints."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def authenticated_client(app: FastAPI, auth_headers: Dict[str, str]) -> TestClient:
    """Authenticated test client."""
    client = TestClient(app)
    client.headers.update(auth_headers)
    return client


@pytest.fixture
def admin_client(app: FastAPI, admin_auth_headers: Dict[str, str]) -> TestClient:
    """Admin authenticated test client."""
    client = TestClient(app)
    client.headers.update(admin_auth_headers)
    return client


# ============================================================================
# TEST DATA FIXTURES
# ============================================================================


@pytest.fixture
def sample_conversation(test_user_id: str) -> Dict[str, Any]:
    """Sample conversation data."""
    return {
        "id": "conv-123",
        "user_id": test_user_id,
        "title": "Test Conversation",
        "is_pinned": False,
        "is_deleted": False,
        "tags": ["test", "sample"],
        "metadata": {"source": "test"},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_conversation_list(test_user_id: int) -> List[Dict[str, Any]]:
    """Sample list of conversations."""
    return [
        {
            "id": i,
            "user_id": test_user_id,
            "title": f"Conversation {i}",
            "is_pinned": i % 2 == 0,
            "is_deleted": False,
            "tags": ["test"],
            "metadata": {},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        for i in range(1, 6)
    ]


@pytest.fixture
def sample_message(test_user_id: str) -> Dict[str, Any]:
    """Sample message data."""
    return {
        "id": "msg-123",
        "conversation_id": "conv-123",
        "user_id": test_user_id,
        "role": "user",
        "content": "Test message content",
        "parent_id": None,
        "is_deleted": False,
        "metadata": {},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_message_tree(test_user_id: str) -> List[Dict[str, Any]]:
    """Sample message tree structure."""
    base_time = datetime.now(timezone.utc)
    return [
        {
            "id": "msg-1",
            "conversation_id": "conv-123",
            "user_id": test_user_id,
            "role": "user",
            "content": "Root message",
            "parent_id": None,
            "depth": 0,
            "path": ["msg-1"],
            "created_at": base_time,
        },
        {
            "id": "msg-2",
            "conversation_id": "conv-123",
            "user_id": test_user_id,
            "role": "assistant",
            "content": "First response",
            "parent_id": "msg-1",
            "depth": 1,
            "path": ["msg-1", "msg-2"],
            "created_at": base_time + timedelta(seconds=1),
        },
        {
            "id": "msg-3",
            "conversation_id": "conv-123",
            "user_id": test_user_id,
            "role": "user",
            "content": "Follow-up question",
            "parent_id": "msg-2",
            "depth": 2,
            "path": ["msg-1", "msg-2", "msg-3"],
            "created_at": base_time + timedelta(seconds=2),
        },
    ]


@pytest.fixture
def sample_version(test_user_id: str) -> Dict[str, Any]:
    """Sample message version data."""
    return {
        "id": "ver-123",
        "message_id": "msg-123",
        "version_number": 1,
        "content": "Version 1 content",
        "metadata": {"edited_by": test_user_id},
        "created_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_file_upload() -> BytesIO:
    """Sample file for upload testing (JPEG image)."""
    # Create a minimal valid JPEG file
    jpeg_header = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    )
    jpeg_footer = b"\xff\xd9"

    file = BytesIO()
    file.write(jpeg_header)
    file.write(b"\x00" * 1000)  # Padding
    file.write(jpeg_footer)
    file.seek(0)

    return file


# ============================================================================
# PARAMETRIZED FIXTURES
# ============================================================================


@pytest.fixture(params=["user", "assistant", "system"])
def message_role(request):
    """Parametrized fixture for message roles."""
    return request.param


@pytest.fixture(params=["created_at", "updated_at", "title"])
def sort_field(request):
    """Parametrized fixture for sort fields."""
    return request.param


@pytest.fixture(params=["asc", "desc"])
def sort_order(request):
    """Parametrized fixture for sort order."""
    return request.param


@pytest.fixture(params=[10, 20, 50, 100])
def page_size(request):
    """Parametrized fixture for pagination sizes."""
    return request.param


# ============================================================================
# DEPENDENCY OVERRIDES
# ============================================================================


@pytest.fixture
def override_dependencies(
    app: FastAPI, mock_db_pool, mock_qa_service, mock_gcs_uploader, fake_redis
):
    """Override FastAPI dependencies for testing."""
    try:
        from app.db.database import get_database_pool
        from app.services.qa_service import get_qa_service

        # Auth override is provided by a separate fixture so unauthorized tests still work

        # Prefer API upload dependency if available; fallback to utils if present
        try:
            from app.api.upload import get_gcs_uploader as api_get_gcs_uploader
        except Exception:
            api_get_gcs_uploader = None
        try:
            from app.utils.gcs_uploader import (
                get_gcs_uploader as utils_get_gcs_uploader,
            )
        except Exception:
            utils_get_gcs_uploader = None
        from app.services.cache import get_redis

        # Store original dependencies
        original_overrides = app.dependency_overrides.copy()

        # Override dependencies
        app.dependency_overrides[get_database_pool] = lambda: mock_db_pool
        app.dependency_overrides[get_qa_service] = lambda: mock_qa_service
        if api_get_gcs_uploader:
            app.dependency_overrides[api_get_gcs_uploader] = lambda: mock_gcs_uploader
        if utils_get_gcs_uploader:
            app.dependency_overrides[utils_get_gcs_uploader] = lambda: mock_gcs_uploader
        app.dependency_overrides[get_redis] = lambda: fake_redis

        yield

        # Restore original dependencies
        app.dependency_overrides = original_overrides
    except ImportError:
        # If imports fail, just yield without overriding
        yield


@pytest.fixture
def override_authenticated_user(app: FastAPI):
    """
    Override only the auth dependency to return a simple active user.
    Use this in tests that require an authenticated user to avoid DB lookups.
    """
    try:
        from types import SimpleNamespace
        from app.auth.dependencies import get_current_active_user
    except Exception:
        yield
        return

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
        id=123, email="test@example.com", is_active=True
    )
    try:
        yield
    finally:
        app.dependency_overrides = original_overrides


@pytest.fixture
def superuser_auth_override(app):
    """Override authentication for superuser tests."""
    from types import SimpleNamespace

    try:
        from app.auth.dependencies import get_current_active_superuser
    except Exception:
        yield
        return

    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_current_active_superuser] = lambda: SimpleNamespace(
        id=1,
        email="admin@health.com",  # Must match dependencies.py check
        is_active=True,
        is_superuser=True,
    )
    try:
        yield
    finally:
        app.dependency_overrides = original_overrides


# ============================================================================
# UTILITY FIXTURES
# ============================================================================


@pytest.fixture
def mock_datetime():
    """Mock datetime for consistent timestamps in tests."""
    fixed_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    with patch("app.db.conversation.datetime") as mock_dt:
        mock_dt.utcnow.return_value = fixed_time
        mock_dt.now.side_effect = (
            lambda tz=None: fixed_time if tz else fixed_time.replace(tzinfo=None)
        )
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        mock_dt.timezone = timezone
        yield mock_dt


@pytest.fixture
def cleanup_test_data():
    """Cleanup fixture to ensure test data is cleaned up after tests."""
    yield
    # Cleanup logic here if needed
    pass


# ============================================================================
# MARKERS
# ============================================================================


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "repository: Repository layer tests")
    config.addinivalue_line("markers", "service: Service layer tests")
    config.addinivalue_line("markers", "api: API endpoint tests")
    config.addinivalue_line("markers", "mock: Tests using mocks")
    config.addinivalue_line("markers", "edge_case: Edge case tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
