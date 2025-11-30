"""
Message business logic and services.
"""

import json
import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from app.config import logger
from app.core.shared.exceptions import (
    ResourceNotFoundException,
    ValidationException,
    DatabaseException,
    ServiceUnavailableException,
)
from app.core.error_context import ErrorContext
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

    def __init__(self, db_pool: asyncpg.Pool, cache_service=None):
        self.message_repo = MessageRepository(db_pool)
        self.version_repo = MessageVersionRepository(db_pool)
        self.conversation_repo = ConversationRepository(db_pool)
        self.cache_service = cache_service

        # Log cache service status
        if self.cache_service and self.cache_service.enabled:
            logger.info("MessageService initialized with caching enabled")
        else:
            logger.info("MessageService initialized without caching")

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

    async def _invalidate_message_caches(self, conversation_id: int):
        """Invalidate all message-related caches for a conversation."""
        if not self.cache_service or not self.cache_service.enabled:
            return

        try:
            # Build patterns for cache invalidation
            patterns = [
                f"msg:list:{conversation_id}:*",  # All message lists with pagination
                f"msg:latest:{conversation_id}",  # Latest message
                f"msg:count:{conversation_id}",  # Message count
            ]

            # Delete all matching patterns
            for pattern in patterns:
                deleted_count = await self.cache_service.delete_pattern(pattern)
                if deleted_count > 0:
                    logger.debug(
                        f"Invalidated {deleted_count} message cache entries for pattern: {pattern}"
                    )

            # Also invalidate conversation message count cache (cross-service)
            conv_msg_count_pattern = f"conv:msgcount:{conversation_id}"
            conv_deleted_count = await self.cache_service.delete_pattern(
                conv_msg_count_pattern
            )
            if conv_deleted_count > 0:
                logger.debug(
                    f"Invalidated {conv_deleted_count} conversation message count cache entries"
                )

            logger.info(
                f"Invalidated message caches for conversation {conversation_id}"
            )

        except Exception as e:
            logger.warning(
                f"Failed to invalidate message caches for conversation {conversation_id}: {e}"
            )

    async def create_message(
        self,
        user_id: int,
        conversation_id: int,
        message_data: MessageCreate,
        ai_chat_service: AIChatService,
    ) -> MessageResponse:
        """Create a new message."""
        # Validate user ownership of conversation
        conversation = await self.conversation_repo.get_conversation_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            raise ValidationException(
                message="Conversation not found or access denied",
                details={"conversation_id": conversation_id, "user_id": user_id},
            )
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

        record = await self.message_repo.create_message(msg_data)
        if not record:
            raise DatabaseException(message="Failed to create message")

        message_response = MessageResponse(**self._transform_message_record(record))

        # Invalidate caches for this conversation
        await self._invalidate_message_caches(conversation_id)

        return message_response

    async def get_message_by_id(
        self, message_id: int, conversation_id: int, user_id: int
    ) -> Optional[MessageResponse]:
        """Get message by ID with user authorization."""
        # First verify user owns the conversation
        conversation = await self.conversation_repo.get_conversation_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            return None

        # Get message
        record = await self.message_repo.get_message(message_id, conversation_id)
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
        conversation = await self.conversation_repo.get_conversation_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            raise ValidationException(
                message="Conversation not found or access denied",
                details={"conversation_id": conversation_id, "user_id": user_id},
            )

        # Check cache (only cache recent messages without pagination for better performance)
        cache_key = None
        if (
            before is None and limit <= 50
        ):  # Only cache first page with reasonable limit
            cache_key = f"msg:list:{conversation_id}:{limit}"
            if self.cache_service and self.cache_service.enabled:
                try:
                    cached_data = await self.cache_service.get_json(cache_key)
                    if cached_data:
                        logger.debug(f"Cache HIT for message list: {cache_key}")
                        return MessageList(**cached_data)
                except Exception as e:
                    logger.warning(f"Cache retrieval failed for {cache_key}: {e}")

        # Cache miss or pagination - get from database
        records = await self.message_repo.list_messages_by_conversation(
            conversation_id, limit=limit, before=before
        )

        messages = []
        for record in records:
            msg_data = self._transform_message_record(record)
            messages.append(MessageResponse(**msg_data))

        # Determine pagination info
        has_more = len(messages) == limit
        cursor = records[-1]["id"] if records and has_more else None
        result = MessageList(messages=messages, has_more=has_more, cursor=cursor)

        # Cache result (only if no pagination and reasonable limit)
        if cache_key and self.cache_service and self.cache_service.enabled:
            try:
                await self.cache_service.set_json(
                    cache_key, result.dict(), ttl=300
                )  # 5 minutes TTL
                logger.debug(f"Cache SET for message list: {cache_key}")
            except Exception as e:
                logger.warning(f"Cache set failed for {cache_key}: {e}")

        return result

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
            raise ValidationException(
                message="Cannot edit message: access denied",
                details={"message_id": message_id, "user_id": user_id},
            )

        # Verify conversation ownership
        conversation = await self.conversation_repo.get_conversation_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            raise ValidationException(
                message="Conversation not found or access denied",
                details={"conversation_id": conversation_id, "user_id": user_id},
            )

        # Update message
        msg_update = {
            "content": update_data.content,
            "metadata": update_data.metadata or {},
        }

        record = await self.message_repo.update(message_id, conversation_id, msg_update)
        if not record:
            raise RuntimeError("Failed to update message")

        message_response = MessageResponse(**self._transform_message_record(record))

        # Invalidate caches for this conversation
        await self._invalidate_message_caches(conversation_id)

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
        conversation = await self.conversation_repo.get_conversation_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            raise ValidationException(
                message="Conversation not found or access denied",
                details={"conversation_id": conversation_id, "user_id": user_id},
            )

        success = await self.message_repo.delete(message_id, conversation_id)

        if success:
            # Invalidate caches for this conversation
            await self._invalidate_message_caches(conversation_id)

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
        version_records = await self.version_repo.list_message_versions(message_id)
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
        version_records = await self.version_repo.list_message_versions(message_id)
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
        conversation = await self.conversation_repo.get_conversation_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            raise ValidationException(
                message="Conversation not found or access denied",
                details={"conversation_id": conversation_id, "user_id": user_id},
            )

        # Get version to restore
        version = await self.version_repo.get_message_version(
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
        conversation = await self.conversation_repo.get_conversation_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            return None

        # Check cache first
        cache_key = f"msg:latest:{conversation_id}"
        if self.cache_service and self.cache_service.enabled:
            try:
                cached_data = await self.cache_service.get_json(cache_key)
                if cached_data:
                    logger.debug(f"Cache HIT for latest message: {cache_key}")
                    return MessageResponse(**cached_data)
            except Exception as e:
                logger.warning(f"Cache retrieval failed for {cache_key}: {e}")

        # Cache miss - get from database
        record = await self.message_repo.get_conversation_latest_message(
            conversation_id
        )
        if not record:
            return None

        message_response = MessageResponse(**self._transform_message_record(record))

        # Cache the result (shorter TTL for latest message)
        if self.cache_service and self.cache_service.enabled:
            try:
                await self.cache_service.set_json(
                    cache_key, message_response.dict(), ttl=120
                )  # 2 minutes TTL
                logger.debug(f"Cache SET for latest message: {cache_key}")
            except Exception as e:
                logger.warning(f"Cache set failed for {cache_key}: {e}")

        return message_response

    async def count_messages_in_conversation(
        self, conversation_id: int, user_id: int
    ) -> Optional[int]:
        """Count messages in a conversation."""
        # Verify conversation ownership
        conversation = await self.conversation_repo.get_conversation_by_id_and_user(
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
        conversation = await self.conversation_repo.get_conversation_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            raise ValidationException(
                message="Conversation not found or access denied",
                details={"conversation_id": conversation_id, "user_id": user_id},
            )

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
        conversation = await self.conversation_repo.get_conversation_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            raise ValidationException(
                message="Conversation not found or access denied",
                details={"conversation_id": conversation_id, "user_id": user_id},
            )

        records = await self.message_repo.get_messages_after_timestamp(
            conversation_id, timestamp, limit
        )

        messages = []
        for record in records:
            msg_data = self._transform_message_record(record)
            messages.append(MessageResponse(**msg_data))

        return messages
