"""Prediction Service - Health predictions with ONNX."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import predict
from app.services.predict_service import PredictService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    logger.info("Starting Prediction Service...")

    # Initialize prediction service with ONNX models
    try:
        app.state.predict_service = await PredictService.create()
        logger.info("Prediction service initialized with ONNX models")
    except Exception as e:
        logger.error(f"Failed to initialize prediction service: {e}")
        raise

    yield

    logger.info("Shutting down Prediction Service...")


# Create FastAPI application
app = FastAPI(
    title="VHealth Prediction Service",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(predict.router, prefix="/api/v1")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "VHealth Prediction Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "predict": "/api/v1/predict/",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }

# Health check endpoint
@app.get("/health")
async def health():
    """Health check endpoint."""
    try:
        model_loaded = app.state.predict_service.is_model_loaded() if hasattr(app.state, 'predict_service') else False
        return {
            "status": "healthy",
            "service": "prediction",
            "model_loaded": model_loaded,
            "version": "1.0.0"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "prediction",
            "error": str(e),
            "version": "1.0.0"
        }