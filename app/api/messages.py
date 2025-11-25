"""
Message API endpoints.
"""

import asyncpg
from typing import List
from typing_extensions import Annotated
from app.config import logger
from app.services.message import MessageService
from app.services.ai_chat import AIChatService
from app.services.qa_service import QAService
from app.db.database import get_database_pool
from app.auth.dependencies import get_current_active_user
from fastapi import APIRouter, Depends, status, Query, Request
from app.schemas.user import UserInDB
from app.core.error_context import ErrorContext
from app.exceptions import (
    ResourceNotFoundException,
)
from app.schemas.message import (
    MessageCreate,
    MessageEditRequest,
    MessageResponse,
    MessageWithVersions,
    MessageList,
    MessageVersionList,
    MessageRestoreRequest,
)

router = APIRouter()


async def create_message_service(
    request: Request,
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> MessageService:
    """Dependency to get message service."""
    # Get cache service from app state
    cache_service = getattr(request.app.state, "cache_service", None)
    return MessageService(db_pool, cache_service=cache_service)


async def create_ai_chat_service(
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
    request: Request,
    message_service: MessageService = Depends(create_message_service),
    ai_chat_service: AIChatService = Depends(create_ai_chat_service),
):
    """Create a new message."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "create_message")
    ErrorContext.add_context("operation", "message_creation")
    ErrorContext.add_context("conversation_id", message_data.conversation_id)
    ErrorContext.add_context("content_type", message_data.content_type)

    with ErrorContext(
        "create_message",
        {
            "user_id": current_user.id,
            "conversation_id": message_data.conversation_id,
            "content_length": len(message_data.content),
            "content_type": message_data.content_type,
        },
    ):
        message = await message_service.create_message(
            current_user.id, message_data.conversation_id, message_data, ai_chat_service
        )
        ErrorContext.add_context("message_id", message.id)
        return message


@router.get("/conversations/{conversation_id}", response_model=MessageList)
async def list_conversation_messages(
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    message_service: MessageService = Depends(create_message_service),
    limit: int = Query(default=50, ge=1, le=100),
    before: int = Query(default=None),
):
    """List messages for a conversation with cursor pagination."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "list_conversation_messages")
    ErrorContext.add_context("operation", "message_list")
    ErrorContext.add_context("conversation_id", conversation_id)
    ErrorContext.add_context("limit", limit)
    ErrorContext.add_context("before", before)

    with ErrorContext(
        "list_conversation_messages",
        {
            "user_id": current_user.id,
            "conversation_id": conversation_id,
            "limit": limit,
            "before": before,
        },
    ):
        messages = await message_service.list_conversation_messages(
            conversation_id, current_user.id, limit=limit, before=before
        )
        ErrorContext.add_context(
            "message_count", len(messages.messages) if messages else 0
        )
        return messages


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: int,
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    message_service: MessageService = Depends(create_message_service),
):
    """Get message by ID."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "get_message")
    ErrorContext.add_context("operation", "message_retrieval")
    ErrorContext.add_context("message_id", message_id)
    ErrorContext.add_context("conversation_id", conversation_id)

    with ErrorContext(
        "get_message",
        {
            "user_id": current_user.id,
            "message_id": message_id,
            "conversation_id": conversation_id,
        },
    ):
        message = await message_service.get_message_by_id(
            message_id, conversation_id, current_user.id
        )
        if not message:
            raise ResourceNotFoundException(
                "Message not found",
                details={
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "user_id": current_user.id,
                },
            )
        return message


@router.put("/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: int,
    conversation_id: int,
    update_data: MessageEditRequest,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    message_service: MessageService = Depends(create_message_service),
):
    """Update message content."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "update_message")
    ErrorContext.add_context("operation", "message_update")
    ErrorContext.add_context("message_id", message_id)
    ErrorContext.add_context("conversation_id", conversation_id)
    ErrorContext.add_context("content_length", len(update_data.content))

    with ErrorContext(
        "update_message",
        {
            "user_id": current_user.id,
            "message_id": message_id,
            "conversation_id": conversation_id,
            "content_length": len(update_data.content),
        },
    ):
        message = await message_service.update_message(
            message_id, conversation_id, current_user.id, update_data
        )
        if not message:
            raise ResourceNotFoundException(
                "Message not found",
                details={
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "user_id": current_user.id,
                },
            )
        return message


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: int,
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    message_service: MessageService = Depends(create_message_service),
):
    """Soft delete a message."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "delete_message")
    ErrorContext.add_context("operation", "message_deletion")
    ErrorContext.add_context("message_id", message_id)
    ErrorContext.add_context("conversation_id", conversation_id)

    with ErrorContext(
        "delete_message",
        {
            "user_id": current_user.id,
            "message_id": message_id,
            "conversation_id": conversation_id,
        },
    ):
        success = await message_service.delete_message(
            message_id, conversation_id, current_user.id
        )
        if not success:
            raise ResourceNotFoundException(
                "Message not found",
                details={
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "user_id": current_user.id,
                },
            )


"""
Message API endpoints - Part 2.
"""


@router.get("/{message_id}/versions", response_model=MessageVersionList)
async def get_message_version_history(
    message_id: int,
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    message_service: MessageService = Depends(create_message_service),
):
    """Get version history for a message."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "get_message_version_history")
    ErrorContext.add_context("operation", "message_version_history")
    ErrorContext.add_context("message_id", message_id)
    ErrorContext.add_context("conversation_id", conversation_id)

    with ErrorContext(
        "get_message_version_history",
        {
            "user_id": current_user.id,
            "message_id": message_id,
            "conversation_id": conversation_id,
        },
    ):
        versions = await message_service.get_message_version_history(
            message_id, conversation_id, current_user.id
        )
        if not versions:
            raise ResourceNotFoundException(
                "Message not found",
                details={
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "user_id": current_user.id,
                },
            )
        ErrorContext.add_context(
            "version_count", len(versions.versions) if versions else 0
        )
        return versions


