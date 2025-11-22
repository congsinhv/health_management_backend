"""
Cache-aware decorators for automatic cache invalidation.

Provides decorators that automatically invalidate relevant caches
when service methods are called.
"""

import functools
import asyncio
from typing import Any, Callable, Optional, List, Dict
from typing_extensions import Union

from app.config import logger
from app.services.cache_invalidation import (
    CacheInvalidator,
    InvalidationEvent,
    invalidate_cache,
)


def cache_invalidate_on(
    event: InvalidationEvent,
    id_param: Optional[str] = None,
    user_id_param: Optional[str] = None,
    conversation_id_param: Optional[str] = None,
    hash_params: Optional[List[str]] = None,
):
    """
    Decorator to automatically invalidate cache when a method is called.

    Args:
        event: The invalidation event type
        id_param: Parameter name for the primary ID (default: 'id' or first param)
        user_id_param: Parameter name for user ID
        conversation_id_param: Parameter name for conversation ID
        hash_params: Parameter names to use for generating hashes
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            # Extract context parameters
            context = {}

            # Get user ID
            if user_id_param:
                context["user_id"] = kwargs.get(user_id_param)
            elif "user_id" in kwargs:
                context["user_id"] = kwargs["user_id"]
            elif args and hasattr(args[0], "__self__"):  # Method call
                # Try to get user_id from self or first argument
                if hasattr(args[0], "user_id"):
                    context["user_id"] = args[0].user_id

            # Get conversation ID
            if conversation_id_param:
                context["conversation_id"] = kwargs.get(conversation_id_param)
            elif "conversation_id" in kwargs:
                context["conversation_id"] = kwargs["conversation_id"]

            # Get primary ID
            if id_param:
                context["id"] = kwargs.get(id_param)
            elif "id" in kwargs:
                context["id"] = kwargs["id"]
            elif len(args) > 1:  # First argument after self
                context["id"] = args[1]

            # Generate hashes if needed
            if hash_params:
                import hashlib

                for param in hash_params:
                    if param in kwargs:
                        value = str(kwargs[param])
                        context[f"{param}_hash"] = hashlib.md5(
                            value.encode()
                        ).hexdigest()

            # Call the original function
            result = await func(*args, **kwargs)

            # Invalidate cache after successful operation
            try:
                # Add result-specific context if available
                if hasattr(result, "id"):
                    context["result_id"] = result.id
                if hasattr(result, "user_id") and not context.get("user_id"):
                    context["user_id"] = result.user_id
                if hasattr(result, "conversation_id") and not context.get(
                    "conversation_id"
                ):
                    context["conversation_id"] = result.conversation_id

                await invalidate_cache(
                    event, **{k: v for k, v in context.items() if v is not None}
                )

            except Exception as e:
                logger.error(f"Cache invalidation failed in decorator for {event}: {e}")

            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            # For sync functions, we can't do async invalidation easily
            # Just call the function and log a warning
            logger.warning(
                f"Cache invalidation decorator used on sync function {func.__name__}"
            )
            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def invalidate_user_cache(on_update: bool = True, on_delete: bool = True):
    """
    Decorator for user service methods to invalidate user caches.

    Args:
        on_update: Invalidate on user updates
        on_delete: Invalidate on user deletion
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Determine if this is a delete operation based on method name or parameters
            is_delete = "delete" in func.__name__.lower() or on_delete

            result = await func(*args, **kwargs)

            try:
                # Extract user_id from result or kwargs
                user_id = kwargs.get("user_id")
                if not user_id and hasattr(result, "id"):
                    user_id = result.id
                elif not user_id and len(args) > 1:
                    user_id = args[1]

                if user_id:
                    event = (
                        InvalidationEvent.USER_DELETE
                        if is_delete
                        else InvalidationEvent.USER_UPDATE
                    )
                    await invalidate_cache(event, user_id=user_id)

            except Exception as e:
                logger.error(f"User cache invalidation failed: {e}")

            return result

        return wrapper

    return decorator


