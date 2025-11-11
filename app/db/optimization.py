"""
Database optimization utilities for performance improvements.
"""

import asyncpg
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

from app.db.database import BaseRepository

logger = logging.getLogger(__name__)


class DatabaseOptimizationRepository(BaseRepository):
    """Repository for database optimization operations."""

    async def get_table_statistics(
        self, table_names: List[str]
    ) -> List[asyncpg.Record]:
        """Get detailed statistics for specified tables."""
        query = """
            SELECT
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
                pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as index_size,
                n_tup_ins as total_inserts,
                n_tup_upd as total_updates,
                n_tup_del as total_deletes,
                n_live_tup as live_tuples,
                n_dead_tup as dead_tuples,
                last_vacuum,
                last_autovacuum,
                last_analyze,
                last_autoanalyze
            FROM pg_stat_user_tables
            WHERE tablename = ANY($1)
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
        """
        return await self.fetch_many(query, table_names)

    async def get_slow_queries(
        self, min_duration_ms: int = 1000, limit: int = 20
    ) -> List[asyncpg.Record]:
        """Get slow queries from pg_stat_statements."""
        try:
            query = """
                SELECT
                    query,
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    max_exec_time,
                    stddev_exec_time,
                    rows,
                    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
                FROM pg_stat_statements
                WHERE mean_exec_time > $1
                ORDER BY mean_exec_time DESC
                LIMIT $2
            """
            return await self.fetch_many(query, min_duration_ms, limit)
        except Exception as e:
            logger.warning(f"pg_stat_statements not available: {e}")
            return []

    async def get_index_usage(self, table_names: List[str]) -> List[asyncpg.Record]:
        """Get index usage statistics for tables."""
        query = """
            SELECT
                schemaname,
                tablename,
                indexname,
                idx_scan as index_scans,
                idx_tup_read as tuples_read,
                idx_tup_fetch as tuples_fetched,
                pg_size_pretty(pg_relation_size(schemaname||'.'||indexrelname)) as index_size
            FROM pg_stat_user_indexes
            WHERE tablename = ANY($1)
            ORDER BY idx_scan DESC
        """
        return await self.fetch_many(query, table_names)

    async def identify_unused_indexes(
        self, table_names: List[str], min_age_days: int = 7
    ) -> List[asyncpg.Record]:
        """Identify potentially unused indexes."""
        query = """
            SELECT
                schemaname,
                tablename,
                indexname,
                idx_scan,
                pg_size_pretty(pg_relation_size(schemaname||'.'||indexrelname)) as index_size
            FROM pg_stat_user_indexes
            WHERE tablename = ANY($1)
                AND idx_scan = 0
                AND schemaname NOT IN ('pg_catalog', 'pg_toast')
            ORDER BY pg_relation_size(schemaname||'.'||indexrelname) DESC
        """
        return await self.fetch_many(query, table_names)

    async def get_cache_hit_ratios(self) -> Dict[str, float]:
        """Get database cache hit ratios."""
        query = """
            SELECT
                datname,
                blks_read,
                blks_hit,
                round(
                    case
                        when blks_hit = 0 then 0
                        else blks_hit::float / (blks_hit + blks_read)
                    end * 100, 2
                ) as cache_hit_ratio
            FROM pg_stat_database
            WHERE datname = current_database()
        """
        result = await self.fetch_one(query)
        return {
            "blocks_read": result["blks_read"],
            "blocks_hit": result["blks_hit"],
            "cache_hit_ratio": result["cache_hit_ratio"],
        }

    async def analyze_bloat(self) -> List[asyncpg.Record]:
        """Analyze table and index bloat."""
        query = """
            WITH constants AS (
                SELECT current_setting('block_size')::integer AS bs,
                23 AS hdr,
                4 AS ma
            ),
            bloat_info AS (
                SELECT
                    ma,bs,schemaname,tablename,
                    (datawidth+(hdr+ma-(case when hdr%ma=0 THEN ma ELSE hdr%ma END)))::numeric AS datahdr,
                    (maxfracsum*(nullhdr+ma-(case when nullhdr%ma=0 THEN ma ELSE nullhdr%ma END))) AS nullhdr2
                FROM (
                    SELECT
                        schemaname, tablename, hdr, ma, bs,
                        SUM((1-null_frac)*avg_width) AS datawidth,
                        MAX(null_frac) AS maxfracsum,
                        hdr+(
                            SELECT 1+COUNT(*)*(8)
                            FROM pg_stats s2
                            WHERE null_frac<>0 AND s2.schemaname=s.schemaname AND s2.tablename=s.tablename
                        ) AS nullhdr
                    FROM pg_stats s, constants
                    GROUP BY 1,2,3,4,5
                ) AS foo
            ),
            table_bloat AS (
                SELECT
                    c.relname,
                    c.relpages,
                    bloat_info.datahdr,
                    bloat_info.nullhdr2,
                    ceil(c.reltuples / ((c.relpages - floor(c.relpages * (c.relallvisible::float / c.relpages)))::float / bs)) AS est_ntup
                FROM bloat_info
                JOIN pg_class c ON c.relname = bloat_info.tablename
                WHERE c.relkind = 'r'
            ),
            index_bloat AS (
                SELECT
                    c.relname AS indexname,
                    c.relpages,
                    bloat_info.datahdr,
                    bloat_info.nullhdr2
                FROM bloat_info
                JOIN pg_class c ON c.relname = bloat_info.tablename
                WHERE c.relkind = 'i'
            )
            SELECT
                'Table' as object_type,
                relname as name,
                relpages as pages,
                ROUND(100 * (relpages - est_ntup) / relpages, 2) AS bloat_percentage,
                ROUND(100 * (relpages - est_ntup) / relpages * (bs / 1024 / 1024), 2) AS bloat_mb
            FROM table_bloat
            WHERE bloat_percentage > 10
            UNION ALL
            SELECT
                'Index' as object_type,
                indexname as name,
                relpages as pages,
                ROUND(100 * (relpages - ((datahdr + nullhdr2) * 8 / bs)) / relpages, 2) AS bloat_percentage,
                ROUND(100 * (relpages - ((datahdr + nullhdr2) * 8 / bs)) / relpages * (bs / 1024 / 1024), 2) AS bloat_mb
            FROM index_bloat
            WHERE bloat_percentage > 10
            ORDER BY bloat_mb DESC
        """
        return await self.fetch_many(query)

    async def get_conversation_query_optimization_stats(self) -> Dict[str, Any]:
        """Get specific optimization stats for conversation queries."""
        # Check materialized view freshness
        view_stats = await self.fetch_one(
            """
            SELECT
                COUNT(*) as total_conversations,
                MAX(updated_at) as last_updated,
                NOW() - MAX(updated_at) as age
            FROM conversation_search_index
        """
        )

        # Check search performance
        search_stats = await self.fetch_one(
            """
            SELECT
                COUNT(*) as total_searchable_content,
                AVG(LENGTH(title) + LENGTH(question)) as avg_content_length,
                MAX(LENGTH(title) + LENGTH(question)) as max_content_length
            FROM qa_conversations
            WHERE deleted_at IS NULL
        """
        )

        # Check message distribution
        message_stats = await self.fetch_one(
            """
            SELECT
                COUNT(*) as total_messages,
                COUNT(DISTINCT conversation_id) as conversations_with_messages,
                AVG(message_count) as avg_messages_per_conversation
            FROM (
                SELECT
                    c.id,
                    COUNT(m.id) as message_count
                FROM qa_conversations c
                LEFT JOIN qa_messages m ON c.id = m.conversation_id AND m.deleted_at IS NULL
                WHERE c.deleted_at IS NULL
                GROUP BY c.id
            ) msg_stats
        """
        )

        return {
            "materialized_view": {
                "total_conversations": view_stats["total_conversations"],
                "last_updated": view_stats["last_updated"],
                "age_seconds": (
                    view_stats["age"].total_seconds() if view_stats["age"] else None
                ),
            },
            "search_content": {
                "total_searchable": search_stats["total_searchable_content"],
                "avg_content_length": search_stats["avg_content_length"],
                "max_content_length": search_stats["max_content_length"],
            },
            "messages": {
                "total_messages": message_stats["total_messages"],
                "conversations_with_messages": message_stats[
                    "conversations_with_messages"
                ],
                "avg_messages_per_conversation": message_stats[
                    "avg_messages_per_conversation"
                ],
            },
        }

    async def suggest_optimizations(self) -> List[Dict[str, Any]]:
        """Suggest optimizations based on current database state."""
        suggestions = []

        # Get table statistics
        conv_tables = ["qa_conversations", "qa_messages", "qa_message_versions"]
        table_stats = await self.get_table_statistics(conv_tables)

        # Check for high bloat
        for table in table_stats:
            if table["dead_tuples"] > table["live_tuples"] * 0.2:
                suggestions.append(
                    {
                        "type": "vacuum",
                        "priority": "high",
                        "table": table["tablename"],
                        "description": f"Table {table['tablename']} has high bloat ({table['dead_tuples']} dead tuples)",
                        "action": "Run VACUUM ANALYZE on this table",
                    }
                )

        # Check cache hit ratio
        cache_stats = await self.get_cache_hit_ratios()
        if cache_stats["cache_hit_ratio"] < 95:
            suggestions.append(
                {
                    "type": "memory",
                    "priority": "medium",
                    "description": f"Low cache hit ratio: {cache_stats['cache_hit_ratio']}%",
                    "action": "Consider increasing shared_buffers or work_mem",
                }
            )

        # Check unused indexes
        unused_indexes = await self.identify_unused_indexes(conv_tables)
        for idx in unused_indexes:
            suggestions.append(
                {
                    "type": "index",
                    "priority": "low",
                    "index": idx["indexname"],
                    "table": idx["tablename"],
                    "description": f"Index {idx['indexname']} on {idx['tablename']} has never been used",
                    "action": "Consider dropping this unused index",
                }
            )

        # Get slow queries
        slow_queries = await self.get_slow_queries()
        for query in slow_queries[:5]:  # Top 5 slow queries
            suggestions.append(
                {
                    "type": "query",
                    "priority": "high",
                    "description": f"Slow query detected (avg {query['mean_exec_time']:.2f}ms)",
                    "action": "Review and optimize this query",
                }
            )

        return suggestions
