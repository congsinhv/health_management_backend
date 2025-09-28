"""
Database connection pool setup using asyncpg.
"""

import asyncpg
import logging
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)


class Database:
    """Database connection pool manager."""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Create database connection pool."""
        try:
            logger.info(
                f"Creating database connection pool with URL: {settings.database_url}"
            )
            self.pool = await asyncpg.create_pool(
                settings.database_url,
                min_size=settings.database_pool_min_size,
                max_size=settings.database_pool_max_size,
                command_timeout=settings.database_pool_timeout,
            )
            logger.info("Database connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create database connection pool: {e}")
            raise

    async def disconnect(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")

    def get_pool(self) -> asyncpg.Pool:
        """Get the database connection pool."""
        if not self.pool:
            raise RuntimeError("Database pool is not initialized")
        return self.pool


# Global database instance
database = Database()


async def get_database_pool() -> asyncpg.Pool:
    """Dependency to get database pool."""
    return database.get_pool()


class BaseRepository:
    """Base repository class with common database operations."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def fetch_one(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Execute query and return one record."""
        async with self.pool.acquire() as connection:
            return await connection.fetchrow(query, *args)

    async def fetch_many(self, query: str, *args) -> list[asyncpg.Record]:
        """Execute query and return multiple records."""
        async with self.pool.acquire() as connection:
            return await connection.fetch(query, *args)

    async def execute(self, query: str, *args) -> str:
        """Execute query and return status."""
        async with self.pool.acquire() as connection:
            return await connection.execute(query, *args)

    async def execute_transaction(self, queries: list[tuple[str, tuple]]) -> None:
        """Execute multiple queries in a transaction."""
        async with self.pool.acquire() as connection:
            async with connection.transaction():
                for query, args in queries:
                    await connection.execute(query, *args)
