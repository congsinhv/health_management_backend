"""
Pydantic schemas package.
"""

from app.schemas.base import BaseSchema, TimestampMixin, IDMixin
from app.schemas.user import (
    UserBase,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserInDB,
    UserLogin,
    Token,
    TokenData,
    RefreshToken,
    TokenPair,
    PasswordResetRequest,
    PasswordReset,
    EmailVerification,
    GoogleOAuthRequest,
    GoogleOAuthCallback,
)
from app.schemas.conversation import (
    ConversationBase,
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationWithMessages,
    ConversationList,
    ConversationPinRequest,
    ConversationArchiveRequest,
)
from app.schemas.message import (
    MessageBase,
    MessageCreate,
    MessageUpdate,
    MessageResponse,
    MessageWithVersions,
    MessageList,
    MessageVersionResponse,
    MessageVersionList,
    MessageRestoreRequest,
    MessageEditRequest,
    AIPromptRequest,
    AIResponse,
)

__all__ = [
    # Base schemas
    "BaseSchema",
    "TimestampMixin",
    "IDMixin",
    # User schemas
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserInDB",
    "UserLogin",
    "Token",
    "TokenData",
    "RefreshToken",
    "TokenPair",
    "PasswordResetRequest",
    "PasswordReset",
    "EmailVerification",
    "GoogleOAuthRequest",
    "GoogleOAuthCallback",
    # Conversation schemas
    "ConversationBase",
    "ConversationCreate",
    "ConversationUpdate",
    "ConversationResponse",
    "ConversationWithMessages",
    "ConversationList",
    "ConversationPinRequest",
    "ConversationArchiveRequest",
    # Message schemas
    "MessageBase",
    "MessageCreate",
    "MessageUpdate",
    "MessageResponse",
    "MessageWithVersions",
    "MessageList",
    "MessageVersionResponse",
    "MessageVersionList",
    "MessageRestoreRequest",
    "MessageEditRequest",
    "AIPromptRequest",
    "AIResponse",
]
