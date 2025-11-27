"""
AI Chat Service for intelligent conversation responses.
"""

import json
import asyncpg
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
from app.services.qa_service import QAService
from app.db.message import MessageRepository
from app.db.conversation import ConversationRepository
from app.schemas.message import (
    AIPromptRequest,
    AIResponse,
    MessageCreate,
    MessageResponse,
)

logger = logging.getLogger(__name__)


class AIChatService:
    """Service for AI-powered chat functionality."""

    def __init__(self, db_pool: asyncpg.Pool, qa_service: QAService):
        self.db_pool = db_pool
        self.message_repo = MessageRepository(db_pool)
        self.conversation_repo = ConversationRepository(db_pool)
        self.qa_service = qa_service
        self.openai_client = qa_service.openai_client

    async def _get_conversation_context(
        self, conversation_id: int, user_id: int, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get recent messages for conversation context."""
        try:
            # Verify user owns the conversation
            conversation = await self.conversation_repo.get_conversation_by_id_and_user(
                conversation_id, user_id
            )
            if not conversation:
                return []

            # Get recent messages
            message_records = await self.message_repo.list_messages_by_conversation(
                conversation_id, limit=limit
            )

            context = []
            for record in reversed(message_records):  # Chronological order
                context.append(
                    {
                        "content": record["content"],
                        "content_type": record["content_type"],
                        "created_at": record["created_at"],
                        "is_ai": json.loads(record.get("metadata", "{}")).get("source")
                        == "ai_generated",
                    }
                )

            return context

        except Exception as e:
            logger.error(f"Error getting conversation context: {e}")
            return []

    async def _try_health_qa_response(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Try to get response from QA service for health-related questions."""
        try:
            # Use QA service to check if this is a health-related question
            qa_result = self.qa_service.ask_question(
                user_question=prompt,
                threshold=0.3,  # Lower threshold for broader matching
                top_k=3,
            )

            # Check if we got meaningful results
            answers = qa_result.get("answers", {})

            # Filter out "No Results Found" and empty responses
            meaningful_answers = {
                field: items
                for field, items in answers.items()
                if field != "No Results Found" and items
            }

            if meaningful_answers:
                return {
                    "question": qa_result.get("question"),
                    "answers": meaningful_answers,
                    "summary": qa_result.get("summary", ""),
                }

            return None

        except Exception as e:
            logger.error(f"Error in QA service: {e}")
            return None

    def _format_qa_response(self, qa_result: Dict[str, Any]) -> str:
        """Format QA service response for chat."""
        answers = qa_result.get("answers", {})
        summary = qa_result.get("summary", "")

        if not answers:
            return "Xin lỗi, tôi không tìm thấy thông tin phù hợp cho câu hỏi của bạn."

        # Format answers by field
        formatted_parts = []
        for field, items in answers.items():
            if items and field != "No Results Found":
                formatted_parts.append(f"**{field}:**")
                for item in items[:2]:  # Limit to 2 items per field
                    formatted_parts.append(f"• {item}")

        # Add AI summary if available
        if summary and summary.strip():
            formatted_parts.append(f"\n**Tóm tắt:** {summary}")

        return "\n".join(formatted_parts)

    async def get_ai_health_suggestions(
        self, user_id: int, conversation_id: int
    ) -> List[str]:
        """Get AI-powered health suggestions based on conversation history."""
        try:
            # Verify user owns the conversation
            conversation = await self.conversation_repo.get_conversation_by_id_and_user(
                conversation_id, user_id
            )
            if not conversation:
                return []

            # Get conversation messages
            message_records = await self.message_repo.list_messages_by_conversation(
                conversation_id, limit=20
            )

            # Extract user messages (non-AI)
            user_messages = []
            for record in message_records:
                metadata = record.get("metadata", {})
                if metadata.get("source") != "ai_generated":
                    user_messages.append(record["content"])

            if not user_messages:
                return []

            # Analyze conversation for health topics
            conversation_text = " ".join(user_messages)

            # Try to get related health information using QA service
            suggestions = []

            # Extract key health keywords from conversation
            health_keywords = self._extract_health_keywords(conversation_text)

            for keyword in health_keywords[:3]:  # Limit to 3 keywords
                try:
                    qa_result = self.qa_service.ask_question(
                        user_question=f"thông tin về {keyword}",
                        threshold=0.4,
                        top_k=2,
                    )

                    answers = qa_result.get("answers", {})
                    if answers and "No Results Found" not in answers:
                        summary = qa_result.get("summary", "")
                        if summary:
                            suggestions.append(f"Về {keyword}: {summary[:200]}...")

                except Exception as e:
                    logger.error(f"Error getting suggestion for {keyword}: {e}")
                    continue

            return suggestions

        except Exception as e:
            logger.error(f"Error getting AI suggestions: {e}")
            return []

    def _extract_health_keywords(self, text: str) -> List[str]:
        """Extract health-related keywords from text."""
        # Simple keyword extraction - could be enhanced with NLP
        health_keywords = [
            "sốt",
            "đau đầu",
            "ho",
            "viêm",
            "tiểu đường",
            "huyết áp",
            "tim mạch",
            "tiêu hóa",
            "xương khớp",
            "da liễu",
            "thần kinh",
            "dị ứng",
            "mệt mỏi",
            "khó thở",
            "đau ngực",
            "đau bụng",
            "táo bón",
            "tiêu chảy",
            "mất ngủ",
            "stress",
            "căng thẳng",
        ]

        text_lower = text.lower()
        found_keywords = []

        for keyword in health_keywords:
            if keyword in text_lower:
                found_keywords.append(keyword)

        return found_keywords

    async def _generate_conversation_title(self, message: str) -> str:
        """Generate conversation title based on text."""
        # Simple title generation - could be enhanced with NLP
        try:
            import requests

            response = self.openai_client.responses.create(
                model="gpt-5-nano",
                reasoning={"effort": "low"},
                input=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {
                        "role": "user",
                        "content": f"Tạo tiêu đề cho cuộc trò chuyện: {message}. Output should be a single line of text with no additional information and without any markdown formatting or any additional information (Using Vietnamese).",
                    },
                ],
                store=True,
            )

            return response.output_text

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return "Xin lỗi, tôi đang gặp sự cố kết nối với dịch vụ AI. Vui lòng thử lại sau."
