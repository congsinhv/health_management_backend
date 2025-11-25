"""
User profile database operations using raw SQL queries with custom exception handling.
"""

import asyncpg
from typing import Optional
from datetime import datetime
from decimal import Decimal
from app.db.database import BaseRepository
from app.schemas.user_profile import UserProfileCreate, UserProfileUpdate
from app.exceptions import (
    ResourceNotFoundException,
    DatabaseException,
    DatabaseConstraintException,
    DuplicateResourceException,
)


class UserProfileRepository(BaseRepository):
    """Repository for user profile database operations."""

    async def create_profile(self, profile_data: UserProfileCreate) -> asyncpg.Record:
        """Create a new user profile."""
        now = datetime.utcnow()
        query = """
            INSERT INTO user_profiles (
                user_id, first_name, last_name, avatar_url, gender, height_cm,
                weight_kg, date_of_birth, family_medical_history, goal,
                created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $11)
            RETURNING id, user_id, first_name, last_name, avatar_url, gender,
                      height_cm, weight_kg, date_of_birth, family_medical_history,
                      goal, created_at, updated_at
        """
        try:
            result = await self.fetch_one(
                query,
                profile_data.user_id,
                profile_data.first_name,
                profile_data.last_name,
                profile_data.avatar_url,
                profile_data.gender,
                profile_data.height_cm,
                profile_data.weight_kg,
                profile_data.date_of_birth,
                profile_data.family_medical_history,
                profile_data.goal,
                now,
            )
            if not result:
                raise DatabaseException(
                    message="Failed to create user profile",
                    details={"user_id": profile_data.user_id},
                )
            return result
        except asyncpg.UniqueViolationError as e:
            raise DuplicateResourceException(
                message="User profile already exists for this user",
                details={"user_id": profile_data.user_id, "constraint": str(e)},
            )
        except asyncpg.ForeignKeyViolationError as e:
            raise ResourceNotFoundException(
                message="User not found for profile creation",
                details={"user_id": profile_data.user_id, "constraint": str(e)},
            )
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while creating user profile",
                details={"user_id": profile_data.user_id, "error": str(e)},
            )

    async def get_profile_by_user_id(self, user_id: int) -> asyncpg.Record:
        """Get user profile by user ID."""
        query = """
            SELECT id, user_id, first_name, last_name, avatar_url, gender,
                   height_cm, weight_kg, date_of_birth, family_medical_history,
                   goal, created_at, updated_at
            FROM user_profiles
            WHERE user_id = $1
        """
        try:
            result = await self.fetch_one(query, user_id)
            if not result:
                raise ResourceNotFoundException(
                    message="User profile not found", details={"user_id": user_id}
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching user profile",
                details={"user_id": user_id, "error": str(e)},
            )

    async def update_profile(
        self, user_id: int, profile_data: UserProfileUpdate
    ) -> asyncpg.Record:
        """Update user profile information."""
        now = datetime.utcnow()
        query = """
            UPDATE user_profiles
            SET first_name = COALESCE($2, first_name),
                last_name = COALESCE($3, last_name),
                avatar_url = COALESCE($4, avatar_url),
                gender = COALESCE($5, gender),
                height_cm = COALESCE($6, height_cm),
                weight_kg = COALESCE($7, weight_kg),
                date_of_birth = COALESCE($8, date_of_birth),
                family_medical_history = COALESCE($9, family_medical_history),
                goal = COALESCE($10, goal),
                updated_at = $11
            WHERE user_id = $1
            RETURNING id, user_id, first_name, last_name, avatar_url, gender,
                      height_cm, weight_kg, date_of_birth, family_medical_history,
                      goal, created_at, updated_at
        """
        try:
            result = await self.fetch_one(
                query,
                user_id,
                profile_data.first_name,
                profile_data.last_name,
                profile_data.avatar_url,
                profile_data.gender,
                profile_data.height_cm,
                profile_data.weight_kg,
                profile_data.date_of_birth,
                profile_data.family_medical_history,
                profile_data.goal,
                now,
            )
            if not result:
                raise ResourceNotFoundException(
                    message="User profile not found for update",
                    details={"user_id": user_id},
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while updating user profile",
                details={"user_id": user_id, "error": str(e)},
            )

    async def delete_profile(self, user_id: int) -> bool:
        """Delete user profile (cascade delete handled by foreign key)."""
        query = """
            DELETE FROM user_profiles
            WHERE user_id = $1
        """
        try:
            result = await self.execute(query, user_id)
            success = "DELETE 1" in result or "DELETE 0" in result
            return success
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while deleting user profile",
                details={"user_id": user_id, "error": str(e)},
            )
