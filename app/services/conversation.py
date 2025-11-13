"""
Conversation service for business logic.
"""

import asyncpg
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import hashlib

from app.db.conversation import ConversationRepository
from app.db.message import MessageRepository
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationDetail,
    ConversationListItem,
    ConversationListResponse,
    ConversationSearchParams,
)
from app.schemas.search import ConversationSearchResponse, ConversationSearchResult
from app.services.cache import conversation_cache
from app.config import settings

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for conversation business logic."""

    def __init__(self, pool: asyncpg.Pool, qa_service=None):
        self.pool = pool
        self.conversation_repo = ConversationRepository(pool)
        self.message_repo = MessageRepository(pool)
        self.qa_service = qa_service

    async def create_conversation(
        self,
        user_id: int,
        title: Optional[str] = None,
        question: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        first_message: Optional[str] = None,
    ) -> ConversationDetail:
        """Create a new conversation."""
        try:
            # Create conversation
            conversation_id = await self.conversation_repo.create_conversation(
                user_id=user_id,
                title=title,
                question=question,
                tags=tags or [],
                metadata=metadata or {},
            )

            # If first message is provided, create it
            if first_message:
                await self.message_repo.create_message(
                    conversation_id=conversation_id, role="user", content=first_message
                )

            # Get created conversation
            conversation = await self.conversation_repo.get_conversation_by_user(
                conversation_id, user_id
            )

            if not conversation:
                raise ValueError("Failed to create conversation")

            return self._convert_to_conversation_detail(conversation)

        except Exception as e:
            logger.error(f"Error creating conversation: {e}")
            raise

    async def get_conversation(
        self, conversation_id: int, user_id: int
    ) -> Optional[ConversationDetail]:
        """Get a conversation by ID."""
        try:
            # Try cache first
            cached = conversation_cache.get_conversation(user_id, conversation_id)
            if cached:
                return ConversationDetail(**cached)

            # Get from database
            conversation = await self.conversation_repo.get_conversation_by_user(
                conversation_id, user_id
            )
            if not conversation:
                return None

            detail = self._convert_to_conversation_detail(conversation)

            # Cache the result
            conversation_cache.set_conversation(
                user_id, conversation_id, detail.model_dump()
            )

            return detail

        except Exception as e:
            logger.error(f"Error getting conversation {conversation_id}: {e}")
            raise

    async def update_conversation(
        self, conversation_id: int, user_id: int, **updates
    ) -> Optional[ConversationDetail]:
        """Update a conversation."""
        try:
            # Validate updates
            valid_fields = ["title", "is_pinned", "tags", "metadata"]
            filtered_updates = {k: v for k, v in updates.items() if k in valid_fields}

            if not filtered_updates:
                raise ValueError("No valid fields to update")

            # Check if user is trying to pin too many conversations
            if filtered_updates.get("is_pinned"):
                pinned_count = len(
                    await self.conversation_repo.get_pinned_conversations(user_id)
                )
                if pinned_count >= getattr(settings, "conversation_max_pinned", 10):
                    raise ValueError(
                        f"Maximum {getattr(settings, 'conversation_max_pinned', 10)} conversations can be pinned"
                    )

            success = await self.conversation_repo.update_conversation(
                conversation_id, user_id, **filtered_updates
            )

            if not success:
                return None

            # Invalidate cache for this conversation
            conversation_cache.delete_conversation(user_id, conversation_id)

            # Invalidate user's conversation list cache
            conversation_cache.delete_pattern(f"conversation_list:{user_id}:*")

            # Invalidate pinned conversations cache if pin status changed
            if "is_pinned" in filtered_updates:
                conversation_cache.delete(f"pinned_conversations:{user_id}")

            # Return updated conversation (will be cached)
            return await self.get_conversation(conversation_id, user_id)

        except Exception as e:
            logger.error(f"Error updating conversation {conversation_id}: {e}")
            raise

    async def delete_conversation(self, conversation_id: int, user_id: int) -> bool:
        """Delete a conversation (soft delete)."""
        try:
            return await self.conversation_repo.delete_conversation(
                conversation_id, user_id
            )

        except Exception as e:
            logger.error(f"Error deleting conversation {conversation_id}: {e}")
            raise

    async def list_conversations(
        self,
        user_id: int,
        page: int = 1,
        page_size: int = 20,
        include_pinned: bool = True,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> ConversationListResponse:
        """List user conversations with pagination."""
        try:
            # Try cache first
            filters = {"include_pinned": include_pinned}
            cached = conversation_cache.get_conversation_list(
                user_id, page, page_size, filters
            )
            if cached:
                return ConversationListResponse(**cached)

            skip = (page - 1) * page_size

            # Get conversations
            conversations = await self.conversation_repo.get_user_conversations(
                user_id=user_id,
                skip=skip,
                limit=page_size,
                include_pinned=include_pinned,
                sort_by=sort_by,
                sort_order=sort_order,
            )

            # Get total count
            total = await self.conversation_repo.count_user_conversations(
                user_id, include_pinned
            )

            # Convert to response format
            conversation_items = [
                self._convert_to_conversation_list_item(conv) for conv in conversations
            ]

            response = ConversationListResponse.create(
                conversations=conversation_items,
                total=total,
                page=page,
                page_size=page_size,
            )

            # Cache the result
            conversation_cache.set_conversation_list(
                user_id, page, page_size, response.model_dump(), filters
            )

            return response

        except Exception as e:
            logger.error(f"Error listing conversations: {e}")
            raise

    async def pin_conversation(
        self, conversation_id: int, user_id: int, is_pinned: bool = True
    ) -> bool:
        """Pin or unpin a conversation."""
        try:
            # Check pin limit if trying to pin
            if is_pinned:
                pinned_count = len(
                    await self.conversation_repo.get_pinned_conversations(user_id)
                )
                if pinned_count >= getattr(settings, "conversation_max_pinned", 10):
                    raise ValueError(
                        f"Maximum {getattr(settings, 'conversation_max_pinned', 10)} conversations can be pinned"
                    )

            return await self.conversation_repo.pin_conversation(
                conversation_id, user_id, is_pinned
            )

        except Exception as e:
            logger.error(f"Error pinning conversation {conversation_id}: {e}")
            raise

    async def update_tags(
        self, conversation_id: int, user_id: int, tags: List[str]
    ) -> Optional[ConversationDetail]:
        """Update conversation tags."""
        try:
            # Validate tags
            if len(tags) > 10:
                raise ValueError("Maximum 10 tags allowed")

            for tag in tags:
                if len(tag) > 50:
                    raise ValueError("Each tag must be 50 characters or less")

            success = await self.conversation_repo.update_tags(
                conversation_id, user_id, tags
            )

            if not success:
                return None

            # Return updated conversation
            return await self.get_conversation(conversation_id, user_id)

        except Exception as e:
            logger.error(f"Error updating tags for conversation {conversation_id}: {e}")
            raise

    async def search_conversations(
        self, user_id: int, params: ConversationSearchParams
    ) -> ConversationSearchResponse:
        """Search conversations with advanced filtering and highlighting."""
        try:
            start_time = datetime.now()

            # Create query hash for caching
            query_hash = hashlib.md5(
                f"{params.query}:{params.tags}:{params.pinned_only}:{params.date_from}:{params.date_to}:{params.sort_by}:{params.sort_order}".encode()
            ).hexdigest()

            # Try cache first
            cached = conversation_cache.get_search_results(
                user_id, query_hash, params.page, params.page_size
            )
            if cached:
                return ConversationSearchResponse(**cached)

            # Build filters
            filters = {
                "tags": params.tags,
                "pinned_only": params.pinned_only,
                "date_from": params.date_from,
                "date_to": params.date_to,
                "sort_by": params.sort_by,
                "sort_order": params.sort_order,
            }

            # Search conversations using enhanced method
            skip = (params.page - 1) * params.page_size
            conversations, total = await self.conversation_repo.full_text_search(
                user_id=user_id,
                query=params.query or "",
                skip=skip,
                limit=params.page_size,
                filters=filters,
            )

            # Convert to search results with highlighting
            results = []
            for conv in conversations:
                # Determine matched fields
                matched_fields = []
                if conv.get("title_highlight") and conv.get(
                    "title_highlight"
                ) != conv.get("title", ""):
                    matched_fields.append("title")
                if conv.get("question_highlight") and conv.get(
                    "question_highlight"
                ) != conv.get("question", ""):
                    matched_fields.append("question")
                if conv.get("content_highlight"):
                    matched_fields.append("content")

                result = ConversationSearchResult(
                    conversation_id=conv["id"],
                    title=conv.get("title"),
                    question=conv.get("question"),
                    tags=conv.get("tags", []),
                    is_pinned=conv.get("is_pinned", False),
                    message_count=conv.get("message_count", 0),
                    last_message_at=conv.get("last_message_at"),
                    created_at=conv["created_at"],
                    updated_at=conv["updated_at"],
                    relevance_score=conv.get("rank", 0.0),
                    highlights=[
                        {
                            "field": "title",
                            "fragment": conv.get(
                                "title_highlight", conv.get("title", "")
                            ),
                            "highlights": self._extract_highlights(
                                conv.get("title_highlight", "")
                            ),
                        },
                        {
                            "field": "question",
                            "fragment": conv.get(
                                "question_highlight", conv.get("question", "")
                            ),
                            "highlights": self._extract_highlights(
                                conv.get("question_highlight", "")
                            ),
                        },
                        {
                            "field": "content",
                            "fragment": conv.get("content_highlight", ""),
                            "highlights": self._extract_highlights(
                                conv.get("content_highlight", "")
                            ),
                        },
                    ],
                    matched_fields=matched_fields,
                )
                results.append(result)

            # Get search suggestions
            suggestions = []
            if params.query:
                suggestions = await self.conversation_repo.get_search_suggestions(
                    user_id, params.query, limit=5
                )

            # Calculate search time
            search_time = (datetime.now() - start_time).total_seconds() * 1000

            response = ConversationSearchResponse(
                query=params.query or "",
                results=results,
                total=total,
                page=params.page,
                page_size=params.page_size,
                total_pages=(
                    (total + params.page_size - 1) // params.page_size
                    if total > 0
                    else 0
                ),
                search_time_ms=search_time,
                suggestions=suggestions,
            )

            # Cache the result
            conversation_cache.set_search_results(
                user_id,
                query_hash,
                params.page,
                params.page_size,
                response.model_dump(),
            )

            return response

        except Exception as e:
            logger.error(f"Error searching conversations: {e}")
            raise

    async def get_search_suggestions(
        self, user_id: int, query: str, limit: int = 5
    ) -> List[str]:
        """Get search suggestions for autocomplete."""
        try:
            return await self.conversation_repo.get_search_suggestions(
                user_id, query, limit
            )
        except Exception as e:
            logger.error(f"Error getting search suggestions: {e}")
            return []

    async def get_popular_search_terms(
        self, user_id: int, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get popular search terms for the user."""
        try:
            return await self.conversation_repo.get_popular_search_terms(user_id, limit)
        except Exception as e:
            logger.error(f"Error getting popular search terms: {e}")
            return []

    async def add_tags(
        self, conversation_id: int, user_id: int, tags: List[str]
    ) -> Optional[ConversationDetail]:
        """Add tags to a conversation (merge with existing)."""
        try:
            # Validate tags
            if len(tags) > 10:
                raise ValueError("Maximum 10 tags allowed")

            for tag in tags:
                if len(tag) > 50:
                    raise ValueError("Each tag must be 50 characters or less")

            # Get current conversation to merge with existing tags
            conversation = await self.conversation_repo.get_conversation_by_user(
                conversation_id, user_id
            )
            if not conversation:
                return None

            # Merge existing tags with new tags
            existing_tags = set(conversation.get("tags", []))
            new_tags = set(tags)
            merged_tags = list(existing_tags.union(new_tags))

            success = await self.conversation_repo.update_tags(
                conversation_id, user_id, merged_tags
            )

            if not success:
                return None

            # Return updated conversation
            return await self.get_conversation(conversation_id, user_id)

        except ValueError as e:
            logger.error(f"Error adding tags: {e}")
            raise
        except Exception as e:
            logger.error(f"Error adding tags to conversation {conversation_id}: {e}")
            raise

    async def remove_tags(
        self, conversation_id: int, user_id: int, tags: List[str]
    ) -> Optional[ConversationDetail]:
        """Remove tags from a conversation."""
        try:
            # Get current conversation
            conversation = await self.conversation_repo.get_conversation_by_user(
                conversation_id, user_id
            )
            if not conversation:
                return None

            # Remove specified tags
            existing_tags = set(conversation.get("tags", []))
            tags_to_remove = set(tags)
            remaining_tags = list(existing_tags - tags_to_remove)

            success = await self.conversation_repo.update_tags(
                conversation_id, user_id, remaining_tags
            )

            if not success:
                return None

            # Return updated conversation
            return await self.get_conversation(conversation_id, user_id)

        except Exception as e:
            logger.error(
                f"Error removing tags from conversation {conversation_id}: {e}"
            )
            raise

    async def get_user_tags(self, user_id: int) -> List[str]:
        """Get all tags used by a user."""
        try:
            # Try cache first
            cached = conversation_cache.get_user_tags(user_id)
            if cached is not None:
                return cached

            tags = await self.conversation_repo.get_user_tags(user_id)

            # Cache the result
            conversation_cache.set_user_tags(user_id, tags)

            return tags
        except Exception as e:
            logger.error(f"Error getting user tags: {e}")
            return []

    def _extract_highlights(self, highlighted_text: str) -> List[str]:
        """Extract highlighted terms from ts_headline output."""
        if not highlighted_text:
            return []

        import re

        # Extract content between <mark> and </mark> tags
        highlights = re.findall(r"<mark>(.*?)</mark>", highlighted_text)
        return highlights

    async def auto_generate_title(self, conversation_id: int, user_id: int) -> str:
        """Auto-generate title from conversation content."""
        try:
            # Check if conversation already has a title
            conversation = await self.conversation_repo.get_conversation_by_user(
                conversation_id, user_id
            )
            if not conversation:
                raise ValueError("Conversation not found")

            if conversation.get("title"):
                return conversation["title"]

            # Get first user message and assistant response
            messages = await self.message_repo.get_conversation_messages(
                conversation_id, user_id, limit=2
            )

            if len(messages) < 2:
                # Fallback to using first message content
                if messages:
                    content = messages[0]["content"]
                    # Truncate to reasonable length
                    title = content[:60] + "..." if len(content) > 60 else content
                    # Update conversation with generated title
                    await self.conversation_repo.update_conversation(
                        conversation_id, user_id, title=title
                    )
                    return title
                else:
                    return "New Conversation"

            user_message = None
            assistant_message = None

            for msg in messages:
                if msg["role"] == "user" and not user_message:
                    user_message = msg
                elif msg["role"] == "assistant" and not assistant_message:
                    assistant_message = msg

            if not user_message or not assistant_message:
                return "New Conversation"

            # Generate title using QAService if available
            if self.qa_service and hasattr(
                self.qa_service, "generate_conversation_title"
            ):
                try:
                    # Extract answers from assistant message
                    answers = assistant_message.get("answers", {})
                    answer_summary = ""
                    if answers:
                        # Combine all answers into a summary
                        all_answers = []
                        for field_answer_list in answers.values():
                            all_answers.extend(field_answer_list)
                        answer_summary = " ".join(all_answers[:3])  # First 3 answers

                    title = await self.qa_service.generate_conversation_title(
                        question=user_message["content"], answer_summary=answer_summary
                    )

                    # Update conversation with generated title
                    await self.conversation_repo.update_conversation(
                        conversation_id, user_id, title=title
                    )

                    return title

                except Exception as e:
                    logger.warning(f"Failed to generate title with QA service: {e}")

            # Fallback: use user message content
            content = user_message["content"]
            title = content[:60] + "..." if len(content) > 60 else content

            # Update conversation with generated title
            await self.conversation_repo.update_conversation(
                conversation_id, user_id, title=title
            )

            return title

        except Exception as e:
            logger.error(
                f"Error auto-generating title for conversation {conversation_id}: {e}"
            )
            raise

    async def get_pinned_conversations(
        self, user_id: int
    ) -> List[ConversationListItem]:
        """Get all pinned conversations for a user."""
        try:
            # Try cache first
            cached = conversation_cache.get_pinned_conversations(user_id)
            if cached:
                return [ConversationListItem(**conv) for conv in cached]

            conversations = await self.conversation_repo.get_pinned_conversations(
                user_id
            )
            result = [
                self._convert_to_conversation_list_item(conv) for conv in conversations
            ]

            # Cache the result
            conversation_cache.set_pinned_conversations(
                user_id, [conv.model_dump() for conv in result]
            )

            return result

        except Exception as e:
            logger.error(f"Error getting pinned conversations: {e}")
            raise

    async def get_conversation_stats(self, user_id: int) -> Dict[str, Any]:
        """Get conversation statistics for a user."""
        try:
            # Get total conversations
            total = await self.conversation_repo.count_user_conversations(user_id)

            # Get pinned conversations
            pinned = len(await self.conversation_repo.get_pinned_conversations(user_id))

            # TODO: Implement more stats when needed
            return {
                "total_conversations": total,
                "pinned_conversations": pinned,
                "total_messages": 0,  # TODO: Implement
                "average_messages_per_conversation": 0.0,  # TODO: Implement
                "most_used_tags": [],  # TODO: Implement
            }

        except Exception as e:
            logger.error(f"Error getting conversation stats: {e}")
            raise

    def _convert_to_conversation_detail(
        self, record: asyncpg.Record
    ) -> ConversationDetail:
        """Convert database record to ConversationDetail."""
        return ConversationDetail(
            id=record["id"],
            user_id=record["user_id"],
            title=record.get("title"),
            question=record.get("question"),
            is_pinned=record.get("is_pinned", False),
            tags=record.get("tags", []),
            created_at=record["created_at"],
            updated_at=record.get("updated_at", record["created_at"]),
            deleted_at=record.get("deleted_at"),
            message_count=record.get("message_count", 0),
            last_message_at=record.get("last_message_at"),
            metadata=record.get("metadata", {}),
        )

    def _convert_to_conversation_list_item(
        self, record: asyncpg.Record
    ) -> ConversationListItem:
        """Convert database record to ConversationListItem."""
        return ConversationListItem(
            id=record["id"],
            user_id=record["user_id"],
            title=record.get("title"),
            question=record.get("question"),
            is_pinned=record.get("is_pinned", False),
            tags=record.get("tags", []),
            created_at=record["created_at"],
            updated_at=record.get("updated_at", record["created_at"]),
            deleted_at=record.get("deleted_at"),
            message_count=record.get("message_count", 0),
            last_message_preview=record.get("last_message_preview"),
            last_message_at=record.get("last_message_at"),
            metadata=record.get("metadata", {}),
        )
