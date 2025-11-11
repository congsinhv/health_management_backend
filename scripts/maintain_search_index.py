#!/usr/bin/env python3
"""
Script to maintain the conversation search index materialized view.
This can be run as a cron job to keep the search index up to date.
"""

import asyncio
import asyncpg
import logging
from datetime import datetime
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def refresh_search_index():
    """Refresh the conversation_search_index materialized view."""
    try:
        # Connect to database
        pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=2)

        async with pool.acquire() as conn:
            logger.info("Refreshing conversation search index...")

            # Refresh materialized view with CONCURRENTLY to avoid blocking
            await conn.execute(
                """
                REFRESH MATERIALIZED VIEW CONCURRENTLY conversation_search_index
            """
            )

            # Get index statistics
            stats = await conn.fetchrow(
                """
                SELECT
                    COUNT(*) as total_conversations,
                    COUNT(CASE WHEN is_pinned THEN 1 END) as pinned_count,
                    MAX(updated_at) as last_updated
                FROM conversation_search_index
            """
            )

            logger.info(f"Search index refreshed successfully:")
            logger.info(f"  Total conversations: {stats['total_conversations']}")
            logger.info(f"  Pinned conversations: {stats['pinned_count']}")
            logger.info(f"  Last updated: {stats['last_updated']}")

        await pool.close()

    except Exception as e:
        logger.error(f"Error refreshing search index: {e}")
        raise


async def analyze_query_performance():
    """Analyze and report on query performance."""
    try:
        pool = await asyncpg.create_pool(settings.database_url)

        async with pool.acquire() as conn:
            logger.info("Analyzing query performance...")

            # Check table sizes
            tables = await conn.fetch(
                """
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    n_tup_ins as inserts,
                    n_tup_upd as updates,
                    n_tup_del as deletes,
                    n_live_tup as live_tuples,
                    n_dead_tup as dead_tuples
                FROM pg_stat_user_tables
                WHERE tablename IN ('qa_conversations', 'qa_messages', 'qa_message_versions', 'conversation_search_index')
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            """
            )

            logger.info("Table statistics:")
            for table in tables:
                logger.info(
                    f"  {table['tablename']}: {table['size']}, "
                    f"Live: {table['live_tuples']}, Dead: {table['dead_tuples']}"
                )

            # Check index usage
            indexes = await conn.fetch(
                """
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan as index_scans,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched
                FROM pg_stat_user_indexes
                WHERE tablename IN ('qa_conversations', 'qa_messages', 'qa_message_versions')
                ORDER BY idx_scan DESC
            """
            )

            logger.info("Index usage statistics:")
            for idx in indexes:
                logger.info(
                    f"  {idx['tablename']}.{idx['indexname']}: "
                    f"{idx['index_scans']} scans"
                )

        await pool.close()

    except Exception as e:
        logger.error(f"Error analyzing query performance: {e}")
        raise


async def vacuum_analyze_tables():
    """Run VACUUM ANALYZE on conversation tables."""
    try:
        pool = await asyncpg.create_pool(settings.database_url)

        async with pool.acquire() as conn:
            logger.info("Running VACUUM ANALYZE on conversation tables...")

            tables = ["qa_conversations", "qa_messages", "qa_message_versions"]

            for table in tables:
                logger.info(f"Vacuum analyzing {table}...")
                await conn.execute(f"VACUUM ANALYZE {table}")

        await pool.close()
        logger.info("VACUUM ANALYZE completed successfully")

    except Exception as e:
        logger.error(f"Error running VACUUM ANALYZE: {e}")
        raise


async def create_performance_indexes():
    """Create additional performance indexes if they don't exist."""
    try:
        pool = await asyncpg.create_pool(settings.database_url)

        async with pool.acquire() as conn:
            logger.info("Creating performance indexes...")

            # Check and create indexes as needed
            indexes_to_create = [
                {
                    "name": "idx_qa_messages_created_at_desc",
                    "table": "qa_messages",
                    "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_messages_created_at_desc ON qa_messages (created_at DESC)",
                },
                {
                    "name": "idx_qa_conversations_updated_at_desc",
                    "table": "qa_conversations",
                    "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_conversations_updated_at_desc ON qa_conversations (updated_at DESC)",
                },
                {
                    "name": "idx_qa_messages_conversation_created",
                    "table": "qa_messages",
                    "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_messages_conversation_created ON qa_messages (conversation_id, created_at)",
                },
                {
                    "name": "idx_qa_message_versions_created_at",
                    "table": "qa_message_versions",
                    "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_qa_message_versions_created_at ON qa_message_versions (created_at DESC)",
                },
            ]

            for idx in indexes_to_create:
                # Check if index exists
                exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_indexes
                        WHERE indexname = $1
                    )
                """,
                    idx["name"],
                )

                if not exists:
                    logger.info(f"Creating index {idx['name']}...")
                    await conn.execute(idx["sql"])
                    logger.info(f"Created index {idx['name']}")
                else:
                    logger.info(f"Index {idx['name']} already exists")

        await pool.close()
        logger.info("Performance indexes creation completed")

    except Exception as e:
        logger.error(f"Error creating performance indexes: {e}")
        raise


async def main():
    """Main maintenance function."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python maintain_search_index.py <command>")
        print("Commands:")
        print("  refresh - Refresh search index")
        print("  analyze - Analyze query performance")
        print("  vacuum - Run VACUUM ANALYZE")
        print("  indexes - Create performance indexes")
        print("  all - Run all maintenance tasks")
        return

    command = sys.argv[1]

    try:
        if command == "refresh":
            await refresh_search_index()
        elif command == "analyze":
            await analyze_query_performance()
        elif command == "vacuum":
            await vacuum_analyze_tables()
        elif command == "indexes":
            await create_performance_indexes()
        elif command == "all":
            logger.info("Running all maintenance tasks...")
            await create_performance_indexes()
            await refresh_search_index()
            await vacuum_analyze_tables()
            await analyze_query_performance()
            logger.info("All maintenance tasks completed")
        else:
            print(f"Unknown command: {command}")
    except Exception as e:
        logger.error(f"Maintenance failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
