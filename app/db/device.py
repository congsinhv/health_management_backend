"""
Device repository for FCM token management.
"""

from typing import Optional, List
import asyncpg

from app.config import logger
from app.db.database import BaseRepository
from app.exceptions import (
    ResourceNotFoundException,
    DatabaseException,
    DuplicateResourceException,
)


class DeviceRepository(BaseRepository):
    """Repository for user device (FCM token) operations."""

    async def register(
        self,
        user_id: int,
        fcm_token: str,
        device_type: Optional[str] = None,
        device_name: Optional[str] = None,
    ) -> asyncpg.Record:
        """Register or update FCM token."""
        query = """
            INSERT INTO user_devices (user_id, fcm_token, device_type, device_name, is_active, last_used_at)
            VALUES ($1, $2, $3, $4, TRUE, NOW())
            ON CONFLICT (user_id, fcm_token)
            DO UPDATE SET
                device_type = COALESCE(EXCLUDED.device_type, user_devices.device_type),
                device_name = COALESCE(EXCLUDED.device_name, user_devices.device_name),
                is_active = TRUE,
                last_used_at = NOW(),
                updated_at = NOW()
            RETURNING *
        """
        try:
            return await self.fetch_one(
                query, user_id, fcm_token, device_type, device_name
            )
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error registering device",
                details={"user_id": user_id, "error": str(e)},
            )

    async def get_active_by_user(self, user_id: int) -> List[asyncpg.Record]:
        """Get all active devices for user."""
        query = """
            SELECT * FROM user_devices
            WHERE user_id = $1 AND is_active = TRUE
            ORDER BY last_used_at DESC
        """
        try:
            return await self.fetch_many(query, user_id)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error fetching devices",
                details={"user_id": user_id, "error": str(e)},
            )

    async def deactivate(self, user_id: int, fcm_token: str) -> bool:
        """Deactivate device token."""
        query = """
            UPDATE user_devices
            SET is_active = FALSE, updated_at = NOW()
            WHERE user_id = $1 AND fcm_token = $2
        """
        try:
            result = await self.execute(query, user_id, fcm_token)
            return "UPDATE 1" in result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error deactivating device",
                details={"user_id": user_id, "error": str(e)},
            )

    async def deactivate_token(self, fcm_token: str) -> int:
        """Deactivate token across all users (for expired tokens)."""
        query = """
            UPDATE user_devices
            SET is_active = FALSE, updated_at = NOW()
            WHERE fcm_token = $1
        """
        try:
            result = await self.execute(query, fcm_token)
            return int(result.split()[-1]) if result else 0
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error deactivating token",
                details={"error": str(e)},
            )

    async def update_last_used(self, device_id: int) -> bool:
        """Update last used timestamp."""
        query = """
            UPDATE user_devices
            SET last_used_at = NOW(), updated_at = NOW()
            WHERE id = $1
        """
        try:
            result = await self.execute(query, device_id)
            return "UPDATE 1" in result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error updating device",
                details={"device_id": device_id, "error": str(e)},
            )
