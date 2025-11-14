"""
Conversation repository for database operations.
"""

import json
from typing import Optional, List, Dict, Any
import asyncpg

from app.config import logger
from app.db.database import BaseRepository


class ConversationRepository(BaseRepository):
    """Repository for conversation database operations."""

    async def create(self, data: Dict[str, Any]) -> Optional[asyncpg.Record]:
        """Create a new conversation."""
        try:
            query = """
                INSERT INTO conversations (title, user_id, metadata)
                VALUES ($1, $2, $3)
                RETURNING *
            """
            return await self.fetch_one(
                query,
                data.get("title"),
                data.get("user_id"),
                json.dumps(data.get("metadata", {})),
            )
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")

    async def get_by_id_and_user(
        self, conversation_id: int, user_id: int
    ) -> Optional[asyncpg.Record]:
        """Get conversation by ID and user ID."""
        query = """
            SELECT * FROM conversations
            WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
        """
        return await self.fetch_one(query, conversation_id, user_id)

    async def list_by_user(
        self, user_id: int, limit: int = 50, offset: int = 0
    ) -> List[asyncpg.Record]:
        """List conversations for a user with pagination."""
        try:
            query = """
                SELECT * FROM conversations
                WHERE user_id = $1 AND deleted_at IS NULL
                ORDER BY is_pinned DESC, updated_at DESC
                LIMIT $2 OFFSET $3
            """
            return await self.fetch_many(query, user_id, limit, offset)
        except Exception as e:
            logger.error(f"Failed to list conversations: {e}")
            raise

    async def update(
        self, conversation_id: int, user_id: int, data: Dict[str, Any]
    ) -> Optional[asyncpg.Record]:
        """Update conversation."""
        # Build dynamic UPDATE query
        try:
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
                return await self.get_by_id_and_user(conversation_id, user_id)

            params.extend([conversation_id, user_id])
            query = f"""
                UPDATE conversations
                SET {', '.join(set_clauses)}, updated_at = NOW()
                WHERE id = ${param_count} AND user_id = ${param_count + 1} AND deleted_at IS NULL
                RETURNING *
            """

            return await self.fetch_one(query, *params)
        except Exception as e:
            logger.error(f"Failed to update conversation: {e}")
            raise

    async def delete(self, conversation_id: int, user_id: int) -> bool:
        """Soft delete conversation."""
        query = """
            UPDATE conversations
            SET deleted_at = NOW()
            WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
        """
        result = await self.execute(query, conversation_id, user_id)
        return "UPDATE 1" in result

    async def get_message_count(self, conversation_id: int) -> int:
        """Get total message count for a conversation."""
        query = """
            SELECT COUNT(*) FROM messages
            WHERE conversation_id = $1 AND deleted_at IS NULL
        """
        result = await self.fetch_one(query, conversation_id)
        return result.get("count", 0)

    async def update_timestamp(self, conversation_id: int) -> bool:
        """Update conversation timestamp for sorting."""
        query = """
            UPDATE conversations
            SET updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
        """
        result = await self.execute(query, conversation_id)
        return "UPDATE 1" in result

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
        return await self.fetch_many(query, conversation_id, limit)

    async def pin_conversation(
        self, conversation_id: int, user_id: int, is_pinned: bool = True
    ) -> Optional[asyncpg.Record]:
        """Pin or unpin a conversation."""
        query = """
            UPDATE conversations
            SET is_pinned = $1, updated_at = NOW()
            WHERE id = $2 AND user_id = $3 AND deleted_at IS NULL
            RETURNING *
        """
        return await self.fetch_one(query, is_pinned, conversation_id, user_id)

    async def count_conversations_by_user(self, user_id: int) -> int:
        """Count total conversations for a user."""
        query = """
            SELECT COUNT(*) FROM conversations
            WHERE user_id = $1 AND deleted_at IS NULL
        """
        result = await self.fetch_one(query, user_id)
        return result.get("count", 0)
