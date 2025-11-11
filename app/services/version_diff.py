"""
Version comparison and diff service for message versions.
"""

import difflib
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import json

import asyncpg
from app.db.database import BaseRepository
from app.db.message_version import MessageVersionRepository

logger = logging.getLogger(__name__)


class VersionDiffService:
    """Service for comparing message versions and generating diffs."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.version_repo = MessageVersionRepository(pool)

    async def compare_versions(
        self,
        message_id: int,
        user_id: int,
        from_version: Optional[int] = None,
        to_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Compare two versions of a message."""
        try:
            # Get version history
            versions = await self.version_repo.get_version_history(message_id, user_id)

            if len(versions) < 2:
                raise ValueError("Not enough versions to compare")

            # Determine which versions to compare
            if from_version is None:
                from_version = (
                    versions[-2]["version_number"]
                    if len(versions) >= 2
                    else versions[0]["version_number"]
                )
            if to_version is None:
                to_version = versions[-1]["version_number"]

            # Get the specific versions
            from_version_data = next(
                (v for v in versions if v["version_number"] == from_version), None
            )
            to_version_data = next(
                (v for v in versions if v["version_number"] == to_version), None
            )

            if not from_version_data or not to_version_data:
                raise ValueError("One or both versions not found")

            # Generate diff
            content_diff = self._generate_text_diff(
                from_version_data["content"], to_version_data["content"]
            )

            # Compare cleaned content if available
            content_cleaned_diff = None
            if from_version_data.get("content_cleaned") and to_version_data.get(
                "content_cleaned"
            ):
                content_cleaned_diff = self._generate_text_diff(
                    from_version_data["content_cleaned"],
                    to_version_data["content_cleaned"],
                )

            # Compare answers if available
            answers_diff = None
            if from_version_data.get("answers") and to_version_data.get("answers"):
                answers_diff = self._compare_answers(
                    from_version_data["answers"], to_version_data["answers"]
                )

            # Compare metadata
            metadata_diff = self._compare_metadata(
                from_version_data.get("metadata", {}),
                to_version_data.get("metadata", {}),
            )

            return {
                "message_id": message_id,
                "from_version": from_version,
                "to_version": to_version,
                "from_timestamp": from_version_data["created_at"],
                "to_timestamp": to_version_data["created_at"],
                "content_diff": content_diff,
                "content_cleaned_diff": content_cleaned_diff,
                "answers_diff": answers_diff,
                "metadata_diff": metadata_diff,
                "changes_summary": self._summarize_changes(
                    from_version_data, to_version_data
                ),
            }

        except Exception as e:
            logger.error(f"Error comparing versions: {e}")
            raise

    async def get_version_timeline(
        self, message_id: int, user_id: int
    ) -> List[Dict[str, Any]]:
        """Get a timeline of all versions with change summaries."""
        try:
            versions = await self.version_repo.get_version_history(message_id, user_id)

            timeline = []
            for i, version in enumerate(versions):
                # Calculate changes from previous version
                changes = {}
                if i > 0:
                    prev_version = versions[i - 1]
                    changes = self._calculate_changes(prev_version, version)

                timeline.append(
                    {
                        "version_number": version["version_number"],
                        "created_at": version["created_at"],
                        "changes_from_previous": changes,
                        "content_preview": (
                            version["content"][:100] + "..."
                            if len(version["content"]) > 100
                            else version["content"]
                        ),
                        "has_answers": bool(version.get("answers")),
                        "metadata_keys": list(version.get("metadata", {}).keys()),
                    }
                )

            return timeline

        except Exception as e:
            logger.error(f"Error getting version timeline: {e}")
            raise

    async def restore_version(
        self,
        message_id: int,
        version_number: int,
        user_id: int,
        create_backup: bool = True,
    ) -> Dict[str, Any]:
        """Restore a message to a specific version."""
        try:
            # Get the version to restore
            version_data = await self.version_repo.get_version(
                message_id, version_number, user_id
            )
            if not version_data:
                raise ValueError("Version not found")

            # Get current message for backup
            from app.db.message import MessageRepository

            message_repo = MessageRepository(self.pool)
            current_message = await message_repo.get_message_by_user(
                message_id, user_id
            )

            if create_backup and current_message:
                # Create a backup of current state before restoring
                await self.version_repo.create_version(
                    message_id=message_id,
                    version_number=await self.version_repo.get_latest_version_number(
                        message_id, user_id
                    )
                    + 1,
                    content=current_message["content"],
                    content_cleaned=current_message.get("content_cleaned"),
                    answers=current_message.get("answers"),
                    metadata=current_message.get("metadata", {}),
                    change_reason="Auto-backup before version restore",
                )

            # Update message with version data
            success = await message_repo.update_message(
                message_id,
                user_id,
                version_data["content"],
                version_data.get("content_cleaned"),
                version_data.get("answers"),
                version_data.get("metadata", {}),
            )

            if not success:
                raise ValueError("Failed to restore version")

            # Create a new version tracking the restore
            await self.version_repo.create_version(
                message_id=message_id,
                version_number=await self.version_repo.get_latest_version_number(
                    message_id, user_id
                )
                + 1,
                content=version_data["content"],
                content_cleaned=version_data.get("content_cleaned"),
                answers=version_data.get("answers"),
                metadata={
                    **(version_data.get("metadata", {})),
                    "restored_from_version": version_number,
                    "restored_at": datetime.now(timezone.utc).isoformat(),
                },
                change_reason=f"Restored from version {version_number}",
            )

            return {
                "message_id": message_id,
                "restored_version": version_number,
                "restored_at": datetime.now(timezone.utc),
                "backup_created": create_backup and current_message is not None,
            }

        except Exception as e:
            logger.error(f"Error restoring version: {e}")
            raise

    def _generate_text_diff(self, old_text: str, new_text: str) -> Dict[str, Any]:
        """Generate a detailed diff between two text strings."""
        # Generate unified diff
        diff_lines = list(
            difflib.unified_diff(
                old_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile="old",
                tofile="new",
                lineterm="",
            )
        )

        # Generate HTML diff for better visualization
        differ = difflib.HtmlDiff()
        html_diff = differ.make_file(
            old_text.splitlines(),
            new_text.splitlines(),
            fromdesc="Old Version",
            todesc="New Version",
            context=True,
            numlines=3,
        )

        # Calculate change statistics
        old_lines = old_text.splitlines()
        new_lines = new_text.splitlines()
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)

        additions = 0
        deletions = 0
        modifications = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "replace":
                modifications += max(i2 - i1, j2 - j1)
            elif tag == "delete":
                deletions += i2 - i1
            elif tag == "insert":
                additions += j2 - j1

        return {
            "unified_diff": "".join(diff_lines),
            "html_diff": html_diff,
            "statistics": {
                "additions": additions,
                "deletions": deletions,
                "modifications": modifications,
                "total_changes": additions + deletions + modifications,
            },
            "similarity_ratio": difflib.SequenceMatcher(
                None, old_text, new_text
            ).ratio(),
        }

    def _compare_answers(
        self, old_answers: Dict[str, List[str]], new_answers: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """Compare answer dictionaries."""
        all_fields = set(old_answers.keys()) | set(new_answers.keys())
        changes = {}

        for field in all_fields:
            old_list = old_answers.get(field, [])
            new_list = new_answers.get(field, [])

            if old_list != new_list:
                # Find added and removed answers
                added = [ans for ans in new_list if ans not in old_list]
                removed = [ans for ans in old_list if ans not in new_list]

                changes[field] = {
                    "added": added,
                    "removed": removed,
                    "old_count": len(old_list),
                    "new_count": len(new_list),
                }

        return {
            "changed_fields": list(changes.keys()),
            "field_changes": changes,
            "has_changes": len(changes) > 0,
        }

    def _compare_metadata(
        self, old_metadata: Dict[str, Any], new_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare metadata dictionaries."""
        all_keys = set(old_metadata.keys()) | set(new_metadata.keys())
        changes = {}

        for key in all_keys:
            old_value = old_metadata.get(key)
            new_value = new_metadata.get(key)

            if old_value != new_value:
                changes[key] = {
                    "old": old_value,
                    "new": new_value,
                    "type": (
                        type(old_value).__name__
                        if old_value
                        else type(new_value).__name__
                    ),
                }

        return {
            "changed_keys": list(changes.keys()),
            "key_changes": changes,
            "has_changes": len(changes) > 0,
        }

    def _summarize_changes(
        self, from_version: asyncpg.Record, to_version: asyncpg.Record
    ) -> Dict[str, Any]:
        """Create a summary of changes between versions."""
        summary = {
            "content_changed": from_version["content"] != to_version["content"],
            "cleaned_content_changed": False,
            "answers_changed": False,
            "metadata_changed": False,
            "major_changes": [],
            "minor_changes": [],
        }

        # Check cleaned content
        if (from_version.get("content_cleaned") or "") != (
            to_version.get("content_cleaned") or ""
        ):
            summary["cleaned_content_changed"] = True

        # Check answers
        if (from_version.get("answers") or {}) != (to_version.get("answers") or {}):
            summary["answers_changed"] = True

        # Check metadata
        if (from_version.get("metadata") or {}) != (to_version.get("metadata") or {}):
            summary["metadata_changed"] = True

        # Determine significance of changes
        content_similarity = difflib.SequenceMatcher(
            None, from_version["content"], to_version["content"]
        ).ratio()

        if content_similarity < 0.5:
            summary["major_changes"].append("Significant content modification")
        elif content_similarity < 0.9:
            summary["minor_changes"].append("Minor content modification")

        if summary["answers_changed"]:
            summary["major_changes"].append("Answers modified")

        if summary["metadata_changed"]:
            summary["minor_changes"].append("Metadata updated")

        return summary

    def _calculate_changes(
        self, prev_version: asyncpg.Record, current_version: asyncpg.Record
    ) -> Dict[str, Any]:
        """Calculate changes between consecutive versions."""
        changes = {
            "content_modified": prev_version["content"] != current_version["content"],
            "answers_modified": (prev_version.get("answers") or {})
            != (current_version.get("answers") or {}),
            "metadata_modified": (prev_version.get("metadata") or {})
            != (current_version.get("metadata") or {}),
            "change_reason": current_version.get("change_reason"),
        }

        # Calculate content similarity
        if changes["content_modified"]:
            similarity = difflib.SequenceMatcher(
                None, prev_version["content"], current_version["content"]
            ).ratio()
            changes["content_similarity"] = round(similarity, 3)

        return changes

    async def export_versions(
        self, message_id: int, user_id: int, format: str = "json"
    ) -> Dict[str, Any]:
        """Export all versions of a message in various formats."""
        try:
            versions = await self.version_repo.get_version_history(message_id, user_id)

            export_data = {
                "message_id": message_id,
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "total_versions": len(versions),
                "versions": [],
            }

            for version in versions:
                version_data = {
                    "version_number": version["version_number"],
                    "created_at": version["created_at"].isoformat(),
                    "content": version["content"],
                    "content_cleaned": version.get("content_cleaned"),
                    "answers": version.get("answers"),
                    "metadata": version.get("metadata", {}),
                    "change_reason": version.get("change_reason"),
                }
                export_data["versions"].append(version_data)

            if format.lower() == "json":
                return export_data
            else:
                # For other formats, you could implement CSV, XML, etc.
                raise ValueError(f"Export format '{format}' not supported")

        except Exception as e:
            logger.error(f"Error exporting versions: {e}")
            raise
