"""
Message-related Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator

from app.schemas.base import BaseSchema, TimestampMixin, IDMixin


class MessageBase(BaseSchema):
    """Base message schema with common fields."""

    content: str = Field(..., description="Message content")
    content_type: str = Field(default="text", description="Message content type")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Message metadata"
    )


class MessageCreate(MessageBase):
    """Schema for creating a new message."""

    conversation_id: int = Field(..., description="Conversation ID")
    user_id: int = Field(..., description="User ID")

    @field_validator("content_type")
    def validate_content_type(cls, v):
        allowed_types = ["text", "image", "file", "system"]
        if v not in allowed_types:
            raise ValueError(f"content_type must be one of: {allowed_types}")
        return v


class MessageUpdate(BaseSchema):
    """Schema for updating a message."""

    content: Optional[str] = Field(None, description="Updated message content")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Updated message metadata"
    )


class MessageResponse(MessageBase, IDMixin, TimestampMixin):
    """Schema for message response."""

    conversation_id: int = Field(..., description="Conversation ID")
    user_id: int = Field(..., description="User ID")
    version_number: Optional[int] = Field(None, description="Current version number")


class MessageWithVersions(MessageResponse):
    """Schema for message with its version history."""

    versions: Optional[List["MessageVersionResponse"]] = Field(
        None, description="Version history"
    )


class MessageList(BaseSchema):
    """Schema for message list response."""

    messages: List[MessageResponse] = Field(..., description="List of messages")
    has_more: bool = Field(..., description="Whether there are more messages")
    cursor: Optional[int] = Field(None, description="Next cursor for pagination")


class MessageVersionResponse(BaseSchema, IDMixin, TimestampMixin):
    """Schema for message version response."""

    message_id: int = Field(..., description="Message ID")
    version_number: int = Field(..., description="Version number")
    content: str = Field(..., description="Version content")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Version metadata"
    )
    user_id: int = Field(..., description="User ID who created this version")


class MessageVersionList(BaseSchema):
    """Schema for message version list response."""

    versions: List[MessageVersionResponse] = Field(
        ..., description="List of message versions"
    )
    total_count: int = Field(..., description="Total number of versions")


class MessageRestoreRequest(BaseSchema):
    """Schema for restoring a message to a previous version."""

    version_number: int = Field(..., description="Version number to restore to")


class MessageEditRequest(BaseSchema):
    """Schema for editing a message."""

    content: str = Field(..., description="New message content")
    metadata: Optional[Dict[str, Any]] = Field(None, description="New message metadata")


class AIPromptRequest(BaseSchema):
    """Schema for AI-generated message."""

    conversation_id: int = Field(..., description="Conversation ID")
    prompt: str = Field(..., description="User prompt")
    context: Optional[Dict[str, Any]] = Field(
        None, description="Additional context for AI"
    )
    user_id: int = Field(..., description="User ID")


class AIResponse(BaseSchema):
    """Schema for AI response."""

    content: str = Field(..., description="AI generated content")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="AI response metadata"
    )
    model_used: Optional[str] = Field(None, description="AI model used for generation")
    tokens_used: Optional[int] = Field(None, description="Number of tokens used")


# Update forward references
MessageWithVersions.model_rebuild()
