"""
Conversation API endpoints.
"""

import asyncpg
from typing import List
from typing_extensions import Annotated
from app.config import logger
from app.services.conversation import ConversationService
from app.db.database import get_database_pool
from app.auth.dependencies import get_current_active_user
from fastapi import APIRouter, Depends, status, Query, Request
from app.schemas.user import UserInDB
from app.core.error_context import ErrorContext
from app.core.shared.exceptions import (
    ResourceNotFoundException,
    ValidationException,
    DatabaseException,
    BusinessLogicException,
)
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationWithMessages,
    ConversationList,
    ConversationPinRequest,
)

router = APIRouter()


async def create_conversation_service(
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> ConversationService:
    """Dependency to get conversation service."""
    # Get cache service from app state
    cache_service = getattr(request.app.state, "cache_service", None)
    return ConversationService(db_pool, cache_service=cache_service)


@router.post(
    "/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED
)
async def create_conversation(
    conversation_data: ConversationCreate,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    conversation_service: ConversationService = Depends(create_conversation_service),
):
    """Create a new conversation."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "create_conversation")
    ErrorContext.add_context("operation", "conversation_creation")

    with ErrorContext(
        "create_conversation",
        {
            "user_id": current_user.id,
            "title": conversation_data.title,
            "metadata": conversation_data.metadata,
        },
    ):
        conversation = await conversation_service.create_conversation(
            current_user.id, conversation_data
        )
        ErrorContext.add_context("conversation_id", conversation.id)
        return conversation


@router.get("/", response_model=ConversationList)
async def list_conversations(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    conversation_service: ConversationService = Depends(create_conversation_service),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_message_count: bool = Query(default=True),
):
    """List user's conversations with pagination."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "list_conversations")
    ErrorContext.add_context("operation", "conversation_list")
    ErrorContext.add_context("limit", limit)
    ErrorContext.add_context("offset", offset)

    with ErrorContext(
        "list_conversations",
        {
            "user_id": current_user.id,
            "limit": limit,
            "offset": offset,
            "include_message_count": include_message_count,
        },
    ):
        conversations = await conversation_service.list_user_conversations(
            current_user.id,
            limit=limit,
            offset=offset,
            include_message_count=include_message_count,
        )
        ErrorContext.add_context(
            "conversation_count",
            len(conversations.conversations) if conversations else 0,
        )
        return conversations


@router.get("/pinned", response_model=List[ConversationResponse])
async def get_pinned_conversations(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    conversation_service: ConversationService = Depends(create_conversation_service),
    limit: int = Query(default=10, ge=1, le=50),
):
    """Get user's pinned conversations."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "get_pinned_conversations")
    ErrorContext.add_context("operation", "pinned_conversations_list")
    ErrorContext.add_context("limit", limit)

    with ErrorContext(
        "get_pinned_conversations", {"user_id": current_user.id, "limit": limit}
    ):
        conversations = await conversation_service.get_pinned_conversations(
            current_user.id, limit=limit
        )
        ErrorContext.add_context("pinned_count", len(conversations))
        return conversations


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    conversation_service: ConversationService = Depends(create_conversation_service),
):
    """Get conversation by ID."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "get_conversation")
    ErrorContext.add_context("operation", "conversation_retrieval")
    ErrorContext.add_context("target_conversation_id", conversation_id)

    with ErrorContext(
        "get_conversation",
        {"user_id": current_user.id, "target_conversation_id": conversation_id},
    ):
        conversation = await conversation_service.get_conversation_by_id(
            conversation_id, current_user.id
        )
        if not conversation:
            raise ResourceNotFoundException(
                "Conversation not found",
                details={
                    "conversation_id": conversation_id,
                    "user_id": current_user.id,
                },
            )
        return conversation


@router.get("/{conversation_id}/messages", response_model=ConversationWithMessages)
async def get_conversation_with_messages(
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    conversation_service: ConversationService = Depends(create_conversation_service),
    message_limit: int = Query(default=50, ge=1, le=100),
):
    """Get conversation with its messages."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "get_conversation_with_messages")
    ErrorContext.add_context("operation", "conversation_with_messages")
    ErrorContext.add_context("target_conversation_id", conversation_id)
    ErrorContext.add_context("message_limit", message_limit)

    with ErrorContext(
        "get_conversation_with_messages",
        {
            "user_id": current_user.id,
            "target_conversation_id": conversation_id,
            "message_limit": message_limit,
        },
    ):
        conversation = await conversation_service.get_conversation_with_messages(
            conversation_id, current_user.id, message_limit=message_limit
        )
        if not conversation:
            raise ResourceNotFoundException(
                "Conversation not found",
                details={
                    "conversation_id": conversation_id,
                    "user_id": current_user.id,
                },
            )
        ErrorContext.add_context(
            "message_count", len(conversation.messages) if conversation.messages else 0
        )
        return conversation


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: int,
    update_data: ConversationUpdate,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    conversation_service: ConversationService = Depends(create_conversation_service),
):
    """Update conversation information."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "update_conversation")
    ErrorContext.add_context("operation", "conversation_update")
    ErrorContext.add_context("target_conversation_id", conversation_id)

    with ErrorContext(
        "update_conversation",
        {
            "user_id": current_user.id,
            "target_conversation_id": conversation_id,
            "update_fields": update_data.model_dump(exclude_unset=True)
            if hasattr(update_data, "model_dump")
            else {},
        },
    ):
        conversation = await conversation_service.update_conversation(
            conversation_id, current_user.id, update_data
        )
        if not conversation:
            raise ResourceNotFoundException(
                "Conversation not found",
                details={
                    "conversation_id": conversation_id,
                    "user_id": current_user.id,
                },
            )
        return conversation


@router.patch("/{conversation_id}/pin", response_model=ConversationResponse)
async def pin_conversation(
    conversation_id: int,
    pin_request: ConversationPinRequest,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    conversation_service: ConversationService = Depends(create_conversation_service),
):
    """Pin or unpin a conversation."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "pin_conversation")
    ErrorContext.add_context("operation", "conversation_pin_update")
    ErrorContext.add_context("target_conversation_id", conversation_id)
    ErrorContext.add_context("is_pinned", pin_request.is_pinned)

    with ErrorContext(
        "pin_conversation",
        {
            "user_id": current_user.id,
            "target_conversation_id": conversation_id,
            "is_pinned": pin_request.is_pinned,
        },
    ):
        conversation = await conversation_service.pin_conversation(
            conversation_id, current_user.id, pin_request
        )
        if not conversation:
            raise ResourceNotFoundException(
                "Conversation not found",
                details={
                    "conversation_id": conversation_id,
                    "user_id": current_user.id,
                },
            )
        return conversation


@router.put("/{conversation_id}/title", response_model=ConversationResponse)
async def update_conversation_title(
    conversation_id: int,
    title: str,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    conversation_service: ConversationService = Depends(create_conversation_service),
):
    """Update conversation title."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "update_conversation_title")
    ErrorContext.add_context("operation", "conversation_title_update")
    ErrorContext.add_context("target_conversation_id", conversation_id)
    ErrorContext.add_context("new_title", title)

    with ErrorContext(
        "update_conversation_title",
        {
            "user_id": current_user.id,
            "target_conversation_id": conversation_id,
            "new_title": title,
            "title_length": len(title),
        },
    ):
        conversation = await conversation_service.update_conversation_title(
            conversation_id, current_user.id, title
        )
        if not conversation:
            raise ResourceNotFoundException(
                "Conversation not found",
                details={
                    "conversation_id": conversation_id,
                    "user_id": current_user.id,
                },
            )
        return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    conversation_service: ConversationService = Depends(create_conversation_service),
):
    """Soft delete a conversation."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "delete_conversation")
    ErrorContext.add_context("operation", "conversation_deletion")
    ErrorContext.add_context("target_conversation_id", conversation_id)

    with ErrorContext(
        "delete_conversation",
        {"user_id": current_user.id, "target_conversation_id": conversation_id},
    ):
        success = await conversation_service.delete_conversation(
            conversation_id, current_user.id
        )
        if not success:
            raise ResourceNotFoundException(
                "Conversation not found",
                details={
                    "conversation_id": conversation_id,
                    "user_id": current_user.id,
                },
            )


@router.get("/{conversation_id}/message-count")
async def get_conversation_message_count(
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    conversation_service: ConversationService = Depends(create_conversation_service),
):
    """Get message count for a conversation."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "get_conversation_message_count")
    ErrorContext.add_context("operation", "conversation_message_count")
    ErrorContext.add_context("target_conversation_id", conversation_id)

    with ErrorContext(
        "get_conversation_message_count",
        {"user_id": current_user.id, "target_conversation_id": conversation_id},
    ):
        count = await conversation_service.get_conversation_message_count(
            conversation_id, current_user.id
        )
        if count is None:
            raise ResourceNotFoundException(
                "Conversation not found",
                details={
                    "conversation_id": conversation_id,
                    "user_id": current_user.id,
                },
            )
        ErrorContext.add_context("message_count", count)
        return {"message_count": count}
