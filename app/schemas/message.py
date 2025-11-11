"""
Message schemas for request/response validation.
"""

from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.base import BaseResponse


class MessageCreate(BaseModel):
    """Schema for creating a new message."""

    content: str = Field(..., min_length=1, max_length=5000)
    content_cleaned: Optional[str] = Field(None, max_length=5000)
    answers: Optional[Dict[str, List[str]]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    parent_message_id: Optional[int] = None


class MessageUpdate(BaseModel):
    """Schema for updating a message."""

    content: str = Field(..., min_length=1, max_length=5000)
    content_cleaned: Optional[str] = Field(None, max_length=5000)
    answers: Optional[Dict[str, List[str]]] = None
    metadata: Optional[Dict[str, Any]] = None
    create_version: bool = Field(
        default=True, description="Create a version when updating"
    )


class MessageBase(BaseModel):
    """Base message schema."""

    id: int
    conversation_id: int
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    content_cleaned: Optional[str]
    answers: Optional[Dict[str, Any]]
    parent_message_id: Optional[int]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class MessageDetail(MessageBase):
    """Detailed message view."""

    version_count: int = 0
    child_count: int = 0
    metadata: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class MessageVersionDetail(BaseModel):
    """Message version detail."""

    id: int
    message_id: int
    version_number: int
    content: str
    content_cleaned: Optional[str]
    answers: Optional[Dict[str, List[str]]]
    metadata: Dict[str, Any] = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageTreeNode(MessageDetail):
    """Message tree node for branching conversations."""

    children: List["MessageTreeNode"] = []
    level: int = 0
    is_leaf: bool = True

    model_config = ConfigDict(from_attributes=True)


# Forward reference resolution
MessageTreeNode.model_rebuild()


class MessageListResponse(BaseResponse):
    """Response schema for message list."""

    success: bool = True
    message: str = ""
    messages: List[MessageDetail] = []
    total: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 0
    has_more: bool = False

    @classmethod
    def create(
        cls, messages: List[MessageDetail], total: int, page: int, page_size: int
    ) -> "MessageListResponse":
        """Create a paginated response."""
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        has_more = page < total_pages
        return cls(
            messages=messages,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_more=has_more,
        )


class MessageBranchRequest(BaseModel):
    """Schema for creating a message branch."""

    content: str = Field(..., min_length=1, max_length=5000)
    content_cleaned: Optional[str] = Field(None, max_length=5000)
    answers: Optional[Dict[str, List[str]]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MessageBranchResponse(BaseResponse):
    """Response schema for message branching."""

    branch_message: MessageDetail
    parent_message: MessageDetail


class MessageVersionListResponse(BaseResponse):
    """Response schema for message version list."""

    success: bool = True
    message: str = ""
    versions: List[MessageVersionDetail] = []
    total: int = 0
    current_version: int = 0


class MessageVersionCompareResponse(BaseResponse):
    """Response schema for version comparison."""

    success: bool = True
    message: str = ""
    version1: MessageVersionDetail
    version2: MessageVersionDetail
    differences: Dict[str, Any] = {}


class MessageVersionRollbackRequest(BaseModel):
    """Schema for rolling back to a specific version."""

    version_number: int = Field(..., ge=1)
    create_backup_version: bool = Field(
        default=True, description="Create a backup of current version"
    )


class MessageVersionRollbackResponse(BaseResponse):
    """Response schema for version rollback."""

    success: bool = True
    message: str = ""
    rolled_back_message: MessageDetail
    rollback_version: int
    backup_version_created: Optional[int] = None


class MessageTreeResponse(BaseResponse):
    """Response schema for conversation tree."""

    success: bool = True
    message: str = ""
    tree: MessageTreeNode
    total_messages: int = 0
    total_branches: int = 0
    max_depth: int = 0


class MessagePathResponse(BaseResponse):
    """Response schema for message path."""

    success: bool = True
    message: str = ""
    path: List[MessageDetail] = []
    branch_points: List[int] = []
    total_length: int = 0


class MessageSearchRequest(BaseModel):
    """Schema for searching messages within a conversation."""

    query: str = Field(..., min_length=1, max_length=200)
    role: Optional[str] = Field(None, pattern="^(user|assistant|system)$")
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    include_content: bool = True
    include_answers: bool = True
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class MessageSearchResponse(BaseResponse):
    """Response schema for message search results."""

    results: List[MessageDetail] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0
    search_time_ms: float = 0.0


class MessageBatchCreateRequest(BaseModel):
    """Schema for batch creating messages."""

    messages: List[MessageCreate] = Field(..., min_length=1, max_length=10)


class MessageBatchCreateResponse(BaseResponse):
    """Response schema for batch message creation."""

    created_messages: List[MessageDetail] = []
    failed_count: int = 0
    errors: List[Dict[str, Any]] = []


class MessageAnalyticsResponse(BaseResponse):
    """Response schema for message analytics."""

    total_messages: int = 0
    user_messages: int = 0
    assistant_messages: int = 0
    system_messages: int = 0
    average_message_length: float = 0.0
    total_versions: int = 0
    branching_points: int = 0
    most_active_day: Optional[str] = None


class MessageExportRequest(BaseModel):
    """Schema for exporting messages."""

    conversation_id: int
    include_versions: bool = False
    include_metadata: bool = True
    format: str = Field(default="json", pattern="^(json|csv|txt)$")
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class MessageExportResponse(BaseResponse):
    """Response schema for message export."""

    download_url: Optional[str] = None
    export_id: str = ...
    status: str = Field(default="processing", pattern="^(processing|completed|failed)$")
    message_count: int = 0


class MessageReactionRequest(BaseModel):
    """Schema for adding reactions to messages."""

    reaction_type: str = Field(..., pattern="^(like|dislike|love|laugh|angry|sad)$")
    emoji: Optional[str] = None


class MessageReactionResponse(BaseResponse):
    """Response schema for message reactions."""

    reaction_id: int
    reaction_type: str
    emoji: Optional[str]
    total_reactions: int = 0


class MessageHighlightRequest(BaseModel):
    """Schema for highlighting message content."""

    text: str = Field(..., min_length=1, max_length=500)
    color: Optional[str] = Field(
        default="yellow", pattern="^(yellow|green|blue|red|purple)$"
    )
    note: Optional[str] = Field(None, max_length=200)


class MessageHighlightResponse(BaseResponse):
    """Response schema for message highlights."""

    highlight_id: int
    text: str
    color: str
    note: Optional[str]
    created_at: datetime


class MessageSummaryRequest(BaseModel):
    """Schema for generating message summaries."""

    message_ids: List[int] = Field(..., min_length=1, max_length=50)
    summary_type: str = Field(
        default="concise", pattern="^(concise|detailed|bullet_points)$"
    )
    max_length: Optional[int] = Field(None, ge=50, le=1000)


class MessageSummaryResponse(BaseResponse):
    """Response schema for message summaries."""

    summary: str = ...
    message_count: int = 0
    summary_type: str = ...
    generated_at: datetime


class MessageBaseResponse(BaseResponse):
    """
    Basic response wrapper for message operations.
    """

    success: bool = True
    message: str = ""
    data: Optional[Dict[str, Any]] = None
