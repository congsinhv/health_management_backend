"""
FastAPI application entrypoint for Health Management API.
"""

import logging
import psutil
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.exceptions import (
    VHealthException,
    ResourceNotFoundException,
    ResourceConflictException,
    AuthenticationException,
    AuthorizationException,
    ValidationException,
    BusinessLogicException,
    ServiceUnavailableException,
    DatabaseException,
    RateLimitException,
    ConfigurationException,
    get_http_status_code,
    sanitize_error_details,
)
from app.core.error_context import ErrorContext

from app.api.auth import router as auth_router
from app.api.qa import router as qa_router
from app.api.user import router as user_router
from app.api.upload import router as upload_router
from app.api.conversations import router as conversations_router
from app.api.messages import router as messages_router
from app.api.schedules import router as schedules_router
from app.api.devices import router as devices_router
from app.api.notifications import router as notifications_router
from app.api import predict
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


async def warm_cache_background(qa_service: QAService):
    """
    Run cache warming in background (Phase 3).

    Pre-computes embeddings for top questions to reduce first-request latency.
    Runs non-blocking, errors are logged but don't crash startup.
    """
    try:
        from pathlib import Path
        from scripts.cache_warmer import load_top_questions, warm_cache

        logger.info("Starting background cache warming...")

        # Load questions
        questions = await load_top_questions(settings.qa_cache_warmup_questions_file)

        if not questions:
            logger.warning("No questions to warm, skipping")
            return

        # Warm cache (top 50)
        await warm_cache(qa_service, questions[:50])
        logger.info("Background cache warming completed successfully")

    except Exception as e:
        logger.warning(f"Cache warming failed (non-critical): {e}")
        # Don't crash startup if warming fails


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    logger.info("Starting up Health Management API")

    # Log initial memory usage
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / 1024 / 1024  # Convert to MB
    logger.info(
        f"Startup memory usage: {memory_mb:.2f} MB (RSS)",
        extra={
            "memory_rss_mb": memory_mb,
            "memory_vms_mb": memory_info.vms / 1024 / 1024,
            "startup_phase": "initial",
        },
    )

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

    # Initialize FCM Service (Phase 3)
    if settings.fcm_enabled and settings.fcm_credentials_json:
        try:
            import json
            from app.services.fcm import FCMService
            creds = json.loads(settings.fcm_credentials_json)
            app.state.fcm_service = FCMService(creds)
            logger.info("FCM Service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize FCM Service: {e}")
            app.state.fcm_service = None
    else:
        app.state.fcm_service = None

    # Initialize Cloud Tasks Service (Phase 5)
    if settings.cloud_tasks_enabled and settings.gcp_project_id:
        try:
            from app.services.cloud_tasks import CloudTasksService
            app.state.cloud_tasks_service = CloudTasksService()
            logger.info(
                f"Cloud Tasks Service initialized (queue: {settings.cloud_tasks_queue})"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Cloud Tasks Service: {e}")
            app.state.cloud_tasks_service = None
    else:
        app.state.cloud_tasks_service = None
        if settings.cloud_tasks_enabled:
            logger.warning("Cloud Tasks enabled but GCP project ID not set")

    # Initialize Q&A Service if enabled (completely non-blocking)
    if settings.qa_enabled:
        logger.info("Q&A Service will initialize in background (non-blocking)")
        app.state.qa_service = None  # Will be set by background task

        async def init_qa_service_async():
            """Initialize QA service in background without blocking startup."""
            try:
                cache_service = getattr(app.state, "cache_service", None)
                logger.info("Starting Q&A Service initialization in background...")

                # Run in thread to avoid blocking event loop
                import asyncio
                from concurrent.futures import ThreadPoolExecutor

                def _init():
                    try:
                        return QAService(settings, cache_service=cache_service)
                    except Exception as e:
                        logger.error(f"Q&A Service initialization error: {e}")
                        return None

                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    qa_service = await loop.run_in_executor(executor, _init)

                if qa_service:
                    app.state.qa_service = qa_service
                    cache_status = (
                        "with caching"
                        if cache_service and cache_service.enabled
                        else "without caching"
                    )
                    logger.info(f"Q&A Service initialized successfully {cache_status}")

                    # Start cache warming if enabled (after QA service is ready)
                    if (
                        settings.qa_cache_warmup_enabled
                        and cache_service
                        and cache_service.enabled
                    ):
                        logger.info("Starting cache warming in background...")
                        asyncio.create_task(warm_cache_background(qa_service))
                else:
                    logger.warning("Q&A Service initialization failed")
            except Exception as e:
                logger.error(f"Q&A Service background init failed: {e}")

        # Start background initialization (fire and forget)
        import asyncio

        asyncio.create_task(init_qa_service_async())
    else:
        logger.info("Q&A Service is disabled in settings")
        app.state.qa_service = None

    # Cache warming is now integrated into QA service background initialization
    # (see init_qa_service_async above)

    # Log final startup memory usage
    memory_info_final = process.memory_info()
    memory_mb_final = memory_info_final.rss / 1024 / 1024
    logger.info(
        f"Startup complete - Memory usage: {memory_mb_final:.2f} MB (RSS)",
        extra={
            "memory_rss_mb": memory_mb_final,
            "memory_vms_mb": memory_info_final.vms / 1024 / 1024,
            "memory_increase_mb": memory_mb_final - memory_mb,
            "startup_phase": "complete",
        },
    )

    yield

    # Shutdown
    logger.info("Shutting down Health Management API")

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
app.include_router(
    predict.router, prefix=f"{settings.api_v1_prefix}/predict", tags=["predict"]
)
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
    schedules_router,
    prefix=f"{settings.api_v1_prefix}/schedules",
    tags=["schedules"],
)
app.include_router(
    devices_router,
    prefix=f"{settings.api_v1_prefix}/devices",
    tags=["devices"],
)
app.include_router(
    notifications_router,
    prefix=f"{settings.api_v1_prefix}/notifications",
    tags=["notifications"],
)


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


