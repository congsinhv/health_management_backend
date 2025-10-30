"""
Q&A API endpoints.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class QuestionRequest(BaseModel):
    """Request model for asking questions."""
    question: str = Field(..., min_length=1, max_length=500, description="User question")
    threshold: float = Field(default=0.55, ge=0.0, le=1.0, description="Similarity threshold")
    top_k: int = Field(default=7, ge=1, le=20, description="Number of top results")


class QuestionResponse(BaseModel):
    """Response model for question answers."""
    question: str
    answers: Dict[str, List[str]]
    summary: str


@router.post("/ask", response_model=QuestionResponse)
async def ask_question(request: Request, question_data: QuestionRequest):
    """
    Ask a health-related question and get answers.
    
    - **question**: The question to ask
    - **threshold**: Minimum similarity score (0.0-1.0)
    - **top_k**: Maximum number of results to return
    """
    try:
        # Get QA service from app state
        qa_service = request.app.state.qa_service
        
        if qa_service is None:
            raise HTTPException(
                status_code=503,
                detail="Q&A service is not available"
            )
        
        # Process question
        result = qa_service.ask_question(
            user_question=question_data.question,
            threshold=question_data.threshold,
            top_k=question_data.top_k
        )
        
        return QuestionResponse(**result)
    
    except ValueError as e:
        logger.warning(f"Invalid question: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def qa_health_check(request: Request):
    """Check Q&A service health status."""
    qa_service = request.app.state.qa_service
    
    if qa_service is None:
        return {
            "status": "unavailable",
            "message": "Q&A service is not initialized"
        }
    
    return {
        "status": "ok",
        "message": "Q&A service is running",
        "model_loaded": qa_service.model is not None,
        "data_loaded": qa_service.df is not None and len(qa_service.df) > 0
    }