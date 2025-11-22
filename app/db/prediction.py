"""
Prediction repository for database operations.
"""

import json
from typing import Optional, List, Dict, Any
import asyncpg

from app.config import logger
from app.db.database import BaseRepository


class PredictionRepository(BaseRepository):
    """Repository for prediction database operations."""

    async def create(
        self, user_id: int, user_input: Dict[str, Any], prediction_data: Dict[str, Any]
    ) -> Optional[asyncpg.Record]:
        """Create a new prediction."""
        try:
            query = """
                INSERT INTO predictions (user_id, user_input, prediction_data)
                VALUES ($1, $2, $3)
                RETURNING *
            """
            return await self.fetch_one(
                query,
                user_id,
                json.dumps(user_input),
                json.dumps(prediction_data),
            )
        except Exception as e:
            logger.error(f"Failed to create prediction: {e}")
            raise

    async def get_by_id_and_user(
        self, prediction_id: int, user_id: int
    ) -> Optional[asyncpg.Record]:
        """Get prediction by ID and user ID."""
        query = """
            SELECT * FROM predictions
            WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
        """
        return await self.fetch_one(query, prediction_id, user_id)

    async def list_by_user(
        self, user_id: int, limit: int = 50, offset: int = 0
    ) -> List[asyncpg.Record]:
        """List predictions for a user with pagination."""
        try:
            query = """
                SELECT * FROM predictions
                WHERE user_id = $1 AND deleted_at IS NULL
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
            """
            return await self.fetch_many(query, user_id, limit, offset)
        except Exception as e:
            logger.error(f"Failed to list predictions: {e}")
            raise

    async def update_pdf_url(
        self, prediction_id: int, user_id: int, pdf_url: str
    ) -> Optional[asyncpg.Record]:
        """Update prediction with generated PDF URL."""
        try:
            query = """
                UPDATE predictions
                SET pdf_url = $1, updated_at = NOW()
                WHERE id = $2 AND user_id = $3 AND deleted_at IS NULL
                RETURNING *
            """
            return await self.fetch_one(query, pdf_url, prediction_id, user_id)
        except Exception as e:
            logger.error(f"Failed to update PDF URL: {e}")
            raise

    async def delete(self, prediction_id: int, user_id: int) -> bool:
        """Soft delete prediction."""
        query = """
            UPDATE predictions
            SET deleted_at = NOW()
            WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
        """
        result = await self.execute(query, prediction_id, user_id)
        return "UPDATE 1" in result

    async def count_predictions_by_user(self, user_id: int) -> int:
        """Count total predictions for a user."""
        query = """
            SELECT COUNT(*) FROM predictions
            WHERE user_id = $1 AND deleted_at IS NULL
        """
        result = await self.fetch_one(query, user_id)
        return result.get("count", 0)

    async def get_latest_prediction_by_user(
        self, user_id: int
    ) -> Optional[asyncpg.Record]:
        """Get the latest prediction for a user."""
        query = """
            SELECT * FROM predictions
            WHERE user_id = $1 AND deleted_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
        """
        return await self.fetch_one(query, user_id)

    async def get_predictions_by_date_range(
        self, user_id: int, start_date: str, end_date: str, limit: int = 100
    ) -> List[asyncpg.Record]:
        """Get predictions for a user within a date range."""
        try:
            query = """
                SELECT * FROM predictions
                WHERE user_id = $1
                  AND created_at >= $2
                  AND created_at <= $3
                  AND deleted_at IS NULL
                ORDER BY created_at DESC
                LIMIT $4
            """
            return await self.fetch_many(query, user_id, start_date, end_date, limit)
        except Exception as e:
            logger.error(f"Failed to get predictions by date range: {e}")
            raise
