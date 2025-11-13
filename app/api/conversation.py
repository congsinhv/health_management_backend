"""
Conversation API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List, Dict, Any

from app.auth.dependencies import get_current_active_user
from app.db.database import get_database_pool
from app.schemas.user import UserInDB
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationDetail,
    ConversationListResponse,
    ConversationPinRequest,
    ConversationTitleResponse,
    ConversationSearchParams,
    ConversationTagRequest,
    ConversationTagResponse,
    ConversationStatsResponse,
    ConversationBaseResponse,
)
from app.schemas.search import ConversationSearchResponse
from app.services.conversation import ConversationService
from app.services.message import MessageService
from app.services.message_version import MessageVersionService
import asyncpg

router = APIRouter()


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


async def get_version_service(
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> MessageVersionService:
    """Dependency to get message version service."""
    return MessageVersionService(pool)


@router.post(
    "/", response_model=ConversationDetail, status_code=status.HTTP_201_CREATED
)
async def create_conversation(
    conversation: ConversationCreate,
    current_user: UserInDB = Depends(get_current_active_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    Create a new conversation.

    - **title**: Optional custom title for the conversation
    - **question**: Initial question (optional)
    - **tags**: List of tags for categorization
    - **metadata**: Additional metadata
    """
    try:
        new_conversation = await service.create_conversation(
            user_id=current_user.id,
            title=conversation.title,
            question=conversation.question,
            tags=conversation.tags,
            metadata=conversation.metadata,
        )
        return new_conversation
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create conversation",
        )


@router.get("/", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    include_pinned: bool = Query(True, description="Include pinned conversations"),
    sort_by: str = Query(
        "updated_at",
        pattern="^(created_at|updated_at|title|message_count)$",
        description="Sort field",
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    current_user: UserInDB = Depends(get_current_active_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    List user conversations with pagination.

    - **page**: Page number (starting from 1)
    - **page_size**: Number of conversations per page (max 100)
    - **include_pinned**: Whether to include pinned conversations
    - **sort_by**: Field to sort by
    - **sort_order**: Sort order (asc or desc)
    """
    try:
        conversations = await service.list_conversations(
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            include_pinned=include_pinned,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return conversations
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list conversations",
        )


@router.get("/search", response_model=ConversationSearchResponse)
async def search_conversations(
    query: str = Query(..., min_length=1, max_length=200, description="Search query"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    date_from: Optional[str] = Query(
        None, description="Filter by date from (ISO format)"
    ),
    date_to: Optional[str] = Query(None, description="Filter by date to (ISO format)"),
    pinned_only: bool = Query(False, description="Show only pinned conversations"),
    sort_by: str = Query(
        "relevance",
        pattern="^(relevance|created_at|updated_at|title)$",
        description="Sort field",
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: UserInDB = Depends(get_current_active_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    Search conversations.

    - **query**: Search query text
    - **tags**: Filter by specific tags
    - **date_from**: Filter conversations from this date
    - **date_to**: Filter conversations to this date
    - **pinned_only**: Show only pinned conversations
    - **sort_by**: Field to sort results by
    - **sort_order**: Sort order (asc or desc)
    - **page**: Page number
    - **page_size**: Items per page
    """
    try:
        # Parse date filters
        from datetime import datetime

        date_from_obj = None
        date_to_obj = None

        if date_from:
            try:
                date_from_obj = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date_from format. Use ISO format.",
                )

        if date_to:
            try:
                date_to_obj = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date_to format. Use ISO format.",
                )

        search_params = ConversationSearchParams(
            query=query,
            tags=tags,
            date_from=date_from_obj,
            date_to=date_to_obj,
            pinned_only=pinned_only,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )

        results = await service.search_conversations(current_user.id, search_params)
        from fastapi.responses import JSONResponse

        return JSONResponse(content=results)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search conversations",
        )


