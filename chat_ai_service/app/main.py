"""
Main FastAPI application for Chat AI microservice.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.qa import create_qa_app
from app.config import settings
from app.core.shared.exceptions import VHealthException, get_http_status_code, sanitize_error_details
from app.core.error_context import ErrorContext

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = create_qa_app()


# Global exception handlers
@app.exception_handler(VHealthException)
async def vhealth_exception_handler(request, exc: VHealthException):
    """Handle VHealth custom exceptions."""
    import json
    from fastapi.responses import JSONResponse

    status_code = get_http_status_code(exc)
    error_response = {
        "error": exc.error_code,
        "message": exc.message,
        "details": sanitize_error_details(exc.details, user_context=True)
    }

    # Log the error
    exc.log("warning", {
        "path": request.url.path,
        "method": request.method,
        "status_code": status_code
    })

    return JSONResponse(
        status_code=status_code,
        content=error_response
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle unexpected exceptions."""
    import json
    from fastapi.responses import JSONResponse

    # Set error context
    ErrorContext.set_request_id()
    ErrorContext.add_context("path", request.url.path)
    ErrorContext.add_context("method", request.method)

    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    error_response = {
        "error": "InternalServerError",
        "message": "An unexpected error occurred",
        "details": {}
    }

    return JSONResponse(
        status_code=500,
        content=error_response
    )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "VHealth Chat AI Service",
        "description": "Microservice for health-related Q&A with AI summarization",
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_check": "/api/v1/qa/health"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )