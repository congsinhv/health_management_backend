"""
Message version repository for database operations.
"""

import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from app.db.database import BaseRepository


class MessageVersionRepository(BaseRepository):
    """Repository for message version-related database operations."""

    async def create_version(
        self,
        message_id: int,
        version_number: int,
        content: str,
        content_cleaned: Optional[str] = None,
        answers: Optional[Dict[str, List[str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Create a new version of a message."""
        query = """
            INSERT INTO qa_message_versions (
                message_id, version_number, content, content_cleaned,
                answers, metadata, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, NOW())
            RETURNING id
        """
        result = await self.fetch_one(
            query,
            message_id,
            version_number,
            content,
            content_cleaned,
            answers,
            metadata or {},
        )
        return result["id"] if result else None

    async def get_message_versions(
        self, message_id: int, user_id: int
    ) -> List[asyncpg.Record]:
        """Get all versions of a message."""
        query = """
            SELECT v.*
            FROM qa_message_versions v
            JOIN qa_messages m ON v.message_id = m.id
            JOIN qa_conversations c ON m.conversation_id = c.id
            WHERE v.message_id = $1 AND c.user_id = $2
                AND m.deleted_at IS NULL AND c.deleted_at IS NULL
            ORDER BY v.version_number DESC
        """
        return await self.fetch_many(query, message_id, user_id)

    async def get_version(
        self, message_id: int, version_number: int, user_id: int
    ) -> Optional[asyncpg.Record]:
        """Get a specific version of a message."""
        query = """
            SELECT v.*
            FROM qa_message_versions v
            JOIN qa_messages m ON v.message_id = m.id
            JOIN qa_conversations c ON m.conversation_id = c.id
            WHERE v.message_id = $1 AND v.version_number = $2 AND c.user_id = $3
                AND m.deleted_at IS NULL AND c.deleted_at IS NULL
        """
        return await self.fetch_one(query, message_id, version_number, user_id)

    async def get_latest_version_number(self, message_id: int, user_id: int) -> int:
        """Get the latest version number for a message."""
        query = """
            SELECT COALESCE(MAX(v.version_number), 0) as latest_version
            FROM qa_message_versions v
            JOIN qa_messages m ON v.message_id = m.id
            JOIN qa_conversations c ON m.conversation_id = c.id
            WHERE v.message_id = $1 AND c.user_id = $2
                AND m.deleted_at IS NULL AND c.deleted_at IS NULL
        """
        result = await self.fetch_one(query, message_id, user_id)
        return result["latest_version"] if result else 0

    async def rollback_to_version(
        self, message_id: int, version_number: int, user_id: int
    ) -> bool:
        """Rollback a message to a specific version."""
        # Get the version content
        version_query = """
            SELECT v.content, v.content_cleaned, v.answers, v.metadata
            FROM qa_message_versions v
            JOIN qa_messages m ON v.message_id = m.id
            JOIN qa_conversations c ON m.conversation_id = c.id
            WHERE v.message_id = $1 AND v.version_number = $2 AND c.user_id = $3
                AND m.deleted_at IS NULL AND c.deleted_at IS NULL
        """
        version_result = await self.fetch_one(
            version_query, message_id, version_number, user_id
        )
        if not version_result:
            return False

        # Get the next version number
        next_version = await self.get_latest_version_number(message_id, user_id) + 1

        # Create a new version with the old content (preserve history)
        await self.create_version(
            message_id=message_id,
            version_number=next_version,
            content=version_result["content"],
            content_cleaned=version_result["content_cleaned"],
            answers=version_result["answers"],
            metadata={
                **(version_result["metadata"] or {}),
                "rollback_from_version": version_number,
                "rollback_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Update the current message
        update_query = """
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
            update_query,
            version_result["content"],
            version_result["content_cleaned"],
            version_result["answers"],
            version_result["metadata"],
            message_id,
            user_id,
        )
        return "UPDATE" in result

    async def compare_versions(
        self, message_id: int, version1: int, version2: int, user_id: int
    ) -> Optional[asyncpg.Record]:
        """Compare two versions of a message."""
        query = """
            SELECT
                v1.content as content_v1,
                v1.content_cleaned as content_cleaned_v1,
                v1.answers as answers_v1,
                v1.metadata as metadata_v1,
                v1.created_at as created_at_v1,
                v2.content as content_v2,
                v2.content_cleaned as content_cleaned_v2,
                v2.answers as answers_v2,
                v2.metadata as metadata_v2,
                v2.created_at as created_at_v2
            FROM qa_message_versions v1
            JOIN qa_message_versions v2 ON v1.message_id = v2.message_id
            JOIN qa_messages m ON v1.message_id = m.id
            JOIN qa_conversations c ON m.conversation_id = c.id
            WHERE v1.message_id = $1
                AND v1.version_number = $2
                AND v2.version_number = $3
                AND c.user_id = $4
                AND m.deleted_at IS NULL
                AND c.deleted_at IS NULL
        """
        return await self.fetch_one(query, message_id, version1, version2, user_id)

    async def get_version_with_metadata(
        self, message_id: int, version_number: int, user_id: int
    ) -> Optional[asyncpg.Record]:
        """Get version with additional metadata."""
        query = """
            SELECT v.*,
                   m.conversation_id,
                   m.role,
                   c.user_id,
                   (
                       SELECT COUNT(*) - 1
                       FROM qa_message_versions v2
                       WHERE v2.message_id = v.message_id
                           AND v2.version_number > v.version_number
                   ) as versions_after
            FROM qa_message_versions v
            JOIN qa_messages m ON v.message_id = m.id
            JOIN qa_conversations c ON m.conversation_id = c.id
            WHERE v.message_id = $1 AND v.version_number = $2 AND c.user_id = $3
                AND m.deleted_at IS NULL AND c.deleted_at IS NULL
        """
        return await self.fetch_one(query, message_id, version_number, user_id)

    async def delete_versions_after(
        self, message_id: int, version_number: int, user_id: int
    ) -> bool:
        """Delete all versions after a specific version."""
        query = """
            DELETE FROM qa_message_versions
            WHERE id IN (
                SELECT v.id
                FROM qa_message_versions v
                JOIN qa_messages m ON v.message_id = m.id
                JOIN qa_conversations c ON m.conversation_id = c.id
                WHERE v.message_id = $1
                    AND v.version_number > $2
                    AND c.user_id = $3
                    AND m.deleted_at IS NULL
                    AND c.deleted_at IS NULL
            )
        """
        result = await self.execute(query, message_id, version_number, user_id)
        return "DELETE" in result

    async def get_all_message_versions_for_cleanup(
        self, user_id: int, limit_per_message: int = 50
    ) -> List[asyncpg.Record]:
        """Get versions that exceed the limit for cleanup."""
        query = """
            WITH version_counts AS (
                SELECT
                    v.message_id,
                    COUNT(*) as total_versions,
                    ARRAY_AGG(v.version_number ORDER BY v.version_number DESC) as all_versions
                FROM qa_message_versions v
                JOIN qa_messages m ON v.message_id = m.id
                JOIN qa_conversations c ON m.conversation_id = c.id
                WHERE c.user_id = $1
                    AND m.deleted_at IS NULL
                    AND c.deleted_at IS NULL
                GROUP BY v.message_id
                HAVING COUNT(*) > $2
            )
            SELECT
                v.message_id,
                v.version_number,
                v.created_at,
                vc.total_versions,
                ARRAY_POSITION(vc.all_versions, v.version_number) as position_from_latest
            FROM qa_message_versions v
            JOIN version_counts vc ON v.message_id = vc.message_id
            WHERE ARRAY_POSITION(vc.all_versions, v.version_number) > $2
            ORDER BY v.message_id, v.version_number DESC
        """
        return await self.fetch_many(query, user_id, limit_per_message)

    async def cleanup_old_versions(
        self,
        user_id: int,
        message_id: int,
        keep_latest: int = 50,
    ) -> int:
        """Clean up old versions, keeping only the latest N versions."""
        query = """
            DELETE FROM qa_message_versions
            WHERE id IN (
                SELECT v.id
                FROM (
                    SELECT v.id,
                           ROW_NUMBER() OVER (PARTITION BY v.message_id ORDER BY v.version_number DESC) as rn
                    FROM qa_message_versions v
                    JOIN qa_messages m ON v.message_id = m.id
                    JOIN qa_conversations c ON m.conversation_id = c.id
                    WHERE v.message_id = $1
                        AND c.user_id = $2
                        AND m.deleted_at IS NULL
                        AND c.deleted_at IS NULL
                ) v
                WHERE v.rn > $3
            )
        """
        result = await self.execute(query, message_id, user_id, keep_latest)
        # Extract number of deleted rows from result
        if "DELETE" in result:
            # Parse result to get count, e.g., "DELETE 5"
            parts = result.split()
            return int(parts[1]) if len(parts) > 1 else 0
        return 0

    async def get_version_summary(
        self, message_id: int, user_id: int
    ) -> Optional[asyncpg.Record]:
        """Get summary of all versions for a message."""
        query = """
            SELECT
                COUNT(*) as total_versions,
                MIN(v.version_number) as first_version,
                MAX(v.version_number) as latest_version,
                MIN(v.created_at) as first_created,
                MAX(v.created_at) as latest_created
            FROM qa_message_versions v
            JOIN qa_messages m ON v.message_id = m.id
            JOIN qa_conversations c ON m.conversation_id = c.id
            WHERE v.message_id = $1 AND c.user_id = $2
                AND m.deleted_at IS NULL AND c.deleted_at IS NULL
        """
        return await self.fetch_one(query, message_id, user_id)