def invalidate_conversation_cache(
    on_create: bool = False,
    on_update: bool = True,
    on_delete: bool = False,
    on_pin: bool = False,
):
    """
    Decorator for conversation service methods to invalidate conversation caches.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            result = await func(*args, **kwargs)

            try:
                # Extract context
                user_id = kwargs.get("user_id")
                conversation_id = kwargs.get("conversation_id")

                if not conversation_id and hasattr(result, "id"):
                    conversation_id = result.id
                elif not conversation_id and len(args) > 1:
                    conversation_id = args[1]

                if not user_id and hasattr(result, "user_id"):
                    user_id = result.user_id
                elif not user_id and "user_id" in kwargs:
                    user_id = kwargs["user_id"]

                # Determine event type
                if on_create or "create" in func.__name__.lower():
                    event = InvalidationEvent.CONVERSATION_CREATE
                elif on_delete or "delete" in func.__name__.lower():
                    event = InvalidationEvent.CONVERSATION_DELETE
                elif on_pin or "pin" in func.__name__.lower():
                    event = InvalidationEvent.CONVERSATION_PIN
                else:
                    event = InvalidationEvent.CONVERSATION_UPDATE

                context = {}
                if user_id:
                    context["user_id"] = user_id
                if conversation_id:
                    context["conversation_id"] = conversation_id

                await invalidate_cache(event, **context)

            except Exception as e:
                logger.error(f"Conversation cache invalidation failed: {e}")

            return result

        return wrapper

    return decorator


def invalidate_message_cache(
    on_create: bool = False, on_update: bool = True, on_delete: bool = False
):
    """
    Decorator for message service methods to invalidate message caches.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            result = await func(*args, **kwargs)

            try:
                # Extract context
                conversation_id = kwargs.get("conversation_id")
                user_id = kwargs.get("user_id")

                if not conversation_id and hasattr(result, "conversation_id"):
                    conversation_id = result.conversation_id
                elif (
                    not conversation_id and len(args) > 2
                ):  # self, message_id, conversation_id
                    conversation_id = args[2]

                if not user_id and "user_id" in kwargs:
                    user_id = kwargs["user_id"]

                # Determine event type
                if on_create or "create" in func.__name__.lower():
                    event = InvalidationEvent.MESSAGE_CREATE
                elif on_delete or "delete" in func.__name__.lower():
                    event = InvalidationEvent.MESSAGE_DELETE
                else:
                    event = InvalidationEvent.MESSAGE_UPDATE

                context = {}
                if user_id:
                    context["user_id"] = user_id
                if conversation_id:
                    context["conversation_id"] = conversation_id

                await invalidate_cache(event, **context)

            except Exception as e:
                logger.error(f"Message cache invalidation failed: {e}")

            return result

        return wrapper

    return decorator


def invalidate_qa_cache(on_answer: bool = True, on_content_update: bool = True):
    """
    Decorator for Q&A service methods to invalidate Q&A caches.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            result = await func(*args, **kwargs)

            try:
                # Extract context for hashing
                if on_answer or "answer" in func.__name__.lower():
                    # For answer creation, hash the question
                    question = kwargs.get("question")
                    if question:
                        import hashlib

                        question_hash = hashlib.md5(question.encode()).hexdigest()
                        await invalidate_cache(
                            InvalidationEvent.QA_ANSWER_CREATE,
                            question_hash=question_hash,
                        )

                if on_content_update or (
                    "summarize" in func.__name__.lower()
                    or "update" in func.__name__.lower()
                ):
                    # For content updates, hash the content
                    content = kwargs.get("content")
                    if content:
                        import hashlib

                        content_hash = hashlib.md5(content.encode()).hexdigest()
                        await invalidate_cache(
                            InvalidationEvent.QA_CONTENT_UPDATE,
                            content_hash=content_hash,
                        )

            except Exception as e:
                logger.error(f"Q&A cache invalidation failed: {e}")

            return result

        return wrapper

    return decorator


class CacheInvalidationMixin:
    """
    Mixin class for services to easily add cache invalidation capabilities.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cache_invalidator = None

    def set_cache_invalidator(self, invalidator: CacheInvalidator):
        """Set the cache invalidator for this service."""
        self._cache_invalidator = invalidator

    async def invalidate_caches(self, event: InvalidationEvent, **kwargs):
        """Invalidate caches for the given event."""
        if self._cache_invalidator:
            await self._cache_invalidator.invalidate(event, **kwargs)

    async def bulk_invalidate_caches(self, events: List[Dict[str, Any]]):
        """Bulk invalidate caches."""
        if self._cache_invalidator:
            await self._cache_invalidator.bulk_invalidate(events)
