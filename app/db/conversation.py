"""
Conversation repository for database operations.
"""

import asyncpg
import json
from typing import Optional, List, Dict, Any, Tuple
from app.db.database import BaseRepository


class ConversationRepository(BaseRepository):
    """Repository for conversation-related database operations."""

    async def create_conversation(
        self,
        user_id: int,
        title: Optional[str] = None,
        question: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Create a new conversation."""
        query = """
            INSERT INTO qa_conversations (
                user_id, title, question, tags, metadata, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
            RETURNING id
        """
        result = await self.fetch_one(
            query, user_id, title, question or '', json.dumps(tags or []), json.dumps(metadata or {})
        )
        return result["id"] if result else None

    async def get_conversation(self, conversation_id: int) -> Optional[asyncpg.Record]:
        """Get conversation by ID."""
        query = """
            SELECT c.*,
                   COUNT(m.id) as message_count,
                   MAX(m.created_at) as last_message_at
            FROM qa_conversations c
            LEFT JOIN qa_messages m ON c.id = m.conversation_id AND m.deleted_at IS NULL
            WHERE c.id = $1 AND c.deleted_at IS NULL
            GROUP BY c.id
        """
        return await self.fetch_one(query, conversation_id)

    async def get_conversation_by_user(
        self, conversation_id: int, user_id: int
    ) -> Optional[asyncpg.Record]:
        """Get conversation by ID and user ID."""
        query = """
            SELECT c.*,
                   COUNT(m.id) as message_count,
                   MAX(m.created_at) as last_message_at
            FROM qa_conversations c
            LEFT JOIN qa_messages m ON c.id = m.conversation_id AND m.deleted_at IS NULL
            WHERE c.id = $1 AND c.user_id = $2 AND c.deleted_at IS NULL
            GROUP BY c.id
        """
        return await self.fetch_one(query, conversation_id, user_id)

    async def update_conversation(
        self, conversation_id: int, user_id: int, **kwargs
    ) -> bool:
        """Update conversation."""
        # Build dynamic SET clause
        set_clauses = []
        values = []
        param_index = 1

        for key, value in kwargs.items():
            if key in ["title", "is_pinned", "tags", "metadata"]:
                set_clauses.append(f"{key} = ${param_index}")
                values.append(value)
                param_index += 1

        if not set_clauses:
            return False

        set_clauses.append("updated_at = NOW()")
        values.extend([conversation_id, user_id])

        query = f"""
            UPDATE qa_conversations
            SET {', '.join(set_clauses)}
            WHERE id = ${param_index} AND user_id = ${param_index + 1} AND deleted_at IS NULL
        """

        result = await self.execute(query, *values)
        return "UPDATE" in result

    async def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        """Soft delete conversation."""
        query = """
            UPDATE qa_conversations
            SET deleted_at = NOW(), updated_at = NOW()
            WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
        """
        result = await self.execute(query, conversation_id, user_id)
        return "UPDATE" in result

    async def get_user_conversations(
        self,
        user_id: int,
        skip: int = 0,
        limit: int = 20,
        include_pinned: bool = True,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> List[asyncpg.Record]:
        """Get user conversations with pagination."""
        # CRITICAL FIX: Safe field mapping to prevent SQL injection
        valid_sort_fields = {
            "created_at": "c.created_at",
            "updated_at": "c.updated_at",
            "title": "c.title",
            "message_count": "COUNT(m.id)",
        }
        if sort_by not in valid_sort_fields:
            sort_by = "updated_at"

        # Validate sort_order
        if sort_order not in ["asc", "desc"]:
            sort_order = "desc"

        # Build WHERE clause
        where_conditions = ["c.user_id = $1", "c.deleted_at IS NULL"]
        params = [user_id]
        param_index = 2

        if not include_pinned:
            where_conditions.append("c.is_pinned = FALSE")

        # Build SELECT with message count
        query = f"""
            SELECT c.*,
                   COUNT(m.id) as message_count,
                   MAX(m.created_at) as last_message_at,
                   (
                       SELECT content
                       FROM qa_messages
                       WHERE conversation_id = c.id AND deleted_at IS NULL
                       ORDER BY created_at DESC
                       LIMIT 1
                   ) as last_message_preview
            FROM qa_conversations c
            LEFT JOIN qa_messages m ON c.id = m.conversation_id AND m.deleted_at IS NULL
            WHERE {' AND '.join(where_conditions)}
            GROUP BY c.id
            ORDER BY c.is_pinned DESC, {valid_sort_fields[sort_by]} {sort_order.upper()}
            LIMIT ${param_index} OFFSET ${param_index + 1}
        """
        params.extend([limit, skip])

        return await self.fetch_many(query, *params)

    async def count_user_conversations(
        self, user_id: int, include_pinned: bool = True
    ) -> int:
        """Count total conversations for a user."""
        query = """
            SELECT COUNT(*) as count
            FROM qa_conversations
            WHERE user_id = $1 AND deleted_at IS NULL
        """
        if not include_pinned:
            query += " AND is_pinned = FALSE"

        result = await self.fetch_one(query, user_id)
        return result["count"] if result else 0

    async def pin_conversation(
        self, conversation_id: int, user_id: int, is_pinned: bool = True
    ) -> bool:
        """Pin or unpin a conversation."""
        query = """
            UPDATE qa_conversations
            SET is_pinned = $1, updated_at = NOW()
            WHERE id = $2 AND user_id = $3 AND deleted_at IS NULL
        """
        result = await self.execute(query, is_pinned, conversation_id, user_id)
        return "UPDATE" in result

    async def update_tags(
        self, conversation_id: int, user_id: int, tags: List[str]
    ) -> bool:
        """Update conversation tags."""
        query = """
            UPDATE qa_conversations
            SET tags = $1, updated_at = NOW()
            WHERE id = $2 AND user_id = $3 AND deleted_at IS NULL
        """
        result = await self.execute(query, tags, conversation_id, user_id)
        return "UPDATE" in result

    async def search_conversations(
        self, user_id: int, query_text: str, skip: int = 0, limit: int = 20
    ) -> List[asyncpg.Record]:
        """Search conversations by text content using materialized view."""
        search_query = """
            SELECT c.*,
                   cs.message_count,
                   cs.last_message_at,
                   ts_rank_cd(cs.search_vector, plainto_tsquery('english', $2)) as rank,
                   ts_headline('english', COALESCE(c.title, ''), plainto_tsquery('english', $2)) as title_highlight,
                   ts_headline('english', COALESCE(c.question, ''), plainto_tsquery('english', $2)) as question_highlight
            FROM conversation_search_index cs
            JOIN qa_conversations c ON cs.id = c.id
            WHERE cs.user_id = $1
                AND cs.search_vector @@ plainto_tsquery('english', $2)
            ORDER BY cs.is_pinned DESC, rank DESC, cs.updated_at DESC
            LIMIT $3 OFFSET $4
        """
        return await self.fetch_many(search_query, user_id, query_text, limit, skip)

    async def full_text_search(
        self, user_id: int, query: str, skip: int, limit: int, filters: dict = None
    ) -> Tuple[List[asyncpg.Record], int]:
        """Advanced full-text search with filters and ranking."""
        filters = filters or {}

        # Build WHERE clause
        where_conditions = [
            "cs.user_id = $1",
            "cs.search_vector @@ plainto_tsquery('english', $2)",
        ]
        params = [user_id, query]
        param_index = 3

        # Add tag filter
        if "tags" in filters and filters["tags"]:
            for tag in filters["tags"]:
                where_conditions.append(f"$${param_index} = ANY(cs.tags)")
                params.append(tag)
                param_index += 1

        # Add pinned filter
        if filters.get("pinned_only"):
            where_conditions.append("cs.is_pinned = TRUE")

        # Add date filters
        if filters.get("date_from"):
            where_conditions.append(f"cs.updated_at >= ${param_index}")
            params.append(filters["date_from"])
            param_index += 1

        if filters.get("date_to"):
            where_conditions.append(f"cs.updated_at <= ${param_index}")
            params.append(filters["date_to"])
            param_index += 1

        # CRITICAL FIX: Safe ORDER BY mapping to prevent SQL injection
        sort_by = filters.get("sort_by", "relevance")
        sort_order = filters.get("sort_order", "desc")

        # Safe order clause mapping
        safe_order_clauses = {
            "relevance_desc": "cs.is_pinned DESC, rank DESC, cs.updated_at DESC",
            "relevance_asc": "cs.is_pinned DESC, rank ASC, cs.updated_at ASC",
            "updated_at_desc": "cs.is_pinned DESC, cs.updated_at DESC",
            "updated_at_asc": "cs.is_pinned DESC, cs.updated_at ASC",
            "created_at_desc": "cs.is_pinned DESC, cs.created_at DESC",
            "created_at_asc": "cs.is_pinned DESC, cs.created_at ASC",
            "title_desc": "cs.is_pinned DESC, cs.title DESC",
            "title_asc": "cs.is_pinned DESC, cs.title ASC",
        }

        # Build safe order key
        if sort_by == "relevance":
            order_key = f"relevance_{sort_order}"
        elif sort_by in ["updated_at", "created_at", "title"]:
            order_key = f"{sort_by}_{sort_order}"
        else:
            order_key = "relevance_desc"

        order_clause = safe_order_clauses.get(
            order_key, safe_order_clauses["relevance_desc"]
        )

        # Search query
        search_query = f"""
            SELECT c.*,
                   cs.message_count,
                   cs.last_message_at,
                   ts_rank_cd(cs.search_vector, plainto_tsquery('english', $2)) as rank,
                   ts_headline('english', COALESCE(c.title, ''), plainto_tsquery('english', $2), 'StartSel=<mark>, StopSel=</mark>') as title_highlight,
                   ts_headline('english', COALESCE(c.question, ''), plainto_tsquery('english', $2), 'StartSel=<mark>, StopSel=</mark>') as question_highlight,
                   ts_headline('english', COALESCE(string_agg(m.content, ' '), ''), plainto_tsquery('english', $2), 'StartSel=<mark>, StopSel=</mark>') as content_highlight
            FROM conversation_search_index cs
            JOIN qa_conversations c ON cs.id = c.id
            LEFT JOIN qa_messages m ON c.id = m.conversation_id AND m.deleted_at IS NULL
            WHERE {' AND '.join(where_conditions)}
            GROUP BY c.id, cs.message_count, cs.last_message_at, cs.search_vector
            ORDER BY {order_clause}
            LIMIT ${param_index} OFFSET ${param_index + 1}
        """

        params.extend([limit, skip])
        results = await self.fetch_many(search_query, *params)

        # Count query
        count_query = f"""
            SELECT COUNT(*) as total
            FROM conversation_search_index cs
            WHERE {' AND '.join(where_conditions)}
        """
        count_result = await self.fetch_one(
            count_query, *params[:-2]
        )  # Exclude limit and offset
        total = count_result["total"] if count_result else 0

        return results, total

    async def refresh_search_index(self) -> None:
        """Refresh the materialized view for search."""
        await self.execute(
            "REFRESH MATERIALIZED VIEW CONCURRENTLY conversation_search_index;"
        )

    async def get_search_suggestions(
        self, user_id: int, query: str, limit: int = 5
    ) -> List[str]:
        """Get search suggestions based on conversation titles and content."""
        suggestions_query = """
            SELECT DISTINCT
                   ts_rank_cd(search_vector, plainto_tsquery('english', $2)) as rank,
                   title as suggestion
            FROM conversation_search_index
            WHERE user_id = $1
                AND search_vector @@ plainto_tsquery('english', $2)
                AND title IS NOT NULL
                AND title != ''
            ORDER BY rank DESC
            LIMIT $3
        """
        results = await self.fetch_many(suggestions_query, user_id, query, limit)
        return [result["suggestion"] for result in results]

    async def get_popular_search_terms(
        self, user_id: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get popular search terms for the user (placeholder for future analytics)."""
        # This would typically involve tracking search queries in a separate table
        # For now, return common keywords from conversation titles and content
        popular_query = """
            SELECT
                   ts_rank_cd(search_vector, plainto_tsquery('english', word)) as rank,
                   word as term
            FROM (
                SELECT unnest(string_to_array(regexp_replace(lower(title), '[^a-zA-Z0-9\\s]', '', 'g'), ' ')) as word
                FROM conversation_search_index
                WHERE user_id = $1 AND title IS NOT NULL
            ) words
            WHERE length(word) > 2
            GROUP BY word
            ORDER BY COUNT(*) DESC, rank DESC
            LIMIT $2
        """
        results = await self.fetch_many(popular_query, user_id, limit)
        return [
            {"term": result["term"], "count": 0, "rank": result["rank"]}
            for result in results
        ]

    async def get_user_tags(self, user_id: int) -> List[str]:
        """Get all tags used by a user."""
        tags_query = """
            SELECT DISTINCT tag
            FROM (
                SELECT unnest(tags) as tag
                FROM qa_conversations
                WHERE user_id = $1 AND deleted_at IS NULL AND tags IS NOT NULL
            ) all_tags
            WHERE tag IS NOT NULL AND tag != ''
            ORDER BY tag
        """
        results = await self.fetch_many(tags_query, user_id)
        return [result["tag"] for result in results]

    async def get_conversations_cursor(
        self,
        user_id: int,
        cursor: Optional[str] = None,
        limit: int = 20,
        direction: str = "forward",
        sort_by: str = "updated_at",
        sort_order: str = "desc",
        include_pinned: bool = True,
    ) -> Tuple[List[asyncpg.Record], Optional[str], bool]:
        """Get conversations using cursor-based pagination."""
        import base64
        import json

        # Parse cursor if provided
        cursor_data = None
        if cursor:
            try:
                cursor_data = json.loads(base64.b64decode(cursor).decode())
            except (ValueError, json.JSONDecodeError):
                raise ValueError("Invalid cursor format")

        # Build WHERE clause
        where_conditions = ["c.user_id = $1", "c.deleted_at IS NULL"]
        params = [user_id]
        param_index = 2

        # Add cursor condition
        if cursor_data:
            if direction == "forward":
                if sort_order == "desc":
                    where_conditions.append(f"c.{sort_by} < ${param_index}")
                else:
                    where_conditions.append(f"c.{sort_by} > ${param_index}")
            else:  # backward
                if sort_order == "desc":
                    where_conditions.append(f"c.{sort_by} > ${param_index}")
                else:
                    where_conditions.append(f"c.{sort_by} < ${param_index}")
            params.append(cursor_data.get(sort_by))
            param_index += 1

        # Add pinned filter
        if not include_pinned:
            where_conditions.append("c.is_pinned = FALSE")

        # CRITICAL FIX: Safe ORDER BY mapping for cursor pagination
        safe_cursor_orders = {
            "forward_created_at_desc": "c.is_pinned DESC, c.created_at DESC",
            "forward_created_at_asc": "c.is_pinned DESC, c.created_at ASC",
            "forward_updated_at_desc": "c.is_pinned DESC, c.updated_at DESC",
            "forward_updated_at_asc": "c.is_pinned DESC, c.updated_at ASC",
            "forward_title_desc": "c.is_pinned DESC, c.title DESC",
            "forward_title_asc": "c.is_pinned DESC, c.title ASC",
            "backward_created_at_desc": "c.is_pinned DESC, c.created_at ASC",
            "backward_created_at_asc": "c.is_pinned DESC, c.created_at DESC",
            "backward_updated_at_desc": "c.is_pinned DESC, c.updated_at ASC",
            "backward_updated_at_asc": "c.is_pinned DESC, c.updated_at DESC",
            "backward_title_desc": "c.is_pinned DESC, c.title ASC",
            "backward_title_asc": "c.is_pinned DESC, c.title DESC",
        }

        # Build safe order key
        if direction == "forward":
            order_key = f"forward_{sort_by}_{sort_order}"
        else:  # backward
            reverse_order = "asc" if sort_order == "desc" else "desc"
            order_key = f"backward_{sort_by}_{reverse_order}"

        order_clause = safe_cursor_orders.get(
            order_key, safe_cursor_orders["forward_updated_at_desc"]
        )

        # Build query
        query = f"""
            SELECT c.*,
                   COUNT(m.id) as message_count,
                   MAX(m.created_at) as last_message_at,
                   (
                       SELECT content
                       FROM qa_messages
                       WHERE conversation_id = c.id AND deleted_at IS NULL
                       ORDER BY created_at DESC
                       LIMIT 1
                   ) as last_message_preview
            FROM qa_conversations c
            LEFT JOIN qa_messages m ON c.id = m.conversation_id AND m.deleted_at IS NULL
            WHERE {' AND '.join(where_conditions)}
            GROUP BY c.id
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
            cursor_data = {sort_by: last_item[sort_by]}
            next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

        # If going backward, reverse results to maintain order
        if direction == "backward":
            results.reverse()

        return results, next_cursor, has_more

    async def count_total_conversations(self, user_id: int) -> int:
        """Count total conversations for a user."""
        query = """
            SELECT COUNT(*) as count
            FROM qa_conversations
            WHERE user_id = $1 AND deleted_at IS NULL
        """
        result = await self.fetch_one(query, user_id)
        return result["count"] if result else 0

    async def get_pinned_conversations(self, user_id: int) -> List[asyncpg.Record]:
        """Get all pinned conversations for a user."""
        query = """
            SELECT c.*,
                   COUNT(m.id) as message_count,
                   MAX(m.created_at) as last_message_at,
                   (
                       SELECT content
                       FROM qa_messages
                       WHERE conversation_id = c.id AND deleted_at IS NULL
                       ORDER BY created_at DESC
                       LIMIT 1
                   ) as last_message_preview
            FROM qa_conversations c
            LEFT JOIN qa_messages m ON c.id = m.conversation_id AND m.deleted_at IS NULL
            WHERE c.user_id = $1 AND c.is_pinned = TRUE AND c.deleted_at IS NULL
            GROUP BY c.id
            ORDER BY c.updated_at DESC
        """
        return await self.fetch_many(query, user_id)

    async def get_conversation_with_message_preview(
        self, conversation_id: int, user_id: int
    ) -> Optional[asyncpg.Record]:
        """Get conversation with last message preview."""
        query = """
            SELECT c.*,
                   COUNT(m.id) as message_count,
                   MAX(m.created_at) as last_message_at,
                   (
                       SELECT content
                       FROM qa_messages
                       WHERE conversation_id = c.id AND deleted_at IS NULL
                       ORDER BY created_at DESC
                       LIMIT 1
                   ) as last_message_preview
            FROM qa_conversations c
            LEFT JOIN qa_messages m ON c.id = m.conversation_id AND m.deleted_at IS NULL
            WHERE c.id = $1 AND c.user_id = $2 AND c.deleted_at IS NULL
            GROUP BY c.id
        """
        return await self.fetch_one(query, conversation_id, user_id)

    async def count_search_results(self, user_id: int, query_text: str) -> int:
        """Count search results for a user."""
        search_query = """
            SELECT COUNT(DISTINCT c.id) as count
            FROM qa_conversations c
            LEFT JOIN qa_messages m ON c.id = m.conversation_id AND m.deleted_at IS NULL
            WHERE c.user_id = $1
                AND c.deleted_at IS NULL
                AND (
                    to_tsvector('english', COALESCE(c.title, '') || ' ' || COALESCE(c.question, '')) @@ plainto_tsquery('english', $2)
                    OR EXISTS (
                        SELECT 1 FROM qa_messages m2
                        WHERE m2.conversation_id = c.id
                            AND m2.deleted_at IS NULL
                            AND to_tsvector('english', m2.content) @@ plainto_tsquery('english', $2)
                    )
                )
        """
        result = await self.fetch_one(search_query, user_id, query_text)
        return result["count"] if result else 0