# Exception Handlers


@app.exception_handler(VHealthException)
async def vhealth_exception_handler(request: Request, exc: VHealthException):
    """Handle all custom VHealth exceptions."""
    # Log the exception with context
    context = ErrorContext.get_all()
    logger.warning(
        f"VHealth exception: {exc.message}",
        extra={
            **context,
            "exception_type": exc.__class__.__name__,
            "error_code": exc.error_code,
            "details": sanitize_error_details(exc.details),
        },
    )

    # Get appropriate HTTP status code
    status_code = get_http_status_code(exc)

    # Prepare response with user-safe details
    user_details = sanitize_error_details(exc.details, user_context=True)

    response_data = {
        "error": exc.error_code,
        "message": exc.message,
        "request_id": ErrorContext.get_request_id(),
    }

    if user_details:
        response_data["details"] = user_details

    return JSONResponse(status_code=status_code, content=response_data)


@app.exception_handler(ResourceNotFoundException)
async def resource_not_found_handler(request: Request, exc: ResourceNotFoundException):
    """Handle resource not found errors."""
    logger.warning(
        f"Resource not found: {exc.message}",
        extra={
            **ErrorContext.get_all(),
            "exception_type": "ResourceNotFoundException",
            "details": sanitize_error_details(exc.details),
        },
    )

    return JSONResponse(
        status_code=404,
        content={
            "error": "ResourceNotFound",
            "message": exc.message,
            "request_id": ErrorContext.get_request_id(),
        },
    )


@app.exception_handler(AuthenticationException)
async def authentication_handler(request: Request, exc: AuthenticationException):
    """Handle authentication errors."""
    logger.warning(
        f"Authentication failed: {exc.message}",
        extra={**ErrorContext.get_all(), "exception_type": "AuthenticationException"},
    )

    return JSONResponse(
        status_code=401,
        content={
            "error": "AuthenticationFailed",
            "message": exc.message,
            "request_id": ErrorContext.get_request_id(),
        },
    )


@app.exception_handler(AuthorizationException)
async def authorization_handler(request: Request, exc: AuthorizationException):
    """Handle authorization errors."""
    logger.warning(
        f"Authorization failed: {exc.message}",
        extra={**ErrorContext.get_all(), "exception_type": "AuthorizationException"},
    )

    return JSONResponse(
        status_code=403,
        content={
            "error": "AuthorizationFailed",
            "message": exc.message,
            "request_id": ErrorContext.get_request_id(),
        },
    )


