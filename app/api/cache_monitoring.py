"""
Cache monitoring and statistics API endpoints.

Provides insights into cache performance, hit rates, and system health.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from typing_extensions import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from app.schemas.user import UserInDB
from app.auth.dependencies import get_current_active_user, get_current_active_superuser
from app.config import logger

router = APIRouter()


@router.get("/stats", summary="Get Cache Statistics")
async def get_cache_stats(
    request: Request,
    current_user: Annotated[UserInDB, Depends(get_current_active_superuser)],
) -> Dict[str, Any]:
    """
    Get comprehensive cache statistics and performance metrics.

    Requires admin privileges.
    """
    try:
        cache_service = getattr(request.app.state, "cache_service", None)
        if not cache_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cache service not available",
            )

        # Get basic cache stats
        basic_stats = await cache_service.get_stats()

        # Get Redis info if available
        redis_info = {}
        if cache_service.enabled:
            try:
                redis_info = await cache_service.redis_client.info()
            except Exception as e:
                logger.warning(f"Failed to get Redis info: {e}")

        # Get invalidation stats
        invalidation_stats = {}
        cache_invalidator = getattr(request.app.state, "cache_invalidator", None)
        if cache_invalidator:
            invalidation_stats = cache_invalidator.get_invalidation_stats(hours=24)

        return {
            "timestamp": datetime.now().isoformat(),
            "cache_enabled": cache_service.enabled,
            "basic_stats": basic_stats,
            "redis_info": {
                "version": redis_info.get("redis_version"),
                "used_memory": redis_info.get("used_memory_human"),
                "used_memory_peak": redis_info.get("used_memory_peak_human"),
                "connected_clients": redis_info.get("connected_clients"),
                "total_commands_processed": redis_info.get("total_commands_processed"),
                "keyspace_hits": redis_info.get("keyspace_hits", 0),
                "keyspace_misses": redis_info.get("keyspace_misses", 0),
                "expired_keys": redis_info.get("expired_keys", 0),
                "evicted_keys": redis_info.get("evicted_keys", 0),
            }
            if redis_info
            else {},
            "invalidation_stats": invalidation_stats,
        }

    except Exception as e:
        logger.error(f"Failed to get cache stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cache statistics",
        )


@router.get("/health", summary="Cache Health Check")
async def get_cache_health(
    request: Request,
    detailed: bool = Query(
        default=False, description="Include detailed health information"
    ),
) -> Dict[str, Any]:
    """
    Get cache system health status.

    This endpoint doesn't require authentication and can be used for health monitoring.
    """
    try:
        cache_service = getattr(request.app.state, "cache_service", None)
        if not cache_service:
            return {
                "status": "unavailable",
                "message": "Cache service not initialized",
                "timestamp": datetime.now().isoformat(),
            }

        # Basic health check
        ping_result = False
        if cache_service.enabled:
            try:
                ping_result = await cache_service.ping()
            except Exception as e:
                logger.warning(f"Cache ping failed: {e}")

        # Determine health status
        if not cache_service.enabled:
            status = "disabled"
            message = "Cache is disabled in configuration"
        elif ping_result:
            status = "healthy"
            message = "Cache is operational"
        else:
            status = "unhealthy"
            message = "Cache ping failed"

        health_response = {
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "cache_enabled": cache_service.enabled,
        }

        if detailed and cache_service.enabled:
            try:
                # Add detailed stats
                stats = await cache_service.get_stats()
                redis_info = await cache_service.redis_client.info()

                health_response.update(
                    {
                        "stats": stats,
                        "redis_info": {
                            "version": redis_info.get("redis_version"),
                            "uptime_in_seconds": redis_info.get("uptime_in_seconds"),
                            "connected_clients": redis_info.get("connected_clients"),
                            "used_memory": redis_info.get("used_memory_human"),
                            "total_commands_processed": redis_info.get(
                                "total_commands_processed"
                            ),
                            "keyspace_hits": redis_info.get("keyspace_hits", 0),
                            "keyspace_misses": redis_info.get("keyspace_misses", 0),
                        },
                    }
                )

                # Calculate hit rate if data available
                hits = redis_info.get("keyspace_hits", 0)
                misses = redis_info.get("keyspace_misses", 0)
                total = hits + misses
                if total > 0:
                    hit_rate = (hits / total) * 100
                    health_response["hit_rate_percent"] = round(hit_rate, 2)

            except Exception as e:
                health_response["detailed_stats_error"] = str(e)

        return health_response

    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        return {
            "status": "error",
            "message": "Health check failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/keys/analysis", summary="Analyze Cache Keys")
async def analyze_cache_keys(
    request: Request,
    current_user: Annotated[UserInDB, Depends(get_current_active_superuser)],
    pattern: str = Query(default="*", description="Redis key pattern to analyze"),
    limit: int = Query(
        default=100, ge=1, le=1000, description="Maximum keys to analyze"
    ),
) -> Dict[str, Any]:
    """
    Analyze cache keys matching a pattern.

    Requires admin privileges.
    """
    try:
        cache_service = getattr(request.app.state, "cache_service", None)
        if not cache_service or not cache_service.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cache service not available or disabled",
            )

        # Get keys matching pattern
        keys = await cache_service.redis_client.keys(pattern)
        if len(keys) > limit:
            keys = keys[:limit]

        # Analyze keys
        analysis = {
            "pattern": pattern,
            "total_keys_found": len(keys),
            "keys_analyzed": min(len(keys), limit),
            "key_types": {},
            "key_sizes": {},
            "ttl_distribution": {},
            "key_patterns": {},
        }

        for key in keys:
            try:
                # Get key type
                key_type = await cache_service.redis_client.type(key)
                analysis["key_types"][key_type] = (
                    analysis["key_types"].get(key_type, 0) + 1
                )

                # Get TTL if applicable
                try:
                    ttl = await cache_service.redis_client.ttl(key)
                    if ttl > 0:
                        ttl_range = (
                            f"{ttl // 3600}h" if ttl >= 3600 else f"{ttl // 60}m"
                        )
                        analysis["ttl_distribution"][ttl_range] = (
                            analysis["ttl_distribution"].get(ttl_range, 0) + 1
                        )
                except:
                    pass

                # Get memory usage if available (Redis 4.0+)
                try:
                    memory = await cache_service.redis_client.memory_usage(key)
                    if memory:
                        size_range = (
                            f"{memory // 1024}KB" if memory >= 1024 else f"{memory}B"
                        )
                        analysis["key_sizes"][size_range] = (
                            analysis["key_sizes"].get(size_range, 0) + 1
                        )
                except:
                    pass

                # Analyze key pattern
                key_str = key.decode() if isinstance(key, bytes) else key
                parts = key_str.split(":")
                if len(parts) > 1:
                    pattern = ":".join(parts[:2]) + ":*"
                    analysis["key_patterns"][pattern] = (
                        analysis["key_patterns"].get(pattern, 0) + 1
                    )

            except Exception as e:
                logger.warning(f"Failed to analyze key {key}: {e}")

        return analysis

    except Exception as e:
        logger.error(f"Failed to analyze cache keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze cache keys",
        )


@router.post("/clear", summary="Clear Cache")
async def clear_cache(
    request: Request,
    current_user: Annotated[UserInDB, Depends(get_current_active_superuser)],
    pattern: str = Query(default="*", description="Redis key pattern to clear"),
    confirm: bool = Query(
        default=False, description="Confirmation required for dangerous operations"
    ),
) -> Dict[str, Any]:
    """
    Clear cache keys matching a pattern.

    **DANGER**: This will permanently delete cached data.
    Requires admin privileges and explicit confirmation.

    For safety, pattern "*" requires confirm=True.
    """
    try:
        if not confirm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Explicit confirmation required for cache clearing",
            )

        cache_service = getattr(request.app.state, "cache_service", None)
        if not cache_service or not cache_service.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cache service not available or disabled",
            )

        # Get keys before deletion for reporting
        keys = await cache_service.redis_client.keys(pattern)
        keys_deleted = len(keys)

        # Delete keys
        if keys:
            await cache_service.redis_client.delete(*keys)

        logger.warning(
            f"Cache cleared by admin {current_user.id}: pattern='{pattern}', keys_deleted={keys_deleted}"
        )

        return {
            "message": "Cache cleared successfully",
            "pattern": pattern,
            "keys_deleted": keys_deleted,
            "cleared_by": current_user.id,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache",
        )


@router.get("/invalidation/history", summary="Get Cache Invalidation History")
async def get_invalidation_history(
    request: Request,
    current_user: Annotated[UserInDB, Depends(get_current_active_superuser)],
    hours: int = Query(
        default=24, ge=1, le=168, description="Hours of history to retrieve"
    ),
    event_type: Optional[str] = Query(default=None, description="Filter by event type"),
) -> Dict[str, Any]:
    """
    Get cache invalidation history and statistics.

    Requires admin privileges.
    """
    try:
        cache_invalidator = getattr(request.app.state, "cache_invalidator", None)
        if not cache_invalidator:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cache invalidator not available",
            )

        # Get invalidation stats
        stats = cache_invalidator.get_invalidation_stats(hours=hours)

        # Get detailed history if available
        history = getattr(cache_invalidator, "_invalidation_history", [])
        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Filter history
        filtered_history = []
        for record in history:
            record_time = datetime.fromisoformat(record["timestamp"])
            if record_time > cutoff_time:
                if event_type is None or record.get("event") == event_type:
                    filtered_history.append(record)

        # Limit to last 100 records for response size
        filtered_history = filtered_history[-100:]

        return {
            "period_hours": hours,
            "event_filter": event_type,
            "statistics": stats,
            "recent_events": filtered_history,
            "total_events_in_period": len(filtered_history),
        }

    except Exception as e:
        logger.error(f"Failed to get invalidation history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve invalidation history",
        )


@router.post("/test", summary="Test Cache Performance")
async def test_cache_performance(
    request: Request,
    current_user: Annotated[UserInDB, Depends(get_current_active_superuser)],
    operations: int = Query(
        default=100, ge=1, le=1000, description="Number of test operations"
    ),
) -> Dict[str, Any]:
    """
    Test cache performance with a series of read/write operations.

    Requires admin privileges.
    """
    try:
        cache_service = getattr(request.app.state, "cache_service", None)
        if not cache_service or not cache_service.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Cache service not available or disabled",
            )

        import time
        import random
        import string

        # Performance test
        test_key_prefix = f"perf_test_{int(time.time())}"
        results = {
            "operations_planned": operations,
            "writes": [],
            "reads": [],
            "total_time_ms": 0,
        }

        start_time = time.time()

        # Write operations
        for i in range(operations):
            key = f"{test_key_prefix}:{i}"
            value = "".join(random.choices(string.ascii_letters + string.digits, k=100))

            write_start = time.time()
            await cache_service.set(key, value, ttl=300)
            write_time = (time.time() - write_start) * 1000
            results["writes"].append(write_time)

        # Read operations
        for i in range(operations):
            key = f"{test_key_prefix}:{i}"

            read_start = time.time()
            await cache_service.get(key)
            read_time = (time.time() - read_start) * 1000
            results["reads"].append(read_time)

        # Cleanup test keys
        test_keys = [f"{test_key_prefix}:{i}" for i in range(operations)]
        if test_keys:
            await cache_service.redis_client.delete(*test_keys)

        total_time = (time.time() - start_time) * 1000
        results["total_time_ms"] = total_time

        # Calculate statistics
        results["write_stats"] = {
            "avg_ms": sum(results["writes"]) / len(results["writes"]),
            "min_ms": min(results["writes"]),
            "max_ms": max(results["writes"]),
            "total_ms": sum(results["writes"]),
        }

        results["read_stats"] = {
            "avg_ms": sum(results["reads"]) / len(results["reads"]),
            "min_ms": min(results["reads"]),
            "max_ms": max(results["reads"]),
            "total_ms": sum(results["reads"]),
        }

        results["ops_per_second"] = (operations * 2) / (total_time / 1000)

        return results

    except Exception as e:
        logger.error(f"Cache performance test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cache performance test failed",
        )
