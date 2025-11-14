"""
Conversation-related Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from app.schemas.base import BaseSchema, TimestampMixin, IDMixin


class ConversationBase(BaseSchema):
    """Base conversation schema with common fields."""

    title: Optional[str] = Field(None, max_length=255, description="Conversation title")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Conversation metadata"
    )


class ConversationCreate(ConversationBase):
    """Schema for creating a new conversation."""

    user_id: int = Field(..., description="User ID")


class ConversationUpdate(BaseSchema):
    """Schema for updating a conversation."""

    title: Optional[str] = Field(None, max_length=255, description="Conversation title")
    is_pinned: Optional[bool] = Field(
        None, description="Whether the conversation is pinned"
    )
    is_archived: Optional[bool] = Field(
        None, description="Whether the conversation is archived"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Conversation metadata"
    )


class ConversationResponse(ConversationBase, IDMixin, TimestampMixin):
    """Schema for conversation response."""

    user_id: int = Field(..., description="User ID")
    is_archived: bool = Field(
        default=False, description="Whether the conversation is archived"
    )
    is_pinned: bool = Field(
        default=False, description="Whether the conversation is pinned"
    )
    message_count: Optional[int] = Field(
        None, description="Number of messages in conversation"
    )


class ConversationWithMessages(ConversationResponse):
    """Schema for conversation with its messages."""

    messages: Optional[list] = Field(None, description="Messages in conversation")


class ConversationList(BaseSchema):
    """Schema for conversation list response."""

    conversations: list[ConversationResponse] = Field(
        ..., description="List of conversations"
    )
    total_count: int = Field(..., description="Total number of conversations")
    has_more: bool = Field(..., description="Whether there are more conversations")


class ConversationPinRequest(BaseSchema):
    """Schema for pinning/unpinning a conversation."""

    is_pinned: bool = Field(..., description="Pin status")


class ConversationArchiveRequest(BaseSchema):
    """Schema for archiving/unarchiving a conversation."""

    is_archived: bool = Field(..., description="Archive status")
