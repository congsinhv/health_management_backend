"""
Conversation schemas for request/response validation.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.base import BaseResponse


class ConversationCreate(BaseModel):
    """Schema for creating a new conversation."""

    title: Optional[str] = Field(None, max_length=255)
    question: Optional[str] = Field(None, max_length=1000)
    answer: Optional[str] = Field(None, max_length=2000)
    tags: List[str] = Field(default_factory=list, max_length=10)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationUpdate(BaseModel):
    """Schema for updating a conversation."""

    title: Optional[str] = Field(None, max_length=255)
    tags: Optional[List[str]] = Field(None, max_length=10)
    is_pinned: Optional[bool] = None
    metadata: Optional[Dict[str, Any]] = None


class ConversationBase(BaseModel):
    """Base conversation schema."""

    id: int
    user_id: int
    title: Optional[str]
    question: Optional[str]
    answer: Optional[str]
    is_pinned: bool = False
    tags: List[str] = []
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class ConversationListItem(ConversationBase):
    """Conversation item for list view."""

    message_count: int = 0
    last_message_preview: Optional[str] = None
    last_message_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}


class ConversationDetail(ConversationBase):
    """Detailed conversation view with messages."""

    message_count: int = 0
    last_message_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class ConversationListResponse(BaseResponse):
    """Response schema for conversation list."""

    conversations: List[ConversationListItem] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0

    @classmethod
    def create(
        cls,
        conversations: List[ConversationListItem],
        total: int,
        page: int,
        page_size: int,
    ) -> "ConversationListResponse":
        """Create a paginated response."""
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        return cls(
            conversations=conversations,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


class ConversationPinRequest(BaseModel):
    """Schema for pinning/unpinning a conversation."""

    is_pinned: bool = Field(..., description="Whether to pin the conversation")


class ConversationTitleGenerateRequest(BaseModel):
    """Schema for auto-generating conversation title."""

    question: Optional[str] = None
    answer_summary: Optional[str] = None


class ConversationTitleResponse(BaseResponse):
    """Response schema for generated title."""

    title: str = Field(..., description="Generated conversation title")


class ConversationSearchRequest(BaseModel):
    """Schema for searching conversations."""

    query: Optional[str] = Field(None, min_length=1, max_length=200)
    tags: Optional[List[str]] = Field(None, max_length=10)
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    pinned_only: bool = False
    sort_by: str = Field(
        default="updated_at", pattern="^(created_at|updated_at|title|message_count)$"
    )
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# Alias for backward compatibility
ConversationSearchParams = ConversationSearchRequest


class ConversationTagRequest(BaseModel):
    """Schema for adding/removing tags."""

    tags: List[str] = Field(..., min_length=1, max_length=10)


class ConversationTagResponse(BaseResponse):
    """Response schema for tag operations."""

    tags: List[str] = []


class ConversationMetadataUpdate(BaseModel):
    """Schema for updating conversation metadata."""

    metadata: Dict[str, Any] = Field(...)


class ConversationStatsResponse(BaseResponse):
    """Response schema for conversation statistics."""

    total_conversations: int = 0
    pinned_conversations: int = 0
    total_messages: int = 0
    average_messages_per_conversation: float = 0.0
    most_used_tags: List[Dict[str, Any]] = []


class ConversationExportRequest(BaseModel):
    """Schema for exporting conversations."""

    conversation_ids: Optional[List[int]] = None
    include_messages: bool = True
    include_versions: bool = False
    format: str = Field(default="json", pattern="^(json|csv|txt)$")


class ConversationExportResponse(BaseResponse):
    """Response schema for conversation export."""

    download_url: Optional[str] = None
    export_id: str = ...
    status: str = Field(default="processing", pattern="^(processing|completed|failed)$")
    message_count: int = 0


class ConversationImportRequest(BaseModel):
    """Schema for importing conversations."""

    file_data: str = Field(..., description="Base64 encoded file data")
    format: str = Field(default="json", pattern="^(json|csv)$")
    merge_strategy: str = Field(
        default="skip_existing", pattern="^(skip_existing|overwrite|merge)$"
    )


class ConversationImportResponse(BaseResponse):
    """Response schema for conversation import."""

    import_id: str = ...
    status: str = Field(default="processing", pattern="^(processing|completed|failed)$")
    imported_conversations: int = 0
    skipped_conversations: int = 0
    errors: List[str] = []


class ConversationShareRequest(BaseModel):
    """Schema for sharing a conversation."""

    is_public: bool = False
    expires_at: Optional[datetime] = None
    password: Optional[str] = Field(None, min_length=4, max_length=50)


class ConversationShareResponse(BaseResponse):
    """Response schema for conversation sharing."""

    share_token: str = ...
    share_url: str = ...
    expires_at: Optional[datetime] = None
    view_count: int = 0


class ConversationBatchUpdateRequest(BaseModel):
    """Schema for batch updating conversations."""

    conversation_ids: List[int] = Field(..., min_length=1, max_length=50)
    updates: ConversationUpdate = ...


class ConversationBatchResponse(BaseResponse):
    """Response schema for batch operations."""

    updated_count: int = 0
    failed_count: int = 0
    errors: List[Dict[str, Any]] = []


class CursorPaginationParams(BaseModel):
    """Cursor pagination parameters."""

    cursor: Optional[str] = Field(None, description="Base64-encoded cursor")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page")
    direction: str = Field(
        default="forward",
        pattern="^(forward|backward)$",
        description="Pagination direction",
    )


class CursorPaginatedResponse(BaseModel):
    """Cursor paginated response."""

    items: List[Any] = []
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None
    has_more: bool = False
    total_count: Optional[int] = None


class ConversationCursorListResponse(CursorPaginatedResponse, BaseResponse):
    """Cursor paginated conversation list response."""

    items: List[ConversationListItem] = []


class MessageCursorListResponse(CursorPaginatedResponse, BaseResponse):
    """Cursor paginated message list response."""

    items: List[
        Dict[str, Any]
    ] = []  # Changed from MessageDetail to avoid circular import


class ConversationLazyLoadResponse(BaseResponse):
    """Response for lazy loading conversations."""

    conversations: List[ConversationListItem] = []
    next_cursor: Optional[str] = None
    has_more: bool = False
    total_loaded: int = 0


class MessageLazyLoadResponse(BaseResponse):
    """Response for lazy loading messages."""

    messages: List[
        Dict[str, Any]
    ] = []  # Changed from MessageDetail to avoid circular import
    next_cursor: Optional[str] = None
    has_more: bool = False
    total_loaded: int = 0
    conversation_id: int


class ConversationBaseResponse(BaseResponse):
    """
    Basic response wrapper for conversation operations.
    """
