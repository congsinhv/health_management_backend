"""
Q&A database operations using raw SQL queries with asyncpg.
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime
from app.db.database import database
import json

logger = logging.getLogger(__name__)


async def create_conversation(
    question: str,
    question_cleaned: str,
    answers: Dict[str, List[str]],
    summary: str,
    threshold: float,
    top_k: int,
    user_id: Optional[int] = None,
) -> int:
    """
    Create a new Q&A conversation record.

    Args:
        question: The original user question
        question_cleaned: The preprocessed question
        answers: Dictionary of answers grouped by field
        summary: AI-generated summary
        threshold: Similarity threshold used
        top_k: Number of top results returned
        user_id: Optional user ID if authenticated

    Returns:
        ID of the created conversation record
    """
    query = """
        INSERT INTO qa_conversations (
            user_id, question, question_cleaned, answers, summary, threshold, top_k
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id
    """

    try:
        pool = database.get_pool()
        async with pool.acquire() as connection:
            conversation_id = await connection.fetchval(
                query,
                user_id,
                question,
                question_cleaned,
                json.dumps(answers, ensure_ascii=False),
                summary,
                threshold,
                top_k,
            )
            logger.info(f"Created conversation with ID: {conversation_id}")
            return conversation_id
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        raise


async def get_conversation_by_id(conversation_id: int) -> Optional[Dict]:
    """
    Retrieve a conversation by its ID.

    Args:
        conversation_id: The conversation ID

    Returns:
        Dictionary with conversation data or None if not found
    """
    query = """
        SELECT 
            id, user_id, question, question_cleaned, 
            answers, summary, threshold, top_k, created_at
        FROM qa_conversations
        WHERE id = $1
    """

    try:
        pool = database.get_pool()
        async with pool.acquire() as connection:
            row = await connection.fetchrow(query, conversation_id)
            if row:
                return {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "question": row["question"],
                    "question_cleaned": row["question_cleaned"],
                    "answers": row["answers"],
                    "summary": row["summary"],
                    "threshold": row["threshold"],
                    "top_k": row["top_k"],
                    "created_at": row["created_at"],
                }
            return None
    except Exception as e:
        logger.error(f"Error retrieving conversation {conversation_id}: {e}")
        raise


async def get_user_conversations(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    """
    Retrieve conversations for a specific user.

    Args:
        user_id: The user ID
        limit: Maximum number of records to return
        offset: Number of records to skip

    Returns:
        List of conversation dictionaries
    """
    query = """
        SELECT 
            id, question, summary, threshold, top_k, created_at
        FROM qa_conversations
        WHERE user_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
    """

    try:
        pool = database.get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(query, user_id, limit, offset)
            return [
                {
                    "id": row["id"],
                    "question": row["question"],
                    "summary": row["summary"],
                    "threshold": row["threshold"],
                    "top_k": row["top_k"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
    except Exception as e:
        logger.error(f"Error retrieving user conversations for user {user_id}: {e}")
        raise


async def get_recent_conversations(
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    """
    Retrieve recent conversations (all users).

    Args:
        limit: Maximum number of records to return
        offset: Number of records to skip

    Returns:
        List of conversation dictionaries
    """
    query = """
        SELECT 
            id, user_id, question, summary, threshold, top_k, created_at
        FROM qa_conversations
        ORDER BY created_at DESC
        LIMIT $1 OFFSET $2
    """

    try:
        pool = database.get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(query, limit, offset)
            return [
                {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "question": row["question"],
                    "summary": row["summary"],
                    "threshold": row["threshold"],
                    "top_k": row["top_k"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
    except Exception as e:
        logger.error(f"Error retrieving recent conversations: {e}")
        raise


async def count_user_conversations(user_id: int) -> int:
    """
    Count total conversations for a user.

    Args:
        user_id: The user ID

    Returns:
        Total count of conversations
    """
    query = """
        SELECT COUNT(*) as count
        FROM qa_conversations
        WHERE user_id = $1
    """

    try:
        pool = database.get_pool()
        async with pool.acquire() as connection:
            count = await connection.fetchval(query, user_id)
            return count
    except Exception as e:
        logger.error(f"Error counting user conversations for user {user_id}: {e}")
        raise


async def delete_conversation(conversation_id: int) -> bool:
    """
    Delete a conversation by ID.

    Args:
        conversation_id: The conversation ID

    Returns:
        True if deleted, False if not found
    """
    query = """
        DELETE FROM qa_conversations
        WHERE id = $1
        RETURNING id
    """

    try:
        pool = database.get_pool()
        async with pool.acquire() as connection:
            deleted_id = await connection.fetchval(query, conversation_id)
            if deleted_id:
                logger.info(f"Deleted conversation {conversation_id}")
                return True
            return False
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id}: {e}")
        raise


async def search_conversations(
    search_query: str,
    user_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict]:
    """
    Search conversations by question text.

    Args:
        search_query: The search query
        user_id: Optional user ID to filter by
        limit: Maximum number of records to return
        offset: Number of records to skip

    Returns:
        List of conversation dictionaries
    """
    if user_id:
        query = """
            SELECT 
                id, question, summary, threshold, top_k, created_at
            FROM qa_conversations
            WHERE user_id = $1 AND question ILIKE $2
            ORDER BY created_at DESC
            LIMIT $3 OFFSET $4
        """
        params = (user_id, f"%{search_query}%", limit, offset)
    else:
        query = """
            SELECT 
                id, user_id, question, summary, threshold, top_k, created_at
            FROM qa_conversations
            WHERE question ILIKE $1
            ORDER BY created_at DESC
            LIMIT $2 OFFSET $3
        """
        params = (f"%{search_query}%", limit, offset)

    try:
        pool = database.get_pool()
        async with pool.acquire() as connection:
            rows = await connection.fetch(query, *params)
            result = []
            for row in rows:
                conv = {
                    "id": row["id"],
                    "question": row["question"],
                    "summary": row["summary"],
                    "threshold": row["threshold"],
                    "top_k": row["top_k"],
                    "created_at": row["created_at"],
                }
                if not user_id:
                    conv["user_id"] = row["user_id"]
                result.append(conv)
            return result
    except Exception as e:
        logger.error(f"Error searching conversations: {e}")
        raise
