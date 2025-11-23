"""
Prediction database operations using raw SQL queries.
"""

import json
import asyncpg
from typing import Optional, Dict, Any
from datetime import datetime
from app.db.database import BaseRepository


class PredictionRepository(BaseRepository):
    """Repository for prediction database operations (PUBLIC - no auth)."""

    async def create_prediction(
        self,
        prediction_id: str,
        user_input: Dict[str, Any],
        prediction_data: Dict[str, Any],
    ) -> Optional[asyncpg.Record]:
        """
        Create a new prediction record.

        Args:
            prediction_id: External prediction ID from PredictionResponse.id
            user_input: UserInput schema as dict
            prediction_data: PredictionResponse schema as dict

        Returns:
            Created prediction record or None
        """
        query = """
            INSERT INTO predictions (
                prediction_id, user_input, prediction_data
            )
            VALUES ($1, $2, $3)
            RETURNING id, prediction_id, user_input, prediction_data,
                      pdf_url, created_at, updated_at
        """
        # Convert dicts to JSON strings for JSONB columns
        return await self.fetch_one(
            query,
            prediction_id,
            json.dumps(user_input),
            json.dumps(prediction_data),
        )

    async def get_prediction_by_prediction_id(
        self, prediction_id: str
    ) -> Optional[asyncpg.Record]:
        """
        Get prediction by prediction_id (PUBLIC - no auth).

        Args:
            prediction_id: External prediction ID from PredictionResponse.id

        Returns:
            Prediction record or None
        """
        query = """
            SELECT id, prediction_id, user_input, prediction_data,
                   pdf_url, created_at, updated_at
            FROM predictions
            WHERE prediction_id = $1 AND deleted_at IS NULL
        """
        return await self.fetch_one(query, prediction_id)

    async def update_pdf_url(
        self, prediction_id: str, pdf_url: str
    ) -> Optional[asyncpg.Record]:
        """
        Update prediction with generated PDF URL.

        Args:
            prediction_id: External prediction ID
            pdf_url: GCS public URL to PDF

        Returns:
            Updated prediction record or None
        """
        query = """
            UPDATE predictions
            SET pdf_url = $2
            WHERE prediction_id = $1 AND deleted_at IS NULL
            RETURNING id, prediction_id, user_input, prediction_data,
                      pdf_url, created_at, updated_at
        """
        return await self.fetch_one(query, prediction_id, pdf_url)

    async def delete_prediction(self, prediction_id: str) -> Optional[asyncpg.Record]:
        """
        Soft delete a prediction (optional feature).

        Args:
            prediction_id: External prediction ID

        Returns:
            Deleted prediction record or None
        """
        query = """
            UPDATE predictions
            SET deleted_at = NOW()
            WHERE prediction_id = $1 AND deleted_at IS NULL
            RETURNING id, prediction_id, user_input, prediction_data,
                      pdf_url, created_at, updated_at, deleted_at
        """
        return await self.fetch_one(query, prediction_id)
