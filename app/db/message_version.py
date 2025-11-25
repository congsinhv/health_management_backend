"""
Message version repository for edit history tracking with custom exception handling.
"""

import json
from typing import Optional, List, Dict, Any
import asyncpg

from app.db.database import BaseRepository
from app.exceptions import (
    ResourceNotFoundException,
    DatabaseException,
    DatabaseConstraintException,
)


class MessageVersionRepository(BaseRepository):
    """Repository for message version database operations."""

    async def create_message_version(self, data: Dict[str, Any]) -> asyncpg.Record:
        """Create a new message version."""
        query = """
            INSERT INTO message_versions (message_id, version_number, content, metadata, user_id)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
        """
        try:
            result = await self.fetch_one(
                query,
                data["message_id"],
                data["version_number"],
                data["content"],
                json.dumps(data.get("metadata", {})),
                data["user_id"],
            )
            if not result:
                raise DatabaseException(
                    message="Failed to create message version",
                    details={
                        "message_id": data["message_id"],
                        "version_number": data["version_number"],
                        "user_id": data["user_id"],
                    },
                )
            return result
        except asyncpg.ForeignKeyViolationError as e:
            if "message_id" in str(e):
                raise ResourceNotFoundException(
                    message="Message not found for version creation",
                    details={
                        "message_id": data["message_id"],
                        "version_number": data["version_number"],
                        "user_id": data["user_id"],
                        "constraint": str(e),
                    },
                )
            elif "user_id" in str(e):
                raise ResourceNotFoundException(
                    message="User not found for version creation",
                    details={
                        "message_id": data["message_id"],
                        "version_number": data["version_number"],
                        "user_id": data["user_id"],
                        "constraint": str(e),
                    },
                )
            else:
                raise DatabaseException(
                    message="Foreign key violation while creating message version",
                    details={
                        "message_id": data["message_id"],
                        "version_number": data["version_number"],
                        "user_id": data["user_id"],
                        "constraint": str(e),
                    },
                )
        except asyncpg.UniqueViolationError as e:
            raise DatabaseConstraintException(
                message="Message version already exists",
                details={
                    "message_id": data["message_id"],
                    "version_number": data["version_number"],
                    "user_id": data["user_id"],
                    "constraint": str(e),
                },
            )
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while creating message version",
                details={
                    "message_id": data["message_id"],
                    "version_number": data["version_number"],
                    "user_id": data["user_id"],
                    "error": str(e),
                },
            )

    async def list_message_versions(self, message_id: int) -> List[asyncpg.Record]:
        """List all versions of a message."""
        query = """
            SELECT * FROM message_versions
            WHERE message_id = $1
            ORDER BY version_number DESC
        """
        try:
            return await self.fetch_many(query, message_id)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while listing message versions",
                details={"message_id": message_id, "error": str(e)},
            )

    async def get_latest_version_number(self, message_id: int) -> int:
        """Get the latest version number for a message."""
        query = """
            SELECT COALESCE(MAX(version_number), 0)
            FROM message_versions
            WHERE message_id = $1
        """
        try:
            result = await self.fetch_one(query, message_id)
            return result["coalesce"] if result else 0
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while getting latest version number",
                details={"message_id": message_id, "error": str(e)},
            )

    async def get_message_version(
        self, message_id: int, version_number: int
    ) -> asyncpg.Record:
        """Get a specific version of a message."""
        query = """
            SELECT * FROM message_versions
            WHERE message_id = $1 AND version_number = $2
        """
        try:
            result = await self.fetch_one(query, message_id, version_number)
            if not result:
                raise ResourceNotFoundException(
                    message="Message version not found",
                    details={
                        "message_id": message_id,
                        "version_number": version_number,
                    },
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching message version",
                details={
                    "message_id": message_id,
                    "version_number": version_number,
                    "error": str(e),
                },
            )

    async def count_versions(self, message_id: int) -> int:
        """Count total versions for a message."""
        query = """
            SELECT COUNT(*) FROM message_versions
            WHERE message_id = $1
        """
        try:
            result = await self.fetch_one(query, message_id)
            return result["count"] if result else 0
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while counting message versions",
                details={"message_id": message_id, "error": str(e)},
            )

    async def get_versions_by_user(
        self, message_id: int, user_id: int
    ) -> List[asyncpg.Record]:
        """Get versions of a message edited by a specific user."""
        query = """
            SELECT * FROM message_versions
            WHERE message_id = $1 AND user_id = $2
            ORDER BY version_number DESC
        """
        try:
            return await self.fetch_many(query, message_id, user_id)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while getting versions by user",
                details={"message_id": message_id, "user_id": user_id, "error": str(e)},
            )

    async def get_latest_version(self, message_id: int) -> Optional[asyncpg.Record]:
        """Get the latest version of a message."""
        query = """
            SELECT * FROM message_versions
            WHERE message_id = $1
            ORDER BY version_number DESC
            LIMIT 1
        """
        try:
            return await self.fetch_one(query, message_id)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while getting latest version",
                details={"message_id": message_id, "error": str(e)},
            )

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
        try:
            return await self.fetch_many(query, message_id, limit)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while getting version history summary",
                details={"message_id": message_id, "limit": limit, "error": str(e)},
            )

    async def restore_version(
        self, message_id: int, version_number: int, user_id: int
    ) -> asyncpg.Record:
        """Restore a message to a specific version."""
        try:
            # Get the version to restore
            version = await self.get_message_version(message_id, version_number)

            # Update the message with the version content
            query = """
                UPDATE messages
                SET content = $1, metadata = $2, updated_at = NOW()
                WHERE id = $3 AND deleted_at IS NULL
                RETURNING *
            """
            result = await self.fetch_one(
                query, version["content"], version["metadata"], message_id
            )
            if not result:
                raise ResourceNotFoundException(
                    message="Message not found for version restore",
                    details={
                        "message_id": message_id,
                        "version_number": version_number,
                        "user_id": user_id,
                    },
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while restoring version",
                details={
                    "message_id": message_id,
                    "version_number": version_number,
                    "user_id": user_id,
                    "error": str(e),
                },
            )

    async def delete_versions_for_message(self, message_id: int) -> bool:
        """Delete all versions for a message."""
        query = """
            DELETE FROM message_versions
            WHERE message_id = $1
        """
        try:
            await self.execute(query, message_id)
            return True  # Always return True, even if no versions were deleted
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while deleting message versions",
                details={"message_id": message_id, "error": str(e)},
            )
