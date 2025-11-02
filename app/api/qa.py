"""
Q&A API endpoints.
"""

from fastapi import APIRouter, HTTPException, Request, Depends, Query
from typing import Optional
import logging
import math
from app.schemas.qa import (
    QuestionRequest,
    QuestionResponse,
    ConversationDetail,
    ConversationListResponse,
    QAHealthResponse,
)
from app.schemas.user import UserInDB
from app.db import qa as qa_db
from app.auth.dependencies import get_current_user_optional

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/ask", response_model=QuestionResponse)
async def ask_question(
    request: Request,
    question_data: QuestionRequest,
    current_user: Optional[UserInDB] = Depends(get_current_user_optional),
):
    """
    Ask a health-related question and get answers.

    - **question**: The question to ask
    - **threshold**: Minimum similarity score (0.0-1.0)
    - **top_k**: Maximum number of results to return
    """
    try:
        # Get QA service from app state
        qa_service = getattr(request.app.state, "qa_service", None)

        if qa_service is None:
            raise HTTPException(status_code=503, detail="Q&A service is not available")

        # Process question
        result = qa_service.ask_question(
            user_question=question_data.question,
            threshold=question_data.threshold,
            top_k=question_data.top_k,
        )

        # Get user_id if authenticated
        user_id = current_user.id if current_user else None

        # Get cleaned question
        question_cleaned = qa_service.preprocess_text(question_data.question)

        # Save conversation to database
        try:
            conversation_id = await qa_db.create_conversation(
                question=question_data.question,
                question_cleaned=question_cleaned,
                answers=result["answers"],
                summary=result["summary"],
                threshold=question_data.threshold or qa_service.settings.qa_threshold,
                top_k=question_data.top_k or qa_service.settings.qa_top_k,
                user_id=user_id,
            )
            result["conversation_id"] = conversation_id
        except Exception as db_error:
            logger.error(f"Failed to save conversation: {db_error}")
            # Continue without saving to database

        return QuestionResponse(**result)

    except ValueError as e:
        logger.warning(f"Invalid question: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Error processing question: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=QAHealthResponse)
async def qa_health_check(request: Request):
    """Check Q&A service health status."""
    qa_service = getattr(request.app.state, "qa_service", None)

    if qa_service is None:
        return QAHealthResponse(
            status="unavailable", message="Q&A service is not initialized"
        )

    return QAHealthResponse(
        status="ok",
        message="Q&A service is running",
        model_loaded=qa_service.model is not None,
        data_loaded=qa_service.df is not None and len(qa_service.df) > 0,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: int,
    current_user: Optional[UserInDB] = Depends(get_current_user_optional),
):
    """
    Get a specific conversation by ID.

    - **conversation_id**: The conversation ID
    """
    try:
        conversation = await qa_db.get_conversation_by_id(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Check if user has access (if authenticated)
        if current_user and conversation["user_id"] != current_user.id:
            # If it's another user's conversation, only allow if it's public (user_id is None)
            if conversation["user_id"] is not None:
                raise HTTPException(status_code=403, detail="Access denied")

        return ConversationDetail(**conversation)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving conversation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search query"),
    current_user: Optional[UserInDB] = Depends(get_current_user_optional),
):
    """
    List conversations for the current user.

    - **page**: Page number (starting from 1)
    - **page_size**: Number of items per page
    - **search**: Optional search query
    """
    try:
        # Calculate offset
        offset = (page - 1) * page_size

        # Get user_id if authenticated
        user_id = current_user.id if current_user else None

        if search:
            conversations = await qa_db.search_conversations(
                search_query=search, user_id=user_id, limit=page_size, offset=offset
            )
        else:
            if user_id:
                conversations = await qa_db.get_user_conversations(
                    user_id=user_id, limit=page_size, offset=offset
                )
            else:
                conversations = await qa_db.get_recent_conversations(
                    limit=page_size, offset=offset
                )

        # Get total count
        if user_id:
            total = await qa_db.count_user_conversations(user_id)
        else:
            # For non-authenticated users, we'll use the page count
            total = len(conversations)

        total_pages = math.ceil(total / page_size)

        return ConversationListResponse(
            conversations=conversations,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    current_user: Optional[UserInDB] = Depends(get_current_user_optional),
):
    """
    Delete a conversation by ID.

    - **conversation_id**: The conversation ID
    """
    try:
        # Get conversation first to check ownership
        conversation = await qa_db.get_conversation_by_id(conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Check if user has permission to delete
        if current_user:
            if conversation["user_id"] != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied")
        else:
            # Non-authenticated users can only delete public conversations
            if conversation["user_id"] is not None:
                raise HTTPException(status_code=403, detail="Access denied")

        # Delete conversation
        deleted = await qa_db.delete_conversation(conversation_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"message": "Conversation deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
