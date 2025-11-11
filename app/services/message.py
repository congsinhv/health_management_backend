"""
Message service for business logic.
"""

import asyncpg
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from app.db.message import MessageRepository
from app.db.message_version import MessageVersionRepository
from app.schemas.message import (
    MessageCreate,
    MessageUpdate,
    MessageDetail,
    MessageListResponse,
    MessageTreeNode,
    MessagePathResponse,
)
from app.services.cache import conversation_cache
from app.config import settings

logger = logging.getLogger(__name__)


class MessageService:
    """Service for message business logic."""

    def __init__(self, pool: asyncpg.Pool, qa_service=None, version_service=None):
        self.pool = pool
        self.message_repo = MessageRepository(pool)
        self.version_repo = MessageVersionRepository(pool)
        self.qa_service = qa_service
        self.version_service = version_service

    async def add_message(
        self,
        conversation_id: int,
        user_id: int,
        content: str,
        role: str = "user",
        content_cleaned: Optional[str] = None,
        answers: Optional[Dict[str, List[str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        parent_message_id: Optional[int] = None,
    ) -> MessageDetail:
        """Add a message to a conversation."""
        try:
            # Validate role
            if role not in ["user", "assistant", "system"]:
                raise ValueError("Invalid message role")

            # Validate content length
            if len(content) > 5000:
                raise ValueError("Message content too long")

            # CRITICAL FIX: Validate conversation ownership before creating message
            conversation_exists = await self.message_repo.verify_conversation_ownership(
                conversation_id, user_id
            )
            if not conversation_exists:
                logger.error(
                    f"Security: User {user_id} attempted to add message to conversation {conversation_id} "
                    f"without ownership"
                )
                raise ValueError("Conversation not found or access denied")

            # Create message
            message_id = await self.message_repo.create_message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                content_cleaned=content_cleaned,
                answers=answers,
                metadata=metadata or {},
                parent_message_id=parent_message_id,
            )

            # Update conversation timestamp
            await self.message_repo.update_conversation_timestamp(
                conversation_id, user_id
            )

            # Get created message
            message = await self.message_repo.get_message_by_user(message_id, user_id)
            if not message:
                raise ValueError("Failed to create message")

            return self._convert_to_message_detail(message)

        except Exception as e:
            logger.error(f"Error adding message to conversation {conversation_id}: {e}")
            raise

    async def get_message(
        self, message_id: int, user_id: int
    ) -> Optional[MessageDetail]:
        """Get a message by ID."""
        try:
            # Get the message to find conversation_id
            message = await self.message_repo.get_message_by_user(message_id, user_id)
            if not message:
                return None

            # Try cache first
            cached = conversation_cache.get_message(
                message["conversation_id"], message_id
            )
            if cached:
                return MessageDetail(**cached)

            # Convert and cache the result
            detail = self._convert_to_message_detail(message)
            conversation_cache.set_message(
                message["conversation_id"], message_id, detail.model_dump()
            )

            return detail

        except Exception as e:
            logger.error(f"Error getting message {message_id}: {e}")
            raise

    async def update_message(
        self,
        message_id: int,
        user_id: int,
        content: str,
        create_version: bool = True,
        content_cleaned: Optional[str] = None,
        answers: Optional[Dict[str, List[str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MessageDetail:
        """Update a message."""
        try:
            # Get current message for versioning and cache invalidation
            current_message = await self.message_repo.get_message_by_user(
                message_id, user_id
            )
            if not current_message:
                raise ValueError("Message not found")

            # Create version if requested
            if create_version:
                latest_version = await self.version_repo.get_latest_version_number(
                    message_id, user_id
                )
                await self.version_repo.create_version(
                    message_id=message_id,
                    version_number=latest_version + 1,
                    content=current_message["content"],
                    content_cleaned=current_message.get("content_cleaned"),
                    answers=current_message.get("answers"),
                    metadata=current_message.get("metadata", {}),
                )

            # Update message
            success = await self.message_repo.update_message(
                message_id, user_id, content, content_cleaned, answers, metadata
            )

            if not success:
                raise ValueError("Failed to update message")

            # Get updated message
            updated_message = await self.message_repo.get_message_by_user(
                message_id, user_id
            )
            if not updated_message:
                raise ValueError("Failed to retrieve updated message")

            # Convert and cache the result
            detail = self._convert_to_message_detail(updated_message)
            conversation_cache.set_message(
                current_message["conversation_id"], message_id, detail.model_dump()
            )

            # Invalidate conversation-related cache
            conversation_cache.invalidate_conversation_cache(
                current_message["conversation_id"]
            )

            return detail

        except Exception as e:
            logger.error(f"Error updating message {message_id}: {e}")
            raise

    async def delete_message(self, message_id: int, user_id: int) -> bool:
        """Delete a message (soft delete)."""
        try:
            # Get message for cache invalidation
            current_message = await self.message_repo.get_message_by_user(
                message_id, user_id
            )
            if not current_message:
                raise ValueError("Message not found")

            # Delete message
            success = await self.message_repo.delete_message(message_id, user_id)

            if success:
                # Delete from cache
                conversation_cache.delete_message(
                    current_message["conversation_id"], message_id
                )

                # Invalidate conversation-related cache
                conversation_cache.invalidate_conversation_cache(
                    current_message["conversation_id"]
                )

            return success

        except Exception as e:
            logger.error(f"Error deleting message {message_id}: {e}")
            raise

    async def list_messages(
        self,
        conversation_id: int,
        user_id: int,
        page: int = 1,
        page_size: int = 50,
        order_by: str = "created_at",
    ) -> MessageListResponse:
        """List messages in a conversation with pagination."""
        try:
            # Try cache first
            cached = conversation_cache.get_message_list(
                conversation_id, page, page_size
            )
            if cached:
                return MessageListResponse(**cached)

            skip = (page - 1) * page_size

            # Get messages
            messages = await self.message_repo.get_conversation_messages(
                conversation_id, user_id, skip, page_size, order_by
            )

            # Get total count
            total = await self.message_repo.count_conversation_messages(
                conversation_id, user_id
            )

            # Convert to response format
            message_details = [self._convert_to_message_detail(msg) for msg in messages]

            response = MessageListResponse.create(
                messages=message_details, total=total, page=page, page_size=page_size
            )

            # Cache the result
            conversation_cache.set_message_list(
                conversation_id, page, page_size, response.model_dump()
            )

            return response

        except Exception as e:
            logger.error(
                f"Error listing messages for conversation {conversation_id}: {e}"
            )
            raise

    async def create_branch(
        self,
        parent_message_id: int,
        user_id: int,
        role: str,
        content: str,
        content_cleaned: Optional[str] = None,
        answers: Optional[Dict[str, List[str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MessageDetail:
        """Create a branch from a parent message."""
        try:
            # Validate parent message exists and user has access
            parent_message = await self.message_repo.get_message_by_user(
                parent_message_id, user_id
            )
            if not parent_message:
                raise ValueError("Parent message not found")

            # Create branched message
            message_id = await self.message_repo.create_message_branch(
                parent_message_id=parent_message_id,
                user_id=user_id,
                role=role,
                content=content,
                content_cleaned=content_cleaned,
                answers=answers,
                metadata=metadata or {},
            )

            if not message_id:
                raise ValueError("Failed to create branch")

            # Update conversation timestamp
            await self.message_repo.update_conversation_timestamp(
                parent_message["conversation_id"], user_id
            )

            # Get created message
            message = await self.message_repo.get_message_by_user(message_id, user_id)
            if not message:
                raise ValueError("Failed to retrieve branched message")

            # Convert and cache the result
            detail = self._convert_to_message_detail(message)
            conversation_cache.set_message(
                parent_message["conversation_id"], message_id, detail.model_dump()
            )

            # Invalidate conversation-related cache
            conversation_cache.invalidate_conversation_cache(
                parent_message["conversation_id"]
            )

            return detail

        except Exception as e:
            logger.error(f"Error creating branch from message {parent_message_id}: {e}")
            raise

    async def get_conversation_tree(
        self, conversation_id: int, user_id: int
    ) -> MessageTreeNode:
        """Get the complete conversation tree with branches."""
        try:
            # Get all messages in conversation
            messages = await self.message_repo.get_conversation_tree(
                conversation_id, user_id
            )

            if not messages:
                raise ValueError("Conversation not found or no messages")

            # Build tree structure
            root_messages = [
                msg for msg in messages if msg["parent_message_id"] is None
            ]

            if not root_messages:
                raise ValueError("No root messages found")

            # For now, return the first root message with its children
            # TODO: Handle multiple root messages properly
            root_message = root_messages[0]
            tree_node = self._build_message_tree(root_message, messages)

            return tree_node

        except Exception as e:
            logger.error(f"Error getting conversation tree for {conversation_id}: {e}")
            raise

    async def get_message_path(
        self, message_id: int, user_id: int
    ) -> MessagePathResponse:
        """Get the path from root to a specific message."""
        try:
            path = await self.message_repo.get_branch_path(message_id, user_id)

            # Convert to MessageDetail objects
            path_messages = [self._convert_to_message_detail(msg) for msg in path]

            # Find branch points (messages with children)
            branch_points = []
            for msg in path:
                if msg.get("child_count", 0) > 0:
                    branch_points.append(msg["id"])

            return MessagePathResponse(
                path=path_messages,
                branch_points=branch_points,
                total_length=len(path_messages),
            )

        except Exception as e:
            logger.error(f"Error getting message path for {message_id}: {e}")
            raise

    async def get_message_children(
        self, message_id: int, user_id: int
    ) -> List[MessageDetail]:
        """Get child messages (branches) of a message."""
        try:
            children = await self.message_repo.get_message_children(message_id, user_id)
            return [self._convert_to_message_detail(child) for child in children]

        except Exception as e:
            logger.error(f"Error getting children for message {message_id}: {e}")
            raise

    async def process_user_message(
        self, conversation_id: int, user_id: int, content: str
    ) -> Tuple[MessageDetail, Optional[MessageDetail]]:
        """Process a user message and generate assistant response."""
        try:
            # Add user message
            user_message = await self.add_message(
                conversation_id=conversation_id,
                user_id=user_id,
                content=content,
                role="user",
            )

            # Generate assistant response using QA service
            assistant_response = None
            if self.qa_service:
                try:
                    # Get conversation context for better responses
                    recent_messages = await self.message_repo.get_conversation_messages(
                        conversation_id, user_id, limit=5
                    )

                    # Extract just the content for context
                    context = []
                    for msg in recent_messages:
                        if msg["role"] == "user":
                            context.append(f"User: {msg['content']}")
                        elif msg["role"] == "assistant":
                            # Extract answers if available
                            if msg.get("answers"):
                                for field, answers in msg["answers"].items():
                                    for answer in answers[
                                        :2
                                    ]:  # Limit to first 2 answers
                                        context.append(f"Assistant: {answer}")
                            else:
                                context.append(f"Assistant: {msg['content']}")

                    # Process with QA service
                    qa_response = await self.qa_service.ask_question(
                        question=content,
                        context=(
                            context[-4:] if context else []
                        ),  # Last 4 messages as context
                    )

                    if qa_response and qa_response.get("answers"):
                        # Create assistant message with structured answers
                        assistant_response = await self.add_message(
                            conversation_id=conversation_id,
                            user_id=user_id,
                            content=qa_response.get("summary", ""),
                            role="assistant",
                            answers=qa_response["answers"],
                            content_cleaned=qa_response.get("cleaned_question"),
                            metadata={
                                "source": "qa_service",
                                "model": qa_response.get("model"),
                                "threshold": qa_response.get("threshold"),
                                "processing_time": qa_response.get("processing_time"),
                            },
                        )
                    else:
                        # Fallback message
                        assistant_response = await self.add_message(
                            conversation_id=conversation_id,
                            user_id=user_id,
                            content="Xin lỗi, tôi không tìm thấy câu trả lời phù hợp cho câu hỏi của bạn.",
                            role="assistant",
                            metadata={"source": "qa_service", "status": "no_results"},
                        )

                except Exception as e:
                    logger.error(f"Error processing message with QA service: {e}")
                    # Create fallback message
                    assistant_response = await self.add_message(
                        conversation_id=conversation_id,
                        user_id=user_id,
                        content="Xin lỗi, đã có lỗi xảy ra khi xử lý câu hỏi của bạn. Vui lòng thử lại.",
                        role="assistant",
                        metadata={"source": "fallback", "error": str(e)},
                    )

            return user_message, assistant_response

        except Exception as e:
            logger.error(f"Error processing user message: {e}")
            raise

    def _convert_to_message_detail(self, record: asyncpg.Record) -> MessageDetail:
        """Convert database record to MessageDetail."""
        return MessageDetail(
            id=record["id"],
            conversation_id=record["conversation_id"],
            role=record["role"],
            content=record["content"],
            content_cleaned=record.get("content_cleaned"),
            answers=record.get("answers"),
            parent_message_id=record.get("parent_message_id"),
            created_at=record["created_at"],
            updated_at=record.get("updated_at", record["created_at"]),
            deleted_at=record.get("deleted_at"),
            version_count=record.get("version_count", 0),
            child_count=record.get("child_count", 0),
            metadata=record.get("metadata", {}),
        )

    def _build_message_tree(
        self,
        root_message: asyncpg.Record,
        all_messages: List[asyncpg.Record],
        level: int = 0,
    ) -> MessageTreeNode:
        """Recursively build message tree structure."""
        # Convert root to TreeNode
        tree_node = MessageTreeNode(
            **self._convert_to_message_detail(root_message).model_dump(),
            level=level,
            is_leaf=True,
        )

        # Find children
        children = [
            msg
            for msg in all_messages
            if msg.get("parent_message_id") == root_message["id"]
        ]

        if children:
            tree_node.is_leaf = False
            for child in children:
                child_tree = self._build_message_tree(child, all_messages, level + 1)
                tree_node.children.append(child_tree)

        return tree_node
