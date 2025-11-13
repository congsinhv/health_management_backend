"""
FastAPI application entrypoint for Health Management API.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.auth import router as auth_router
from app.api.qa import router as qa_router
from app.api.user import router as user_router
from app.api.upload import router as upload_router
from app.api.conversation import router as conversation_router
from app.api.message import router as message_router
from app.api.performance import router as performance_router
from app.api.branching import router as branching_router
from app.api.version import router as version_router
from app.config import settings
from app.db.database import database
from app.services.qa_service import QAService

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ForwardedProtoMiddleware(BaseHTTPMiddleware):
    """Middleware to handle X-Forwarded-Proto header correctly."""

    async def dispatch(self, request: Request, call_next):
        # Check for X-Forwarded-Proto header (set by load balancer/proxy)
        forwarded_proto = request.headers.get("x-forwarded-proto")
        if forwarded_proto:
            # Update the request scope to use the correct protocol
            request.scope["scheme"] = forwarded_proto.lower()
            request.scope["type"] = "http"

        # Also handle X-Forwarded-Host if present
        forwarded_host = request.headers.get("x-forwarded-host")
        if forwarded_host:
            request.scope["server"] = (forwarded_host, 443 if forwarded_proto == "https" else 80)

        # Handle X-Forwarded-Port if present
        forwarded_port = request.headers.get("x-forwarded-port")
        if forwarded_port:
            host, _ = request.scope["server"]
            request.scope["server"] = (host, int(forwarded_port))

        response = await call_next(request)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    logger.info("Starting up Health Management API")
    await database.connect()

    # Initialize Q&A Service if enabled
    if settings.qa_enabled:
        try:
            logger.info("Initializing Q&A Service...")
            qa_service = QAService(settings)
            app.state.qa_service = qa_service
            logger.info("Q&A Service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Q&A Service: {e}")
            logger.warning("Q&A Service will not be available")
            app.state.qa_service = None
    else:
        logger.info("Q&A Service is disabled in settings")
        app.state.qa_service = None

    yield

    # Shutdown
    logger.info("Shutting down Health Management API")
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

# Add forwarded proto middleware first (to handle load balancer headers)
app.add_middleware(ForwardedProtoMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Include routers
app.include_router(
    user_router, prefix=f"{settings.api_v1_prefix}/users", tags=["users"]
)
app.include_router(
    auth_router, prefix=f"{settings.api_v1_prefix}/auth", tags=["authentication"]
)
app.include_router(qa_router, prefix=f"{settings.api_v1_prefix}/qa", tags=["Q&A"])
app.include_router(
    upload_router, prefix=f"{settings.api_v1_prefix}/upload", tags=["upload"]
)
app.include_router(
    conversation_router,
    prefix=f"{settings.api_v1_prefix}/conversations",
    tags=["conversations"],
)
app.include_router(
    message_router, prefix=f"{settings.api_v1_prefix}/conversations", tags=["messages"]
)
app.include_router(
    performance_router, prefix=f"{settings.api_v1_prefix}", tags=["performance"]
)
app.include_router(
    branching_router,
    prefix=f"{settings.api_v1_prefix}/conversations",
    tags=["branching"],
)
app.include_router(
    version_router, prefix=f"{settings.api_v1_prefix}/conversations", tags=["versions"]
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

        return {
            "status": "healthy",
            "database": "connected",
            "qa_service": qa_status,
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
