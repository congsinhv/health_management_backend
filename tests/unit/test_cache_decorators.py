"""
Unit tests for Cache Decorators.

Tests cover automatic cache invalidation decorators and
their integration with service methods.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Any

from app.services.cache_decorators import (
    cache_invalidate_on,
    invalidate_user_cache,
    invalidate_conversation_cache,
    invalidate_message_cache,
    invalidate_qa_cache,
    CacheInvalidationMixin,
)
from app.services.cache_invalidation import InvalidationEvent


class TestCacheInvalidateOnDecorator:
    """Test the generic cache_invalidate_on decorator."""

    @pytest.mark.asyncio
    async def test_basic_invalidation(self):
        """Test basic invalidation decorator functionality."""
        mock_result = Mock()
        mock_result.id = 123
        mock_result.user_id = 456

        with patch("app.services.cache_decorators.invalidate_cache") as mock_invalidate:
            mock_invalidate.return_value = None

            @cache_invalidate_on(InvalidationEvent.USER_UPDATE)
            async def test_function(user_id: int, name: str):
                return mock_result

            result = await test_function(user_id=456, name="test")

            # Verify function was called and result returned
            assert result == mock_result

            # Verify invalidation was called
            mock_invalidate.assert_called_once()
            call_args = mock_invalidate.call_args[1]
            assert call_args["user_id"] == 456
            assert call_args["result_id"] == 123

    @pytest.mark.asyncio
    async def test_with_id_param(self):
        """Test decorator with custom ID parameter."""
        with patch("app.services.cache_decorators.invalidate_cache") as mock_invalidate:

            @cache_invalidate_on(
                InvalidationEvent.CONVERSATION_UPDATE, id_param="conversation_id"
            )
            async def test_function(conversation_id: int, user_id: int):
                return Mock(id=789)

            await test_function(conversation_id=789, user_id=456)

            call_args = mock_invalidate.call_args[1]
            assert call_args["id"] == 789
            assert call_args["user_id"] == 456

    @pytest.mark.asyncio
    async def test_with_hash_params(self):
        """Test decorator with hash parameters."""
        with patch("app.services.cache_decorators.invalidate_cache") as mock_invalidate:

            @cache_invalidate_on(
                InvalidationEvent.QA_ANSWER_CREATE, hash_params=["question"]
            )
            async def test_function(question: str, user_id: int):
                return Mock()

            await test_function(question="What is health?", user_id=456)

            call_args = mock_invalidate.call_args[1]
            assert "question_hash" in call_args
            # Should be MD5 hash of the question
            expected_hash = (
                "7c47222f71333d1716513aa7230e8f45"  # MD5 of "What is health?"
            )
            assert call_args["question_hash"] == expected_hash

    @pytest.mark.asyncio
    async def test_sync_function_warning(self):
        """Test decorator with sync function logs warning."""
        with patch("app.services.cache_decorators.logger") as mock_logger:

            @cache_invalidate_on(InvalidationEvent.USER_UPDATE)
            def sync_function(user_id: int):
                return Mock(id=123)

            result = sync_function(user_id=456)

            assert result is not None
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidation_error_handling(self):
        """Test that invalidation errors don't break the function."""
        with patch("app.services.cache_decorators.invalidate_cache") as mock_invalidate:
            mock_invalidate.side_effect = Exception("Invalidation failed")

            @cache_invalidate_on(InvalidationEvent.USER_UPDATE)
            async def test_function(user_id: int):
                return Mock(id=123)

            # Should not raise exception
            result = await test_function(user_id=456)
            assert result is not None


class TestUserCacheDecorator:
    """Test user-specific cache decorators."""

    @pytest.mark.asyncio
    async def test_user_update_decorator(self):
        """Test user cache invalidation on update."""
        mock_result = Mock()
        mock_result.id = 123

        with patch("app.services.cache_decorators.invalidate_cache") as mock_invalidate:

            @invalidate_user_cache(on_update=True, on_delete=False)
            async def update_user(user_id: int, **kwargs):
                return mock_result

            result = await update_user(user_id=123)

            assert result == mock_result
            mock_invalidate.assert_called_once_with(
                InvalidationEvent.USER_UPDATE, user_id=123
            )

    @pytest.mark.asyncio
    async def test_user_delete_decorator(self):
        """Test user cache invalidation on delete."""
        with patch("app.services.cache_decorators.invalidate_cache") as mock_invalidate:

            @invalidate_user_cache(on_update=False, on_delete=True)
            async def delete_user(user_id: int):
                return Mock(id=123)

            await delete_user(user_id=456)

            mock_invalidate.assert_called_once_with(
                InvalidationEvent.USER_DELETE, user_id=456
            )

    @pytest.mark.asyncio
    async def test_user_delete_by_method_name(self):
        """Test user deletion detection by method name."""
        with patch("app.services.cache_decorators.invalidate_cache") as mock_invalidate:

            @invalidate_user_cache()
            async def delete_user_account(user_id: int):
                return Mock(id=789)

            await delete_user_account(user_id=789)

            # Should detect delete in method name
            mock_invalidate.assert_called_once_with(
                InvalidationEvent.USER_DELETE, user_id=789
            )


