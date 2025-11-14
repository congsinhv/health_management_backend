"""
Message business logic and services.
"""

import json
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from app.db.message import MessageRepository
from app.db.message_version import MessageVersionRepository
from app.db.conversation import ConversationRepository
from app.schemas.message import (
    MessageCreate,
    MessageResponse,
    MessageWithVersions,
    MessageList,
    MessageVersionResponse,
    MessageVersionList,
    MessageRestoreRequest,
    MessageEditRequest,
)
from app.services.ai_chat import AIChatService


class MessageService:
    """Service layer for message operations."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.message_repo = MessageRepository(db_pool)
        self.version_repo = MessageVersionRepository(db_pool)
        self.conversation_repo = ConversationRepository(db_pool)

    def _transform_message_record(self, record: asyncpg.Record) -> Dict[str, Any]:
        """Transform database record to MessageResponse format."""
        return {
            "id": record["id"],
            "conversation_id": record["conversation_id"],
            "user_id": record["user_id"],
            "content": record["content"],
            "content_type": record["content_type"],
            "metadata": json.loads(record.get("metadata") or "{}"),
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
        }

    async def create_message(
        self,
        user_id: int,
        conversation_id: int,
        message_data: MessageCreate,
        ai_chat_service: AIChatService,
    ) -> MessageResponse:
        """Create a new message."""
        # Validate user ownership of conversation
        conversation = await self.conversation_repo.get_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            raise ValueError("Conversation not found or access denied")
        elif conversation.get("is_archived"):
            raise ValueError("Conversation is archived")
        elif conversation.get("title") == "Cuộc trò chuyện mới":
            # Genereate new titel for the conversation
            generated_title = await ai_chat_service._generate_conversation_title(
                message_data.content
            )
            if generated_title:
                conv_update = {"title": generated_title}
                record = await self.conversation_repo.update(
                    conversation_id, user_id, conv_update
                )

        # Create message
        msg_data = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "content": message_data.content,
            "content_type": message_data.content_type,
            "metadata": message_data.metadata,
        }

        record = await self.message_repo.create(msg_data)
        if not record:
            raise RuntimeError("Failed to create message")

        message_response = MessageResponse(**self._transform_message_record(record))

        # Broadcast message creation to conversation participants
        await self._broadcast_message_created(
            message_response, conversation_id, exclude_user=str(user_id)
        )

        return message_response

    async def get_message_by_id(
        self, message_id: int, conversation_id: int, user_id: int
    ) -> Optional[MessageResponse]:
        """Get message by ID with user authorization."""
        # First verify user owns the conversation
        conversation = await self.conversation_repo.get_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            return None

        # Get message
        record = await self.message_repo.get_by_id(message_id, conversation_id)
        if not record:
            return None

        return MessageResponse(**self._transform_message_record(record))

    async def list_conversation_messages(
        self,
        conversation_id: int,
        user_id: int,
        limit: int = 50,
        before: Optional[int] = None,
    ) -> MessageList:
        """List messages for a conversation with cursor pagination."""
        # Verify user owns the conversation
        conversation = await self.conversation_repo.get_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            raise ValueError("Conversation not found or access denied")

        # Get messages
        records = await self.message_repo.list_by_conversation(
            conversation_id, limit=limit, before=before
        )

        messages = []
        for record in records:
            msg_data = self._transform_message_record(record)
            messages.append(MessageResponse(**msg_data))

        # Determine pagination info
        has_more = len(messages) == limit
        cursor = records[-1]["id"] if records and has_more else None

        return MessageList(messages=messages, has_more=has_more, cursor=cursor)

    async def update_message(
        self,
        message_id: int,
        conversation_id: int,
        user_id: int,
        update_data: MessageEditRequest,
    ) -> Optional[MessageResponse]:
        """Update message content (creates version automatically)."""
        # Verify user can edit the message
        can_edit = await self.message_repo.can_user_edit_message(message_id, user_id)
        if not can_edit:
            raise ValueError("Cannot edit message: access denied")

        # Verify conversation ownership
        conversation = await self.conversation_repo.get_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            raise ValueError("Conversation not found or access denied")

        # Update message
        msg_update = {
            "content": update_data.content,
            "metadata": update_data.metadata or {},
        }

        record = await self.message_repo.update(message_id, conversation_id, msg_update)
        if not record:
            raise RuntimeError("Failed to update message")

        message_response = MessageResponse(**self._transform_message_record(record))

        # Broadcast message update to conversation participants
        await self._broadcast_message_updated(
            message_response, conversation_id, exclude_user=str(user_id)
        )

        return message_response

    async def delete_message(
        self, message_id: int, conversation_id: int, user_id: int
    ) -> bool:
        """Soft delete a message."""
        # Verify user can edit the message (same permissions)
        can_edit = await self.message_repo.can_user_edit_message(message_id, user_id)
        if not can_edit:
            raise ValueError("Cannot delete message: access denied")

        # Verify conversation ownership
        conversation = await self.conversation_repo.get_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            raise ValueError("Conversation not found or access denied")

        success = await self.message_repo.delete(message_id, conversation_id)

        if success:
            # Broadcast message deletion to conversation participants
            await self._broadcast_message_deleted(
                message_id, conversation_id, exclude_user=str(user_id)
            )

        return success

    async def get_message_with_versions(
        self, message_id: int, conversation_id: int, user_id: int
    ) -> Optional[MessageWithVersions]:
        """Get message with its version history."""
        # Get message
        message = await self.get_message_by_id(message_id, conversation_id, user_id)
        if not message:
            return None

        # Get version history
        version_records = await self.version_repo.list_by_message(message_id)
        versions = []
        for version_record in version_records:
            version_data = {
                "id": version_record["id"],
                "message_id": version_record["message_id"],
                "version_number": version_record["version_number"],
                "content": version_record["content"],
                "metadata": version_record.get("metadata") or {},
                "user_id": version_record["user_id"],
                "created_at": version_record["created_at"],
            }
            versions.append(MessageVersionResponse(**version_data))

        return MessageWithVersions(**message.dict(), versions=versions)

    async def get_message_version_history(
        self, message_id: int, conversation_id: int, user_id: int
    ) -> Optional[MessageVersionList]:
        """Get version history for a message."""
        # Verify message access
        message = await self.get_message_by_id(message_id, conversation_id, user_id)
        if not message:
            return None

        # Get version history
        version_records = await self.version_repo.list_by_message(message_id)
        versions = []
        for version_record in version_records:
            version_data = {
                "id": version_record["id"],
                "message_id": version_record["message_id"],
                "version_number": version_record["version_number"],
                "content": version_record["content"],
                "metadata": version_record.get("metadata") or {},
                "user_id": version_record["user_id"],
                "created_at": version_record["created_at"],
            }
            versions.append(MessageVersionResponse(**version_data))

        return MessageVersionList(versions=versions, total_count=len(versions))

    async def restore_message_to_version(
        self,
        message_id: int,
        conversation_id: int,
        user_id: int,
        restore_request: MessageRestoreRequest,
    ) -> Optional[MessageResponse]:
        """Restore message to a previous version."""
        # Verify user can edit the message
        can_edit = await self.message_repo.can_user_edit_message(message_id, user_id)
        if not can_edit:
            raise ValueError("Cannot restore message: access denied")

        # Verify conversation ownership
        conversation = await self.conversation_repo.get_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            raise ValueError("Conversation not found or access denied")

        # Get version to restore
        version = await self.version_repo.get_by_message_and_version(
            message_id, restore_request.version_number
        )
        if not version:
            raise ValueError("Version not found")

        # Update message with version content
        msg_update = {
            "content": version["content"],
            "metadata": version.get("metadata") or {},
        }

        record = await self.message_repo.update(message_id, conversation_id, msg_update)
        if not record:
            raise RuntimeError("Failed to restore message")

        return MessageResponse(**self._transform_message_record(record))

    async def get_latest_message(
        self, conversation_id: int, user_id: int
    ) -> Optional[MessageResponse]:
        """Get the latest message in a conversation."""
        # Verify conversation ownership
        conversation = await self.conversation_repo.get_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            return None

        record = await self.message_repo.get_conversation_latest_message(
            conversation_id
        )
        if not record:
            return None

        return MessageResponse(**self._transform_message_record(record))

    async def count_messages_in_conversation(
        self, conversation_id: int, user_id: int
    ) -> Optional[int]:
        """Count messages in a conversation."""
        # Verify conversation ownership
        conversation = await self.conversation_repo.get_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            return None

        return await self.message_repo.count_by_conversation(conversation_id)

    async def get_user_messages_in_conversation(
        self, conversation_id: int, user_id: int, target_user_id: int
    ) -> List[MessageResponse]:
        """Get all messages from a specific user in a conversation."""
        # Verify conversation ownership
        conversation = await self.conversation_repo.get_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            raise ValueError("Conversation not found or access denied")

        records = await self.message_repo.get_user_messages_in_conversation(
            conversation_id, target_user_id
        )

        messages = []
        for record in records:
            msg_data = self._transform_message_record(record)
            messages.append(MessageResponse(**msg_data))

        return messages

    async def search_messages(
        self,
        conversation_id: int,
        user_id: int,
        query: str,
        limit: int = 20,
    ) -> List[MessageResponse]:
        """Search messages in a conversation."""
        # This would require implementing full-text search
        # For now, return empty list
        return []

    async def get_messages_after_timestamp(
        self,
        conversation_id: int,
        user_id: int,
        timestamp: datetime,
        limit: int = 100,
    ) -> List[MessageResponse]:
        """Get messages created after a timestamp."""
        # Verify conversation ownership
        conversation = await self.conversation_repo.get_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            raise ValueError("Conversation not found or access denied")

        records = await self.message_repo.get_messages_after_timestamp(
            conversation_id, timestamp, limit
        )

        messages = []
        for record in records:
            msg_data = self._transform_message_record(record)
            messages.append(MessageResponse(**msg_data))

        return messages

    async def _broadcast_message_created(
        self,
        message: MessageResponse,
        conversation_id: int,
        exclude_user: Optional[str] = None,
    ) -> None:
        """Broadcast message creation to conversation participants."""
        try:
            from app.utils.websocket_helpers import broadcast_message_created

            await broadcast_message_created(message, conversation_id, exclude_user)
        except Exception as e:
            # Don't fail the main operation if WebSocket broadcast fails
            pass

    async def _broadcast_message_updated(
        self,
        message: MessageResponse,
        conversation_id: int,
        exclude_user: Optional[str] = None,
    ) -> None:
        """Broadcast message update to conversation participants."""
        try:
            from app.utils.websocket_helpers import broadcast_message_updated

            await broadcast_message_updated(message, conversation_id, exclude_user)
        except Exception as e:
            # Don't fail the main operation if WebSocket broadcast fails
            pass

    async def _broadcast_message_deleted(
        self, message_id: int, conversation_id: int, exclude_user: Optional[str] = None
    ) -> None:
        """Broadcast message deletion to conversation participants."""
        try:
            from app.utils.websocket_helpers import broadcast_message_deleted

            await broadcast_message_deleted(message_id, conversation_id, exclude_user)
        except Exception as e:
            # Don't fail the main operation if WebSocket broadcast fails
            pass
