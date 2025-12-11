"""
Prediction database operations using raw SQL queries with custom exception handling.
"""

import json
import asyncpg
from typing import Optional, Dict, Any
from datetime import datetime
from app.db.database import BaseRepository
from app.exceptions import (
    ResourceNotFoundException,
    DatabaseException,
    DatabaseConstraintException,
    DuplicateResourceException,
    PredictionException,
)


class PredictionRepository(BaseRepository):
    """Repository for prediction database operations (PUBLIC - no auth)."""

    async def create_prediction(
        self,
        prediction_id: str,
        user_input: Dict[str, Any],
        prediction_data: Dict[str, Any],
    ) -> asyncpg.Record:
        """
        Create a new prediction record.

        Args:
            prediction_id: External prediction ID from PredictionResponse.id
            user_input: UserInput schema as dict
            prediction_data: PredictionResponse schema as dict

        Returns:
            Created prediction record
        """
        query = """
            INSERT INTO predictions (
                prediction_id, user_input, prediction_data
            )
            VALUES ($1, $2, $3)
            RETURNING id, prediction_id, user_input, prediction_data,
                      pdf_url, created_at, updated_at
        """
        try:
            # Convert dicts to JSON strings for JSONB columns
            result = await self.fetch_one(
                query,
                prediction_id,
                json.dumps(user_input),
                json.dumps(prediction_data),
            )
            if not result:
                raise DatabaseException(
                    message="Failed to create prediction",
                    details={"prediction_id": prediction_id},
                )
            return result
        except asyncpg.UniqueViolationError as e:
            raise DuplicateResourceException(
                message="Prediction with this ID already exists",
                details={"prediction_id": prediction_id, "constraint": str(e)},
            )
        except asyncpg.PostgresError as e:
            raise PredictionException(
                message="Database error while creating prediction",
                details={"prediction_id": prediction_id, "error": str(e)},
            )

    async def get_prediction_by_prediction_id(
        self, prediction_id: str
    ) -> asyncpg.Record:
        """
        Get prediction by prediction_id (PUBLIC - no auth).

        Args:
            prediction_id: External prediction ID from PredictionResponse.id

        Returns:
            Prediction record
        """
        query = """
            SELECT id, prediction_id, user_input, prediction_data,
                   pdf_url, created_at, updated_at
            FROM predictions
            WHERE prediction_id = $1 AND deleted_at IS NULL
        """
        try:
            result = await self.fetch_one(query, prediction_id)
            if not result:
                raise ResourceNotFoundException(
                    message="Prediction not found",
                    details={"prediction_id": prediction_id},
                )
            return result
        except asyncpg.PostgresError as e:
            raise PredictionException(
                message="Database error while fetching prediction",
                details={"prediction_id": prediction_id, "error": str(e)},
            )

    async def update_pdf_url(self, prediction_id: str, pdf_url: str) -> asyncpg.Record:
        """
        Update prediction with generated PDF URL.

        Args:
            prediction_id: External prediction ID
            pdf_url: GCS public URL to PDF

        Returns:
            Updated prediction record
        """
        query = """
            UPDATE predictions
            SET pdf_url = $2
            WHERE prediction_id = $1 AND deleted_at IS NULL
            RETURNING id, prediction_id, user_input, prediction_data,
                      pdf_url, created_at, updated_at
        """
        try:
            result = await self.fetch_one(query, prediction_id, pdf_url)
            if not result:
                raise ResourceNotFoundException(
                    message="Prediction not found for PDF URL update",
                    details={"prediction_id": prediction_id, "pdf_url": pdf_url},
                )
            return result
        except asyncpg.PostgresError as e:
            raise PredictionException(
                message="Database error while updating prediction PDF URL",
                details={
                    "prediction_id": prediction_id,
                    "pdf_url": pdf_url,
                    "error": str(e),
                },
            )

    async def delete_prediction(self, prediction_id: str) -> asyncpg.Record:
        """
        Soft delete a prediction (optional feature).

        Args:
            prediction_id: External prediction ID

        Returns:
            Deleted prediction record
        """
        query = """
            UPDATE predictions
            SET deleted_at = NOW()
            WHERE prediction_id = $1 AND deleted_at IS NULL
            RETURNING id, prediction_id, user_input, prediction_data,
                      pdf_url, created_at, updated_at, deleted_at
        """
        try:
            result = await self.fetch_one(query, prediction_id)
            if not result:
                raise ResourceNotFoundException(
                    message="Prediction not found for deletion",
                    details={"prediction_id": prediction_id},
                )
            return result
        except asyncpg.PostgresError as e:
            raise PredictionException(
                message="Database error while deleting prediction",
                details={"prediction_id": prediction_id, "error": str(e)},
            )
    async def get_prediction(self, prediction_id: str) -> asyncpg.Record:
        """
        Backward-compatible method used by other services.

        Alias for get_prediction_by_prediction_id().
        Ensures older service code calling repo.get_prediction() still works.
        """
        return await self.get_prediction_by_prediction_id(prediction_id)
    async def update_prediction(
        self,
        prediction_id: str,
        prediction_data: Dict[str, Any],
    ) -> asyncpg.Record:
        """
        Backward-compatible method used by other services.

        Alias for updating prediction_data of a prediction record.
        Ensures older service code calling repo.update_prediction() still works.
        """
        query = """
            UPDATE predictions
            SET prediction_data = $2, updated_at = NOW()
            WHERE prediction_id = $1 AND deleted_at IS NULL
            RETURNING id, prediction_id, user_input, prediction_data,
                      pdf_url, created_at, updated_at
        """
        try:
            result = await self.fetch_one(
                query,
                prediction_id,
                json.dumps(prediction_data),
            )
            if not result:
                raise ResourceNotFoundException(
                    message="Prediction not found for update",
                    details={"prediction_id": prediction_id},
                )
            return result
        except asyncpg.PostgresError as e:
            raise PredictionException(
                message="Database error while updating prediction",
                details={"prediction_id": prediction_id, "error": str(e)},
            )

    async def get_prediction_by_id(self, id: int) -> asyncpg.Record:
        """
        Get prediction by internal database ID.

        Args:
            id: Internal database ID (primary key)

        Returns:
            Prediction record
        """
        query = """
            SELECT id, prediction_id, user_input, prediction_data,
                pdf_url, created_at, updated_at
            FROM predictions
            WHERE id = $1 AND deleted_at IS NULL
        """
        try:
            result = await self.fetch_one(query, id)
            if not result:
                raise ResourceNotFoundException(
                    message="Prediction not found",
                    details={"id": id},
                )
            return result
        except asyncpg.PostgresError as e:
            raise PredictionException(
                message="Database error while fetching prediction",
                details={"id": id, "error": str(e)},
            )