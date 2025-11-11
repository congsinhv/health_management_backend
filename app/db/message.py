"""
Message repository for database operations.
"""

import asyncpg
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from app.db.database import BaseRepository


class MessageRepository(BaseRepository):
    """Repository for message-related database operations."""

    async def create_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        content_cleaned: Optional[str] = None,
        answers: Optional[Dict[str, List[str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        parent_message_id: Optional[int] = None,
    ) -> int:
        """Create a new message."""
        query = """
            INSERT INTO qa_messages (
                conversation_id, role, content, content_cleaned, answers,
                metadata, parent_message_id, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())
            RETURNING id
        """
        result = await self.fetch_one(
            query,
            conversation_id,
            role,
            content,
            content_cleaned,
            answers,
            metadata or {},
            parent_message_id,
        )
        return result["id"] if result else None

    async def get_message(self, message_id: int) -> Optional[asyncpg.Record]:
        """Get message by ID."""
        query = """
            SELECT m.*,
                   c.user_id,
                   COUNT(v.id) as version_count,
                   COUNT(child.id) as child_count
            FROM qa_messages m
            JOIN qa_conversations c ON m.conversation_id = c.id
            LEFT JOIN qa_message_versions v ON m.id = v.message_id
            LEFT JOIN qa_messages child ON m.id = child.parent_message_id AND child.deleted_at IS NULL
            WHERE m.id = $1 AND m.deleted_at IS NULL AND c.deleted_at IS NULL
            GROUP BY m.id, c.user_id
        """
        return await self.fetch_one(query, message_id)

    async def get_message_by_user(
        self, message_id: int, user_id: int
    ) -> Optional[asyncpg.Record]:
        """Get message by ID and user ID."""
        query = """
            SELECT m.*,
                   COUNT(v.id) as version_count,
                   COUNT(child.id) as child_count
            FROM qa_messages m
            JOIN qa_conversations c ON m.conversation_id = c.id
            LEFT JOIN qa_message_versions v ON m.id = v.message_id
            LEFT JOIN qa_messages child ON m.id = child.parent_message_id AND child.deleted_at IS NULL
            WHERE m.id = $1 AND c.user_id = $2 AND m.deleted_at IS NULL AND c.deleted_at IS NULL
            GROUP BY m.id
        """
        return await self.fetch_one(query, message_id, user_id)

    async def get_conversation_messages(
        self,
        conversation_id: int,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
        order_by: str = "created_at",
    ) -> List[asyncpg.Record]:
        """Get messages for a conversation with pagination."""
        # Validate order_by
        valid_order_fields = ["created_at", "updated_at"]
        if order_by not in valid_order_fields:
            order_by = "created_at"

        query = f"""
            SELECT m.*,
                   COUNT(v.id) as version_count,
                   COUNT(child.id) as child_count
            FROM qa_messages m
            JOIN qa_conversations c ON m.conversation_id = c.id
            LEFT JOIN qa_message_versions v ON m.id = v.message_id
            LEFT JOIN qa_messages child ON m.id = child.parent_message_id AND child.deleted_at IS NULL
            WHERE m.conversation_id = $1 AND c.user_id = $2
                AND m.deleted_at IS NULL AND c.deleted_at IS NULL
            GROUP BY m.id
            ORDER BY m.{order_by} ASC
            LIMIT $3 OFFSET $4
        """
        return await self.fetch_many(query, conversation_id, user_id, limit, skip)

    async def count_conversation_messages(
        self, conversation_id: int, user_id: int
    ) -> int:
        """Count messages in a conversation."""
        query = """
            SELECT COUNT(*) as count
            FROM qa_messages m
            JOIN qa_conversations c ON m.conversation_id = c.id
            WHERE m.conversation_id = $1 AND c.user_id = $2
                AND m.deleted_at IS NULL AND c.deleted_at IS NULL
        """
        result = await self.fetch_one(query, conversation_id, user_id)
        return result["count"] if result else 0

    async def update_message(
        self,
        message_id: int,
        user_id: int,
        content: str,
        content_cleaned: Optional[str] = None,
        answers: Optional[Dict[str, List[str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update message content."""
        query = """
            UPDATE qa_messages
            SET content = $1,
                content_cleaned = $2,
                answers = $3,
                metadata = $4,
                updated_at = NOW()
            FROM qa_conversations c
            WHERE qa_messages.id = $5
                AND qa_messages.conversation_id = c.id
                AND c.user_id = $6
                AND qa_messages.deleted_at IS NULL
                AND c.deleted_at IS NULL
        """
        result = await self.execute(
            query,
            content,
            content_cleaned,
            answers,
            metadata or {},
            message_id,
            user_id,
        )
        return "UPDATE" in result

    async def delete_message(self, message_id: int, user_id: int) -> bool:
        """Soft delete message."""
        query = """
            UPDATE qa_messages
            SET deleted_at = NOW(), updated_at = NOW()
            FROM qa_conversations c
            WHERE qa_messages.id = $1
                AND qa_messages.conversation_id = c.id
                AND c.user_id = $2
                AND qa_messages.deleted_at IS NULL
                AND c.deleted_at IS NULL
        """
        result = await self.execute(query, message_id, user_id)
        return "UPDATE" in result

    async def create_message_branch(
        self,
        parent_message_id: int,
        user_id: int,
        role: str,
        content: str,
        content_cleaned: Optional[str] = None,
        answers: Optional[Dict[str, List[str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Create a branch from a parent message."""
        # Get conversation_id from parent message
        parent_query = """
            SELECT m.conversation_id
            FROM qa_messages m
            JOIN qa_conversations c ON m.conversation_id = c.id
            WHERE m.id = $1 AND c.user_id = $2
                AND m.deleted_at IS NULL AND c.deleted_at IS NULL
        """
        parent_result = await self.fetch_one(parent_query, parent_message_id, user_id)
        if not parent_result:
            return None

        conversation_id = parent_result["conversation_id"]

        # Create branched message
        return await self.create_message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            content_cleaned=content_cleaned,
            answers=answers,
            metadata=metadata,
            parent_message_id=parent_message_id,
        )

    async def get_message_children(
        self, message_id: int, user_id: int
    ) -> List[asyncpg.Record]:
        """Get child messages (branches) of a message."""
        query = """
            SELECT m.*,
                   COUNT(v.id) as version_count,
                   COUNT(child.id) as child_count
            FROM qa_messages m
            JOIN qa_conversations c ON m.conversation_id = c.id
            LEFT JOIN qa_message_versions v ON m.id = v.message_id
            LEFT JOIN qa_messages child ON m.id = child.parent_message_id AND child.deleted_at IS NULL
            WHERE m.parent_message_id = $1 AND c.user_id = $2
                AND m.deleted_at IS NULL AND c.deleted_at IS NULL
            GROUP BY m.id
            ORDER BY m.created_at ASC
        """
        return await self.fetch_many(query, message_id, user_id)

    async def get_conversation_tree(
        self, conversation_id: int, user_id: int
    ) -> List[asyncpg.Record]:
        """Get all messages in a conversation with branching structure."""
        query = """
            SELECT m.*,
                   parent_message_id,
                   COUNT(v.id) as version_count,
                   COUNT(child.id) as child_count
            FROM qa_messages m
            JOIN qa_conversations c ON m.conversation_id = c.id
            LEFT JOIN qa_message_versions v ON m.id = v.message_id
            LEFT JOIN qa_messages child ON m.id = child.parent_message_id AND child.deleted_at IS NULL
            WHERE m.conversation_id = $1 AND c.user_id = $2
                AND m.deleted_at IS NULL AND c.deleted_at IS NULL
            GROUP BY m.id, m.parent_message_id
            ORDER BY m.created_at ASC
        """
        return await self.fetch_many(query, conversation_id, user_id)

    async def get_root_messages(
        self, conversation_id: int, user_id: int
    ) -> List[asyncpg.Record]:
        """Get root messages (messages without parents) in a conversation."""
        query = """
            SELECT m.*,
                   COUNT(v.id) as version_count,
                   COUNT(child.id) as child_count
            FROM qa_messages m
            JOIN qa_conversations c ON m.conversation_id = c.id
            LEFT JOIN qa_message_versions v ON m.id = v.message_id
            LEFT JOIN qa_messages child ON m.id = child.parent_message_id AND child.deleted_at IS NULL
            WHERE m.conversation_id = $1 AND c.user_id = $2
                AND m.parent_message_id IS NULL
                AND m.deleted_at IS NULL AND c.deleted_at IS NULL
            GROUP BY m.id
            ORDER BY m.created_at ASC
        """
        return await self.fetch_many(query, conversation_id, user_id)

    async def get_branch_path(
        self, message_id: int, user_id: int
    ) -> List[asyncpg.Record]:
        """Get the path from root to a specific message."""
        # Use recursive CTE to get the full path
        query = """
            WITH RECURSIVE message_path AS (
                -- Base case: the target message
                SELECT m.*, 0 as level
                FROM qa_messages m
                JOIN qa_conversations c ON m.conversation_id = c.id
                WHERE m.id = $1 AND c.user_id = $2
                    AND m.deleted_at IS NULL AND c.deleted_at IS NULL

                UNION ALL

                -- Recursive case: get parent
                SELECT m.*, mp.level + 1
                FROM qa_messages m
                JOIN qa_conversations c ON m.conversation_id = c.id
                JOIN message_path mp ON m.id = mp.parent_message_id
                WHERE m.deleted_at IS NULL AND c.deleted_at IS NULL
            )
            SELECT mp.*,
                   COUNT(v.id) as version_count,
                   COUNT(child.id) as child_count
            FROM message_path mp
            LEFT JOIN qa_message_versions v ON mp.id = v.message_id
            LEFT JOIN qa_messages child ON mp.id = child.parent_message_id AND child.deleted_at IS NULL
            GROUP BY mp.id
            ORDER BY mp.level ASC
        """
        return await self.fetch_many(query, message_id, user_id)

    async def get_first_message(
        self, conversation_id: int, user_id: int
    ) -> Optional[asyncpg.Record]:
        """Get the first message in a conversation."""
        query = """
            SELECT m.*,
                   COUNT(v.id) as version_count,
                   COUNT(child.id) as child_count
            FROM qa_messages m
            JOIN qa_conversations c ON m.conversation_id = c.id
            LEFT JOIN qa_message_versions v ON m.id = v.message_id
            LEFT JOIN qa_messages child ON m.id = child.parent_message_id AND child.deleted_at IS NULL
            WHERE m.conversation_id = $1 AND c.user_id = $2
                AND m.deleted_at IS NULL AND c.deleted_at IS NULL
            GROUP BY m.id
            ORDER BY m.created_at ASC
            LIMIT 1
        """
        return await self.fetch_one(query, conversation_id, user_id)

    async def get_last_message(
        self, conversation_id: int, user_id: int
    ) -> Optional[asyncpg.Record]:
        """Get the last message in a conversation."""
        query = """
            SELECT m.*,
                   COUNT(v.id) as version_count,
                   COUNT(child.id) as child_count
            FROM qa_messages m
            JOIN qa_conversations c ON m.conversation_id = c.id
            LEFT JOIN qa_message_versions v ON m.id = v.message_id
            LEFT JOIN qa_messages child ON m.id = child.parent_message_id AND child.deleted_at IS NULL
            WHERE m.conversation_id = $1 AND c.user_id = $2
                AND m.deleted_at IS NULL AND c.deleted_at IS NULL
            GROUP BY m.id
            ORDER BY m.created_at DESC
            LIMIT 1
        """
        return await self.fetch_one(query, conversation_id, user_id)

    async def update_conversation_timestamp(
        self, conversation_id: int, user_id: int
    ) -> bool:
        """Update conversation's updated_at timestamp."""
        query = """
            UPDATE qa_conversations
            SET updated_at = NOW()
            WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
        """
        result = await self.execute(query, conversation_id, user_id)
        return "UPDATE" in result

    async def get_messages_cursor(
        self,
        conversation_id: int,
        user_id: int,
        cursor: Optional[str] = None,
        limit: int = 50,
        direction: str = "forward",
        order_by: str = "created_at",
    ) -> Tuple[List[asyncpg.Record], Optional[str], bool]:
        """Get messages using cursor-based pagination."""
        import base64
        import json

        # Validate order_by
        valid_order_fields = ["created_at", "updated_at"]
        if order_by not in valid_order_fields:
            order_by = "created_at"

        # Parse cursor if provided
        cursor_data = None
        if cursor:
            try:
                cursor_data = json.loads(base64.b64decode(cursor).decode())
            except (ValueError, json.JSONDecodeError):
                raise ValueError("Invalid cursor format")

        # Build WHERE clause
        where_conditions = [
            "m.conversation_id = $1",
            "c.user_id = $2",
            "m.deleted_at IS NULL",
            "c.deleted_at IS NULL",
        ]
        params = [conversation_id, user_id]
        param_index = 3

        # Add cursor condition
        if cursor_data:
            if direction == "forward":
                where_conditions.append(f"m.{order_by} > ${param_index}")
            else:  # backward
                where_conditions.append(f"m.{order_by} < ${param_index}")
            params.append(cursor_data.get(order_by))
            param_index += 1

        # Build ORDER BY
        if direction == "backward":
            order_clause = f"m.{order_by} DESC"
        else:
            order_clause = f"m.{order_by} ASC"

        # Build query
        query = f"""
            SELECT m.*,
                   COUNT(v.id) as version_count,
                   COUNT(child.id) as child_count
            FROM qa_messages m
            JOIN qa_conversations c ON m.conversation_id = c.id
            LEFT JOIN qa_message_versions v ON m.id = v.message_id
            LEFT JOIN qa_messages child ON m.id = child.parent_message_id AND child.deleted_at IS NULL
            WHERE {' AND '.join(where_conditions)}
            GROUP BY m.id
            ORDER BY {order_clause}
            LIMIT ${param_index}
        """
        params.append(limit + 1)  # Fetch one extra to check if there are more

        results = await self.fetch_many(query, *params)

        # Determine if there are more results
        has_more = len(results) > limit
        if has_more:
            results = results[:-1]  # Remove the extra item

        # Generate next cursor
        next_cursor = None
        if results and has_more:
            last_item = results[-1]
            cursor_data = {order_by: last_item[order_by]}
            next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

        # If going backward, reverse results to maintain order
        if direction == "backward":
            results.reverse()

        return results, next_cursor, has_more