@app.exception_handler(ValidationException)
async def validation_handler(request: Request, exc: ValidationException):
    """Handle validation errors."""
    logger.warning(
        f"Validation failed: {exc.message}",
        extra={
            **ErrorContext.get_all(),
            "exception_type": "ValidationException",
            "details": sanitize_error_details(exc.details),
        },
    )

    user_details = sanitize_error_details(exc.details, user_context=True)

    response_data = {
        "error": "ValidationFailed",
        "message": exc.message,
        "request_id": ErrorContext.get_request_id(),
    }

    if user_details:
        response_data["details"] = user_details

    return JSONResponse(status_code=422, content=response_data)


@app.exception_handler(BusinessLogicException)
async def business_logic_handler(request: Request, exc: BusinessLogicException):
    """Handle business logic errors."""
    logger.warning(
        f"Business logic error: {exc.message}",
        extra={
            **ErrorContext.get_all(),
            "exception_type": "BusinessLogicException",
            "details": sanitize_error_details(exc.details),
        },
    )

    status_code = 400  # Default for business logic errors

    # Specific status codes for certain business logic errors
    if "duplicate" in exc.message.lower() or "conflict" in exc.message.lower():
        status_code = 409
    elif "quota" in exc.message.lower() or "limit" in exc.message.lower():
        status_code = 429

    user_details = sanitize_error_details(exc.details, user_context=True)

    response_data = {
        "error": "BusinessLogicError",
        "message": exc.message,
        "request_id": ErrorContext.get_request_id(),
    }

    if user_details:
        response_data["details"] = user_details

    return JSONResponse(status_code=status_code, content=response_data)


@app.exception_handler(ServiceUnavailableException)
async def service_unavailable_handler(
    request: Request, exc: ServiceUnavailableException
):
    """Handle service unavailable errors."""
    logger.error(
        f"Service unavailable: {exc.message}",
        extra={
            **ErrorContext.get_all(),
            "exception_type": "ServiceUnavailableException",
            "details": sanitize_error_details(exc.details),
        },
    )

    return JSONResponse(
        status_code=503,
        content={
            "error": "ServiceUnavailable",
            "message": "Service temporarily unavailable. Please try again later.",
            "request_id": ErrorContext.get_request_id(),
        },
    )


@app.exception_handler(DatabaseException)
async def database_handler(request: Request, exc: DatabaseException):
    """Handle database errors."""
    logger.error(
        f"Database error: {exc.message}",
        extra={
            **ErrorContext.get_all(),
            "exception_type": "DatabaseException",
            "details": sanitize_error_details(exc.details),
        },
    )

    # Don't expose database details to users
    return JSONResponse(
        status_code=500,
        content={
            "error": "DatabaseError",
            "message": "An error occurred while processing your request.",
            "request_id": ErrorContext.get_request_id(),
        },
    )


@app.exception_handler(RateLimitException)
async def rate_limit_handler(request: Request, exc: RateLimitException):
    """Handle rate limiting errors."""
    logger.warning(
        f"Rate limit exceeded: {exc.message}",
        extra={**ErrorContext.get_all(), "exception_type": "RateLimitException"},
    )

    return JSONResponse(
        status_code=429,
        content={
            "error": "RateLimitExceeded",
            "message": "Too many requests. Please try again later.",
            "request_id": ErrorContext.get_request_id(),
        },
    )


@app.exception_handler(ConfigurationException)
async def configuration_handler(request: Request, exc: ConfigurationException):
    """Handle configuration errors."""
    logger.error(
        f"Configuration error: {exc.message}",
        extra={
            **ErrorContext.get_all(),
            "exception_type": "ConfigurationException",
            "details": sanitize_error_details(exc.details),
        },
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "ConfigurationError",
            "message": "Service configuration error. Please contact support.",
            "request_id": ErrorContext.get_request_id(),
        },
    )


# Global exception handler for unhandled exceptions
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(
        f"Unhandled exception: {str(exc)}",
        extra={
            **ErrorContext.get_all(),
            "exception_type": exc.__class__.__name__,
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred. Please try again later.",
            "request_id": ErrorContext.get_request_id(),
        },
    )


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