@router.get("/{message_id}/versions/full", response_model=MessageWithVersions)
async def get_message_with_versions(
    message_id: int,
    conversation_id: int,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    message_service: MessageService = Depends(create_message_service),
):
    """Get message with its version history."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "get_message_with_versions")
    ErrorContext.add_context("operation", "message_with_versions")
    ErrorContext.add_context("message_id", message_id)
    ErrorContext.add_context("conversation_id", conversation_id)

    with ErrorContext(
        "get_message_with_versions",
        {
            "user_id": current_user.id,
            "message_id": message_id,
            "conversation_id": conversation_id,
        },
    ):
        message = await message_service.get_message_with_versions(
            message_id, conversation_id, current_user.id
        )
        if not message:
            raise ResourceNotFoundException(
                "Message not found",
                details={
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "user_id": current_user.id,
                },
            )
        ErrorContext.add_context(
            "version_count", len(message.versions) if message.versions else 0
        )
        return message


@router.post("/{message_id}/restore", response_model=MessageResponse)
async def restore_message_to_version(
    message_id: int,
    conversation_id: int,
    restore_request: MessageRestoreRequest,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    message_service: MessageService = Depends(create_message_service),
):
    """Restore message to a previous version."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "restore_message_to_version")
    ErrorContext.add_context("operation", "message_restore")
    ErrorContext.add_context("message_id", message_id)
    ErrorContext.add_context("conversation_id", conversation_id)
    ErrorContext.add_context("target_version_id", restore_request.version_id)

    with ErrorContext(
        "restore_message_to_version",
        {
            "user_id": current_user.id,
            "message_id": message_id,
            "conversation_id": conversation_id,
            "target_version_id": restore_request.version_id,
        },
    ):
        message = await message_service.restore_message_to_version(
            message_id, conversation_id, current_user.id, restore_request
        )
        if not message:
            raise ResourceNotFoundException(
                "Message not found",
                details={
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "user_id": current_user.id,
                },
            )
        return message
