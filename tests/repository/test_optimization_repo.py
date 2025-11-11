"""
Tests for DatabaseOptimizationRepository.

Tests database optimization operations including statistics collection,
slow query detection, index usage analysis, and performance suggestions.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any

from app.db.optimization import DatabaseOptimizationRepository


@pytest.mark.repository
@pytest.mark.unit
class TestOptimizationRepository:
    """Test cases for DatabaseOptimizationRepository."""

    @pytest.fixture
    def repo(self, mock_db_pool):
        """Create repository instance with mocked pool."""
        return DatabaseOptimizationRepository(mock_db_pool)

    # ========================================================================
    # TABLE STATISTICS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_table_statistics_success(self, repo, mock_db_pool):
        """Test getting table statistics successfully."""
        # Arrange
        table_names = ["qa_conversations", "qa_messages"]
        mock_stats = [
            {
                "schemaname": "public",
                "tablename": "qa_conversations",
                "total_size": "1024 kB",
                "table_size": "800 kB",
                "index_size": "224 kB",
                "total_inserts": 1000,
                "total_updates": 500,
                "total_deletes": 50,
                "live_tuples": 950,
                "dead_tuples": 50,
                "last_vacuum": datetime.now(timezone.utc),
                "last_autovacuum": datetime.now(timezone.utc),
                "last_analyze": datetime.now(timezone.utc),
                "last_autoanalyze": datetime.now(timezone.utc),
            },
            {
                "schemaname": "public",
                "tablename": "qa_messages",
                "total_size": "2048 kB",
                "table_size": "1600 kB",
                "index_size": "448 kB",
                "total_inserts": 5000,
                "total_updates": 1000,
                "total_deletes": 100,
                "live_tuples": 4900,
                "dead_tuples": 100,
                "last_vacuum": datetime.now(timezone.utc),
                "last_autovacuum": datetime.now(timezone.utc),
                "last_analyze": datetime.now(timezone.utc),
                "last_autoanalyze": datetime.now(timezone.utc),
            },
        ]

        # Set the mock connection to return our test data
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_stats)

        # Act
        result = await repo.get_table_statistics(table_names)

        # Assert
        assert len(result) == 2
        assert result[0]["tablename"] == "qa_conversations"
        assert result[1]["tablename"] == "qa_messages"
        assert result[0]["live_tuples"] == 950
        assert result[1]["live_tuples"] == 4900

    @pytest.mark.asyncio
    async def test_get_table_statistics_empty_list(self, repo, mock_db_pool):
        """Test getting table statistics with empty table list."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_table_statistics([])

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_get_table_statistics_large_bloat(self, repo, mock_db_pool):
        """Test detecting tables with large dead tuple bloat."""
        # Arrange
        table_names = ["qa_conversations"]
        mock_stats = [
            {
                "tablename": "qa_conversations",
                "live_tuples": 1000,
                "dead_tuples": 500,  # 50% bloat
            }
        ]

        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_stats)

        # Act
        result = await repo.get_table_statistics(table_names)

        # Assert
        assert len(result) > 0
        assert result[0]["dead_tuples"] > result[0]["live_tuples"] * 0.2

    # ========================================================================
    # SLOW QUERIES TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_slow_queries_success(self, repo, mock_db_pool):
        """Test getting slow queries successfully."""
        # Arrange
        mock_queries = [
            {
                "query": "SELECT * FROM qa_conversations WHERE user_id = $1",
                "calls": 1000,
                "total_exec_time": 5000.0,
                "mean_exec_time": 5.0,
                "max_exec_time": 10.0,
                "stddev_exec_time": 1.5,
                "rows": 10000,
                "hit_percent": 95.5,
            },
            {
                "query": "SELECT * FROM qa_messages WHERE conversation_id = $1",
                "calls": 500,
                "total_exec_time": 3000.0,
                "mean_exec_time": 6.0,
                "max_exec_time": 15.0,
                "stddev_exec_time": 2.0,
                "rows": 5000,
                "hit_percent": 92.0,
            },
        ]

        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_queries)

        # Act
        result = await repo.get_slow_queries(min_duration_ms=1000, limit=20)

        # Assert
        assert len(result) == 2
        assert result[0]["mean_exec_time"] == 5.0
        assert result[1]["mean_exec_time"] == 6.0

    @pytest.mark.asyncio
    async def test_get_slow_queries_extension_not_available(self, repo, mock_db_pool):
        """Test handling when pg_stat_statements extension is not available."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(
            side_effect=Exception("pg_stat_statements not available")
        )

        # Act
        result = await repo.get_slow_queries()

        # Assert - should return empty list instead of raising
        assert result == []

    @pytest.mark.asyncio
    async def test_get_slow_queries_custom_params(self, repo, mock_db_pool):
        """Test getting slow queries with custom parameters."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.get_slow_queries(min_duration_ms=500, limit=10)

        # Assert
        assert result == []

    # ========================================================================
    # INDEX USAGE TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_index_usage_success(self, repo, mock_db_pool):
        """Test getting index usage statistics successfully."""
        # Arrange
        table_names = ["qa_conversations"]
        mock_indexes = [
            {
                "schemaname": "public",
                "tablename": "qa_conversations",
                "indexname": "qa_conversations_pkey",
                "index_scans": 10000,
                "tuples_read": 50000,
                "tuples_fetched": 45000,
                "index_size": "128 kB",
            },
            {
                "schemaname": "public",
                "tablename": "qa_conversations",
                "indexname": "idx_conversations_user_id",
                "index_scans": 5000,
                "tuples_read": 25000,
                "tuples_fetched": 20000,
                "index_size": "64 kB",
            },
        ]

        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_indexes)

        # Act
        result = await repo.get_index_usage(table_names)

        # Assert
        assert len(result) == 2
        assert result[0]["index_scans"] == 10000
        assert result[1]["index_scans"] == 5000

    @pytest.mark.asyncio
    async def test_get_index_usage_multiple_tables(self, repo, mock_db_pool):
        """Test getting index usage for multiple tables."""
        # Arrange
        table_names = ["qa_conversations", "qa_messages"]
        mock_indexes = [
            {"tablename": "qa_conversations", "index_scans": 1000},
            {"tablename": "qa_messages", "index_scans": 2000},
        ]

        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_indexes)

        # Act
        result = await repo.get_index_usage(table_names)

        # Assert
        assert len(result) == 2

    # ========================================================================
    # UNUSED INDEXES TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_identify_unused_indexes_success(self, repo, mock_db_pool):
        """Test identifying unused indexes successfully."""
        # Arrange
        table_names = ["qa_conversations"]
        mock_unused = [
            {
                "schemaname": "public",
                "tablename": "qa_conversations",
                "indexname": "idx_never_used",
                "idx_scan": 0,
                "index_size": "512 kB",
            }
        ]

        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_unused)

        # Act
        result = await repo.identify_unused_indexes(table_names)

        # Assert
        assert len(result) == 1
        assert result[0]["idx_scan"] == 0
        assert result[0]["indexname"] == "idx_never_used"

    @pytest.mark.asyncio
    async def test_identify_unused_indexes_none_found(self, repo, mock_db_pool):
        """Test when no unused indexes are found."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.identify_unused_indexes(["qa_conversations"])

        # Assert
        assert result == []

    @pytest.mark.asyncio
    async def test_identify_unused_indexes_custom_age(self, repo, mock_db_pool):
        """Test identifying unused indexes with custom age parameter."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.identify_unused_indexes(
            ["qa_conversations"], min_age_days=30
        )

        # Assert
        assert result == []

    # ========================================================================
    # CACHE HIT RATIO TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_cache_hit_ratios_high(self, repo, mock_db_pool):
        """Test getting cache hit ratios with high hit rate."""
        # Arrange
        mock_stats = {
            "datname": "health_db",
            "blks_read": 1000,
            "blks_hit": 19000,
            "cache_hit_ratio": 95.00,
        }

        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_stats)

        # Act
        result = await repo.get_cache_hit_ratios()

        # Assert
        assert result["blocks_read"] == 1000
        assert result["blocks_hit"] == 19000
        assert result["cache_hit_ratio"] == 95.00

    @pytest.mark.asyncio
    async def test_get_cache_hit_ratios_low(self, repo, mock_db_pool):
        """Test getting cache hit ratios with low hit rate."""
        # Arrange
        mock_stats = {
            "datname": "health_db",
            "blks_read": 5000,
            "blks_hit": 5000,
            "cache_hit_ratio": 50.00,
        }

        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_stats)

        # Act
        result = await repo.get_cache_hit_ratios()

        # Assert
        assert result["cache_hit_ratio"] == 50.00

    @pytest.mark.asyncio
    async def test_get_cache_hit_ratios_zero_blocks(self, repo, mock_db_pool):
        """Test getting cache hit ratios with zero blocks."""
        # Arrange
        mock_stats = {
            "datname": "health_db",
            "blks_read": 0,
            "blks_hit": 0,
            "cache_hit_ratio": 0.00,
        }

        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=mock_stats)

        # Act
        result = await repo.get_cache_hit_ratios()

        # Assert
        assert result["cache_hit_ratio"] == 0.00

    # ========================================================================
    # BLOAT ANALYSIS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_analyze_bloat_success(self, repo, mock_db_pool):
        """Test analyzing table and index bloat successfully."""
        # Arrange
        mock_bloat = [
            {
                "object_type": "Table",
                "name": "qa_conversations",
                "pages": 1000,
                "bloat_percentage": 25.50,
                "bloat_mb": 10.5,
            },
            {
                "object_type": "Index",
                "name": "idx_conversations_user_id",
                "pages": 200,
                "bloat_percentage": 15.00,
                "bloat_mb": 2.0,
            },
        ]

        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=mock_bloat)

        # Act
        result = await repo.analyze_bloat()

        # Assert
        assert len(result) == 2
        assert result[0]["object_type"] == "Table"
        assert result[1]["object_type"] == "Index"
        assert result[0]["bloat_percentage"] > 10

    @pytest.mark.asyncio
    async def test_analyze_bloat_no_bloat(self, repo, mock_db_pool):
        """Test when no significant bloat is found."""
        # Arrange
        mock_db_pool._mock_connection.fetch = AsyncMock(return_value=[])

        # Act
        result = await repo.analyze_bloat()

        # Assert
        assert result == []

    # ========================================================================
    # CONVERSATION QUERY OPTIMIZATION TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_get_conversation_query_optimization_stats_success(
        self, repo, mock_db_pool
    ):
        """Test getting conversation-specific optimization stats."""
        # Arrange
        now = datetime.now(timezone.utc)
        view_stats = {
            "total_conversations": 1000,
            "last_updated": now - timedelta(hours=1),
            "age": timedelta(hours=1),
        }
        search_stats = {
            "total_searchable_content": 1000,
            "avg_content_length": 250,
            "max_content_length": 5000,
        }
        message_stats = {
            "total_messages": 5000,
            "conversations_with_messages": 950,
            "avg_messages_per_conversation": 5.26,
        }

        # Set up fetchrow to return different values on each call
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            side_effect=[view_stats, search_stats, message_stats]
        )

        # Act
        result = await repo.get_conversation_query_optimization_stats()

        # Assert
        assert result["materialized_view"]["total_conversations"] == 1000
        assert result["search_content"]["total_searchable"] == 1000
        assert result["messages"]["total_messages"] == 5000
        assert result["materialized_view"]["age_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_get_conversation_query_optimization_stats_no_age(
        self, repo, mock_db_pool
    ):
        """Test optimization stats when age is None."""
        # Arrange
        view_stats = {"total_conversations": 0, "last_updated": None, "age": None}
        search_stats = {
            "total_searchable_content": 0,
            "avg_content_length": None,
            "max_content_length": None,
        }
        message_stats = {
            "total_messages": 0,
            "conversations_with_messages": 0,
            "avg_messages_per_conversation": None,
        }

        # Set up fetchrow to return different values on each call
        mock_db_pool._mock_connection.fetchrow = AsyncMock(
            side_effect=[view_stats, search_stats, message_stats]
        )

        # Act
        result = await repo.get_conversation_query_optimization_stats()

        # Assert
        assert result["materialized_view"]["age_seconds"] is None

    # ========================================================================
    # OPTIMIZATION SUGGESTIONS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_suggest_optimizations_high_bloat(self, repo, mock_db_pool):
        """Test suggestions when tables have high bloat."""
        # Arrange
        table_stats = [
            {
                "tablename": "qa_conversations",
                "live_tuples": 1000,
                "dead_tuples": 300,  # 30% bloat
            }
        ]
        cache_stats = {"blks_read": 400, "blks_hit": 9600, "cache_hit_ratio": 96.0}

        # Setup mocks - fetch is called 3 times, fetchrow once
        mock_db_pool._mock_connection.fetch = AsyncMock(
            side_effect=[
                table_stats,
                [],
                [],
            ]  # table_stats, unused_indexes, slow_queries
        )
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=cache_stats)

        # Act
        result = await repo.suggest_optimizations()

        # Assert
        vacuum_suggestions = [s for s in result if s["type"] == "vacuum"]
        assert len(vacuum_suggestions) > 0
        assert vacuum_suggestions[0]["priority"] == "high"

    @pytest.mark.asyncio
    async def test_suggest_optimizations_low_cache_hit(self, repo, mock_db_pool):
        """Test suggestions when cache hit ratio is low."""
        # Arrange
        table_stats = [
            {"tablename": "qa_conversations", "live_tuples": 1000, "dead_tuples": 50}
        ]
        cache_stats = {
            "blks_read": 1500,
            "blks_hit": 8500,
            "cache_hit_ratio": 85.0,  # Below 95%
        }

        # Setup mocks
        mock_db_pool._mock_connection.fetch = AsyncMock(
            side_effect=[table_stats, [], []]
        )
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=cache_stats)

        # Act
        result = await repo.suggest_optimizations()

        # Assert
        memory_suggestions = [s for s in result if s["type"] == "memory"]
        assert len(memory_suggestions) > 0
        assert memory_suggestions[0]["priority"] == "medium"

    @pytest.mark.asyncio
    async def test_suggest_optimizations_unused_indexes(self, repo, mock_db_pool):
        """Test suggestions for unused indexes."""
        # Arrange
        table_stats = [
            {"tablename": "qa_conversations", "live_tuples": 1000, "dead_tuples": 50}
        ]
        cache_stats = {"blks_read": 400, "blks_hit": 9600, "cache_hit_ratio": 96.0}
        unused_indexes = [
            {
                "indexname": "idx_never_used",
                "tablename": "qa_conversations",
                "idx_scan": 0,
            }
        ]

        # Setup mocks
        mock_db_pool._mock_connection.fetch = AsyncMock(
            side_effect=[table_stats, unused_indexes, []]
        )
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=cache_stats)

        # Act
        result = await repo.suggest_optimizations()

        # Assert
        index_suggestions = [s for s in result if s["type"] == "index"]
        assert len(index_suggestions) > 0
        assert index_suggestions[0]["priority"] == "low"

    @pytest.mark.asyncio
    async def test_suggest_optimizations_slow_queries(self, repo, mock_db_pool):
        """Test suggestions for slow queries."""
        # Arrange
        table_stats = [
            {"tablename": "qa_conversations", "live_tuples": 1000, "dead_tuples": 50}
        ]
        cache_stats = {"blks_read": 400, "blks_hit": 9600, "cache_hit_ratio": 96.0}
        slow_queries = [
            {"query": "SELECT * FROM qa_conversations", "mean_exec_time": 1500.0}
        ]

        # Setup mocks
        mock_db_pool._mock_connection.fetch = AsyncMock(
            side_effect=[table_stats, [], slow_queries]
        )
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=cache_stats)

        # Act
        result = await repo.suggest_optimizations()

        # Assert
        query_suggestions = [s for s in result if s["type"] == "query"]
        assert len(query_suggestions) > 0
        assert query_suggestions[0]["priority"] == "high"

    @pytest.mark.asyncio
    async def test_suggest_optimizations_no_issues(self, repo, mock_db_pool):
        """Test when no optimization suggestions are needed."""
        # Arrange
        table_stats = [
            {
                "tablename": "qa_conversations",
                "live_tuples": 1000,
                "dead_tuples": 10,  # Low bloat
            }
        ]
        cache_stats = {"blks_read": 200, "blks_hit": 9800, "cache_hit_ratio": 98.0}

        # Setup mocks
        mock_db_pool._mock_connection.fetch = AsyncMock(
            side_effect=[table_stats, [], []]
        )
        mock_db_pool._mock_connection.fetchrow = AsyncMock(return_value=cache_stats)

        # Act
        result = await repo.suggest_optimizations()

        # Assert
        assert result == []
