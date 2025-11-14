"""
Message version repository for edit history tracking.
"""

from typing import Optional, List, Dict, Any
import asyncpg

from app.db.database import BaseRepository


class MessageVersionRepository(BaseRepository):
    """Repository for message version database operations."""

    async def create(self, data: Dict[str, Any]) -> Optional[asyncpg.Record]:
        """Create a new message version."""
        query = """
            INSERT INTO message_versions (message_id, version_number, content, metadata, user_id)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """
        return await self.fetch_one(
            query,
            data["message_id"],
            data["version_number"],
            data["content"],
            data.get("metadata", {}),
            data["user_id"],
        )

    async def list_by_message(self, message_id: int) -> List[asyncpg.Record]:
        """List all versions of a message."""
        query = """
            SELECT * FROM message_versions
            WHERE message_id = $1
            ORDER BY version_number DESC
        """
        return await self.fetch_many(query, message_id)

    async def get_latest_version_number(self, message_id: int) -> int:
        """Get the latest version number for a message."""
        query = """
            SELECT COALESCE(MAX(version_number), 0)
            FROM message_versions
            WHERE message_id = $1
        """
        result = await self.fetch_one(query, message_id)
        return result["coalesce"] if result else 0

    async def get_by_version(
        self, message_id: int, version_number: int
    ) -> Optional[asyncpg.Record]:
        """Get a specific version of a message."""
        query = """
            SELECT * FROM message_versions
            WHERE message_id = $1 AND version_number = $2
        """
        return await self.fetch_one(query, message_id, version_number)

    async def count_versions(self, message_id: int) -> int:
        """Count total versions for a message."""
        query = """
            SELECT COUNT(*) FROM message_versions
            WHERE message_id = $1
        """
        result = await self.fetch_one(query, message_id)
        return result["count"] if result else 0

    async def get_versions_by_user(
        self, message_id: int, user_id: int
    ) -> List[asyncpg.Record]:
        """Get versions of a message edited by a specific user."""
        query = """
            SELECT * FROM message_versions
            WHERE message_id = $1 AND user_id = $2
            ORDER BY version_number DESC
        """
        return await self.fetch_many(query, message_id, user_id)

    async def get_latest_version(self, message_id: int) -> Optional[asyncpg.Record]:
        """Get the latest version of a message."""
        query = """
            SELECT * FROM message_versions
            WHERE message_id = $1
            ORDER BY version_number DESC
            LIMIT 1
        """
        return await self.fetch_one(query, message_id)

    async def get_version_history_summary(
        self, message_id: int, limit: int = 10
    ) -> List[asyncpg.Record]:
        """Get version history summary with user information."""
        query = """
            SELECT mv.*, u.email as editor_email, up.first_name, up.last_name
            FROM message_versions mv
            LEFT JOIN users u ON mv.user_id = u.id
            LEFT JOIN user_profiles up ON mv.user_id = up.user_id
            WHERE mv.message_id = $1
            ORDER BY mv.version_number DESC
            LIMIT $2
        """
        return await self.fetch_many(query, message_id, limit)

    async def restore_version(
        self, message_id: int, version_number: int, user_id: int
    ) -> Optional[asyncpg.Record]:
        """Restore a message to a specific version."""
        # Get the version to restore
        version = await self.get_by_version(message_id, version_number)
        if not version:
            return None

        # Update the message with the version content
        query = """
            UPDATE messages
            SET content = $1, metadata = $2, updated_at = NOW()
            WHERE id = $3 AND deleted_at IS NULL
            RETURNING *
        """
        return await self.fetch_one(
            query, version["content"], version["metadata"], message_id
        )

    async def delete_versions_for_message(self, message_id: int) -> bool:
        """Delete all versions for a message."""
        query = """
            DELETE FROM message_versions
            WHERE message_id = $1
        """
        result = await self.execute(query, message_id)
        return True  # Always return True, even if no versions were deleted
