"""
Schemas for conversation branching operations.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.base import BaseResponse


class BranchCreate(BaseModel):
    """Schema for creating a new branch."""

    parent_message_id: int
    role: str = Field(
        ..., description="Role of the new message (user, assistant, system)"
    )
    content: str = Field(..., min_length=1, max_length=5000)
    content_cleaned: Optional[str] = None
    answers: Optional[Dict[str, List[str]]] = None
    metadata: Optional[Dict[str, Any]] = None
    branch_name: Optional[str] = Field(None, max_length=100)


class BranchInfo(BaseModel):
    """Schema for branch information."""

    branch_point_id: int
    branch_name: str
    branch_order: int
    created_at: datetime
    parent_conversation_id: int


class BranchPoint(BaseModel):
    """Schema for a branch point in conversation."""

    branch_point_id: int
    branch_point_role: str
    branch_point_content: str
    num_branches: int
    branches: List[Dict[str, Any]]


class BranchMerge(BaseModel):
    """Schema for merging branches."""

    source_message_id: int
    target_message_id: int
    merge_strategy: str = Field(
        "replace",
        pattern="^(replace|append|prepend)$",
        description="Strategy for merging: replace, append, prepend",
    )


class BranchDelete(BaseModel):
    """Schema for deleting a branch."""

    message_id: int
    cascade: bool = Field(True, description="Delete all descendants as well")


class BranchStatistics(BaseModel):
    """Schema for branch statistics."""

    total_messages: int
    max_depth: int
    branch_points: int
    max_branches_from_point: int
    messages_by_level: Dict[int, int]
    branch_distribution: Dict[str, int]


class TreeNode(BaseModel):
    """Schema for a tree node."""

    id: int
    role: str
    content: str
    created_at: datetime
    depth: int
    children: List["TreeNode"] = []


# Resolve forward reference
TreeNode.model_rebuild()


class TreeVisualization(BaseModel):
    """Schema for tree visualization."""

    conversation_id: int
    total_messages: int
    tree: List[TreeNode]
    max_depth: int


class BranchListResponse(BaseResponse):
    """Response schema for branch list."""

    success: bool = True
    message: str = ""
    branches: List[BranchPoint]


class BranchStatisticsResponse(BaseResponse):
    """Response schema for branch statistics."""

    success: bool = True
    message: str = ""
    statistics: BranchStatistics


class TreeVisualizationResponse(BaseResponse):
    """Response schema for tree visualization."""

    success: bool = True
    message: str = ""
    visualization: TreeVisualization


class BranchPathResponse(BaseResponse):
    """Response schema for branch path."""

    success: bool = True
    message: str = ""
    path: List[Dict[str, Any]]
    branch_points: List[int]
    total_length: int


class BranchMergeResponse(BaseResponse):
    """Response schema for branch merge."""

    success: bool = True
    message: str = ""
    merged_message: Dict[str, Any]
    merge_info: Dict[str, Any]
