"""
Unit tests for CacheService.

Tests cover cache operations, error handling, TTL enforcement,
and graceful fallback when Redis is unavailable.
"""

import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from app.services.cache import CacheService, CacheStats, create_cache_service
from app.config import settings
from redis.exceptions import ConnectionError, TimeoutError, RedisError


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    client = AsyncMock()
    client.ping.return_value = True
    client.get.return_value = None
    client.setex.return_value = True
    client.delete.return_value = 1
    client.keys.return_value = []
    client.flushdb.return_value = True
    client.info.return_value = {
        "redis_version": "7.0.0",
        "used_memory_human": "1M",
        "connected_clients": 1,
        "total_commands_processed": 100,
    }
    client.close = AsyncMock()
    return client


@pytest.fixture
def cache_service(mock_redis_client):
    """Create CacheService with mock Redis client."""
    return CacheService(mock_redis_client)


@pytest.fixture
def disabled_cache_service():
    """Create CacheService without Redis client (disabled mode)."""
    return CacheService(None)


class TestCacheService:
    """Test CacheService functionality."""

    def test_init_with_redis(self, mock_redis_client):
        """Test initialization with Redis client."""
        service = CacheService(mock_redis_client)
        assert service.enabled is True
        assert service.redis_client == mock_redis_client
        assert isinstance(service.stats, CacheStats)

    def test_init_without_redis(self):
        """Test initialization without Redis client."""
        service = CacheService(None)
        assert service.enabled is False
        assert service.redis_client is None
        assert isinstance(service.stats, CacheStats)

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, cache_service, mock_redis_client):
        """Test successful cache get operation."""
        mock_redis_client.get.return_value = b'{"test": "data"}'

        result = await cache_service.get("test:key")

        assert result == '{"test": "data"}'
        mock_redis_client.get.assert_called_once_with("test:key")
        assert cache_service.stats.hits == 1
        assert cache_service.stats.misses == 0
        assert cache_service.stats.hit_rate == 100.0

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache_service, mock_redis_client):
        """Test cache miss scenario."""
        mock_redis_client.get.return_value = None

        result = await cache_service.get("test:key")

        assert result is None
        mock_redis_client.get.assert_called_once_with("test:key")
        assert cache_service.stats.hits == 0
        assert cache_service.stats.misses == 1
        assert cache_service.stats.hit_rate == 0.0

    @pytest.mark.asyncio
    async def test_get_connection_error(self, cache_service, mock_redis_client):
        """Test cache get with connection error."""
        mock_redis_client.get.side_effect = ConnectionError("Redis down")

        result = await cache_service.get("test:key")

        assert result is None
        assert cache_service.stats.errors == 1
        assert cache_service.stats.error_rate > 0.0

    @pytest.mark.asyncio
    async def test_get_disabled(self, disabled_cache_service):
        """Test cache get when disabled."""
        result = await disabled_cache_service.get("test:key")

        assert result is None
        assert disabled_cache_service.stats.misses == 1
        assert disabled_cache_service.stats.hit_rate == 0.0

    @pytest.mark.asyncio
    async def test_set_success(self, cache_service, mock_redis_client):
        """Test successful cache set operation."""
        result = await cache_service.set("test:key", "test_value", ttl=300)

        assert result is True
        mock_redis_client.setex.assert_called_once_with("test:key", 300, "test_value")

    @pytest.mark.asyncio
    async def test_set_default_ttl(self, cache_service, mock_redis_client):
        """Test cache set with default TTL."""
        result = await cache_service.set("test:key", "test_value")

        assert result is True
        mock_redis_client.setex.assert_called_once_with("test:key", 300, "test_value")

    @pytest.mark.asyncio
    async def test_set_connection_error(self, cache_service, mock_redis_client):
        """Test cache set with connection error."""
        mock_redis_client.setex.side_effect = TimeoutError("Redis timeout")

        result = await cache_service.set("test:key", "test_value")

        assert result is False
        assert cache_service.stats.errors == 1

    @pytest.mark.asyncio
    async def test_set_disabled(self, disabled_cache_service):
        """Test cache set when disabled."""
        result = await disabled_cache_service.set("test:key", "test_value")

        assert result is True  # Pass-through mode returns True

    @pytest.mark.asyncio
    async def test_delete_success(self, cache_service, mock_redis_client):
        """Test successful cache delete operation."""
        mock_redis_client.delete.return_value = 1

        result = await cache_service.delete("test:key")

        assert result is True
        mock_redis_client.delete.assert_called_once_with("test:key")

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, cache_service, mock_redis_client):
        """Test delete non-existent key."""
        mock_redis_client.delete.return_value = 0

        result = await cache_service.delete("test:key")

        assert result is True  # Still returns True for non-existent keys

    @pytest.mark.asyncio
    async def test_delete_disabled(self, disabled_cache_service):
        """Test cache delete when disabled."""
        result = await disabled_cache_service.delete("test:key")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_pattern_success(self, cache_service, mock_redis_client):
        """Test successful delete pattern operation."""
        mock_redis_client.keys.return_value = [b"test:key1", b"test:key2"]
        mock_redis_client.delete.return_value = 2

        result = await cache_service.delete_pattern("test:*")

        assert result == 2
        mock_redis_client.keys.assert_called_once_with("test:*")
        mock_redis_client.delete.assert_called_once_with(b"test:key1", b"test:key2")

    @pytest.mark.asyncio
    async def test_delete_pattern_no_matches(self, cache_service, mock_redis_client):
        """Test delete pattern with no matching keys."""
        mock_redis_client.keys.return_value = []

        result = await cache_service.delete_pattern("nonexistent:*")

        assert result == 0
        mock_redis_client.keys.assert_called_once_with("nonexistent:*")

    @pytest.mark.asyncio
    async def test_delete_pattern_disabled(self, disabled_cache_service):
        """Test delete pattern when disabled."""
        result = await disabled_cache_service.delete_pattern("test:*")

        assert result == 0

    @pytest.mark.asyncio
    async def test_clear_all_success(self, cache_service, mock_redis_client):
        """Test successful clear all operation."""
        result = await cache_service.clear_all()

        assert result is True
        mock_redis_client.flushdb.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_all_disabled(self, disabled_cache_service):
        """Test clear all when disabled."""
        result = await disabled_cache_service.clear_all()

        assert result is True

    @pytest.mark.asyncio
    async def test_ping_success(self, cache_service, mock_redis_client):
        """Test successful ping operation."""
        mock_redis_client.ping.return_value = True

        result = await cache_service.ping()

        assert result is True
        mock_redis_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_ping_failure(self, cache_service, mock_redis_client):
        """Test ping failure."""
        mock_redis_client.ping.side_effect = ConnectionError("Redis down")

        result = await cache_service.ping()

        assert result is False
        assert cache_service.stats.errors == 1

    @pytest.mark.asyncio
    async def test_ping_disabled(self, disabled_cache_service):
        """Test ping when disabled."""
        result = await disabled_cache_service.ping()

        assert result is False

    @pytest.mark.asyncio
    async def test_get_stats_enabled(self, cache_service, mock_redis_client):
        """Test getting stats when cache is enabled."""
        # Add some stats
        cache_service.stats.hits = 80
        cache_service.stats.misses = 20
        cache_service.stats.errors = 5
        cache_service.stats.total_requests = 100

        stats = await cache_service.get_stats()

        assert stats["enabled"] is True
        assert stats["hits"] == 80
        assert stats["misses"] == 20
        assert stats["errors"] == 5
        assert stats["total_requests"] == 100
        assert stats["hit_rate"] == 80.0
        assert stats["error_rate"] == 5.0
        assert stats["redis_version"] == "7.0.0"

    @pytest.mark.asyncio
    async def test_get_stats_disabled(self, disabled_cache_service):
        """Test getting stats when cache is disabled."""
        stats = await disabled_cache_service.get_stats()

        assert stats["enabled"] is False
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0

    def test_build_key(self, cache_service):
        """Test cache key building."""
        key = cache_service.build_key("app", "conversation", "123", "messages")
        assert key == "app:conversation:123:messages"

        key = cache_service.build_key("app", "user", "456")
        assert key == "app:user:456"

    @pytest.mark.asyncio
    async def test_get_json_success(self, cache_service, mock_redis_client):
        """Test successful JSON get operation."""
        test_data = {"id": 1, "name": "test"}
        mock_redis_client.get.return_value = json.dumps(test_data)

        result = await cache_service.get_json("test:key")

        assert result == test_data

    @pytest.mark.asyncio
    async def test_get_json_invalid_json(self, cache_service, mock_redis_client):
        """Test JSON get with invalid JSON data."""
        mock_redis_client.get.return_value = "invalid json"

        result = await cache_service.get_json("test:key")

        assert result is None
        mock_redis_client.delete.assert_called_once_with("test:key")

    @pytest.mark.asyncio
    async def test_get_json_miss(self, cache_service, mock_redis_client):
        """Test JSON get with cache miss."""
        mock_redis_client.get.return_value = None

        result = await cache_service.get_json("test:key")

        assert result is None

    @pytest.mark.asyncio
    async def test_set_json_success(self, cache_service, mock_redis_client):
        """Test successful JSON set operation."""
        test_data = {"id": 1, "name": "test"}

        result = await cache_service.set_json("test:key", test_data, ttl=300)

        assert result is True
        expected_json = json.dumps(test_data, ensure_ascii=False, default=str)
        mock_redis_client.setex.assert_called_once_with("test:key", 300, expected_json)

    @pytest.mark.asyncio
    async def test_set_json_serialization_error(self, cache_service, mock_redis_client):
        """Test JSON set with serialization error."""

        # Test by causing a serialization error
        with patch("json.dumps", side_effect=TypeError("Cannot serialize")):
            obj = {"test": "data"}

            result = await cache_service.set_json("test:key", obj)

            assert result is False


