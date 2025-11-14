"""
Message API endpoints.
"""

import asyncpg
from typing import List, Annotated
from app.config import logger
from app.services.message import MessageService
from app.services.ai_chat import AIChatService
from app.services.qa_service import QAService
from app.db.database import get_database_pool
from app.auth.dependencies import get_current_active_user
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from app.schemas.user import UserInDB
from app.schemas.message import (
    MessageCreate,
    MessageUpdate,
    MessageEditRequest,
    MessageResponse,
    MessageWithVersions,
    MessageList,
    MessageVersionList,
    MessageRestoreRequest,
    AIPromptRequest,
    AIResponse,
)

router = APIRouter()


async def get_message_service(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> MessageService:
    """Dependency to get message service."""
    return MessageService(db_pool)


async def get_ai_chat_service(
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> AIChatService:
    """Dependency to get AI chat service."""
    # Get QA service from app state
    qa_service = request.app.state.qa_service
    if qa_service is None:
        from app.config import settings

        qa_service = QAService(settings)

    return AIChatService(db_pool, qa_service)


@router.post("/", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    message_data: MessageCreate,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    message_service: MessageService = Depends(get_message_service),
    ai_chat_service: AIChatService = Depends(get_ai_chat_service),
):
    """Create a new message."""
    try:
        message = await message_service.create_message(
            current_user.id, message_data.conversation_id, message_data, ai_chat_service
        )
        return message
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create message",
        )


@router.get("/conversations/{conversation_id}", response_model=MessageList)
async def list_conversation_messages(
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    message_service: MessageService = Depends(get_message_service),
    limit: int = Query(default=50, ge=1, le=100),
    before: int = Query(default=None),
):
    """List messages for a conversation with cursor pagination."""
    try:
        messages = await message_service.list_conversation_messages(
            conversation_id, current_user.id, limit=limit, before=before
        )
        return messages
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to fetch messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch messages",
        )


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: int,
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    message_service: MessageService = Depends(get_message_service),
):
    """Get message by ID."""
    try:
        message = await message_service.get_message_by_id(
            message_id, conversation_id, current_user.id
        )
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
            )
        return message
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch message",
        )


@router.put("/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: int,
    conversation_id: int,
    update_data: MessageEditRequest,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    message_service: MessageService = Depends(get_message_service),
):
    """Update message content."""
    try:
        message = await message_service.update_message(
            message_id, conversation_id, current_user.id, update_data
        )
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
            )
        return message
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update message",
        )


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: int,
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    message_service: MessageService = Depends(get_message_service),
):
    """Soft delete a message."""
    try:
        success = await message_service.delete_message(
            message_id, conversation_id, current_user.id
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete message",
        )


@router.get("/{message_id}/versions", response_model=MessageVersionList)
async def get_message_version_history(
    message_id: int,
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    message_service: MessageService = Depends(get_message_service),
):
    """Get version history for a message."""
    try:
        versions = await message_service.get_message_version_history(
            message_id, conversation_id, current_user.id
        )
        if not versions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
            )
        return versions
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch message versions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch message versions",
        )


@router.get("/{message_id}/versions/full", response_model=MessageWithVersions)
async def get_message_with_versions(
    message_id: int,
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    message_service: MessageService = Depends(get_message_service),
):
    """Get message with its version history."""
    try:
        message = await message_service.get_message_with_versions(
            message_id, conversation_id, current_user.id
        )
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
            )
        return message
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch message with versions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch message with versions",
        )


@router.post("/{message_id}/restore", response_model=MessageResponse)
async def restore_message_to_version(
    message_id: int,
    conversation_id: int,
    restore_request: MessageRestoreRequest,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    message_service: MessageService = Depends(get_message_service),
):
    """Restore message to a previous version."""
    try:
        message = await message_service.restore_message_to_version(
            message_id, conversation_id, current_user.id, restore_request
        )
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
            )
        return message
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restore message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore message",
        )


@router.get("/conversations/{conversation_id}/latest", response_model=MessageResponse)
async def get_latest_message(
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    message_service: MessageService = Depends(get_message_service),
):
    """Get the latest message in a conversation."""
    try:
        message = await message_service.get_latest_message(
            conversation_id, current_user.id
        )
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No messages found"
            )
        return message
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch latest message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch latest message",
        )


@router.get("/conversations/{conversation_id}/count")
async def count_messages_in_conversation(
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    message_service: MessageService = Depends(get_message_service),
):
    """Count messages in a conversation."""
    try:
        count = await message_service.count_messages_in_conversation(
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
        logger.error(f"Failed to count messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to count messages",
        )


@router.post("/ai/generate", response_model=AIResponse)
async def generate_ai_response(
    ai_request: AIPromptRequest,
    http_request: Request,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    ai_chat_service: AIChatService = Depends(get_ai_chat_service),
):
    """Generate AI response for a prompt."""
    try:
        response = await ai_chat_service.generate_ai_response(
            current_user.id, ai_request
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to generate AI response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate AI response",
        )


@router.post("/ai/chat", response_model=List[MessageResponse])
async def create_ai_chat_pair(
    conversation_id: int,
    user_prompt: str,
    http_request: Request,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    ai_chat_service: AIChatService = Depends(get_ai_chat_service),
):
    """Create user message and AI response pair."""
    try:
        user_message, ai_message = await ai_chat_service.create_ai_message_pair(
            current_user.id, conversation_id, user_prompt
        )

        messages = [user_message]
        if ai_message:
            messages.append(ai_message)

        return messages
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create chat pair: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create chat pair",
        )


@router.get("/conversations/{conversation_id}/ai/suggestions")
async def get_ai_health_suggestions(
    conversation_id: int,
    http_request: Request,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    ai_chat_service: AIChatService = Depends(get_ai_chat_service),
):
    """Get AI-powered health suggestions based on conversation history."""
    try:
        suggestions = await ai_chat_service.get_ai_health_suggestions(
            current_user.id, conversation_id
        )
        return {"suggestions": suggestions}
    except Exception as e:
        logger.error(f"Failed to get AI suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get AI suggestions",
        )