class TestConversationCacheDecorator:
    """Test conversation-specific cache decorators."""

    @pytest.mark.asyncio
    async def test_conversation_create_decorator(self):
        """Test conversation cache invalidation on create."""
        mock_result = Mock()
        mock_result.id = 123
        mock_result.user_id = 456

        with patch("app.services.cache_decorators.invalidate_cache") as mock_invalidate:

            @invalidate_conversation_cache(on_create=True)
            async def create_conversation(user_id: int, **kwargs):
                return mock_result

            result = await create_conversation(user_id=456)

            assert result == mock_result
            mock_invalidate.assert_called_once_with(
                InvalidationEvent.CONVERSATION_CREATE, user_id=456, conversation_id=123
            )

    @pytest.mark.asyncio
    async def test_conversation_pin_decorator(self):
        """Test conversation cache invalidation on pin."""
        with patch("app.services.cache_decorators.invalidate_cache") as mock_invalidate:

            @invalidate_conversation_cache(on_pin=True)
            async def pin_conversation(conversation_id: int, user_id: int):
                return Mock(id=conversation_id, user_id=user_id)

            await pin_conversation(conversation_id=789, user_id=456)

            mock_invalidate.assert_called_once_with(
                InvalidationEvent.CONVERSATION_PIN, conversation_id=789, user_id=456
            )


class TestMessageCacheDecorator:
    """Test message-specific cache decorators."""

    @pytest.mark.asyncio
    async def test_message_create_decorator(self):
        """Test message cache invalidation on create."""
        mock_result = Mock()
        mock_result.id = 123
        mock_result.conversation_id = 456
        mock_result.user_id = 789

        with patch("app.services.cache_decorators.invalidate_cache") as mock_invalidate:

            @invalidate_message_cache(on_create=True)
            async def create_message(conversation_id: int, user_id: int, **kwargs):
                return mock_result

            result = await create_message(conversation_id=456, user_id=789)

            assert result == mock_result
            mock_invalidate.assert_called_once_with(
                InvalidationEvent.MESSAGE_CREATE, conversation_id=456, user_id=789
            )

    @pytest.mark.asyncio
    async def test_message_delete_decorator(self):
        """Test message cache invalidation on delete."""
        with patch("app.services.cache_decorators.invalidate_cache") as mock_invalidate:

            @invalidate_message_cache(on_delete=True)
            async def delete_message(
                message_id: int, conversation_id: int, user_id: int
            ):
                return Mock(id=message_id)

            await delete_message(message_id=123, conversation_id=456, user_id=789)

            mock_invalidate.assert_called_once_with(
                InvalidationEvent.MESSAGE_DELETE, conversation_id=456, user_id=789
            )


class TestQACacheDecorator:
    """Test Q&A-specific cache decorators."""

    @pytest.mark.asyncio
    async def test_qa_answer_decorator(self):
        """Test Q&A cache invalidation on answer."""
        with patch("app.services.cache_decorators.invalidate_cache") as mock_invalidate:
            import hashlib

            @invalidate_qa_cache(on_answer=True)
            async def ask_question(question: str, **kwargs):
                return Mock()

            await ask_question(question="What is health?")

            # Verify the question was hashed correctly
            expected_hash = hashlib.md5("What is health?".encode()).hexdigest()
            mock_invalidate.assert_called_once_with(
                InvalidationEvent.QA_ANSWER_CREATE, question_hash=expected_hash
            )

    @pytest.mark.asyncio
    async def test_qa_content_update_decorator(self):
        """Test Q&A cache invalidation on content update."""
        with patch("app.services.cache_decorators.invalidate_cache") as mock_invalidate:
            import hashlib

            @invalidate_qa_cache(on_content_update=True)
            async def update_content(content: str, **kwargs):
                return Mock()

            await update_content(content="New medical article content")

            # Verify the content was hashed correctly
            expected_hash = hashlib.md5(
                "New medical article content".encode()
            ).hexdigest()
            mock_invalidate.assert_called_once_with(
                InvalidationEvent.QA_CONTENT_UPDATE, content_hash=expected_hash
            )