class TestCreateCacheService:
    """Test cache service creation function."""

    @pytest.mark.asyncio
    async def test_create_cache_service_enabled(self):
        """Test creating cache service when Redis is enabled."""
        with patch("app.services.cache.settings") as mock_settings:
            mock_settings.enable_redis_cache = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.redis_max_connections = 20
            mock_settings.redis_connection_timeout = 5

            with patch("redis.asyncio.from_url") as mock_from_url:
                mock_redis = AsyncMock()
                mock_redis.ping.return_value = True
                mock_from_url.return_value = mock_redis

                service = await create_cache_service()

                assert service.enabled is True
                assert service.redis_client == mock_redis
                mock_from_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_cache_service_disabled(self):
        """Test creating cache service when Redis is disabled."""
        with patch("app.services.cache.settings") as mock_settings:
            mock_settings.enable_redis_cache = False

            service = await create_cache_service()

            assert service.enabled is False
            assert service.redis_client is None

    @pytest.mark.asyncio
    async def test_create_cache_service_connection_error(self):
        """Test creating cache service with Redis connection error."""
        with patch("app.services.cache.settings") as mock_settings:
            mock_settings.enable_redis_cache = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.redis_max_connections = 20
            mock_settings.redis_connection_timeout = 5

            with patch("redis.asyncio.from_url") as mock_from_url:
                mock_from_url.side_effect = ConnectionError("Redis down")

                service = await create_cache_service()

                assert service.enabled is False
                assert service.redis_client is None

    @pytest.mark.asyncio
    async def test_create_cache_service_ping_failure(self):
        """Test creating cache service when Redis ping fails."""
        with patch("app.services.cache.settings") as mock_settings:
            mock_settings.enable_redis_cache = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.redis_max_connections = 20
            mock_settings.redis_connection_timeout = 5

            with patch("redis.asyncio.from_url") as mock_from_url:
                mock_redis = AsyncMock()
                mock_redis.ping.side_effect = TimeoutError("Redis timeout")
                mock_from_url.return_value = mock_redis

                service = await create_cache_service()

                assert service.enabled is False
                assert service.redis_client is None


class TestCacheStats:
    """Test CacheStats functionality."""

    def test_calculate_rates(self):
        """Test hit and error rate calculation."""
        stats = CacheStats(hits=80, misses=20, errors=5, total_requests=100)
        stats.calculate_rates()

        assert stats.hit_rate == 80.0
        assert stats.error_rate == 5.0

    def test_calculate_rates_zero_requests(self):
        """Test rate calculation with zero requests."""
        stats = CacheStats()
        stats.calculate_rates()

        assert stats.hit_rate == 0.0
        assert stats.error_rate == 0.0

    def test_calculate_rates_partial_data(self):
        """Test rate calculation with incomplete data."""
        stats = CacheStats(hits=50, total_requests=100)
        stats.calculate_rates()

        assert stats.hit_rate == 50.0
        assert stats.error_rate == 0.0
