"""
Performance monitoring and database optimization endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional
import logging

from app.db.database import get_database_pool, asyncpg
from app.db.optimization import DatabaseOptimizationRepository
from app.services.cache import cache_service, conversation_cache
from app.auth.dependencies import get_current_active_superuser
from app.schemas.base import StandardResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/performance", tags=["Performance"])


@router.get("/stats", response_model=StandardResponse[Dict[str, Any]])
async def get_performance_stats(
    current_user=Depends(get_current_active_superuser),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Get comprehensive performance statistics."""
    try:
        optimization_repo = DatabaseOptimizationRepository(pool)

        # Get table statistics
        table_stats = await optimization_repo.get_table_statistics(
            [
                "qa_conversations",
                "qa_messages",
                "qa_message_versions",
                "users",
                "auth_logs",
            ]
        )

        # Get index usage
        index_usage = await optimization_repo.get_index_usage(
            ["qa_conversations", "qa_messages", "qa_message_versions"]
        )

        # Get cache statistics
        cache_stats = await optimization_repo.get_cache_hit_ratios()

        # Get conversation-specific stats
        conv_stats = await optimization_repo.get_conversation_query_optimization_stats()

        # Get Redis cache info if available
        redis_info = cache_service.get_memory_info()

        # Get bloat analysis
        bloat_analysis = await optimization_repo.analyze_bloat()

        return StandardResponse.success(
            data={
                "table_statistics": [dict(stat) for stat in table_stats],
                "index_usage": [dict(idx) for idx in index_usage],
                "cache_hit_ratios": cache_stats,
                "conversation_stats": conv_stats,
                "redis_info": redis_info,
                "bloat_analysis": [dict(bloat) for bloat in bloat_analysis],
                "timestamp": "now",
            }
        )

    except Exception as e:
        logger.error(f"Error getting performance stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve performance statistics",
        )


@router.get("/slow-queries", response_model=StandardResponse[List[Dict[str, Any]]])
async def get_slow_queries(
    min_duration_ms: int = 1000,
    limit: int = 20,
    current_user=Depends(get_current_active_superuser),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Get slow queries from the database."""
    try:
        optimization_repo = DatabaseOptimizationRepository(pool)
        slow_queries = await optimization_repo.get_slow_queries(min_duration_ms, limit)

        return StandardResponse.success(data=[dict(query) for query in slow_queries])

    except Exception as e:
        logger.error(f"Error getting slow queries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve slow queries",
        )


@router.get("/optimizations", response_model=StandardResponse[List[Dict[str, Any]]])
async def get_optimization_suggestions(
    current_user=Depends(get_current_active_superuser),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Get optimization suggestions based on current database state."""
    try:
        optimization_repo = DatabaseOptimizationRepository(pool)
        suggestions = await optimization_repo.suggest_optimizations()

        return StandardResponse.success(data=suggestions)

    except Exception as e:
        logger.error(f"Error getting optimization suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve optimization suggestions",
        )


@router.post("/refresh-search-index", response_model=StandardResponse[str])
async def refresh_search_index(
    current_user=Depends(get_current_active_superuser),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Refresh the conversation search materialized view."""
    try:
        async with pool.acquire() as conn:
            # Refresh with CONCURRENTLY to avoid blocking
            await conn.execute(
                """
                REFRESH MATERIALIZED VIEW CONCURRENTLY conversation_search_index
            """
            )

        return StandardResponse.success(data="Search index refreshed successfully")

    except Exception as e:
        logger.error(f"Error refreshing search index: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh search index",
        )


@router.post("/vacuum-analyze", response_model=StandardResponse[str])
async def vacuum_analyze_tables(
    tables: Optional[List[str]] = None,
    current_user=Depends(get_current_active_superuser),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Run VACUUM ANALYZE on specified tables."""
    try:
        if tables is None:
            tables = ["qa_conversations", "qa_messages", "qa_message_versions"]

        async with pool.acquire() as conn:
            for table in tables:
                await conn.execute(f"VACUUM ANALYZE {table}")

        return StandardResponse.success(
            data=f"VACUUM ANALYZE completed for tables: {', '.join(tables)}"
        )

    except Exception as e:
        logger.error(f"Error running VACUUM ANALYZE: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to run VACUUM ANALYZE",
        )


@router.delete("/unused-indexes", response_model=StandardResponse[List[str]])
async def remove_unused_indexes(
    dry_run: bool = True,
    current_user=Depends(get_current_active_superuser),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Remove or identify unused indexes."""
    try:
        optimization_repo = DatabaseOptimizationRepository(pool)
        unused_indexes = await optimization_repo.identify_unused_indexes(
            ["qa_conversations", "qa_messages", "qa_message_versions"]
        )

        dropped_indexes = []

        async with pool.acquire() as conn:
            for idx in unused_indexes:
                if dry_run:
                    dropped_indexes.append(f"Would drop: {idx['indexname']}")
                else:
                    try:
                        await conn.execute(f'DROP INDEX {idx["indexname"]}')
                        dropped_indexes.append(f"Dropped: {idx['indexname']}")
                    except Exception as e:
                        dropped_indexes.append(
                            f"Failed to drop {idx['indexname']}: {e}"
                        )

        return StandardResponse.success(data=dropped_indexes)

    except Exception as e:
        logger.error(f"Error removing unused indexes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove unused indexes",
        )


@router.post("/invalidate-cache", response_model=StandardResponse[Dict[str, Any]])
async def invalidate_cache(
    user_id: Optional[int] = None,
    conversation_id: Optional[int] = None,
    pattern: Optional[str] = None,
    current_user=Depends(get_current_active_superuser),
):
    """Invalidate cache entries."""
    try:
        invalidated = {}

        if user_id:
            count = conversation_cache.invalidate_user_cache(user_id)
            invalidated["user_cache"] = count

        if conversation_id:
            count = conversation_cache.invalidate_conversation_cache(conversation_id)
            invalidated["conversation_cache"] = count

        if pattern:
            count = cache_service.delete_pattern(pattern)
            invalidated["pattern_cache"] = count

        if not any([user_id, conversation_id, pattern]):
            # Invalidate all cache
            count = cache_service.flush_db()
            invalidated["all_cache"] = count

        return StandardResponse.success(data=invalidated)

    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to invalidate cache",
        )


@router.get("/cache-info", response_model=StandardResponse[Dict[str, Any]])
async def get_cache_info(current_user=Depends(get_current_active_superuser)):
    """Get Redis cache information."""
    try:
        redis_info = cache_service.get_memory_info()
        cache_enabled = cache_service.enabled

        return StandardResponse.success(
            data={"enabled": cache_enabled, "memory_info": redis_info}
        )

    except Exception as e:
        logger.error(f"Error getting cache info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cache information",
        )