@router.get("/search/suggestions", response_model=List[str])
async def get_search_suggestions(
    query: str = Query(
        ..., min_length=1, max_length=50, description="Search query for suggestions"
    ),
    limit: int = Query(5, ge=1, le=20, description="Number of suggestions to return"),
    current_user: UserInDB = Depends(get_current_active_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    Get search suggestions for autocomplete.

    - **query**: Partial search query
    - **limit**: Number of suggestions to return
    """
    try:
        suggestions = await service.get_search_suggestions(
            current_user.id, query, limit
        )
        return suggestions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get search suggestions",
        )


@router.get("/search/popular", response_model=List[Dict[str, Any]])
async def get_popular_search_terms(
    limit: int = Query(
        10, ge=1, le=50, description="Number of popular terms to return"
    ),
    current_user: UserInDB = Depends(get_current_active_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    Get popular search terms for the user.

    - **limit**: Number of popular terms to return
    """
    try:
        popular_terms = await service.get_popular_search_terms(current_user.id, limit)
        return popular_terms
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get popular search terms",
        )


@router.get("/tags", response_model=List[str])
async def get_user_tags(
    current_user: UserInDB = Depends(get_current_active_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    Get all tags used by the user.
    """
    try:
        tags = await service.get_user_tags(current_user.id)
        return tags
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user tags",
        )


@router.post("/search/index/refresh", response_model=ConversationBaseResponse)
async def refresh_search_index(
    current_user: UserInDB = Depends(get_current_active_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    Refresh the search index (admin operation).

    This endpoint refreshes the materialized view used for search.
    """
    try:
        # In a real application, you might want to check if user is admin
        # For now, we'll allow any authenticated user
        await service.conversation_repo.refresh_search_index()
        return ConversationBaseResponse(
            success=True, message="Search index refreshed successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh search index",
        )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: int,
    current_user: UserInDB = Depends(get_current_active_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    Get a specific conversation by ID.

    - **conversation_id**: ID of the conversation to retrieve
    """
    try:
        conversation = await service.get_conversation(conversation_id, current_user.id)
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
            detail="Failed to get conversation",
        )


@router.patch("/{conversation_id}", response_model=ConversationDetail)
async def update_conversation(
    conversation_id: int,
    updates: ConversationUpdate,
    current_user: UserInDB = Depends(get_current_active_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    Update a conversation.

    - **conversation_id**: ID of the conversation to update
    - **title**: New title (optional)
    - **tags**: New list of tags (optional)
    - **is_pinned**: Pin/unpin the conversation (optional)
    - **metadata**: Updated metadata (optional)
    """
    try:
        updated_conversation = await service.update_conversation(
            conversation_id, current_user.id, **updates.model_dump(exclude_unset=True)
        )
        if not updated_conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )
        return updated_conversation
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update conversation",
        )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    current_user: UserInDB = Depends(get_current_active_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    Delete a conversation (soft delete).

    - **conversation_id**: ID of the conversation to delete
    """
    try:
        success = await service.delete_conversation(conversation_id, current_user.id)
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


@router.post("/{conversation_id}/pin", response_model=ConversationDetail)
async def pin_conversation(
    conversation_id: int,
    pin_request: ConversationPinRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    Pin or unpin a conversation.

    - **conversation_id**: ID of the conversation to pin/unpin
    - **is_pinned**: Whether to pin the conversation
    """
    try:
        success = await service.pin_conversation(
            conversation_id, current_user.id, pin_request.is_pinned
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )

        # Return updated conversation
        conversation = await service.get_conversation(conversation_id, current_user.id)
        return conversation
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pin conversation",
        )


@router.post(
    "/{conversation_id}/title/auto-generate", response_model=ConversationTitleResponse
)
async def auto_generate_title(
    conversation_id: int,
    current_user: UserInDB = Depends(get_current_active_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    Auto-generate a title for a conversation based on its content.

    - **conversation_id**: ID of the conversation to generate title for
    """
    try:
        title = await service.auto_generate_title(conversation_id, current_user.id)
        return ConversationTitleResponse(
            success=True, message="Title generated successfully", title=title
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate title",
        )


@router.post("/{conversation_id}/tags", response_model=ConversationTagResponse)
async def add_tags(
    conversation_id: int,
    tag_request: ConversationTagRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    Add tags to a conversation.

    - **conversation_id**: ID of the conversation
    - **tags**: List of tags to add
    """
    try:
        # Get current conversation to merge with existing tags
        conversation = await service.get_conversation(conversation_id, current_user.id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )

        # Merge existing tags with new tags
        existing_tags = set(conversation.tags)
        new_tags = set(tag_request.tags)
        merged_tags = list(existing_tags.union(new_tags))

        updated_conversation = await service.update_tags(
            conversation_id, current_user.id, merged_tags
        )

        if not updated_conversation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update tags"
            )

        return ConversationTagResponse(
            success=True,
            message="Tags added successfully",
            tags=updated_conversation.tags,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add tags",
        )


@router.delete("/{conversation_id}/tags", response_model=ConversationTagResponse)
async def remove_tags(
    conversation_id: int,
    tag_request: ConversationTagRequest,
    current_user: UserInDB = Depends(get_current_active_user),
    service: ConversationService = Depends(get_conversation_service),
):
    """
    Remove tags from a conversation.

    - **conversation_id**: ID of the conversation
    - **tags**: List of tags to remove
    """
    try:
        # Get current conversation
        conversation = await service.get_conversation(conversation_id, current_user.id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )

        # Remove specified tags
        existing_tags = set(conversation.tags)
        tags_to_remove = set(tag_request.tags)
        remaining_tags = list(existing_tags - tags_to_remove)

        updated_conversation = await service.update_tags(
            conversation_id, current_user.id, remaining_tags
        )

        if not updated_conversation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to update tags"
            )

        return ConversationTagResponse(
            success=True,
            message="Tags removed successfully",
            tags=updated_conversation.tags,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove tags",
        )
