"""
Conversation API endpoints.
"""

import asyncpg
from typing import List, Annotated
from app.config import logger
from app.services.conversation import ConversationService
from app.db.database import get_database_pool
from app.auth.dependencies import get_current_active_user
from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.schemas.user import UserInDB
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationWithMessages,
    ConversationList,
    ConversationPinRequest,
)

router = APIRouter()


async def get_conversation_service(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ConversationService:
    """Dependency to get conversation service."""
    return ConversationService(db_pool)


@router.post(
    "/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED
)
async def create_conversation(
    conversation_data: ConversationCreate,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """Create a new conversation."""
    try:
        conversation = await conversation_service.create_conversation(
            current_user.id, conversation_data
        )
        return conversation
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create conversation",
        )


@router.get("/", response_model=ConversationList)
async def list_conversations(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    conversation_service: ConversationService = Depends(get_conversation_service),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_message_count: bool = Query(default=True),
):
    """List user's conversations with pagination."""
    try:
        conversations = await conversation_service.list_user_conversations(
            current_user.id,
            limit=limit,
            offset=offset,
            include_message_count=include_message_count,
        )
        return conversations
    except Exception as e:
        logger.error(f"Failed to fetch conversations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch conversations",
        )


@router.get("/pinned", response_model=List[ConversationResponse])
async def get_pinned_conversations(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    conversation_service: ConversationService = Depends(get_conversation_service),
    limit: int = Query(default=10, ge=1, le=50),
):
    """Get user's pinned conversations."""
    try:
        conversations = await conversation_service.get_pinned_conversations(
            current_user.id, limit=limit
        )
        return conversations
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch pinned conversations",
        )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """Get conversation by ID."""
    try:
        conversation = await conversation_service.get_conversation_by_id(
            conversation_id, current_user.id
        )
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch conversation",
        )


@router.get("/{conversation_id}/messages", response_model=ConversationWithMessages)
async def get_conversation_with_messages(
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    conversation_service: ConversationService = Depends(get_conversation_service),
    message_limit: int = Query(default=50, ge=1, le=100),
):
    """Get conversation with its messages."""
    try:
        conversation = await conversation_service.get_conversation_with_messages(
            conversation_id, current_user.id, message_limit=message_limit
        )
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch conversation with messages",
        )


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: int,
    update_data: ConversationUpdate,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """Update conversation information."""
    try:
        conversation = await conversation_service.update_conversation(
            conversation_id, current_user.id, update_data
        )
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )
        return conversation
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update conversation",
        )


@router.patch("/{conversation_id}/pin", response_model=ConversationResponse)
async def pin_conversation(
    conversation_id: int,
    pin_request: ConversationPinRequest,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """Pin or unpin a conversation."""
    try:
        conversation = await conversation_service.pin_conversation(
            conversation_id, current_user.id, pin_request
        )
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pin conversation",
        )


@router.put("/{conversation_id}/title", response_model=ConversationResponse)
async def update_conversation_title(
    conversation_id: int,
    title: str,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """Update conversation title."""
    try:
        conversation = await conversation_service.update_conversation_title(
            conversation_id, current_user.id, title
        )
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )
        return conversation
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update conversation title",
        )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """Soft delete a conversation."""
    try:
        success = await conversation_service.delete_conversation(
            conversation_id, current_user.id
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation",
        )


@router.get("/{conversation_id}/message-count")
async def get_conversation_message_count(
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    conversation_service: ConversationService = Depends(get_conversation_service),
):
    """Get message count for a conversation."""
    try:
        count = await conversation_service.get_conversation_message_count(
            conversation_id, current_user.id
        )
        if count is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )
        return {"message_count": count}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get message count",
        )
