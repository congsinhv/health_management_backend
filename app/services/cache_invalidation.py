"""
Comprehensive cache invalidation system.

Provides hooks, event listeners, and intelligent invalidation strategies
for maintaining cache coherence across all entities.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, Set, Callable
from datetime import datetime, timedelta
from enum import Enum

from app.exceptions import (
    CacheException,
    CacheUnavailableException,
    ServiceUnavailableException,
)
from app.core.error_context import ErrorContext
from app.config import logger
from app.services.cache import CacheService


class InvalidationEvent(Enum):
    """Cache invalidation event types."""

    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    CONVERSATION_CREATE = "conversation_create"
    CONVERSATION_UPDATE = "conversation_update"
    CONVERSATION_DELETE = "conversation_delete"
    CONVERSATION_PIN = "conversation_pin"
    MESSAGE_CREATE = "message_create"
    MESSAGE_UPDATE = "message_update"
    MESSAGE_DELETE = "message_delete"
    QA_ANSWER_CREATE = "qa_answer_create"
    QA_CONTENT_UPDATE = "qa_content_update"


class CacheInvalidator:
    """Comprehensive cache invalidation system."""

    def __init__(self, cache_service: CacheService):
        self.cache_service = cache_service
        self._event_handlers: Dict[InvalidationEvent, List[Callable]] = {}
        self._invalidation_history: List[Dict[str, Any]] = []
        self._bulk_invalidation_queue: List[Dict[str, Any]] = []
        self._processing_bulk = False

        # Register default handlers
        self._register_default_handlers()

    def _register_default_handlers(self):
        """Register default invalidation handlers for each event type."""
        self._event_handlers[InvalidationEvent.USER_UPDATE] = [
            self._invalidate_user_on_update
        ]
        self._event_handlers[InvalidationEvent.USER_DELETE] = [
            self._invalidate_user_on_delete
        ]
        self._event_handlers[InvalidationEvent.CONVERSATION_CREATE] = [
            self._invalidate_conversation_lists_on_create
        ]
        self._event_handlers[InvalidationEvent.CONVERSATION_UPDATE] = [
            self._invalidate_conversation_on_update
        ]
        self._event_handlers[InvalidationEvent.CONVERSATION_DELETE] = [
            self._invalidate_conversation_on_delete
        ]
        self._event_handlers[InvalidationEvent.CONVERSATION_PIN] = [
            self._invalidate_pinned_conversations
        ]
        self._event_handlers[InvalidationEvent.MESSAGE_CREATE] = [
            self._invalidate_messages_on_create
        ]
        self._event_handlers[InvalidationEvent.MESSAGE_UPDATE] = [
            self._invalidate_messages_on_update
        ]
        self._event_handlers[InvalidationEvent.MESSAGE_DELETE] = [
            self._invalidate_messages_on_delete
        ]
        self._event_handlers[InvalidationEvent.QA_ANSWER_CREATE] = [
            self._invalidate_qa_on_answer
        ]
        self._event_handlers[InvalidationEvent.QA_CONTENT_UPDATE] = [
            self._invalidate_qa_on_content_update
        ]

    async def invalidate(self, event: InvalidationEvent, **kwargs):
        """
        Invalidate cache entries based on event and context.

        Args:
            event: The invalidation event type
            **kwargs: Context data for the invalidation (user_id, conversation_id, etc.)
        """
        if not self.cache_service or not self.cache_service.enabled:
            return

        start_time = datetime.now()
        invalidated_patterns = []

        try:
            # Get handlers for this event
            handlers = self._event_handlers.get(event, [])

            # Execute all handlers
            for handler in handlers:
                try:
                    patterns = await handler(**kwargs)
                    if patterns:
                        invalidated_patterns.extend(patterns)
                except Exception as e:
                    logger.error(f"Cache invalidation handler failed for {event}: {e}")

            # Record invalidation
            duration = (datetime.now() - start_time).total_seconds() * 1000
            self._record_invalidation(event, kwargs, invalidated_patterns, duration)

            if invalidated_patterns:
                logger.debug(
                    f"Invalidated {len(invalidated_patterns)} cache patterns for {event}"
                )

        except Exception as e:
            logger.error(f"Cache invalidation failed for {event}: {e}")

    async def bulk_invalidate(self, events: List[Dict[str, Any]]):
        """
        Process multiple invalidation events efficiently.

        Args:
            events: List of events with their context
                   [{'event': InvalidationEvent, 'kwargs': {...}}, ...]
        """
        if not self.cache_service or not self.cache_service.enabled:
            return

        # Add to bulk queue
        self._bulk_invalidation_queue.extend(events)

        # Process if not already processing
        if not self._processing_bulk:
            await self._process_bulk_queue()

    async def _process_bulk_queue(self):
        """Process the bulk invalidation queue."""
        if self._processing_bulk or not self._bulk_invalidation_queue:
            return

        self._processing_bulk = True
        start_time = datetime.now()

        try:
            # Collect all unique patterns
            all_patterns = set()
            processed_events = []

            while self._bulk_invalidation_queue:
                event_data = self._bulk_invalidation_queue.pop(0)
                event = event_data["event"]
                kwargs = event_data["kwargs"]

                # Get handlers and collect patterns
                handlers = self._event_handlers.get(event, [])
                for handler in handlers:
                    try:
                        patterns = await handler(**kwargs)
                        if patterns:
                            all_patterns.update(patterns)
                    except Exception as e:
                        logger.error(
                            f"Bulk invalidation handler failed for {event}: {e}"
                        )

                processed_events.append(event)

            # Execute all pattern deletions in batch
            if all_patterns:
                for pattern in all_patterns:
                    try:
                        await self.cache_service.delete_pattern(pattern)
                    except Exception as e:
                        logger.error(f"Bulk pattern deletion failed for {pattern}: {e}")

            # Record bulk invalidation
            duration = (datetime.now() - start_time).total_seconds() * 1000
            self._record_bulk_invalidation(
                processed_events, len(all_patterns), duration
            )

            logger.debug(
                f"Bulk invalidated {len(all_patterns)} patterns for {len(processed_events)} events"
            )

        except Exception as e:
            logger.error(f"Bulk cache invalidation failed: {e}")
        finally:
            self._processing_bulk = False

    # User invalidation handlers
    async def _invalidate_user_on_update(self, user_id: int, **kwargs) -> List[str]:
        """Invalidate user caches on user update."""
        patterns = [
            f"user:detail:{user_id}",
            f"user:email:*",  # All email-based caches
        ]

        for pattern in patterns:
            await self.cache_service.delete_pattern(pattern)

        return patterns

    async def _invalidate_user_on_delete(self, user_id: int, **kwargs) -> List[str]:
        """Invalidate all user data on user deletion."""
        patterns = [
            f"user:detail:{user_id}",
            f"user:email:*",
            f"conv:list:{user_id}:*",  # All conversation lists
            f"conv:count:{user_id}",
            f"conv:pinned:{user_id}:*",
            f"conv:search:{user_id}:*",
            f"msg:list:*:{user_id}:*",  # All message caches
        ]

        for pattern in patterns:
            await self.cache_service.delete_pattern(pattern)

        return patterns

    # Conversation invalidation handlers
    async def _invalidate_conversation_lists_on_create(
        self, user_id: int, **kwargs
    ) -> List[str]:
        """Invalidate conversation list caches on new conversation."""
        patterns = [
            f"conv:list:{user_id}:*",
            f"conv:count:{user_id}",
            f"conv:pinned:{user_id}:*",
            f"conv:search:{user_id}:*",
        ]

        for pattern in patterns:
            await self.cache_service.delete_pattern(pattern)

        return patterns

    async def _invalidate_conversation_on_update(
        self, conversation_id: int, user_id: int, **kwargs
    ) -> List[str]:
        """Invalidate conversation caches on conversation update."""
        patterns = [
            f"conv:detail:{conversation_id}:{user_id}",
            f"conv:list:{user_id}:*",
            f"conv:pinned:{user_id}:*",
            f"conv:search:{user_id}:*",
        ]

        for pattern in patterns:
            await self.cache_service.delete_pattern(pattern)

        return patterns

    async def _invalidate_conversation_on_delete(
        self, conversation_id: int, user_id: int, **kwargs
    ) -> List[str]:
        """Invalidate all conversation data on conversation deletion."""
        patterns = [
            f"conv:detail:{conversation_id}:{user_id}",
            f"conv:list:{user_id}:*",
            f"conv:count:{user_id}",
            f"conv:pinned:{user_id}:*",
            f"conv:search:{user_id}:*",
            f"msg:list:{conversation_id}:*",
            f"msg:latest:{conversation_id}",
            f"msg:count:{conversation_id}",
            f"conv:msgcount:{conversation_id}",  # Cross-service cache
        ]

        for pattern in patterns:
            await self.cache_service.delete_pattern(pattern)

        return patterns

    async def _invalidate_pinned_conversations(
        self, user_id: int, **kwargs
    ) -> List[str]:
        """Invalidate pinned conversation caches."""
        patterns = [
            f"conv:pinned:{user_id}:*",
            f"conv:list:{user_id}:*",
        ]

        for pattern in patterns:
            await self.cache_service.delete_pattern(pattern)

        return patterns

    # Message invalidation handlers
    async def _invalidate_messages_on_create(
        self, conversation_id: int, user_id: int, **kwargs
    ) -> List[str]:
        """Invalidate message caches on new message."""
        patterns = [
            f"msg:list:{conversation_id}:*",
            f"msg:latest:{conversation_id}",
            f"msg:count:{conversation_id}",
            f"conv:msgcount:{conversation_id}",
        ]

        for pattern in patterns:
            await self.cache_service.delete_pattern(pattern)

        return patterns

    async def _invalidate_messages_on_update(
        self, conversation_id: int, **kwargs
    ) -> List[str]:
        """Invalidate message caches on message update."""
        patterns = [
            f"msg:list:{conversation_id}:*",
            f"msg:latest:{conversation_id}",
        ]

        for pattern in patterns:
            await self.cache_service.delete_pattern(pattern)

        return patterns

    async def _invalidate_messages_on_delete(
        self, conversation_id: int, **kwargs
    ) -> List[str]:
        """Invalidate message caches on message deletion."""
        patterns = [
            f"msg:list:{conversation_id}:*",
            f"msg:latest:{conversation_id}",
            f"msg:count:{conversation_id}",
            f"conv:msgcount:{conversation_id}",
        ]

        for pattern in patterns:
            await self.cache_service.delete_pattern(pattern)

        return patterns

    # Q&A invalidation handlers
    async def _invalidate_qa_on_answer(self, question_hash: str, **kwargs) -> List[str]:
        """Invalidate Q&A caches when new answer is created."""
        patterns = [
            f"qa:answers:{question_hash}:*",
        ]

        for pattern in patterns:
            await self.cache_service.delete_pattern(pattern)

        return patterns

    async def _invalidate_qa_on_content_update(
        self, content_hash: str, **kwargs
    ) -> List[str]:
        """Invalidate Q&A summary caches on content update."""
        patterns = [
            f"qa:summary:{content_hash}",
        ]

        for pattern in patterns:
            await self.cache_service.delete_pattern(pattern)

        return patterns

    def _record_invalidation(
        self,
        event: InvalidationEvent,
        context: Dict[str, Any],
        patterns: List[str],
        duration_ms: float,
    ):
        """Record invalidation event for monitoring."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "event": event.value,
            "context": context,
            "patterns_invalidated": len(patterns),
            "patterns": patterns,
            "duration_ms": duration_ms,
        }
        self._invalidation_history.append(record)

        # Keep only last 1000 records
        if len(self._invalidation_history) > 1000:
            self._invalidation_history = self._invalidation_history[-1000:]

    def _record_bulk_invalidation(
        self, events: List[InvalidationEvent], patterns_count: int, duration_ms: float
    ):
        """Record bulk invalidation event."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "event_type": "bulk_invalidation",
            "events_processed": [event.value for event in events],
            "patterns_invalidated": patterns_count,
            "duration_ms": duration_ms,
        }
        self._invalidation_history.append(record)

        # Keep only last 1000 records
        if len(self._invalidation_history) > 1000:
            self._invalidation_history = self._invalidation_history[-1000:]

    def get_invalidation_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get invalidation statistics for the last N hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_records = [
            record
            for record in self._invalidation_history
            if datetime.fromisoformat(record["timestamp"]) > cutoff_time
        ]

        if not recent_records:
            return {
                "period_hours": hours,
                "total_invalidations": 0,
                "total_patterns_invalidated": 0,
                "avg_duration_ms": 0,
                "event_breakdown": {},
            }

        total_patterns = sum(
            record.get("patterns_invalidated", 0) for record in recent_records
        )
        total_duration = sum(record.get("duration_ms", 0) for record in recent_records)

        # Event breakdown
        event_breakdown = {}
        for record in recent_records:
            event = record.get("event", "unknown")
            if event not in event_breakdown:
                event_breakdown[event] = {
                    "count": 0,
                    "patterns_invalidated": 0,
                    "total_duration_ms": 0,
                }

            event_breakdown[event]["count"] += 1
            event_breakdown[event]["patterns_invalidated"] += record.get(
                "patterns_invalidated", 0
            )
            event_breakdown[event]["total_duration_ms"] += record.get("duration_ms", 0)

        return {
            "period_hours": hours,
            "total_invalidations": len(recent_records),
            "total_patterns_invalidated": total_patterns,
            "avg_duration_ms": total_duration / len(recent_records)
            if recent_records
            else 0,
            "event_breakdown": event_breakdown,
        }

    def register_custom_handler(self, event: InvalidationEvent, handler: Callable):
        """Register a custom invalidation handler."""
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(handler)
        logger.info(f"Registered custom handler for {event}")

    def clear_history(self):
        """Clear invalidation history."""
        self._invalidation_history.clear()
        logger.info("Cache invalidation history cleared")


# Global invalidator instance
_invalidator: Optional[CacheInvalidator] = None


def get_cache_invalidator(cache_service: CacheService) -> CacheInvalidator:
    """Get or create the global cache invalidator instance."""
    global _invalidator
    if _invalidator is None:
        _invalidator = CacheInvalidator(cache_service)
    return _invalidator


async def invalidate_cache(event: InvalidationEvent, **kwargs):
    """Convenience function to invalidate cache for an event."""
    global _invalidator
    if _invalidator:
        await _invalidator.invalidate(event, **kwargs)


async def bulk_invalidate_cache(events: List[Dict[str, Any]]):
    """Convenience function to bulk invalidate cache."""
    global _invalidator
    if _invalidator:
        await _invalidator.bulk_invalidate(events)
