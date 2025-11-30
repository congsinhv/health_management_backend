"""
Message repository for database operations with custom exception handling.
"""

import json
from typing import Optional, List, Dict, Any
import asyncpg

from app.db.database import BaseRepository
from app.core.shared.exceptions import (
    ResourceNotFoundException,
    DatabaseException,
    DatabaseConstraintException,
)


class MessageRepository(BaseRepository):
    """Repository for message database operations."""

    async def create_message(self, data: Dict[str, Any]) -> asyncpg.Record:
        """Create a new message."""
        query = """
            INSERT INTO messages (conversation_id, user_id, content, content_type, metadata)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """
        try:
            result = await self.fetch_one(
                query,
                data["conversation_id"],
                data["user_id"],
                data["content"],
                data.get("content_type", "text"),
                json.dumps(data.get("metadata", {})),
            )
            if not result:
                raise DatabaseException(
                    message="Failed to create message",
                    details={
                        "conversation_id": data["conversation_id"],
                        "user_id": data["user_id"],
                    },
                )
            return result
        except asyncpg.ForeignKeyViolationError as e:
            if "conversation_id" in str(e):
                raise ResourceNotFoundException(
                    message="Conversation not found for message creation",
                    details={
                        "conversation_id": data["conversation_id"],
                        "user_id": data["user_id"],
                        "constraint": str(e),
                    },
                )
            elif "user_id" in str(e):
                raise ResourceNotFoundException(
                    message="User not found for message creation",
                    details={
                        "conversation_id": data["conversation_id"],
                        "user_id": data["user_id"],
                        "constraint": str(e),
                    },
                )
            else:
                raise DatabaseException(
                    message="Foreign key violation while creating message",
                    details={
                        "conversation_id": data["conversation_id"],
                        "user_id": data["user_id"],
                        "constraint": str(e),
                    },
                )
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while creating message",
                details={
                    "conversation_id": data["conversation_id"],
                    "user_id": data["user_id"],
                    "error": str(e),
                },
            )

    async def get_message(
        self, message_id: int, conversation_id: int
    ) -> asyncpg.Record:
        """Get message by ID and conversation ID."""
        query = """
            SELECT * FROM messages
            WHERE id = $1 AND conversation_id = $2 AND deleted_at IS NULL
        """
        try:
            result = await self.fetch_one(query, message_id, conversation_id)
            if not result:
                raise ResourceNotFoundException(
                    message="Message not found",
                    details={
                        "message_id": message_id,
                        "conversation_id": conversation_id,
                    },
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching message",
                details={
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "error": str(e),
                },
            )

    async def list_messages_by_conversation(
        self, conversation_id: int, limit: int = 50, before: Optional[int] = None
    ) -> List[asyncpg.Record]:
        """List messages for a conversation with cursor pagination."""
        try:
            if before:
                query = """
                    SELECT * FROM messages
                    WHERE conversation_id = $1 AND created_at < (
                        SELECT created_at FROM messages WHERE id = $2
                    ) AND deleted_at IS NULL
                    ORDER BY created_at ASC
                    LIMIT $3
                """
                return await self.fetch_many(query, conversation_id, before, limit)
            else:
                query = """
                    SELECT * FROM messages
                    WHERE conversation_id = $1 AND deleted_at IS NULL
                    ORDER BY created_at ASC
                    LIMIT $2
                """
                return await self.fetch_many(query, conversation_id, limit)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while listing messages",
                details={
                    "conversation_id": conversation_id,
                    "limit": limit,
                    "before": before,
                    "error": str(e),
                },
            )

    async def update(
        self, message_id: int, conversation_id: int, data: Dict[str, Any]
    ) -> asyncpg.Record:
        """Update message content (creates version automatically)."""
        query = """
            UPDATE messages
            SET content = $1, metadata = $2, updated_at = NOW()
            WHERE id = $3 AND conversation_id = $4 AND deleted_at IS NULL
            RETURNING *
        """
        try:
            result = await self.fetch_one(
                query,
                data["content"],
                json.dumps(data.get("metadata", {})),
                message_id,
                conversation_id,
            )
            if not result:
                raise ResourceNotFoundException(
                    message="Message not found for update",
                    details={
                        "message_id": message_id,
                        "conversation_id": conversation_id,
                        "content": data["content"][:100] + "..."
                        if len(data.get("content", "")) > 100
                        else data["content"],
                    },
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while updating message",
                details={
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "error": str(e),
                },
            )

    async def delete(self, message_id: int, conversation_id: int) -> bool:
        """Soft delete message."""
        query = """
            UPDATE messages
            SET deleted_at = NOW()
            WHERE id = $1 AND conversation_id = $2 AND deleted_at IS NULL
        """
        try:
            result = await self.execute(query, message_id, conversation_id)
            success = "UPDATE 1" in result
            if not success:
                raise ResourceNotFoundException(
                    message="Message not found for deletion",
                    details={
                        "message_id": message_id,
                        "conversation_id": conversation_id,
                    },
                )
            return success
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while deleting message",
                details={
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "error": str(e),
                },
            )

    async def get_conversation_latest_message(
        self, conversation_id: int
    ) -> Optional[asyncpg.Record]:
        """Get the latest message in a conversation."""
        query = """
            SELECT * FROM messages
            WHERE conversation_id = $1 AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
        """
        try:
            return await self.fetch_one(query, conversation_id)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching latest message",
                details={"conversation_id": conversation_id, "error": str(e)},
            )

    async def count_by_conversation(self, conversation_id: int) -> int:
        """Count messages in a conversation."""
        query = """
            SELECT COUNT(*) FROM messages
            WHERE conversation_id = $1 AND deleted_at IS NULL
        """
        try:
            result = await self.fetch_one(query, conversation_id)
            return result["count"] if result else 0
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while counting messages",
                details={"conversation_id": conversation_id, "error": str(e)},
            )

    async def get_messages_after_timestamp(
        self, conversation_id: int, timestamp, limit: int = 100
    ) -> List[asyncpg.Record]:
        """Get messages created after a specific timestamp."""
        query = """
            SELECT * FROM messages
            WHERE conversation_id = $1 AND created_at > $2 AND deleted_at IS NULL
            ORDER BY created_at ASC
            LIMIT $3
        """
        try:
            return await self.fetch_many(query, conversation_id, timestamp, limit)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching messages after timestamp",
                details={
                    "conversation_id": conversation_id,
                    "timestamp": timestamp,
                    "limit": limit,
                    "error": str(e),
                },
            )

    async def get_user_messages_in_conversation(
        self, conversation_id: int, user_id: int
    ) -> List[asyncpg.Record]:
        """Get all messages from a specific user in a conversation."""
        query = """
            SELECT * FROM messages
            WHERE conversation_id = $1 AND user_id = $2 AND deleted_at IS NULL
            ORDER BY created_at ASC
        """
        try:
            return await self.fetch_many(query, conversation_id, user_id)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching user messages",
                details={
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "error": str(e),
                },
            )

    async def can_user_edit_message(self, message_id: int, user_id: int) -> bool:
        """Check if user can edit the message."""
        query = """
            SELECT EXISTS (
                SELECT 1 FROM messages
                WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
            )
        """
        try:
            result = await self.fetch_one(query, message_id, user_id)
            return result["exists"] if result else False
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while checking message edit permissions",
                details={"message_id": message_id, "user_id": user_id, "error": str(e)},
            )

    async def get_message_with_conversation(
        self, message_id: int
    ) -> Optional[asyncpg.Record]:
        """Get message along with conversation information."""
        query = """
            SELECT m.*, c.user_id as conversation_owner
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            WHERE m.id = $1 AND m.deleted_at IS NULL AND c.deleted_at IS NULL
        """
        try:
            return await self.fetch_one(query, message_id)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching message with conversation",
                details={"message_id": message_id, "error": str(e)},
            )
