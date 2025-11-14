"""
Conversation business logic and services.
"""

import json
import logging
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from app.db.conversation import ConversationRepository
from app.db.message import MessageRepository
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationWithMessages,
    ConversationList,
    ConversationPinRequest,
)
from app.schemas.message import MessageResponse


class ConversationService:
    """Service layer for conversation operations."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.conversation_repo = ConversationRepository(db_pool)
        self.message_repo = MessageRepository(db_pool)

    def _transform_conversation_record(
        self, record: asyncpg.Record, include_message_count: bool = False
    ) -> Dict[str, Any]:
        """Transform database record to ConversationResponse format."""
        conversation_data = {
            "id": record.get("id"),
            "user_id": record.get("user_id"),
            "title": record.get("title"),
            "is_pinned": record.get("is_pinned"),
            "is_archived": record.get("is_archived"),
            "metadata": json.loads(record.get("metadata") or "{}"),
            "created_at": record.get("created_at"),
            "updated_at": record.get("updated_at"),
        }

        # Include message count if available
        if include_message_count and "message_count" in record:
            conversation_data["message_count"] = record.get("message_count")

        return conversation_data

    async def create_conversation(
        self, user_id: int, conversation_data: ConversationCreate
    ) -> ConversationResponse:
        """Create a new conversation."""
        try:
            # Validate user ownership
            if conversation_data.user_id != user_id:
                raise ValueError("User ID mismatch")

            # Create conversation
            conv_data = {
                "title": conversation_data.title,
                "metadata": conversation_data.metadata,
                "user_id": user_id,
            }

            record = await self.conversation_repo.create(conv_data)
            if not record:
                raise Exception("Failed to create conversation")

            conversation_response = ConversationResponse(
                **self._transform_conversation_record(record)
            )

            # Broadcast conversation creation to user's WebSocket connections
            await self._broadcast_conversation_update(user_id, conversation_response)

            return conversation_response
        except Exception as e:
            raise Exception(f"Failed to create conversation: {e}")

    async def get_conversation_by_id(
        self, conversation_id: int, user_id: int
    ) -> Optional[ConversationResponse]:
        """Get conversation by ID with user authorization."""
        try:
            record = await self.conversation_repo.get_by_id_and_user(
                conversation_id, user_id
            )
            if not record:
                return None

            return ConversationResponse(**self._transform_conversation_record(record))
        except Exception as e:
            raise Exception(f"Failed to get conversation by ID: {e}")

    async def get_conversation_with_messages(
        self, conversation_id: int, user_id: int, message_limit: int = 50
    ) -> Optional[ConversationWithMessages]:
        """Get conversation with its messages."""
        try:
            # Get conversation
            conversation = await self.get_conversation_by_id(conversation_id, user_id)
            if not conversation:
                return None

            # Get messages
            message_records = await self.message_repo.list_by_conversation(
                conversation_id, limit=message_limit
            )

            messages = []
            for msg_record in message_records:
                msg_data = {
                    "id": msg_record.get("id"),
                    "conversation_id": msg_record.get("conversation_id"),
                    "user_id": msg_record.get("user_id"),
                    "content": msg_record.get("content"),
                    "content_type": msg_record.get("content_type"),
                    "metadata": msg_record.get("metadata") or {},
                    "created_at": msg_record.get("created_at"),
                    "updated_at": msg_record.get("updated_at"),
                }
                messages.append(MessageResponse(**msg_data))

            return ConversationWithMessages(
                **conversation.model_dump(), messages=messages
            )
        except Exception as e:
            raise Exception(f"Failed to get conversation with messages: {e}")

    async def list_user_conversations(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        include_message_count: bool = True,
    ) -> ConversationList:
        """List conversations for a user with pagination."""
        try:
            # Get conversations
            records = await self.conversation_repo.list_by_user(
                user_id, limit=limit, offset=offset
            )

            # Transform records
            conversations = []
            for record in records:
                conv_data = self._transform_conversation_record(
                    record, include_message_count
                )
                conversations.append(ConversationResponse(**conv_data))

            # Get total count for pagination
            total_count = await self.conversation_repo.count_conversations_by_user(
                user_id
            )
            has_more = (offset + limit) < total_count

            return ConversationList(
                conversations=conversations, total_count=total_count, has_more=has_more
            )
        except Exception as e:
            raise Exception(f"Failed to list user conversations: {e}")

    async def update_conversation(
        self,
        conversation_id: int,
        user_id: int,
        update_data: ConversationUpdate,
    ) -> Optional[ConversationResponse]:
        """Update conversation information."""
        # Check if conversation exists and user owns it
        try:
            existing = await self.conversation_repo.get_by_id_and_user(
                conversation_id, user_id
            )
            if not existing:
                return None

            # Transform update data
            conv_update = {}
            if update_data.title is not None:
                conv_update["title"] = update_data.title
            if update_data.is_pinned is not None:
                conv_update["is_pinned"] = update_data.is_pinned
            if update_data.metadata is not None:
                conv_update["metadata"] = update_data.metadata

            # Update conversation
            if not conv_update:
                # No updates, return existing
                return ConversationResponse(
                    **self._transform_conversation_record(existing)
                )

            record = await self.conversation_repo.update(
                conversation_id, user_id, conv_update
            )
            if not record:
                raise RuntimeError("Failed to update conversation")

            conversation_response = ConversationResponse(
                **self._transform_conversation_record(record)
            )

            # Broadcast conversation update to user's WebSocket connections
            await self._broadcast_conversation_update(user_id, conversation_response)

            return conversation_response
        except Exception as e:
            raise Exception(f"Failed to update conversation: {e}")

    async def pin_conversation(
        self,
        conversation_id: int,
        user_id: int,
        pin_request: ConversationPinRequest,
    ) -> Optional[ConversationResponse]:
        """Pin or unpin a conversation."""
        try:
            record = await self.conversation_repo.pin_conversation(
                conversation_id, user_id, pin_request.is_pinned
            )
            if not record:
                return None

            conversation_response = ConversationResponse(
                **self._transform_conversation_record(record)
            )

            # Broadcast conversation update to user's WebSocket connections
            await self._broadcast_conversation_update(user_id, conversation_response)

            return conversation_response
        except Exception as e:
            raise Exception(f"Failed to pin conversation: {e}")

    async def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        """Soft delete a conversation."""
        # Check if conversation exists and user owns it
        try:
            existing = await self.conversation_repo.get_by_id_and_user(
                conversation_id, user_id
            )
            if not existing:
                return False

            return await self.conversation_repo.delete(conversation_id, user_id)
        except Exception as e:
            raise Exception(f"Failed to delete conversation: {e}")

    async def get_conversation_message_count(
        self, conversation_id: int, user_id: int
    ) -> Optional[int]:
        """Get message count for a conversation."""
        # Verify conversation ownership
        try:
            conversation = await self.conversation_repo.get_by_id_and_user(
                conversation_id, user_id
            )
            if not conversation:
                return None

            return await self.conversation_repo.get_message_count(conversation_id)
        except Exception as e:
            raise Exception(f"Failed to get conversation message count: {e}")

    async def search_conversations(
        self,
        user_id: int,
        query: str,
        limit: int = 20,
        offset: int = 0,
    ) -> ConversationList:
        """Search conversations by title or content."""
        # This would require implementing full-text search
        # For now, return empty list
        try:
            return ConversationList(conversations=[], total_count=0, has_more=False)
        except Exception as e:
            raise Exception(f"Failed to search conversations: {e}")

    async def get_pinned_conversations(
        self, user_id: int, limit: int = 10
    ) -> List[ConversationResponse]:
        """Get pinned conversations for a user."""
        # Get all conversations with pinned first
        try:
            records = await self.conversation_repo.list_by_user(
                user_id, limit=limit, offset=0
            )

            # Filter only pinned conversations
            pinned_conversations = []
            for record in records:
                if record["is_pinned"]:
                    conv_data = self._transform_conversation_record(
                        record, include_message_count=True
                    )
                    pinned_conversations.append(ConversationResponse(**conv_data))

            return pinned_conversations
        except Exception as e:
            raise Exception(f"Failed to get pinned conversations: {e}")

    async def update_conversation_title(
        self,
        conversation_id: int,
        user_id: int,
        title: str,
    ) -> Optional[ConversationResponse]:
        """Update conversation title."""
        try:
            update_data = ConversationUpdate(title=title)
            return await self.update_conversation(conversation_id, user_id, update_data)
        except Exception as e:
            raise Exception(f"Failed to update conversation title: {e}")

    async def archive_conversation(
        self,
        conversation_id: int,
        user_id: int,
        is_archived: bool = True,
    ) -> Optional[ConversationResponse]:
        """Archive or unarchive a conversation."""
        try:
            update_data = ConversationUpdate(is_archived=is_archived)
            return await self.update_conversation(conversation_id, user_id, update_data)
        except Exception as e:
            raise Exception(f"Failed to archive conversation: {e}")

    async def _broadcast_conversation_update(
        self, user_id: int, conversation: ConversationResponse
    ) -> None:
        """Broadcast conversation update to user's WebSocket connections."""
        try:
            from app.utils.websocket_helpers import send_conversation_update

            await send_conversation_update(str(user_id), conversation)
        except Exception as e:
            # Don't fail the main operation if WebSocket broadcast fails
            logger.error(f"Failed to broadcast conversation update: {e}")
