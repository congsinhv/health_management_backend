"""
Message version service for business logic.
"""

import asyncpg
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import difflib

from app.db.message_version import MessageVersionRepository
from app.db.message import MessageRepository
from app.schemas.message import (
    MessageVersionDetail,
    MessageVersionListResponse,
    MessageVersionCompareResponse,
    MessageVersionRollbackResponse,
)
from app.config import settings

logger = logging.getLogger(__name__)


class MessageVersionService:
    """Service for message version business logic."""

    def __init__(self, pool: asyncpg.Pool, message_repo: MessageRepository = None):
        self.pool = pool
        self.version_repo = MessageVersionRepository(pool)
        self.message_repo = message_repo or MessageRepository(pool)

    async def create_version(
        self,
        message_id: int,
        user_id: int,
        content: str,
        content_cleaned: Optional[str] = None,
        answers: Optional[Dict[str, List[str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Create a new version of a message."""
        try:
            # Verify message exists and user has access
            message = await self.message_repo.get_message_by_user(message_id, user_id)
            if not message:
                raise ValueError("Message not found")

            # Get next version number
            latest_version = await self.version_repo.get_latest_version_number(
                message_id, user_id
            )
            next_version = latest_version + 1

            # Check version limit
            max_versions = getattr(settings, "message_version_limit", 50)
            if next_version > max_versions:
                # Clean up old versions
                await self.cleanup_old_versions(user_id, message_id, max_versions - 10)

            # Create version
            version_id = await self.version_repo.create_version(
                message_id=message_id,
                version_number=next_version,
                content=content,
                content_cleaned=content_cleaned,
                answers=answers,
                metadata=metadata or {},
            )

            return version_id

        except Exception as e:
            logger.error(f"Error creating version for message {message_id}: {e}")
            raise

    async def get_versions(
        self, message_id: int, user_id: int
    ) -> MessageVersionListResponse:
        """Get all versions of a message."""
        try:
            versions = await self.version_repo.get_message_versions(message_id, user_id)
            current_version = await self.version_repo.get_latest_version_number(
                message_id, user_id
            )

            version_details = [
                self._convert_to_version_detail(version) for version in versions
            ]

            return MessageVersionListResponse(
                versions=version_details,
                total=len(version_details),
                current_version=current_version,
            )

        except Exception as e:
            logger.error(f"Error getting versions for message {message_id}: {e}")
            raise

    async def get_version(
        self, message_id: int, version_number: int, user_id: int
    ) -> Optional[MessageVersionDetail]:
        """Get a specific version of a message."""
        try:
            version = await self.version_repo.get_version(
                message_id, version_number, user_id
            )
            if not version:
                return None

            return self._convert_to_version_detail(version)

        except Exception as e:
            logger.error(
                f"Error getting version {version_number} for message {message_id}: {e}"
            )
            raise

    async def rollback_to_version(
        self,
        message_id: int,
        version_number: int,
        user_id: int,
        create_backup_version: bool = True,
    ) -> MessageVersionRollbackResponse:
        """Rollback a message to a specific version."""
        try:
            # Get current message for backup
            current_message = await self.message_repo.get_message_by_user(
                message_id, user_id
            )
            if not current_message:
                raise ValueError("Message not found")

            # Get target version
            target_version = await self.version_repo.get_version(
                message_id, version_number, user_id
            )
            if not target_version:
                raise ValueError("Version not found")

            backup_version_id = None
            if create_backup_version:
                # Create backup of current version
                latest_version = await self.version_repo.get_latest_version_number(
                    message_id, user_id
                )
                backup_version_id = await self.version_repo.create_version(
                    message_id=message_id,
                    version_number=latest_version + 1,
                    content=current_message["content"],
                    content_cleaned=current_message.get("content_cleaned"),
                    answers=current_message.get("answers"),
                    metadata={
                        **(current_message.get("metadata", {}) or {}),
                        "rollback_backup": True,
                        "rollback_backup_at": datetime.now(timezone.utc).isoformat(),
                    },
                )

            # Perform rollback
            success = await self.version_repo.rollback_to_version(
                message_id, version_number, user_id
            )

            if not success:
                raise ValueError("Failed to rollback message")

            # Get updated message
            updated_message = await self.message_repo.get_message_by_user(
                message_id, user_id
            )
            if not updated_message:
                raise ValueError("Failed to retrieve updated message")

            return MessageVersionRollbackResponse(
                rolled_back_message=self._convert_to_message_detail(updated_message),
                rollback_version=version_number,
                backup_version_created=backup_version_id,
            )

        except Exception as e:
            logger.error(
                f"Error rolling back message {message_id} to version {version_number}: {e}"
            )
            raise

    async def compare_versions(
        self, message_id: int, version1: int, version2: int, user_id: int
    ) -> MessageVersionCompareResponse:
        """Compare two versions of a message."""
        try:
            comparison = await self.version_repo.compare_versions(
                message_id, version1, version2, user_id
            )
            if not comparison:
                raise ValueError("Failed to compare versions")

            # Get version details
            v1_detail = await self.get_version(message_id, version1, user_id)
            v2_detail = await self.get_version(message_id, version2, user_id)

            if not v1_detail or not v2_detail:
                raise ValueError("One or both versions not found")

            # Calculate differences
            differences = self._calculate_differences(
                comparison["content_v1"], comparison["content_v2"]
            )

            return MessageVersionCompareResponse(
                version1=v1_detail, version2=v2_detail, differences=differences
            )

        except Exception as e:
            logger.error(f"Error comparing versions for message {message_id}: {e}")
            raise

    async def cleanup_old_versions(
        self, user_id: int, message_id: int, keep_latest: int = 50
    ) -> int:
        """Clean up old versions, keeping only the latest N versions."""
        try:
            return await self.version_repo.cleanup_old_versions(
                user_id, message_id, keep_latest
            )

        except Exception as e:
            logger.error(f"Error cleaning up versions for message {message_id}: {e}")
            raise

    async def get_version_summary(
        self, message_id: int, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get summary of all versions for a message."""
        try:
            summary = await self.version_repo.get_version_summary(message_id, user_id)
            if not summary:
                return None

            return {
                "total_versions": summary["total_versions"],
                "first_version": summary["first_version"],
                "latest_version": summary["latest_version"],
                "first_created": summary["first_created"],
                "latest_created": summary["latest_created"],
            }

        except Exception as e:
            logger.error(f"Error getting version summary for message {message_id}: {e}")
            raise

    async def delete_versions_after(
        self, message_id: int, version_number: int, user_id: int
    ) -> bool:
        """Delete all versions after a specific version."""
        try:
            return await self.version_repo.delete_versions_after(
                message_id, version_number, user_id
            )

        except Exception as e:
            logger.error(
                f"Error deleting versions after {version_number} for message {message_id}: {e}"
            )
            raise

    async def bulk_cleanup_versions(
        self, user_id: int, keep_latest: int = 50
    ) -> Dict[str, Any]:
        """Clean up versions for all messages of a user."""
        try:
            # Get messages that exceed version limit
            messages_to_clean = (
                await self.version_repo.get_all_message_versions_for_cleanup(
                    user_id, keep_latest
                )
            )

            total_cleaned = 0
            errors = []

            for message_data in messages_to_clean:
                try:
                    cleaned = await self.cleanup_old_versions(
                        user_id, message_data["message_id"], keep_latest
                    )
                    total_cleaned += cleaned
                except Exception as e:
                    errors.append(
                        {"message_id": message_data["message_id"], "error": str(e)}
                    )

            return {
                "total_messages_processed": len(messages_to_clean),
                "total_versions_cleaned": total_cleaned,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"Error in bulk cleanup for user {user_id}: {e}")
            raise

    def _convert_to_version_detail(
        self, record: asyncpg.Record
    ) -> MessageVersionDetail:
        """Convert database record to MessageVersionDetail."""
        return MessageVersionDetail(
            id=record["id"],
            message_id=record["message_id"],
            version_number=record["version_number"],
            content=record["content"],
            content_cleaned=record.get("content_cleaned"),
            answers=record.get("answers"),
            metadata=record.get("metadata", {}),
            created_at=record["created_at"],
        )

    def _convert_to_message_detail(self, record: asyncpg.Record):
        """Convert database record to MessageDetail."""
        from app.schemas.message import MessageDetail

        return MessageDetail(
            id=record["id"],
            conversation_id=record["conversation_id"],
            role=record["role"],
            content=record["content"],
            content_cleaned=record.get("content_cleaned"),
            answers=record.get("answers"),
            parent_message_id=record.get("parent_message_id"),
            created_at=record["created_at"],
            updated_at=record.get("updated_at", record["created_at"]),
            deleted_at=record.get("deleted_at"),
            version_count=0,  # Not relevant in this context
            child_count=0,  # Not relevant in this context
            metadata=record.get("metadata", {}),
        )

    def _calculate_differences(self, content1: str, content2: str) -> Dict[str, Any]:
        """Calculate differences between two content strings."""
        try:
            # Use difflib to calculate differences
            lines1 = content1.splitlines(keepends=True)
            lines2 = content2.splitlines(keepends=True)

            differ = difflib.unified_diff(
                lines1, lines2, fromfile="version1", tofile="version2", lineterm=""
            )

            diff_lines = list(differ)

            # Calculate statistics
            added_lines = 0
            removed_lines = 0
            modified_lines = 0

            for line in diff_lines:
                if line.startswith("+") and not line.startswith("+++"):
                    added_lines += 1
                elif line.startswith("-") and not line.startswith("---"):
                    removed_lines += 1

            modified_lines = min(added_lines, removed_lines)
            added_lines -= modified_lines
            removed_lines -= modified_lines

            return {
                "diff": "\n".join(diff_lines),
                "added_lines": added_lines,
                "removed_lines": removed_lines,
                "modified_lines": modified_lines,
                "total_changes": added_lines + removed_lines + modified_lines,
                "similarity": self._calculate_similarity(content1, content2),
            }

        except Exception as e:
            logger.error(f"Error calculating differences: {e}")
            return {
                "diff": "",
                "added_lines": 0,
                "removed_lines": 0,
                "modified_lines": 0,
                "total_changes": 0,
                "similarity": 0.0,
                "error": str(e),
            }

    def _calculate_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity ratio between two content strings."""
        try:
            # Use SequenceMatcher to calculate similarity
            similarity = difflib.SequenceMatcher(None, content1, content2).ratio()
            return round(similarity, 4)

        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0
