"""
FastAPI application entrypoint for Health Management API.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.qa import router as qa_router
from app.api.user import router as user_router
from app.api.upload import router as upload_router
from app.api.conversations import router as conversations_router
from app.api.messages import router as messages_router
from app.api.websocket import router as websocket_router
from app.api import cache_monitoring
from app.config import settings
from app.db.database import database
from app.middleware.rate_limit import init_rate_limiter
from app.middleware.security import SecurityHeadersMiddleware
from app.services.qa_service import QAService
from app.services.cache import create_cache_service
from app.services.cache_invalidation import get_cache_invalidator
from app.api import predict

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    logger.info("Starting up Health Management API")
    await database.connect()

    # Initialize rate limiter
    try:
        redis_url = getattr(settings, "redis_url", None)
        rate_limiter = init_rate_limiter(redis_url=redis_url)
        logger.info("Rate limiter initialized")
    except Exception as e:
        logger.error(f"Failed to initialize rate limiter: {e}")

    # Initialize Cache Service (must be before QA Service)
    logger.info("Initializing Cache Service...")
    try:
        cache_service = await create_cache_service()
        app.state.cache_service = cache_service

        # Test cache connectivity
        if cache_service.enabled:
            ping_result = await cache_service.ping()
            if ping_result:
                logger.info(
                    "Cache Service initialized successfully with Redis connection"
                )
            else:
                logger.warning(
                    "Cache Service initialized but Redis ping failed - operating in degraded mode"
                )
        else:
            logger.info(
                "Cache Service initialized in pass-through mode (Redis disabled)"
            )

        # Initialize Cache Invalidator
        cache_invalidator = get_cache_invalidator(cache_service)
        app.state.cache_invalidator = cache_invalidator
        logger.info("Cache Invalidator initialized")

    except Exception as e:
        logger.error(f"Failed to initialize Cache Service: {e}")
        # Create fallback cache service with Redis disabled
        from app.services.cache import CacheService

        cache_service = CacheService(None)
        app.state.cache_service = cache_service

        # Initialize invalidator with disabled cache
        cache_invalidator = get_cache_invalidator(cache_service)
        app.state.cache_invalidator = cache_invalidator
        logger.warning(
            "Cache Service and Invalidator created in fallback mode (no Redis)"
        )

    # Initialize Q&A Service if enabled
    if settings.qa_enabled:
        try:
            logger.info("Initializing Q&A Service...")
            # Get cache service from app state (initialized above)
            cache_service = getattr(app.state, "cache_service", None)

            # Initialize QA Service in background to avoid blocking startup
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            def init_qa_service():
                try:
                    return QAService(settings, cache_service=cache_service)
                except Exception as e:
                    logger.error(f"Failed to initialize Q&A Service: {e}")
                    return None

            # Initialize QA Service with timeout to prevent Cloud Run startup timeout
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(init_qa_service)
                try:
                    # Wait up to 30 seconds for QA Service initialization
                    qa_service = future.result(timeout=30)
                    if qa_service:
                        app.state.qa_service = qa_service
                        cache_status = (
                            "with caching"
                            if cache_service and cache_service.enabled
                            else "without caching"
                        )
                        logger.info(
                            f"Q&A Service initialized successfully {cache_status}"
                        )
                    else:
                        logger.warning("Q&A Service initialization returned None")
                        app.state.qa_service = None
                except Exception as e:
                    logger.error(f"Q&A Service initialization timed out or failed: {e}")
                    logger.warning(
                        "Q&A Service will not be available - continuing startup"
                    )
                    app.state.qa_service = None

        except Exception as e:
            logger.error(f"Failed to start Q&A Service initialization: {e}")
            logger.warning("Q&A Service will not be available")
            app.state.qa_service = None
    else:
        logger.info("Q&A Service is disabled in settings")
        app.state.qa_service = None

    # Initialize WebSocket connection cleanup task
    import asyncio
    from app.services.websocket_manager import connection_manager

    async def websocket_cleanup_task():
        """Background task to clean up stale WebSocket connections."""
        while True:
            try:
                await connection_manager.cleanup_stale_connections()
                await asyncio.sleep(300)  # Run every 5 minutes
            except Exception as e:
                logger.error(f"WebSocket cleanup task error: {e}")
                await asyncio.sleep(60)  # Retry after 1 minute on error

    # Start cleanup task
    cleanup_task = asyncio.create_task(websocket_cleanup_task())
    logger.info("WebSocket connection cleanup task started")

    yield

    # Shutdown
    logger.info("Shutting down Health Management API")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

    # Close Redis connection if cache is enabled
    if hasattr(app.state, "cache_service") and app.state.cache_service.enabled:
        try:
            await app.state.cache_service.redis_client.close()
            logger.info("Redis connection closed gracefully")
        except Exception as e:
            logger.warning(f"Error closing Redis connection: {e}")

    await database.disconnect()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Include routers
app.include_router(
    user_router, prefix=f"{settings.api_v1_prefix}/users", tags=["users"]
)
app.include_router(
    auth_router, prefix=f"{settings.api_v1_prefix}/auth", tags=["authentication"]
)
app.include_router(qa_router, prefix=f"{settings.api_v1_prefix}/qa", tags=["Q&A"])
app.include_router(predict.router)
app.include_router(
    upload_router, prefix=f"{settings.api_v1_prefix}/upload", tags=["upload"]
)
app.include_router(
    conversations_router,
    prefix=f"{settings.api_v1_prefix}/conversations",
    tags=["conversations"],
)
app.include_router(
    messages_router, prefix=f"{settings.api_v1_prefix}/messages", tags=["messages"]
)
app.include_router(
    cache_monitoring.router, prefix=f"{settings.api_v1_prefix}/cache", tags=["cache"]
)
app.include_router(websocket_router, tags=["websocket"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "docs_url": (
            "/docs" if settings.debug else "Documentation disabled in production"
        ),
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        pool = database.get_pool()
        async with pool.acquire() as connection:
            await connection.fetchval("SELECT 1")

        # Check QA service status
        qa_status = (
            "initialized"
            if app.state.qa_service is not None
            else ("disabled" if not settings.qa_enabled else "not initialized")
        )

        # Check WebSocket connection manager status
        from app.services.websocket_manager import connection_manager

        ws_stats = connection_manager.get_connection_stats()

        # Check Cache Service status
        cache_status = "disabled"
        cache_stats = {}
        if hasattr(app.state, "cache_service"):
            cache_service = app.state.cache_service
            if cache_service.enabled:
                cache_ping = await cache_service.ping()
                cache_status = "connected" if cache_ping else "disconnected"
                cache_stats = await cache_service.get_stats()
            else:
                cache_status = "disabled"

        return {
            "status": "healthy",
            "database": "connected",
            "qa_service": qa_status,
            "cache": {
                "status": cache_status,
                "stats": cache_stats,
            },
            "websocket": {
                "active_connections": ws_stats["total_connections"],
                "active_conversations": ws_stats["total_conversations"],
                "active_users": ws_stats["total_users"],
            },
            "version": settings.app_version,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
