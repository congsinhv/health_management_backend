"""
User database operations using raw SQL queries with custom exception handling.
"""

import asyncpg
from typing import Optional, List
from datetime import datetime
from app.db.database import BaseRepository
from app.schemas.user import UserCreate, UserUpdate
from app.exceptions import (
    ResourceNotFoundException,
    DatabaseException,
    DatabaseConstraintException,
    DuplicateResourceException,
)


class UserRepository(BaseRepository):
    """Repository for user database operations."""

    async def create_user(
        self, user_data: UserCreate, password_hash: Optional[str] = None
    ) -> asyncpg.Record:
        """Create a new user."""
        now = datetime.utcnow()
        query = """
            INSERT INTO users (
                email, password_hash, is_active, 
                provider, google_id, email_verified, created_at, updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $7)
            RETURNING id, email, is_active, provider, 
                      google_id, email_verified, created_at, updated_at
        """
        try:
            result = await self.fetch_one(
                query,
                user_data.email,
                password_hash,
                user_data.is_active,
                user_data.provider,
                user_data.google_id,
                user_data.email_verified,
                now,
            )
            if not result:
                raise DatabaseException(
                    "Failed to create user", details={"email": user_data.email}
                )
            return result
        except asyncpg.UniqueViolationError as e:
            raise DuplicateResourceException(
                message="User with this email already exists",
                details={"email": user_data.email, "constraint": str(e)},
            )
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while creating user",
                details={"email": user_data.email, "error": str(e)},
            )

    async def get_user_by_id(self, user_id: int) -> asyncpg.Record:
        """Get user by ID."""
        query = """
            SELECT u.id, u.email, u.password_hash, u.is_active, u.provider,
                   u.google_id, u.email_verified, u.email_verification_token,
                   u.email_verification_sent_at, u.password_reset_token, u.password_reset_sent_at,
                   u.created_at, u.updated_at,
                   up.id as profile_id, up.first_name, up.last_name, up.avatar_url,
                   up.gender, up.height_cm, up.weight_kg, up.date_of_birth,
                   up.family_medical_history, up.goal, up.created_at as profile_created_at,
                   up.updated_at as profile_updated_at
            FROM users u
            LEFT JOIN user_profiles up ON u.id = up.user_id
            WHERE u.id = $1 AND u.deleted_at IS NULL
        """
        try:
            result = await self.fetch_one(query, user_id)
            if not result:
                raise ResourceNotFoundException(
                    message="User not found", details={"user_id": user_id}
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching user by ID",
                details={"user_id": user_id, "error": str(e)},
            )

    async def get_user_by_email(self, email: str) -> asyncpg.Record:
        """Get user by email."""
        query = """
            SELECT u.id, u.email, u.password_hash, u.is_active, u.provider,
                   u.google_id, u.email_verified, u.email_verification_token,
                   u.email_verification_sent_at, u.password_reset_token, u.password_reset_sent_at,
                   u.created_at, u.updated_at,
                   up.id as profile_id, up.first_name, up.last_name, up.avatar_url,
                   up.gender, up.height_cm, up.weight_kg, up.date_of_birth,
                   up.family_medical_history, up.goal, up.created_at as profile_created_at,
                   up.updated_at as profile_updated_at
            FROM users u
            LEFT JOIN user_profiles up ON u.id = up.user_id
            WHERE u.email = $1 AND u.deleted_at IS NULL
        """
        try:
            result = await self.fetch_one(query, email)
            if not result:
                raise ResourceNotFoundException(
                    message="User not found", details={"email": email}
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching user by email",
                details={"email": email, "error": str(e)},
            )

    async def get_users(
        self, limit: int = 100, offset: int = 0
    ) -> List[asyncpg.Record]:
        """Get all users with pagination."""
        query = """
            SELECT u.id, u.email, u.is_active, u.provider,
                   u.email_verified, u.created_at, u.updated_at,
                   up.id as profile_id, up.first_name, up.last_name, up.avatar_url,
                   up.gender, up.height_cm, up.weight_kg, up.date_of_birth,
                   up.family_medical_history, up.goal, up.created_at as profile_created_at,
                   up.updated_at as profile_updated_at
            FROM users u
            LEFT JOIN user_profiles up ON u.id = up.user_id
            WHERE u.deleted_at IS NULL
            ORDER BY u.created_at DESC
            LIMIT $1 OFFSET $2
        """
        try:
            return await self.fetch_many(query, limit, offset)
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching users",
                details={"limit": limit, "offset": offset, "error": str(e)},
            )

    async def update_user(self, user_id: int, user_data: UserUpdate) -> asyncpg.Record:
        """Update user information."""
        now = datetime.utcnow()
        query = """
            UPDATE users
            SET email = COALESCE($2, email),
                is_active = COALESCE($3, is_active),
                updated_at = $4
            WHERE id = $1 AND deleted_at IS NULL
            RETURNING id, email, is_active, created_at, updated_at
        """
        try:
            result = await self.fetch_one(
                query,
                user_id,
                user_data.email,
                user_data.is_active,
                now,
            )
            if not result:
                raise ResourceNotFoundException(
                    message="User not found or update failed",
                    details={"user_id": user_id, "email": user_data.email},
                )
            return result
        except asyncpg.UniqueViolationError as e:
            raise DuplicateResourceException(
                message="User with this email already exists",
                details={
                    "user_id": user_id,
                    "email": user_data.email,
                    "constraint": str(e),
                },
            )
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while updating user",
                details={"user_id": user_id, "email": user_data.email, "error": str(e)},
            )

    async def delete_user(self, user_id: int) -> asyncpg.Record:
        """Soft delete user."""
        now = datetime.utcnow()
        query = """
            UPDATE users
            SET deleted_at = $2, updated_at = $2
            WHERE id = $1 AND deleted_at IS NULL
            RETURNING id
        """
        try:
            result = await self.fetch_one(query, user_id, now)
            if not result:
                raise ResourceNotFoundException(
                    message="User not found for deletion", details={"user_id": user_id}
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while deleting user",
                details={"user_id": user_id, "error": str(e)},
            )

    async def count_users(self) -> int:
        """Count total users."""
        query = """
            SELECT COUNT(*) FROM users WHERE deleted_at IS NULL
        """
        try:
            result = await self.fetch_one(query)
            return result["count"] if result else 0
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while counting users", details={"error": str(e)}
            )

    # OAuth and Authentication methods

    async def get_user_by_google_id(self, google_id: str) -> asyncpg.Record:
        """Get user by Google ID."""
        query = """
            SELECT u.id, u.email, u.password_hash, u.is_active, u.provider,
                   u.google_id, u.email_verified, u.created_at, u.updated_at,
                   up.id as profile_id, up.first_name, up.last_name, up.avatar_url,
                   up.gender, up.height_cm, up.weight_kg, up.date_of_birth,
                   up.family_medical_history, up.goal, up.created_at as profile_created_at,
                   up.updated_at as profile_updated_at
            FROM users u
            LEFT JOIN user_profiles up ON u.id = up.user_id
            WHERE u.google_id = $1 AND u.deleted_at IS NULL
        """
        try:
            result = await self.fetch_one(query, google_id)
            if not result:
                raise ResourceNotFoundException(
                    message="User not found", details={"google_id": google_id}
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching user by Google ID",
                details={"google_id": google_id, "error": str(e)},
            )

    async def set_email_verification_token(self, user_id: int, token: str) -> bool:
        """Set email verification token for user."""
        now = datetime.utcnow()
        query = """
            UPDATE users
            SET email_verification_token = $2,
                email_verification_sent_at = $3,
                updated_at = $3
            WHERE id = $1 AND deleted_at IS NULL
        """
        try:
            result = await self.execute(query, user_id, token, now)
            success = "UPDATE 1" in result
            if not success:
                raise ResourceNotFoundException(
                    message="User not found for email verification token",
                    details={"user_id": user_id},
                )
            return success
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while setting email verification token",
                details={"user_id": user_id, "error": str(e)},
            )

    async def verify_email(self, token: str) -> asyncpg.Record:
        """Verify email using token."""
        now = datetime.utcnow()
        query = """
            UPDATE users
            SET email_verified = TRUE,
                email_verification_token = NULL,
                email_verification_sent_at = NULL,
                updated_at = $2
            WHERE email_verification_token = $1 AND deleted_at IS NULL
            RETURNING id, email
        """
        try:
            result = await self.fetch_one(query, token, now)
            if not result:
                raise ResourceNotFoundException(
                    message="Invalid or expired email verification token",
                    details={"token": token},
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while verifying email",
                details={"token": token, "error": str(e)},
            )

    async def set_password_reset_token(self, email: str, token: str) -> bool:
        """Set password reset token for user."""
        now = datetime.utcnow()
        query = """
            UPDATE users
            SET password_reset_token = $2,
                password_reset_sent_at = $3,
                updated_at = $3
            WHERE email = $1 AND deleted_at IS NULL
        """
        try:
            result = await self.execute(query, email, token, now)
            success = "UPDATE 1" in result
            if not success:
                raise ResourceNotFoundException(
                    message="User not found for password reset token",
                    details={"email": email},
                )
            return success
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while setting password reset token",
                details={"email": email, "error": str(e)},
            )

    async def reset_password(self, token: str, password_hash: str) -> asyncpg.Record:
        """Reset password using token."""
        now = datetime.utcnow()
        query = """
            UPDATE users
            SET password_hash = $2,
                password_reset_token = NULL,
                password_reset_sent_at = NULL,
                updated_at = $3
            WHERE password_reset_token = $1 AND deleted_at IS NULL
            RETURNING id, email
        """
        try:
            result = await self.fetch_one(query, token, password_hash, now)
            if not result:
                raise ResourceNotFoundException(
                    message="Invalid or expired password reset token",
                    details={"token": token},
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while resetting password",
                details={"token": token, "error": str(e)},
            )

    async def update_password(self, user_id: int, password_hash: str) -> bool:
        """Update user password."""
        now = datetime.utcnow()
        query = """
            UPDATE users
            SET password_hash = $2, updated_at = $3
            WHERE id = $1 AND deleted_at IS NULL
        """
        try:
            result = await self.execute(query, user_id, password_hash, now)
            success = "UPDATE 1" in result
            if not success:
                raise ResourceNotFoundException(
                    message="User not found for password update",
                    details={"user_id": user_id},
                )
            return success
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while updating password",
                details={"user_id": user_id, "error": str(e)},
            )

    async def link_google_account(
        self, user_id: int, google_id: str, avatar_url: Optional[str] = None
    ) -> bool:
        """Link Google account to existing user."""
        now = datetime.utcnow()
        try:
            # Update users table
            query = """
                UPDATE users
                SET google_id = $2, updated_at = $3
                WHERE id = $1 AND deleted_at IS NULL
            """
            result = await self.execute(query, user_id, google_id, now)
            success = "UPDATE 1" in result
            if not success:
                raise ResourceNotFoundException(
                    message="User not found for Google account linking",
                    details={"user_id": user_id, "google_id": google_id},
                )

            # Update avatar_url in user_profiles if provided
            if avatar_url:
                profile_query = """
                    INSERT INTO user_profiles (user_id, avatar_url, created_at, updated_at)
                    VALUES ($1, $2, $3, $3)
                    ON CONFLICT (user_id) DO UPDATE
                    SET avatar_url = $2, updated_at = $3
                """
                await self.execute(profile_query, user_id, avatar_url, now)

            return success
        except asyncpg.UniqueViolationError as e:
            raise DuplicateResourceException(
                message="Google account already linked to another user",
                details={
                    "user_id": user_id,
                    "google_id": google_id,
                    "constraint": str(e),
                },
            )
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while linking Google account",
                details={"user_id": user_id, "google_id": google_id, "error": str(e)},
            )

    # Refresh Token methods

    async def store_refresh_token(
        self, user_id: int, token_hash: str, expires_at: datetime
    ) -> asyncpg.Record:
        """Store a refresh token in the database."""
        query = """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES ($1, $2, $3)
            RETURNING id, user_id, token_hash, expires_at, revoked, created_at, updated_at
        """
        try:
            result = await self.fetch_one(query, user_id, token_hash, expires_at)
            if not result:
                raise DatabaseException(
                    message="Failed to store refresh token",
                    details={"user_id": user_id},
                )
            return result
        except asyncpg.ForeignKeyViolationError as e:
            raise ResourceNotFoundException(
                message="User not found for refresh token",
                details={"user_id": user_id, "constraint": str(e)},
            )
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while storing refresh token",
                details={"user_id": user_id, "error": str(e)},
            )

    async def get_refresh_token_by_hash(self, token_hash: str) -> asyncpg.Record:
        """Get a refresh token by its hash."""
        query = """
            SELECT id, user_id, token_hash, expires_at, revoked, created_at, updated_at
            FROM refresh_tokens
            WHERE token_hash = $1 AND revoked = FALSE
        """
        try:
            result = await self.fetch_one(query, token_hash)
            if not result:
                raise ResourceNotFoundException(
                    message="Refresh token not found or revoked",
                    details={"token_hash": token_hash},
                )
            return result
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while fetching refresh token",
                details={"token_hash": token_hash, "error": str(e)},
            )

    async def revoke_refresh_token(self, token_hash: str) -> bool:
        """Revoke a refresh token by marking it as revoked."""
        now = datetime.utcnow()
        query = """
            UPDATE refresh_tokens
            SET revoked = TRUE, updated_at = $2
            WHERE token_hash = $1 AND revoked = FALSE
        """
        try:
            result = await self.execute(query, token_hash, now)
            success = "UPDATE 1" in result or "UPDATE 0" in result
            return success
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while revoking refresh token",
                details={"token_hash": token_hash, "error": str(e)},
            )

    async def revoke_all_user_refresh_tokens(self, user_id: int) -> bool:
        """Revoke all refresh tokens for a user."""
        now = datetime.utcnow()
        query = """
            UPDATE refresh_tokens
            SET revoked = TRUE, updated_at = $2
            WHERE user_id = $1 AND revoked = FALSE
        """
        try:
            await self.execute(query, user_id, now)
            return True  # Always return True, even if no tokens were revoked
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while revoking user refresh tokens",
                details={"user_id": user_id, "error": str(e)},
            )

    async def cleanup_expired_refresh_tokens(self) -> int:
        """Delete expired refresh tokens from the database."""
        query = """
            DELETE FROM refresh_tokens
            WHERE expires_at < NOW()
        """
        try:
            result = await self.execute(query)
            # Extract number from result string like "DELETE 5"
            try:
                return int(result.split()[-1]) if result.split()[-1].isdigit() else 0
            except (IndexError, ValueError):
                return 0
        except asyncpg.PostgresError as e:
            raise DatabaseException(
                message="Database error while cleaning up expired refresh tokens",
                details={"error": str(e)},
            )
