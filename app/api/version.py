"""
API endpoints for message version comparison and management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
import logging

import asyncpg
from app.db.database import get_database_pool
from app.services.version_diff import VersionDiffService
from app.services.message_version import MessageVersionService
from app.services.message import MessageService
from app.services.cache import conversation_cache
from app.auth.dependencies import get_current_active_user
from app.schemas.version import (
    VersionComparisonResponse,
    VersionTimelineResponse,
    VersionRestoreResponse,
    VersionExportResponse,
    VersionListResponse,
    VersionDetailResponse,
    VersionRestore,
    VersionExport,
)
from app.schemas.base import StandardResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/message/{message_id}/versions", response_model=VersionListResponse)
async def get_message_versions(
    message_id: int,
    current_user=Depends(get_current_active_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Get all versions of a message."""
    try:
        version_service = MessageVersionService(pool)
        versions = await version_service.get_version_history(
            message_id, current_user.id
        )

        return VersionListResponse(
            success=True,
            message="Versions retrieved successfully",
            versions=[dict(v) for v in versions],
            message_id=message_id,
            total_versions=len(versions),
        )

    except Exception as e:
        logger.error(f"Failed to retrieve message versions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve message versions",
        )


@router.get(
    "/message/{message_id}/versions/{version_number}",
    response_model=VersionDetailResponse,
)
async def get_version_detail(
    message_id: int,
    version_number: int,
    current_user=Depends(get_current_active_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Get detailed information about a specific version."""
    try:
        version_service = MessageVersionService(pool)
        version = await version_service.get_version(
            message_id, version_number, current_user.id
        )

        if not version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Version not found"
            )

        # Check if this is the current version
        message_service = MessageService(pool)
        current_message = await message_service.get_message(message_id, current_user.id)
        is_current = (
            current_message
            and current_message.content == version["content"]
            and current_message.content_cleaned == version.get("content_cleaned")
            and current_message.answers == version.get("answers")
        )

        version_detail = {
            "version_number": version["version_number"],
            "created_at": version["created_at"],
            "content": version["content"],
            "content_cleaned": version.get("content_cleaned"),
            "answers": version.get("answers"),
            "metadata": version.get("metadata", {}),
            "change_reason": version.get("change_reason"),
            "is_current": is_current,
        }

        return VersionDetailResponse(
            success=True,
            message="Version detail retrieved successfully",
            version=version_detail,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve version detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve version detail",
        )


@router.get(
    "/message/{message_id}/versions/compare", response_model=VersionComparisonResponse
)
async def compare_versions(
    message_id: int,
    from_version: Optional[int] = Query(None, description="Source version number"),
    to_version: Optional[int] = Query(None, description="Target version number"),
    current_user=Depends(get_current_active_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Compare two versions of a message."""
    try:
        diff_service = VersionDiffService(pool)
        comparison = await diff_service.compare_versions(
            message_id, current_user.id, from_version, to_version
        )

        return VersionComparisonResponse(
            success=True,
            message="Versions compared successfully",
            comparison=comparison,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to compare versions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare versions",
        )


@router.get(
    "/message/{message_id}/versions/timeline", response_model=VersionTimelineResponse
)
async def get_version_timeline(
    message_id: int,
    current_user=Depends(get_current_active_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Get a timeline of all versions with change summaries."""
    try:
        diff_service = VersionDiffService(pool)
        timeline = await diff_service.get_version_timeline(message_id, current_user.id)

        return VersionTimelineResponse(
            success=True,
            message="Version timeline retrieved successfully",
            timeline=timeline,
            total_versions=len(timeline),
        )

    except Exception as e:
        logger.error(f"Failed to retrieve version timeline: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve version timeline",
        )


@router.post(
    "/message/{message_id}/versions/restore", response_model=VersionRestoreResponse
)
async def restore_version(
    message_id: int,
    restore_data: VersionRestore,
    current_user=Depends(get_current_active_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Restore a message to a specific version."""
    try:
        diff_service = VersionDiffService(pool)
        restore_result = await diff_service.restore_version(
            message_id,
            restore_data.version_number,
            current_user.id,
            restore_data.create_backup,
        )

        # Invalidate cache for the conversation
        conversation_id = await pool.fetchval(
            "SELECT conversation_id FROM qa_messages WHERE id = $1", message_id
        )
        if conversation_id:
            conversation_cache.invalidate_conversation_cache(conversation_id)

        return VersionRestoreResponse(
            success=True,
            message="Version restored successfully",
            restore_result=restore_result,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to restore version: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore version",
        )


@router.post(
    "/message/{message_id}/versions/export", response_model=VersionExportResponse
)
async def export_versions(
    message_id: int,
    export_data: VersionExport,
    current_user=Depends(get_current_active_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Export all versions of a message."""
    try:
        diff_service = VersionDiffService(pool)
        export_data_result = await diff_service.export_versions(
            message_id, current_user.id, export_data.format
        )

        return VersionExportResponse(
            success=True,
            message="Versions exported successfully",
            export_data=export_data_result,
            format=export_data.format,
            exported_at="now",
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to export versions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export versions",
        )


@router.delete("/message/{message_id}/versions", response_model=StandardResponse[str])
async def delete_version_history(
    message_id: int,
    confirm: bool = Query(False, description="Must be true to delete version history"),
    keep_current: bool = Query(True, description="Keep current version as version 1"),
    current_user=Depends(get_current_active_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Delete version history for a message (dangerous operation)."""
    try:
        if not confirm:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must confirm deletion by setting confirm=true",
            )

        version_service = MessageVersionService(pool)
        deleted_count = await version_service.delete_version_history(
            message_id, current_user.id, keep_current
        )

        # Invalidate cache for the conversation
        conversation_id = await pool.fetchval(
            "SELECT conversation_id FROM qa_messages WHERE id = $1", message_id
        )
        if conversation_id:
            conversation_cache.invalidate_conversation_cache(conversation_id)

        return StandardResponse.success(
            data=f"Deleted {deleted_count} versions from history"
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete version history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete version history",
        )


@router.get(
    "/message/{message_id}/versions/latest", response_model=VersionDetailResponse
)
async def get_latest_version(
    message_id: int,
    current_user=Depends(get_current_active_user),
    pool: asyncpg.Pool = Depends(get_database_pool),
):
    """Get the latest version of a message."""
    try:
        version_service = MessageVersionService(pool)
        latest_version = await version_service.get_latest_version(
            message_id, current_user.id
        )

        if not latest_version:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No versions found"
            )

        version_detail = {
            "version_number": latest_version["version_number"],
            "created_at": latest_version["created_at"],
            "content": latest_version["content"],
            "content_cleaned": latest_version.get("content_cleaned"),
            "answers": latest_version.get("answers"),
            "metadata": latest_version.get("metadata", {}),
            "change_reason": latest_version.get("change_reason"),
            "is_current": True,
        }

        return VersionDetailResponse(
            success=True,
            message="Latest version retrieved successfully",
            version=version_detail,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve latest version: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve latest version",
        )
