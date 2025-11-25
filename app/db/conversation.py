"""
Conversation repository for database operations with custom exception handling.
"""

import json
from typing import Optional, List, Dict, Any
import asyncpg

from app.config import logger
from app.db.database import BaseRepository
from app.exceptions import (
    ResourceNotFoundException,
    DatabaseException,
    DatabaseConstraintException,
    DuplicateResourceException,
)


class ConversationRepository(BaseRepository):
    """Repository for conversation database operations."""

    async def create_conversation(self, data: Dict[str, Any]) -> asyncpg.Record:
        """Create a new conversation."""
        query = """
            INSERT INTO conversations (title, user_id, metadata)
            VALUES ($1, $2, $3)
            RETURNING *
        """
        try:
            result = await self.fetch_one(
                query,
                data.get("title"),
                data.get("user_id"),
                json.dumps(data.get("metadata", {})),
            )
            if not result:
                raise DatabaseException(
                    message="Failed to create conversation",
                    details={
                        "user_id": data.get("user_id"),
                        "title": data.get("title"),
                    },
                )
            return result
        except asyncpg.ForeignKeyViolationError as e:
            raise ResourceNotFoundException(
                message="User not found for conversation creation",
                details={"user_id": data.get("user_id"), "constraint": str(e)},
            )
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while creating conversation",
                details={
                    "user_id": data.get("user_id"),
                    "title": data.get("title"),
                    "error": str(e),
                },
            )

    async def get_conversation_by_id_and_user(
        self, conversation_id: int, user_id: int
    ) -> asyncpg.Record:
        """Get conversation by ID and user ID."""
        query = """
            SELECT * FROM conversations
            WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
        """
        try:
            result = await self.fetch_one(query, conversation_id, user_id)
            if not result:
                raise ResourceNotFoundException(
                    message="Conversation not found",
                    details={"conversation_id": conversation_id, "user_id": user_id},
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching conversation",
                details={
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "error": str(e),
                },
            )

    async def list_conversations_by_user(
        self, user_id: int, limit: int = 50, offset: int = 0
    ) -> List[asyncpg.Record]:
        """List conversations for a user with pagination."""
        query = """
            SELECT * FROM conversations
            WHERE user_id = $1 AND deleted_at IS NULL
            ORDER BY is_pinned DESC, updated_at DESC
            LIMIT $2 OFFSET $3
        """
        try:
            return await self.fetch_many(query, user_id, limit, offset)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while listing conversations",
                details={
                    "user_id": user_id,
                    "limit": limit,
                    "offset": offset,
                    "error": str(e),
                },
            )

    async def update(
        self, conversation_id: int, user_id: int, data: Dict[str, Any]
    ) -> asyncpg.Record:
        """Update conversation."""
        # Build dynamic UPDATE query
        set_clauses = []
        params = []
        param_count = 1

        for key, value in data.items():
            if key in ["title", "is_pinned", "is_archived", "metadata"]:
                set_clauses.append(f"{key} = ${param_count}")
                if key == "metadata":
                    params.append(json.dumps(value))
                else:
                    params.append(value)
                param_count += 1

        if not set_clauses:
            return await self.get_conversation_by_id_and_user(conversation_id, user_id)

        params.extend([conversation_id, user_id])
        query = f"""
            UPDATE conversations
            SET {', '.join(set_clauses)}, updated_at = NOW()
            WHERE id = ${param_count} AND user_id = ${param_count + 1} AND deleted_at IS NULL
            RETURNING *
        """

        try:
            result = await self.fetch_one(query, *params)
            if not result:
                raise ResourceNotFoundException(
                    message="Conversation not found for update",
                    details={
                        "conversation_id": conversation_id,
                        "user_id": user_id,
                        "data": data,
                    },
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while updating conversation",
                details={
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "data": data,
                    "error": str(e),
                },
            )

    async def delete(self, conversation_id: int, user_id: int) -> bool:
        """Soft delete conversation."""
        query = """
            UPDATE conversations
            SET deleted_at = NOW()
            WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
        """
        try:
            result = await self.execute(query, conversation_id, user_id)
            success = "UPDATE 1" in result
            if not success:
                raise ResourceNotFoundException(
                    message="Conversation not found for deletion",
                    details={"conversation_id": conversation_id, "user_id": user_id},
                )
            return success
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while deleting conversation",
                details={
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "error": str(e),
                },
            )

    async def get_message_count(self, conversation_id: int) -> int:
        """Get total message count for a conversation."""
        query = """
            SELECT COUNT(*) FROM messages
            WHERE conversation_id = $1 AND deleted_at IS NULL
        """
        try:
            result = await self.fetch_one(query, conversation_id)
            return result.get("count", 0)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while getting message count",
                details={"conversation_id": conversation_id, "error": str(e)},
            )

    async def update_timestamp(self, conversation_id: int) -> bool:
        """Update conversation timestamp for sorting."""
        query = """
            UPDATE conversations
            SET updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
        """
        try:
            result = await self.execute(query, conversation_id)
            success = "UPDATE 1" in result
            if not success:
                raise ResourceNotFoundException(
                    message="Conversation not found for timestamp update",
                    details={"conversation_id": conversation_id},
                )
            return success
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while updating conversation timestamp",
                details={"conversation_id": conversation_id, "error": str(e)},
            )

    async def get_latest_messages_preview(
        self, conversation_id: int, limit: int = 2
    ) -> List[asyncpg.Record]:
        """Get latest few messages for conversation preview."""
        query = """
            SELECT content, user_id, created_at
            FROM messages
            WHERE conversation_id = $1 AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT $2
        """
        try:
            return await self.fetch_many(query, conversation_id, limit)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while getting latest messages preview",
                details={
                    "conversation_id": conversation_id,
                    "limit": limit,
                    "error": str(e),
                },
            )

    async def pin_conversation(
        self, conversation_id: int, user_id: int, is_pinned: bool = True
    ) -> asyncpg.Record:
        """Pin or unpin a conversation."""
        query = """
            UPDATE conversations
            SET is_pinned = $1, updated_at = NOW()
            WHERE id = $2 AND user_id = $3 AND deleted_at IS NULL
            RETURNING *
        """
        try:
            result = await self.fetch_one(query, is_pinned, conversation_id, user_id)
            if not result:
                raise ResourceNotFoundException(
                    message="Conversation not found for pin operation",
                    details={
                        "conversation_id": conversation_id,
                        "user_id": user_id,
                        "is_pinned": is_pinned,
                    },
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while pinning conversation",
                details={
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "is_pinned": is_pinned,
                    "error": str(e),
                },
            )

    async def count_conversations_by_user(self, user_id: int) -> int:
        """Count total conversations for a user."""
        query = """
            SELECT COUNT(*) FROM conversations
            WHERE user_id = $1 AND deleted_at IS NULL
        """
        try:
            result = await self.fetch_one(query, user_id)
            return result.get("count", 0)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while counting conversations",
                details={"user_id": user_id, "error": str(e)},
            )
