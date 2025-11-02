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
from app.config import settings
from app.db.database import database
from app.services.qa_service import QAService

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
