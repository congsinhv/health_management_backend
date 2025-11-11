"""
Q&A API endpoints.
"""

import logging
from typing import Dict, List, Optional

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Query, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_active_user
from app.schemas.user import UserInDB
from app.schemas.message import MessageDetail
from app.schemas.conversation import ConversationDetail
from app.db.database import get_database_pool
from app.services.conversation import ConversationService
from app.services.message import MessageService
import asyncpg

logger = logging.getLogger(__name__)

router = APIRouter()


class QuestionRequest(BaseModel):
    """Request model for asking questions."""

    question: str = Field(
        ..., min_length=1, max_length=500, description="User question"
    )
    threshold: float = Field(
        default=0.55, ge=0.0, le=1.0, description="Similarity threshold"
    )
    top_k: int = Field(default=7, ge=1, le=20, description="Number of top results")
    conversation_id: Optional[int] = Field(
        None, description="Continue existing conversation"
    )
    create_conversation: bool = Field(
        True, description="Create new conversation if none provided"
    )
    title: Optional[str] = Field(
        None, max_length=255, description="Custom title for new conversation"
    )


class QuestionResponse(BaseModel):
    """Response model for question answers."""

    question: str
    answers: Dict[str, List[str]]
    summary: str
    conversation_id: Optional[int] = None
    conversation: Optional[ConversationDetail] = None
    user_message: Optional[MessageDetail] = None
    assistant_message: Optional[MessageDetail] = None
    title_generated: bool = False


async def get_conversation_service(
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> ConversationService:
    """Dependency to get conversation service."""
    return ConversationService(pool)


async def get_message_service(
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> MessageService:
    """Dependency to get message service."""
    return MessageService(pool)


@router.post("/ask", response_model=QuestionResponse, status_code=status.HTTP_200_OK)
async def ask_question(
    request: Request,
    question_data: QuestionRequest,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    conversation_service: ConversationService = Depends(get_conversation_service),
    message_service: MessageService = Depends(get_message_service),
):
    """
    Ask a health-related question and get answers.

    Requires authentication. Users must be logged in to ask questions.

    - **question**: The question to ask (1-500 characters)
    - **threshold**: Minimum similarity score (0.0-1.0)
    - **top_k**: Maximum number of results to return (1-20)
    - **conversation_id**: Continue existing conversation (optional)
    - **create_conversation**: Create new conversation if none provided
    - **title**: Custom title for new conversation (optional)

    Returns:
        QuestionResponse with answers grouped by field, AI summary, and conversation info
    """
    try:
        # Get QA service from app state
        qa_service = request.app.state.qa_service

        if qa_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Q&A service is not available",
            )

        # Initialize services with QA service
        conversation_service.qa_service = qa_service
        message_service.qa_service = qa_service

        conversation_id = question_data.conversation_id
        conversation = None
        title_generated = False

        # Create new conversation if needed
        if not conversation_id and question_data.create_conversation:
            conversation = await conversation_service.create_conversation(
                user_id=current_user.id,
                title=question_data.title,
                question=question_data.question,
                first_message=question_data.question,
            )
            conversation_id = conversation.id

        # Verify conversation exists and user has access
        elif conversation_id:
            conversation = await conversation_service.get_conversation(
                conversation_id, current_user.id
            )
            if not conversation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found",
                )

        # Process question with QA service
        result = qa_service.ask_question(
            user_question=question_data.question,
            threshold=question_data.threshold,
            top_k=question_data.top_k,
        )

        # Save messages to conversation if we have one
        user_message = None
        assistant_message = None

        if conversation_id:
            # Process user message and generate assistant response
            (
                user_message,
                assistant_message,
            ) = await message_service.process_user_message(
                conversation_id=conversation_id,
                user_id=current_user.id,
                content=question_data.question,
            )

            # Auto-generate title if this is a new conversation without title
            if conversation and not conversation.title and not question_data.title:
                try:
                    generated_title = await conversation_service.auto_generate_title(
                        conversation_id, current_user.id
                    )
                    title_generated = True
                    # Refresh conversation to get updated title
                    conversation = await conversation_service.get_conversation(
                        conversation_id, current_user.id
                    )
                except Exception as e:
                    logger.warning(f"Failed to auto-generate title: {e}")

        # Build response
        response_data = {
            "question": result["question"],
            "answers": result["answers"],
            "summary": result["summary"],
            "conversation_id": conversation_id,
            "conversation": conversation,
            "user_message": user_message,
            "assistant_message": assistant_message,
            "title_generated": title_generated,
        }

        return QuestionResponse(**response_data)

    except ValueError as e:
        logger.warning(f"Invalid question from user {current_user.email}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error processing question: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/health", status_code=status.HTTP_200_OK)
async def qa_health_check(request: Request):
    """
    Check Q&A service health status.

    Public endpoint - no authentication required.

    Returns:
        Status information about the Q&A service
    """
    qa_service = request.app.state.qa_service

    if qa_service is None:
        return {
            "status": "unavailable",
            "message": "Q&A service is not initialized",
        }

    return {
        "status": "ok",
        "message": "Q&A service is running",
        "model_loaded": qa_service.model is not None,
        "data_loaded": qa_service.df is not None and len(qa_service.df) > 0,
    }
