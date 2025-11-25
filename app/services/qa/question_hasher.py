"""
Question and content hashing for Q&A service.

This module provides functions for normalizing and hashing questions
and content to create consistent cache keys.
"""

import hashlib
import json
import re
from typing import List, Dict


def hash_question(question: str) -> str:
    """
    Normalize and hash question for consistent cache keys.

    Args:
        question: The question text to hash

    Returns:
        16-character MD5 hash of normalized question
    """
    # Normalize: lowercase, strip, collapse whitespace, remove extra punctuation
    normalized = question.lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)  # Collapse multiple spaces
    normalized = normalized.strip()  # Remove leading/trailing spaces

    # Generate MD5 hash and return first 16 characters
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()[:16]


def hash_content_for_summary(question: str, answers: List[Dict]) -> str:
    """
    Hash question and answers for summary caching.

    Args:
        question: The question text
        answers: List of answer dictionaries

    Returns:
        16-character MD5 hash of content
    """
    # Create content string for hashing
    content = question + json.dumps(answers, sort_keys=True, ensure_ascii=False)

    # Generate MD5 hash and return first 16 characters
    return hashlib.md5(content.encode("utf-8")).hexdigest()[:16]


def normalize_question_text(text: str) -> str:
    """
    Normalize question text for consistent processing.

    Args:
        text: Raw question text

    Returns:
        Normalized text with consistent formatting
    """
    # Convert to lowercase
    text = text.lower()

    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    # Keep Vietnamese characters (U+00C0 to U+017F)
    text = re.sub(r"[^a-z0-9\u00C0-\u017F\s]", " ", text)

    # Final cleanup of multiple spaces
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def create_cache_key(question: str, threshold: float = None, top_k: int = None) -> str:
    """
    Create standardized cache key for Q&A requests.

    Args:
        question: The question text
        threshold: Similarity threshold used
        top_k: Number of results requested

    Returns:
        Standardized cache key
    """
    question_hash = hash_question(question)

    if threshold is not None and top_k is not None:
        return f"qa:answers:{question_hash}:{threshold}:{top_k}"
    else:
        return f"qa:answers:{question_hash}"


def create_summary_cache_key(question: str, answers: List[Dict]) -> str:
    """
    Create cache key for Q&A summary requests.

    Args:
        question: The question text
        answers: List of answer dictionaries

    Returns:
        Cache key for summary
    """
    content_hash = hash_content_for_summary(question, answers)
    return f"qa:summary:{content_hash}"
