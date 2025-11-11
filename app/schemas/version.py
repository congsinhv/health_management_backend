"""
Schemas for message version comparison and diff operations.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.base import BaseResponse


class VersionComparison(BaseModel):
    """Schema for version comparison results."""

    message_id: int
    from_version: int
    to_version: int
    from_timestamp: datetime
    to_timestamp: datetime
    content_diff: Dict[str, Any]
    content_cleaned_diff: Optional[Dict[str, Any]]
    answers_diff: Optional[Dict[str, Any]]
    metadata_diff: Optional[Dict[str, Any]]
    changes_summary: Dict[str, Any]


class VersionTimeline(BaseModel):
    """Schema for version timeline entry."""

    version_number: int
    created_at: datetime
    changes_from_previous: Dict[str, Any]
    content_preview: str
    has_answers: bool
    metadata_keys: List[str]


class VersionRestore(BaseModel):
    """Schema for version restore request."""

    version_number: int
    create_backup: bool = Field(
        True, description="Create backup of current version before restoring"
    )


class VersionRestoreResult(BaseModel):
    """Schema for version restore result."""

    message_id: int
    restored_version: int
    restored_at: datetime
    backup_created: bool


class VersionExport(BaseModel):
    """Schema for version export request."""

    format: str = Field("json", description="Export format: json, csv, xml")


class DiffStatistics(BaseModel):
    """Schema for diff statistics."""

    additions: int
    deletions: int
    modifications: int
    total_changes: int
    similarity_ratio: float


class TextDiff(BaseModel):
    """Schema for text diff."""

    unified_diff: str
    html_diff: str
    statistics: DiffStatistics


class AnswerDiff(BaseModel):
    """Schema for answer diff."""

    changed_fields: List[str]
    field_changes: Dict[str, Dict[str, Any]]
    has_changes: bool


class MetadataDiff(BaseModel):
    """Schema for metadata diff."""

    changed_keys: List[str]
    key_changes: Dict[str, Dict[str, Any]]
    has_changes: bool


class ChangesSummary(BaseModel):
    """Schema for changes summary."""

    content_changed: bool
    cleaned_content_changed: bool
    answers_changed: bool
    metadata_changed: bool
    major_changes: List[str]
    minor_changes: List[str]


class VersionComparisonResponse(BaseResponse):
    """Response schema for version comparison."""

    comparison: VersionComparison


class VersionTimelineResponse(BaseResponse):
    """Response schema for version timeline."""

    timeline: List[VersionTimeline]
    total_versions: int


class VersionRestoreResponse(BaseResponse):
    """Response schema for version restore."""

    restore_result: VersionRestoreResult


class VersionExportResponse(BaseResponse):
    """Response schema for version export."""

    export_data: Dict[str, Any]
    format: str
    exported_at: datetime


class VersionListResponse(BaseResponse):
    """Response schema for version list."""

    versions: List[Dict[str, Any]]
    message_id: int
    total_versions: int


class VersionDetail(BaseModel):
    """Schema for detailed version information."""

    version_number: int
    created_at: datetime
    content: str
    content_cleaned: Optional[str]
    answers: Optional[Dict[str, List[str]]]
    metadata: Dict[str, Any]
    change_reason: Optional[str]
    is_current: bool = False


class VersionDetailResponse(BaseResponse):
    """Response schema for version detail."""

    version: VersionDetail
