"""
API endpoints for conversation branching operations.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional, Dict, Any

import asyncpg
from app.db.database import get_database_pool
from app.services.branching import BranchingService
from app.schemas.base import StandardResponse
from app.services.message import MessageService
from app.auth.dependencies import get_current_active_user
from app.schemas.branching import (
    BranchCreate,
    BranchMerge,
    BranchDelete,
    BranchListResponse,
    BranchStatisticsResponse,
    TreeVisualizationResponse,
    BranchPathResponse,
    BranchMergeResponse,
)
from app.schemas.base import StandardResponse
from app.schemas.message import MessageDetail

router = APIRouter()


async def get_branching_service(
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> BranchingService:
    """Dependency to get branching service."""
    return BranchingService(pool)


async def get_message_service(
    pool: asyncpg.Pool = Depends(get_database_pool),
) -> MessageService:
    """Dependency to get message service."""
    return MessageService(pool)


@router.post("/create", response_model=StandardResponse[MessageDetail])
async def create_branch(
    branch_data: BranchCreate,
    current_user=Depends(get_current_active_user),
    branching_service: BranchingService = Depends(get_branching_service),
    message_service: MessageService = Depends(get_message_service),
):
    """Create a new branch from a parent message."""
    try:
        # Create branch point metadata
        branch_info = await branching_service.create_branch_point(
            branch_data.parent_message_id, current_user.id, branch_data.branch_name
        )

        # Create the actual message
        new_message = await message_service.create_branch(
            parent_message_id=branch_data.parent_message_id,
            user_id=current_user.id,
            role=branch_data.role,
            content=branch_data.content,
            content_cleaned=branch_data.content_cleaned,
            answers=branch_data.answers,
            metadata={
                **(branch_data.metadata or {}),
                "branch_info": branch_info.dict(),
            },
        )

        return StandardResponse.success(data=new_message.model_dump())

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create branch: {str(e)}",
        )


@router.get(
    "/conversation/{conversation_id}/branches", response_model=BranchListResponse
)
async def get_conversation_branches(
    conversation_id: int,
    current_user=Depends(get_current_active_user),
    branching_service: BranchingService = Depends(get_branching_service),
):
    """Get all branches in a conversation."""
    try:
        branches = await branching_service.get_conversation_branches(
            conversation_id, current_user.id
        )

        return BranchListResponse(
            success=True, message="Branches retrieved successfully", branches=branches
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve branches",
        )


@router.get("/message/{message_id}/path", response_model=BranchPathResponse)
async def get_branch_path(
    message_id: int,
    current_user=Depends(get_current_active_user),
    branching_service: BranchingService = Depends(get_branching_service),
    message_service: MessageService = Depends(get_message_service),
):
    """Get the complete path from root to a specific message."""
    try:
        path = await branching_service.get_branch_path(message_id, current_user.id)

        # Find branch points (messages with children)
        branch_points = []
        for msg in path:
            children = await message_service.get_message_children(
                msg.id, current_user.id
            )
            if children:
                branch_points.append(msg.id)

        return BranchPathResponse(
            success=True,
            message="Branch path retrieved successfully",
            path=[msg.dict() for msg in path],
            branch_points=branch_points,
            total_length=len(path),
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve branch path",
        )


@router.post("/merge", response_model=BranchMergeResponse)
async def merge_branches(
    merge_data: BranchMerge,
    current_user=Depends(get_current_active_user),
    branching_service: BranchingService = Depends(get_branching_service),
):
    """Merge a branch back into the main conversation."""
    try:
        merged_message = await branching_service.merge_branches(
            merge_data.source_message_id,
            merge_data.target_message_id,
            current_user.id,
            merge_data.merge_strategy,
        )

        merge_info = {
            "source_message_id": merge_data.source_message_id,
            "target_message_id": merge_data.target_message_id,
            "merge_strategy": merge_data.merge_strategy,
            "merged_at": "now",
        }

        return BranchMergeResponse(
            success=True,
            message="Branch merged successfully",
            merged_message=merged_message.dict(),
            merge_info=merge_info,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to merge branches",
        )


@router.delete("/delete", response_model=StandardResponse[str])
async def delete_branch(
    delete_data: BranchDelete,
    current_user=Depends(get_current_active_user),
    branching_service: BranchingService = Depends(get_branching_service),
):
    """Delete a branch and optionally all its children."""
    try:
        success = await branching_service.delete_branch(
            delete_data.message_id, current_user.id, delete_data.cascade
        )

        return StandardResponse.success(
            data="Branch deleted successfully" if success else "Failed to delete branch"
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete branch",
        )


@router.get(
    "/conversation/{conversation_id}/statistics",
    response_model=BranchStatisticsResponse,
)
async def get_branch_statistics(
    conversation_id: int,
    current_user=Depends(get_current_active_user),
    branching_service: BranchingService = Depends(get_branching_service),
):
    """Get statistics about branches in a conversation."""
    try:
        stats = await branching_service.get_branch_statistics(
            conversation_id, current_user.id
        )

        return BranchStatisticsResponse(
            success=True,
            message="Branch statistics retrieved successfully",
            statistics=stats,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve branch statistics",
        )


@router.get(
    "/conversation/{conversation_id}/visualize",
    response_model=TreeVisualizationResponse,
)
async def visualize_conversation_tree(
    conversation_id: int,
    max_depth: int = Query(10, ge=1, le=20, description="Maximum depth to visualize"),
    current_user=Depends(get_current_active_user),
    branching_service: BranchingService = Depends(get_branching_service),
):
    """Create a visual representation of the conversation tree."""
    try:
        visualization = await branching_service.visualize_tree(
            conversation_id, current_user.id, max_depth
        )

        return TreeVisualizationResponse(
            success=True,
            message="Tree visualization created successfully",
            visualization=visualization,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tree visualization",
        )


@router.get(
    "/message/{message_id}/children",
    response_model=StandardResponse[List[Dict[str, Any]]],
)
async def get_message_branches(
    message_id: int,
    current_user=Depends(get_current_active_user),
    message_service: MessageService = Depends(get_message_service),
):
    """Get all direct branches (children) of a message."""
    try:
        children = await message_service.get_message_children(
            message_id, current_user.id
        )

        return StandardResponse.success(data=[child.dict() for child in children])

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve message branches",
        )


@router.post(
    "/message/{message_id}/branch-point",
    response_model=StandardResponse[Dict[str, Any]],
)
async def create_branch_point(
    message_id: int,
    branch_name: Optional[str] = None,
    current_user=Depends(get_current_active_user),
    branching_service: BranchingService = Depends(get_branching_service),
):
    """Mark a message as a branch point."""
    try:
        branch_info = await branching_service.create_branch_point(
            message_id, current_user.id, branch_name
        )

        return StandardResponse.success(data=branch_info)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create branch point",
        )
