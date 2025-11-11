"""
Message API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List
import logging

from app.auth.dependencies import get_current_active_user
from app.db.database import get_database_pool
from app.schemas.user import UserInDB
from app.schemas.message import (
    MessageCreate,
    MessageUpdate,
    MessageDetail,
    MessageListResponse,
    MessageBranchRequest,
    MessageBranchResponse,
    MessageTreeResponse,
    MessagePathResponse,
    MessageVersionListResponse,
    MessageVersionCompareResponse,
    MessageVersionRollbackRequest,
    MessageVersionRollbackResponse,
    MessageBaseResponse,
)
from app.services.message import MessageService
from app.services.message_version import MessageVersionService
import asyncpg

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_message_service(
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> MessageService:
    """Dependency to get message service."""
    return MessageService(pool)


async def get_version_service(
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> MessageVersionService:
    """Dependency to get message version service."""
    return MessageVersionService(pool)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageDetail,
    status_code=status.HTTP_201_CREATED,
)
async def add_message(
    conversation_id: int,
    message: MessageCreate,
    current_user: UserInDB = Depends(get_current_active_user),
    service: MessageService = Depends(get_message_service),
):
    """
    Add a new message to a conversation.

    - **conversation_id**: ID of the conversation
    - **content**: Message content
    - **parent_message_id**: Optional parent message ID for branching
    """
    try:
        new_message = await service.add_message(
            conversation_id=conversation_id,
            user_id=current_user.id,
            content=message.content,
            role="user",  # Default to user role for manual additions
            content_cleaned=message.content_cleaned,
            answers=message.answers,
            metadata=message.metadata,
            parent_message_id=message.parent_message_id,
        )
        return new_message
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to add message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add message",
        )


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def list_messages(
    conversation_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    order_by: str = Query(
        "created_at", pattern="^(created_at|updated_at)$", description="Sort field"
    ),
    current_user: UserInDB = Depends(get_current_active_user),
    service: MessageService = Depends(get_message_service),
):
    """
    List messages in a conversation with pagination.

    - **conversation_id**: ID of the conversation
    - **page**: Page number (starting from 1)
    - **page_size**: Number of messages per page (max 200)
    - **order_by**: Field to sort by (created_at or updated_at)
    """
    try:
        messages = await service.list_messages(
            conversation_id=conversation_id,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            order_by=order_by,
        )
        return messages
    except Exception as e:
        logger.error(f"Failed to list messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list messages",
        )


@router.get("/messages/{message_id}", response_model=MessageDetail)
async def get_message(
    message_id: int,
    current_user: UserInDB = Depends(get_current_active_user),
    service: MessageService = Depends(get_message_service),
):
    """
    Get a specific message by ID.

    - **message_id**: ID of the message to retrieve
    """
    try:
        message = await service.get_message(message_id, current_user.id)
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
            )
        return message
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get message",
        )


@router.patch("/messages/{message_id}", response_model=MessageDetail)
async def update_message(
    message_id: int,
    update: MessageUpdate,
    current_user: UserInDB = Depends(get_current_active_user),
    service: MessageService = Depends(get_message_service),
):
    """
    Update a message.

    - **message_id**: ID of the message to update
    - **content**: New message content
    - **create_version**: Whether to create a version backup
    """
    try:
        updated_message = await service.update_message(
            message_id=message_id,
            user_id=current_user.id,
            content=update.content,
            create_version=update.create_version,
            content_cleaned=update.content_cleaned,
            answers=update.answers,
            metadata=update.metadata,
        )
        return updated_message
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to update message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update message",
        )


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: int,
    current_user: UserInDB = Depends(get_current_active_user),
    service: MessageService = Depends(get_message_service),
):
    """
    Delete a message (soft delete).

    - **message_id**: ID of the message to delete
    """
    try:
        success = await service.delete_message(message_id, current_user.id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete message",
        )


@router.post("/messages/{message_id}/branch", response_model=MessageDetail)
async def create_message_branch(
    message_id: int,
    branch_request: MessageBranchRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    service: MessageService = Depends(get_message_service),
):
    """
    Create a branch from a message.

    - **message_id**: ID of the parent message
    - **content**: Content for the branched message
    """
    try:
        branched_message = await service.create_branch(
            parent_message_id=message_id,
            user_id=current_user.id,
            role="user",  # Default to user role
            content=branch_request.content,
            content_cleaned=branch_request.content_cleaned,
            answers=branch_request.answers,
            metadata=branch_request.metadata,
        )
        return branched_message
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create message branch",
        )


@router.get("/{conversation_id}/tree", response_model=MessageTreeResponse)
async def get_conversation_tree(
    conversation_id: int,
    current_user: UserInDB = Depends(get_current_active_user),
    service: MessageService = Depends(get_message_service),
):
    """
    Get the complete conversation tree with branching structure.

    - **conversation_id**: ID of the conversation
    """
    try:
        tree = await service.get_conversation_tree(conversation_id, current_user.id)

        # Calculate additional stats
        total_messages = 0
        total_branches = 0
        max_depth = 0

        def count_nodes(node):
            nonlocal total_messages, total_branches, max_depth
            total_messages += 1
            max_depth = max(max_depth, node.level)
            if node.children:
                total_branches += len(node.children)
                for child in node.children:
                    count_nodes(child)

        count_nodes(tree)

        return MessageTreeResponse(
            success=True,
            message="Conversation tree retrieved successfully",
            tree=tree,
            total_messages=total_messages,
            total_branches=total_branches,
            max_depth=max_depth,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get conversation tree",
        )


@router.get("/messages/{message_id}/path", response_model=MessagePathResponse)
async def get_message_path(
    message_id: int,
    current_user: UserInDB = Depends(get_current_active_user),
    service: MessageService = Depends(get_message_service),
):
    """
    Get the path from root to a specific message.

    - **message_id**: ID of the target message
    """
    try:
        path = await service.get_message_path(message_id, current_user.id)
        return path
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get message path",
        )


@router.get("/messages/{message_id}/children", response_model=List[MessageDetail])
async def get_message_children(
    message_id: int,
    current_user: UserInDB = Depends(get_current_active_user),
    service: MessageService = Depends(get_message_service),
):
    """
    Get child messages (branches) of a message.

    - **message_id**: ID of the parent message
    """
    try:
        children = await service.get_message_children(message_id, current_user.id)
        return children
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get message children",
        )


@router.get(
    "/messages/{message_id}/versions", response_model=MessageVersionListResponse
)
async def get_message_versions(
    message_id: int,
    current_user: UserInDB = Depends(get_current_active_user),
    version_service: MessageVersionService = Depends(get_version_service),
):
    """
    Get all versions of a message.

    - **message_id**: ID of the message
    """
    try:
        versions = await version_service.get_versions(message_id, current_user.id)
        return versions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get message versions",
        )


@router.get(
    "/messages/{message_id}/versions/{version_number}", response_model=MessageDetail
)
async def get_message_version(
    message_id: int,
    version_number: int,
    current_user: UserInDB = Depends(get_current_active_user),
    version_service: MessageVersionService = Depends(get_version_service),
):
    """
    Get a specific version of a message.

    - **message_id**: ID of the message
    - **version_number**: Version number to retrieve
    """
    try:
        version = await version_service.get_version(
            message_id, version_number, current_user.id
        )
        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message version not found",
            )
        return version
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get message version",
        )


@router.post(
    "/messages/{message_id}/versions/compare",
    response_model=MessageVersionCompareResponse,
)
async def compare_message_versions(
    message_id: int,
    version1: int = Query(..., description="First version number"),
    version2: int = Query(..., description="Second version number"),
    current_user: UserInDB = Depends(get_current_active_user),
    version_service: MessageVersionService = Depends(get_version_service),
):
    """
    Compare two versions of a message.

    - **message_id**: ID of the message
    - **version1**: First version number
    - **version2**: Second version number
    """
    try:
        comparison = await version_service.compare_versions(
            message_id, version1, version2, current_user.id
        )
        return comparison
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare message versions",
        )


@router.post(
    "/messages/{message_id}/rollback", response_model=MessageVersionRollbackResponse
)
async def rollback_message_version(
    message_id: int,
    rollback_request: MessageVersionRollbackRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    version_service: MessageVersionService = Depends(get_version_service),
):
    """
    Rollback a message to a specific version.

    - **message_id**: ID of the message
    - **version_number**: Version number to rollback to
    - **create_backup_version**: Whether to create a backup of current version
    """
    try:
        rollback_response = await version_service.rollback_to_version(
            message_id=message_id,
            version_number=rollback_request.version_number,
            user_id=current_user.id,
            create_backup_version=rollback_request.create_backup_version,
        )
        return rollback_response
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rollback message version",
        )


@router.post(
    "/messages/{message_id}/versions/cleanup", response_model=MessageBaseResponse
)
async def cleanup_message_versions(
    message_id: int,
    keep_latest: int = Query(
        50, ge=1, le=100, description="Number of latest versions to keep"
    ),
    current_user: UserInDB = Depends(get_current_active_user),
    version_service: MessageVersionService = Depends(get_version_service),
):
    """
    Clean up old versions of a message, keeping only the latest N versions.

    - **message_id**: ID of the message
    - **keep_latest**: Number of latest versions to keep
    """
    try:
        cleaned_count = await version_service.cleanup_old_versions(
            message_id, current_user.id, keep_latest
        )
        return MessageBaseResponse(
            success=True,
            message=f"Cleaned up {cleaned_count} old versions",
            data={"cleaned_count": cleaned_count},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup message versions",
        )