class TestCacheInvalidationMixin:
    """Test CacheInvalidationMixin functionality."""

    def test_mixin_initialization(self):
        """Test mixin initialization."""

        class TestService(CacheInvalidationMixin):
            def __init__(self):
                super().__init__()

        service = TestService()
        assert service._cache_invalidator is None

    def test_set_cache_invalidator(self):
        """Test setting cache invalidator."""

        class TestService(CacheInvalidationMixin):
            def __init__(self):
                super().__init__()

        service = TestService()
        mock_invalidator = Mock()

        service.set_cache_invalidator(mock_invalidator)
        assert service._cache_invalidator == mock_invalidator

    @pytest.mark.asyncio
    async def test_invalidate_caches_with_invalidator(self):
        """Test cache invalidation with invalidator set."""

        class TestService(CacheInvalidationMixin):
            def __init__(self):
                super().__init__()

        service = TestService()
        mock_invalidator = AsyncMock()
        service.set_cache_invalidator(mock_invalidator)

        await service.invalidate_caches(InvalidationEvent.USER_UPDATE, user_id=123)

        mock_invalidator.invalidate.assert_called_once_with(
            InvalidationEvent.USER_UPDATE, user_id=123
        )

    @pytest.mark.asyncio
    async def test_invalidate_caches_without_invalidator(self):
        """Test cache invalidation without invalidator set."""

        class TestService(CacheInvalidationMixin):
            def __init__(self):
                super().__init__()

        service = TestService()
        # No invalidator set

        # Should not raise exception
        await service.invalidate_caches(InvalidationEvent.USER_UPDATE, user_id=123)

    @pytest.mark.asyncio
    async def test_bulk_invalidate_caches(self):
        """Test bulk cache invalidation."""

        class TestService(CacheInvalidationMixin):
            def __init__(self):
                super().__init__()

        service = TestService()
        mock_invalidator = AsyncMock()
        service.set_cache_invalidator(mock_invalidator)

        events = [
            {"event": InvalidationEvent.USER_UPDATE, "kwargs": {"user_id": 123}},
            {
                "event": InvalidationEvent.MESSAGE_CREATE,
                "kwargs": {"conversation_id": 456},
            },
        ]

        await service.bulk_invalidate_caches(events)

        mock_invalidator.bulk_invalidate.assert_called_once_with(events)


class TestIntegrationWithServices:
    """Test integration of decorators with service-like classes."""

    @pytest.mark.asyncio
    async def test_service_with_multiple_decorators(self):
        """Test service method with multiple cache considerations."""
        with patch("app.services.cache_decorators.invalidate_cache") as mock_invalidate:

            class MockService:
                @invalidate_user_cache()
                @invalidate_conversation_cache()
                async def complex_operation(
                    self, user_id: int, conversation_id: int = None
                ):
                    return Mock(
                        id=123, user_id=user_id, conversation_id=conversation_id
                    )

            service = MockService()
            result = await service.complex_operation(user_id=456, conversation_id=789)

            assert result is not None
            # Should have been called twice (once for each decorator)
            assert mock_invalidate.call_count == 2

    @pytest.mark.asyncio
    async def test_service_method_parameter_extraction(self):
        """Test parameter extraction from service methods."""
        with patch("app.services.cache_decorators.invalidate_cache") as mock_invalidate:

            class MockService:
                def __init__(self):
                    self.user_id = 999  # Service-level user_id

                @cache_invalidate_on(
                    InvalidationEvent.CONVERSATION_UPDATE,
                    conversation_id_param="conv_id",
                )
                async def update_conversation(self, conv_id: int, title: str):
                    return Mock(id=conv_id, user_id=self.user_id)

            service = MockService()
            await service.update_conversation(conv_id=123, title="New Title")

            call_args = mock_invalidate.call_args[1]
            assert call_args["conversation_id"] == 123
            # Should extract user_id from self
            assert call_args["user_id"] == 999
            assert call_args["result_id"] == 123
