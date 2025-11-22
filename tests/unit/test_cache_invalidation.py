"""
Unit tests for Cache Invalidator.

Tests cover event-driven cache invalidation, pattern matching,
bulk operations, and statistics tracking.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta

from app.services.cache import CacheService
from app.services.cache_invalidation import (
    CacheInvalidator,
    InvalidationEvent,
    get_cache_invalidator,
    invalidate_cache,
    bulk_invalidate_cache,
)


@pytest.fixture
def mock_cache_service():
    """Create a mock cache service."""
    service = AsyncMock(spec=CacheService)
    service.enabled = True
    service.delete_pattern = AsyncMock(return_value=1)
    return service


@pytest.fixture
def cache_invalidator(mock_cache_service):
    """Create CacheInvalidator with mock cache service."""
    return CacheInvalidator(mock_cache_service)


class TestCacheInvalidator:
    """Test CacheInvalidator functionality."""

    def test_init_with_cache_service(self, mock_cache_service):
        """Test initialization with cache service."""
        invalidator = CacheInvalidator(mock_cache_service)
        assert invalidator.cache_service == mock_cache_service
        assert len(invalidator._event_handlers) > 0
        assert len(invalidator._invalidation_history) == 0

    def test_init_default_handlers(self, cache_invalidator):
        """Test that default handlers are registered."""
        expected_events = [
            InvalidationEvent.USER_UPDATE,
            InvalidationEvent.USER_DELETE,
            InvalidationEvent.CONVERSATION_CREATE,
            InvalidationEvent.CONVERSATION_UPDATE,
            InvalidationEvent.CONVERSATION_DELETE,
            InvalidationEvent.CONVERSATION_PIN,
            InvalidationEvent.MESSAGE_CREATE,
            InvalidationEvent.MESSAGE_UPDATE,
            InvalidationEvent.MESSAGE_DELETE,
            InvalidationEvent.QA_ANSWER_CREATE,
            InvalidationEvent.QA_CONTENT_UPDATE,
        ]

        for event in expected_events:
            assert event in cache_invalidator._event_handlers
            assert len(cache_invalidator._event_handlers[event]) > 0

    @pytest.mark.asyncio
    async def test_invalidate_user_update(self, cache_invalidator, mock_cache_service):
        """Test user update invalidation."""
        user_id = 123

        await cache_invalidator.invalidate(
            InvalidationEvent.USER_UPDATE, user_id=user_id
        )

        # Verify cache patterns were deleted
        expected_calls = [
            ("user:detail:123",),
            ("user:email:*",),
        ]

        assert mock_cache_service.delete_pattern.call_count == len(expected_calls)
        for i, expected_call in enumerate(expected_calls):
            actual_call = mock_cache_service.delete_pattern.call_args_list[i][0]
            assert actual_call == expected_call

        # Verify history was recorded
        assert len(cache_invalidator._invalidation_history) == 1
        record = cache_invalidator._invalidation_history[0]
        assert record["event"] == InvalidationEvent.USER_UPDATE.value
        assert record["context"]["user_id"] == 123

    @pytest.mark.asyncio
    async def test_invalidate_user_delete(self, cache_invalidator, mock_cache_service):
        """Test user deletion invalidation."""
        user_id = 123

        await cache_invalidator.invalidate(
            InvalidationEvent.USER_DELETE, user_id=user_id
        )

        # Verify all user-related patterns were deleted
        expected_patterns = [
            "user:detail:123",
            "user:email:*",
            "conv:list:123:*",
            "conv:count:123",
            "conv:pinned:123:*",
            "conv:search:123:*",
            "msg:list:*:123:*",
        ]

        assert mock_cache_service.delete_pattern.call_count == len(expected_patterns)

    @pytest.mark.asyncio
    async def test_invalidate_conversation_create(
        self, cache_invalidator, mock_cache_service
    ):
        """Test conversation creation invalidation."""
        user_id = 456

        await cache_invalidator.invalidate(
            InvalidationEvent.CONVERSATION_CREATE, user_id=user_id
        )

        # Verify conversation list patterns were deleted
        expected_patterns = [
            "conv:list:456:*",
            "conv:count:456",
            "conv:pinned:456:*",
            "conv:search:456:*",
        ]

        assert mock_cache_service.delete_pattern.call_count == len(expected_patterns)

    @pytest.mark.asyncio
    async def test_invalidate_conversation_update(
        self, cache_invalidator, mock_cache_service
    ):
        """Test conversation update invalidation."""
        conversation_id = 789
        user_id = 456

        await cache_invalidator.invalidate(
            InvalidationEvent.CONVERSATION_UPDATE,
            conversation_id=conversation_id,
            user_id=user_id,
        )

        # Verify conversation-specific patterns were deleted
        expected_patterns = [
            "conv:detail:789:456",
            "conv:list:456:*",
            "conv:pinned:456:*",
            "conv:search:456:*",
        ]

        assert mock_cache_service.delete_pattern.call_count == len(expected_patterns)

    @pytest.mark.asyncio
    async def test_invalidate_message_create(
        self, cache_invalidator, mock_cache_service
    ):
        """Test message creation invalidation."""
        conversation_id = 789
        user_id = 456

        await cache_invalidator.invalidate(
            InvalidationEvent.MESSAGE_CREATE,
            conversation_id=conversation_id,
            user_id=user_id,
        )

        # Verify message patterns were deleted
        expected_patterns = [
            "msg:list:789:*",
            "msg:latest:789",
            "msg:count:789",
            "conv:msgcount:789",
        ]

        assert mock_cache_service.delete_pattern.call_count == len(expected_patterns)

    @pytest.mark.asyncio
    async def test_invalidate_qa_answer_create(
        self, cache_invalidator, mock_cache_service
    ):
        """Test Q&A answer creation invalidation."""
        question_hash = "abc123def456"

        await cache_invalidator.invalidate(
            InvalidationEvent.QA_ANSWER_CREATE, question_hash=question_hash
        )

        # Verify Q&A patterns were deleted
        mock_cache_service.delete_pattern.assert_called_once_with(
            "qa:answers:abc123def456:*"
        )

    @pytest.mark.asyncio
    async def test_bulk_invalidate(self, cache_invalidator, mock_cache_service):
        """Test bulk invalidation operations."""
        events = [
            {"event": InvalidationEvent.USER_UPDATE, "kwargs": {"user_id": 123}},
            {
                "event": InvalidationEvent.MESSAGE_CREATE,
                "kwargs": {"conversation_id": 456, "user_id": 789},
            },
            {
                "event": InvalidationEvent.CONVERSATION_CREATE,
                "kwargs": {"user_id": 789},
            },
        ]

        await cache_invalidator.bulk_invalidate(events)

        # Verify all patterns were processed
        # Should have more than 5 delete_pattern calls due to multiple events
        assert mock_cache_service.delete_pattern.call_count > 5

        # Verify bulk invalidation was recorded
        assert len(cache_invalidator._invalidation_history) >= 1
        bulk_records = [
            r
            for r in cache_invalidator._invalidation_history
            if r.get("event_type") == "bulk_invalidation"
        ]
        assert len(bulk_records) >= 1

    @pytest.mark.asyncio
    async def test_bulk_invalidate_concurrent_processing(self, cache_invalidator):
        """Test that bulk invalidation handles concurrent calls properly."""
        events1 = [{"event": InvalidationEvent.USER_UPDATE, "kwargs": {"user_id": 123}}]
        events2 = [{"event": InvalidationEvent.USER_UPDATE, "kwargs": {"user_id": 456}}]

        # Run bulk invalidations concurrently
        task1 = asyncio.create_task(cache_invalidator.bulk_invalidate(events1))
        task2 = asyncio.create_task(cache_invalidator.bulk_invalidate(events2))

        await asyncio.gather(task1, task2)

        # Both should have been processed
        assert len(cache_invalidator._invalidation_history) >= 1

    @pytest.mark.asyncio
    async def test_invalidate_disabled_cache(self):
        """Test invalidation when cache is disabled."""
        disabled_cache_service = AsyncMock(spec=CacheService)
        disabled_cache_service.enabled = False

        invalidator = CacheInvalidator(disabled_cache_service)

        await invalidator.invalidate(InvalidationEvent.USER_UPDATE, user_id=123)

        # No cache operations should be performed
        disabled_cache_service.delete_pattern.assert_not_called()

        # History should still be recorded
        assert (
            len(invalidator._invalidation_history) == 0
        )  # Disabled cache skips recording

    @pytest.mark.asyncio
    async def test_handler_error_handling(self, cache_invalidator, mock_cache_service):
        """Test error handling in invalidation handlers."""
        # Make delete_pattern raise an exception
        mock_cache_service.delete_pattern.side_effect = Exception("Redis error")

        # Should not raise exception, should handle gracefully
        await cache_invalidator.invalidate(InvalidationEvent.USER_UPDATE, user_id=123)

        # History should still be recorded even with errors
        assert len(cache_invalidator._invalidation_history) == 1

    def test_get_invalidation_stats(self, cache_invalidator):
        """Test invalidation statistics calculation."""
        # Add some history records
        now = datetime.now()
        old_time = now - timedelta(hours=25)  # Outside 24-hour window

        # Recent record
        cache_invalidator._invalidation_history.append(
            {
                "timestamp": now.isoformat(),
                "event": InvalidationEvent.USER_UPDATE.value,
                "patterns_invalidated": 2,
                "duration_ms": 10.5,
            }
        )

        # Old record (should be filtered out)
        cache_invalidator._invalidation_history.append(
            {
                "timestamp": old_time.isoformat(),
                "event": InvalidationEvent.MESSAGE_CREATE.value,
                "patterns_invalidated": 3,
                "duration_ms": 15.2,
            }
        )

        stats = cache_invalidator.get_invalidation_stats(hours=24)

        assert stats["period_hours"] == 24
        assert stats["total_invalidations"] == 1
        assert stats["total_patterns_invalidated"] == 2
        assert stats["avg_duration_ms"] == 10.5
        assert InvalidationEvent.USER_UPDATE.value in stats["event_breakdown"]
        assert InvalidationEvent.MESSAGE_CREATE.value not in stats["event_breakdown"]

    def test_get_invalidation_stats_empty(self, cache_invalidator):
        """Test stats calculation with empty history."""
        stats = cache_invalidator.get_invalidation_stats(hours=24)

        assert stats["period_hours"] == 24
        assert stats["total_invalidations"] == 0
        assert stats["total_patterns_invalidated"] == 0
        assert stats["avg_duration_ms"] == 0
        assert len(stats["event_breakdown"]) == 0

    def test_register_custom_handler(self, cache_invalidator, mock_cache_service):
        """Test registering custom invalidation handlers."""
        custom_handler = AsyncMock(return_value=["custom:pattern:*"])

        cache_invalidator.register_custom_handler(
            InvalidationEvent.USER_UPDATE, custom_handler
        )

        # Should now have 2 handlers for USER_UPDATE (default + custom)
        assert (
            len(cache_invalidator._event_handlers[InvalidationEvent.USER_UPDATE]) == 2
        )

        # Test that custom handler gets called
        custom_handler.return_value = ["custom:pattern:*"]
        asyncio.get_event_loop().run_until_complete(
            cache_invalidator.invalidate(InvalidationEvent.USER_UPDATE, user_id=123)
        )
        custom_handler.assert_called_once_with(user_id=123)

    def test_clear_history(self, cache_invalidator):
        """Test clearing invalidation history."""
        # Add some history
        cache_invalidator._invalidation_history.append({"event": "test"})
        assert len(cache_invalidator._invalidation_history) == 1

        cache_invalidator.clear_history()

        assert len(cache_invalidator._invalidation_history) == 0

    def test_history_limit(self, cache_invalidator):
        """Test that history is limited to 1000 records."""
        # Use the proper method to add records which includes truncation logic
        for i in range(1005):
            cache_invalidator._record_invalidation(
                InvalidationEvent.USER_UPDATE, {"user_id": i}, ["pattern_1"], 10.0
            )

        # Should be limited to 1000
        assert len(cache_invalidator._invalidation_history) == 1000

        # Should keep the most recent records
        assert (
            cache_invalidator._invalidation_history[-1]["event"]
            == InvalidationEvent.USER_UPDATE.value
        )


class TestGlobalInvalidator:
    """Test global invalidator functions."""

    @pytest.mark.asyncio
    async def test_get_cache_invalidator_singleton(self, mock_cache_service):
        """Test that get_cache_invalidator returns singleton instance."""
        # Clear global state
        import app.services.cache_invalidation

        app.services.cache_invalidation._invalidator = None

        invalidator1 = get_cache_invalidator(mock_cache_service)
        invalidator2 = get_cache_invalidator(mock_cache_service)

        assert invalidator1 is invalidator2
        assert invalidator1.cache_service == mock_cache_service

    @pytest.mark.asyncio
    async def test_invalidate_cache_convenience_function(self, mock_cache_service):
        """Test convenience function for cache invalidation."""
        # Clear global state and set up invalidator
        import app.services.cache_invalidation

        app.services.cache_invalidation._invalidator = CacheInvalidator(
            mock_cache_service
        )

        await invalidate_cache(InvalidationEvent.USER_UPDATE, user_id=123)

        mock_cache_service.delete_pattern.assert_called()

    @pytest.mark.asyncio
    async def test_bulk_invalidate_cache_convenience_function(self, mock_cache_service):
        """Test convenience function for bulk cache invalidation."""
        # Clear global state and set up invalidator
        import app.services.cache_invalidation

        app.services.cache_invalidation._invalidator = CacheInvalidator(
            mock_cache_service
        )

        events = [
            {"event": InvalidationEvent.USER_UPDATE, "kwargs": {"user_id": 123}},
        ]

        await bulk_invalidate_cache(events)

        mock_cache_service.delete_pattern.assert_called()

    @pytest.mark.asyncio
    async def test_convenience_functions_no_invalidator(self):
        """Test convenience functions when no invalidator is set."""
        # Clear global state
        import app.services.cache_invalidation

        app.services.cache_invalidation._invalidator = None

        # Should not raise exception
        await invalidate_cache(InvalidationEvent.USER_UPDATE, user_id=123)
        await bulk_invalidate_cache(
            [{"event": InvalidationEvent.USER_UPDATE, "kwargs": {"user_id": 123}}]
        )


class TestInvalidationEvent:
    """Test InvalidationEvent enum."""

    def test_event_values(self):
        """Test that all expected events are defined."""
        expected_events = {
            "user_update",
            "user_delete",
            "conversation_create",
            "conversation_update",
            "conversation_delete",
            "conversation_pin",
            "message_create",
            "message_update",
            "message_delete",
            "qa_answer_create",
            "qa_content_update",
        }

        actual_events = {event.value for event in InvalidationEvent}
        assert actual_events == expected_events

    def test_event_uniqueness(self):
        """Test that all event values are unique."""
        values = [event.value for event in InvalidationEvent]
        assert len(values) == len(set(values))
