"""
Pre-warm embedding cache with common questions.

Run at startup or as scheduled job to pre-compute embeddings for frequently
asked questions, reducing first-request latency.

Usage:
    python scripts/cache_warmer.py

Environment variables:
    QA_CACHE_WARMUP_QUESTIONS_FILE: Path to questions file (default: data/top_questions.txt)
"""
import asyncio
import logging
import sys
from pathlib import Path
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.qa_service import QAService
from app.services.cache import create_cache_service
from app.config import settings

logger = logging.getLogger(__name__)


async def load_top_questions(file_path: str) -> List[str]:
    """
    Load top questions from file.

    Args:
        file_path: Path to questions file (one question per line)

    Returns:
        List of question strings
    """
    if not Path(file_path).exists():
        logger.warning(f"Top questions file not found: {file_path}")
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        questions = [line.strip() for line in f if line.strip()]

    logger.info(f"Loaded {len(questions)} questions from {file_path}")
    return questions


async def warm_cache(qa_service: QAService, questions: List[str]):
    """
    Pre-compute embeddings for common questions.

    This function calls _get_question_embedding() for each question, which:
    1. Computes the embedding using SBERT/ONNX
    2. Caches it in Redis with 24h TTL
    3. Subsequent requests get <5ms cache hits

    Args:
        qa_service: Initialized QA service with model loaded
        questions: List of questions to cache
    """
    logger.info(f"Starting cache warmup for {len(questions)} questions...")

    cached_count = 0
    failed_count = 0

    for i, question in enumerate(questions, 1):
        try:
            # Compute and cache embedding (non-blocking per question)
            await qa_service._get_question_embedding(question)
            cached_count += 1

            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(questions)} embeddings cached...")

        except Exception as e:
            failed_count += 1
            logger.warning(f"Failed to cache question '{question}': {e}")

    logger.info(
        f"Cache warmup complete: {cached_count}/{len(questions)} cached, "
        f"{failed_count} failed"
    )


async def main():
    """Run cache warming."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("Starting cache warming service...")

    # Check if cache is enabled
    if not settings.enable_redis_cache:
        logger.error("Redis cache is disabled (ENABLE_REDIS_CACHE=false)")
        logger.error("Enable Redis to use cache warming")
        sys.exit(1)

    # Initialize services
    logger.info("Initializing cache service...")
    cache_service = await create_cache_service()

    if not cache_service.enabled:
        logger.error("Cache service failed to initialize")
        sys.exit(1)

    logger.info("Initializing QA service...")
    qa_service = await QAService.create(settings, cache_service)

    # Ensure model is loaded
    logger.info("Loading SBERT model...")
    await qa_service._ensure_model_loaded()
    logger.info(f"Model loaded: {qa_service.model_format}")

    # Load top questions
    questions_file = settings.qa_cache_warmup_questions_file
    logger.info(f"Loading questions from: {questions_file}")
    questions = await load_top_questions(questions_file)

    if not questions:
        logger.warning("No questions to cache, skipping warmup")
        return

    # Warm cache (top 50 only to avoid excessive load)
    max_questions = 50
    questions_to_cache = questions[:max_questions]
    logger.info(f"Warming cache with top {len(questions_to_cache)} questions...")

    await warm_cache(qa_service, questions_to_cache)

    logger.info("Cache warming complete!")


if __name__ == "__main__":
    asyncio.run(main())
