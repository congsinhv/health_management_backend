"""
Practice schedule business logic and services.
"""

import asyncpg
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from app.db.practice import PracticeRepository
from app.schemas.practice import (
    PracticeCreate,
    PracticeUpdate,
    PracticeResponse,
    PracticeListResponse,
)
from app.config import logger

# Vietnam timezone offset
VIETNAM_OFFSET = timedelta(hours=7)


class PracticeService:
    """Service layer for practice schedule operations."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.practice_repo = PracticeRepository(db_pool)

    def _transform_practice_record(self, record: asyncpg.Record) -> Dict[str, Any]:
        """Transform database record to PracticeResponse format."""
        # Convert UTC to Vietnam time
        created_at = record["created_at"]
        updated_at = record["updated_at"]
        
        if created_at and created_at.tzinfo:
            # If timezone-aware, convert to Vietnam time then remove timezone
            created_at = created_at.astimezone(timezone(VIETNAM_OFFSET)).replace(tzinfo=None)
        
        if updated_at and updated_at.tzinfo:
            updated_at = updated_at.astimezone(timezone(VIETNAM_OFFSET)).replace(tzinfo=None)
        
        return {
            "id": record["id"],
            "user_id": record["user_id"],
            "day_of_week": record["day_of_week"],
            "start_time": record["start_time"],
            "end_time": record["end_time"],
            "exercises": list(record["exercises"]),  # Convert array to list
            "notes": record["notes"],
            "created_at": created_at,
            "updated_at": updated_at,
        }

    async def create_practice(
        self, practice_data: PracticeCreate
    ) -> PracticeResponse:
        """Create a new practice schedule."""
        logger.info(
            f"Creating practice schedule for user_id={practice_data.user_id}, "
            f"day={practice_data.day_of_week}"
        )

        practice_record = await self.practice_repo.create_practice(
            user_id=practice_data.user_id,
            day_of_week=practice_data.day_of_week,
            start_time=practice_data.start_time,
            end_time=practice_data.end_time,
            exercises=practice_data.exercises,
            notes=practice_data.notes,
        )

        logger.info(f"Practice schedule created successfully: id={practice_record['id']}")
        return PracticeResponse(**self._transform_practice_record(practice_record))

    async def get_practice_by_id(self, practice_id: int) -> Optional[PracticeResponse]:
        """Get practice schedule by ID."""
        logger.debug(f"Fetching practice schedule by id={practice_id}")

        practice_record = await self.practice_repo.get_practice_by_id(practice_id)
        if not practice_record:
            logger.warning(f"Practice schedule not found: id={practice_id}")
            return None

        return PracticeResponse(**self._transform_practice_record(practice_record))

    async def get_practices_by_user(
        self, user_id: int, limit: int = 100, offset: int = 0
    ) -> PracticeListResponse:
        """Get all practice schedules for a user with pagination."""
        logger.debug(
            f"Fetching practices for user_id={user_id}, limit={limit}, offset={offset}"
        )

        # Get practice records
        practice_records = await self.practice_repo.get_practices_by_user(
            user_id, limit, offset
        )

        # Get total count
        total = await self.practice_repo.count_practices_by_user(user_id)

        # Transform records
        items = [
            PracticeResponse(**self._transform_practice_record(record))
            for record in practice_records
        ]

        logger.debug(
            f"Found {len(items)} practices for user_id={user_id} (total: {total})"
        )

        return PracticeListResponse(items=items, total=total, limit=limit, offset=offset)

    async def get_practices_by_user_and_day(
        self, user_id: int, day_of_week: int
    ) -> List[PracticeResponse]:
        """Get practice schedules for a specific day of week."""
        logger.debug(
            f"Fetching practices for user_id={user_id}, day_of_week={day_of_week}"
        )

        practice_records = await self.practice_repo.get_practices_by_user_and_day(
            user_id, day_of_week
        )

        items = [
            PracticeResponse(**self._transform_practice_record(record))
            for record in practice_records
        ]

        logger.debug(
            f"Found {len(items)} practices for user_id={user_id} on day {day_of_week}"
        )

        return items

    async def update_practice(
        self, practice_id: int, practice_data: PracticeUpdate
    ) -> Optional[PracticeResponse]:
        """Update practice schedule information."""
        logger.info(f"Updating practice schedule: id={practice_id}")

        # Check if practice exists
        existing_practice = await self.practice_repo.get_practice_by_id(practice_id)
        if not existing_practice:
            logger.warning(f"Practice schedule not found for update: id={practice_id}")
            return None

        # Update practice
        practice_record = await self.practice_repo.update_practice(
            practice_id=practice_id,
            day_of_week=practice_data.day_of_week,
            start_time=practice_data.start_time,
            end_time=practice_data.end_time,
            exercises=practice_data.exercises,
            notes=practice_data.notes,
        )

        if not practice_record:
            logger.error(f"Failed to update practice schedule: id={practice_id}")
            return None

        logger.info(f"Practice schedule updated successfully: id={practice_id}")
        return PracticeResponse(**self._transform_practice_record(practice_record))

    async def delete_practice(self, practice_id: int) -> bool:
        """Delete practice schedule (soft delete)."""
        logger.info(f"Deleting practice schedule: id={practice_id}")

        result = await self.practice_repo.delete_practice(practice_id)

        if result:
            logger.info(f"Practice schedule deleted successfully: id={practice_id}")
            return True
        else:
            logger.warning(f"Practice schedule not found for deletion: id={practice_id}")
            return False

    async def delete_practices_by_user(self, user_id: int) -> int:
        """Delete all practice schedules for a user (soft delete)."""
        logger.info(f"Deleting all practices for user_id={user_id}")

        deleted_count = await self.practice_repo.delete_practices_by_user(user_id)

        logger.info(
            f"Deleted {deleted_count} practice schedules for user_id={user_id}"
        )

        return deleted_count

    async def get_all_practices(
        self, limit: int = 100, offset: int = 0
    ) -> PracticeListResponse:
        """Get all practice schedules with pagination (admin only)."""
        logger.debug(f"Fetching all practices, limit={limit}, offset={offset}")

        # Get practice records
        practice_records = await self.practice_repo.get_all_practices(limit, offset)

        # For total count, we would need a new repo method
        # For now, just return the count of fetched items
        total = len(practice_records)

        # Transform records
        items = [
            PracticeResponse(**self._transform_practice_record(record))
            for record in practice_records
        ]

        logger.debug(f"Found {len(items)} practices (total: {total})")

        return PracticeListResponse(items=items, total=total, limit=limit, offset=offset)
