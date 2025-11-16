"""
AI Chat Service for intelligent conversation responses.
"""

import json
import asyncpg
import logging
from typing import Optional, Dict, Any, List
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

    async def generate_ai_response(
        self, user_id: int, request: AIPromptRequest
    ) -> AIResponse:
        """Generate AI response for user prompt."""
        # Verify user owns the conversation
        conversation = await self.conversation_repo.get_by_id_and_user(
            request.conversation_id, user_id
        )
        if not conversation:
            raise ValueError("Conversation not found or access denied")

        try:
            # Get conversation context (recent messages)
            recent_messages = await self._get_conversation_context(
                request.conversation_id, user_id, limit=5
            )

            # Build context for AI
            context = {
                "conversation_title": conversation.get("title"),
                "recent_messages": recent_messages,
                "user_metadata": conversation.get("metadata", {}),
                "additional_context": request.context or {},
            }

            # Check if prompt is health-related and use QA service
            health_response = await self._try_health_qa_response(request.prompt)

            if health_response and health_response.get("answers"):
                # Use QA service response for health-related questions
                ai_content = self._format_qa_response(health_response)
                metadata = {
                    "response_type": "health_qa",
                    "model_used": "vietnamese-sbert",
                    "qa_results": health_response.get("answers", {}),
                }
            else:
                # Use OpenRouter for general conversation
                ai_content = await self._generate_general_response(
                    request.prompt, context
                )
                metadata = {
                    "response_type": "general_conversation",
                    "model_used": self.qa_service.openrouter_model,
                }

            return AIResponse(
                content=ai_content,
                metadata=metadata,
                model_used=metadata["model_used"],
            )

        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            # Fallback response
            return AIResponse(
                content="Xin lỗi, tôi đang gặp sự cố khi xử lý yêu cầu của bạn. Vui lòng thử lại sau.",
                metadata={"response_type": "error", "error": str(e)},
                model_used="fallback",
            )

    async def create_ai_message_pair(
        self, user_id: int, conversation_id: int, user_prompt: str
    ) -> tuple[MessageResponse, Optional[MessageResponse]]:
        """Create user message and AI response pair."""
        # Verify user owns the conversation
        conversation = await self.conversation_repo.get_by_id_and_user(
            conversation_id, user_id
        )
        if not conversation:
            raise ValueError("Conversation not found or access denied")

        # Create user message
        user_message_data = MessageCreate(
            conversation_id=conversation_id,
            user_id=user_id,
            content=user_prompt,
            content_type="text",
            metadata={"source": "user_input"},
        )

        user_message_record = await self.message_repo.create(
            {
                "conversation_id": conversation_id,
                "user_id": user_id,
                "content": user_prompt,
                "content_type": "text",
                "metadata": {"source": "user_input"},
            }
        )

        if not user_message_record:
            raise RuntimeError("Failed to create user message")

        user_message = MessageResponse(
            id=user_message_record["id"],
            conversation_id=user_message_record["conversation_id"],
            user_id=user_message_record["user_id"],
            content=user_message_record["content"],
            content_type=user_message_record["content_type"],
            metadata=json.loads(user_message_record.get("metadata") or "{}"),
            created_at=user_message_record["created_at"],
            updated_at=user_message_record["updated_at"],
        )

        # Generate AI response
        try:
            ai_request = AIPromptRequest(
                conversation_id=conversation_id,
                prompt=user_prompt,
                user_id=user_id,
            )

            ai_response = await self.generate_ai_response(user_id, ai_request)

            # Create AI message
            ai_message_record = await self.message_repo.create(
                {
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "content": ai_response.content,
                    "content_type": "text",
                    "metadata": {
                        "source": "ai_generated",
                        "model_used": ai_response.model_used,
                        "response_type": ai_response.metadata.get("response_type"),
                        **ai_response.metadata,
                    },
                }
            )

            ai_message = None
            if ai_message_record:
                ai_message = MessageResponse(
                    id=ai_message_record["id"],
                    conversation_id=ai_message_record["conversation_id"],
                    user_id=ai_message_record["user_id"],
                    content=ai_message_record["content"],
                    content_type=ai_message_record["content_type"],
                    metadata=json.loads(ai_message_record.get("metadata") or "{}"),
                    created_at=ai_message_record["created_at"],
                    updated_at=ai_message_record["updated_at"],
                )

        except Exception as e:
            logger.error(f"Error creating AI message: {e}")
            ai_message = None

        return user_message, ai_message

    async def _get_conversation_context(
        self, conversation_id: int, user_id: int, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get recent messages for conversation context."""
        try:
            # Verify user owns the conversation
            conversation = await self.conversation_repo.get_by_id_and_user(
                conversation_id, user_id
            )
            if not conversation:
                return []

            # Get recent messages
            message_records = await self.message_repo.list_by_conversation(
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

    async def _generate_general_response(
        self, prompt: str, context: Dict[str, Any]
    ) -> str:
        """Generate general conversation response using OpenRouter."""
        if not self.qa_service.openrouter_api_key:
            return "Xin lỗi, dịch vụ AI hiện không khả dụng. Vui lòng liên hệ quản trị viên."

        # Build conversation context
        recent_messages = context.get("recent_messages", [])
        context_text = ""

        if recent_messages:
            context_text = "Ngữ cảnh trò chuyện gần đây:\n"
            for msg in recent_messages[-3:]:  # Last 3 messages
                sender = "Trợ lý AI" if msg["is_ai"] else "Bạn"
                context_text += f"{sender}: {msg['content']}\n"
            context_text += "\n"

        headers = {
            "Authorization": f"Bearer {self.qa_service.openrouter_api_key}",
            "Content-Type": "application/json",
        }

        system_prompt = (
            "Bạn là một trợ lý y tế thông minh và thân thiện. Hãy trả lời câu hỏi của người dùng "
            "bằng tiếng Việt một cách chính xác, dễ hiểu và có trách nhiệm. Nếu câu hỏi không liên quan đến y tế, "
            "hãy trả lời một cách khéo léo và hướng dẫn người dùng đến chủ đề phù hợp hơn."
        )

        user_prompt = f"{context_text}Câu hỏi của người dùng: {prompt}"

        payload = {
            "model": self.qa_service.openrouter_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self.qa_service.openrouter_temperature,
            "max_tokens": self.qa_service.openrouter_max_tokens,
        }

        try:
            import requests

            response = requests.post(
                self.qa_service.openrouter_url,
                headers=headers,
                json=payload,
                timeout=self.qa_service.openrouter_timeout,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

        except Exception as e:
            logger.error(f"Error calling OpenRouter API: {e}")
            return "Xin lỗi, tôi đang gặp sự cố kết nối với dịch vụ AI. Vui lòng thử lại sau."

    async def get_ai_health_suggestions(
        self, user_id: int, conversation_id: int
    ) -> List[str]:
        """Get AI-powered health suggestions based on conversation history."""
        try:
            # Verify user owns the conversation
            conversation = await self.conversation_repo.get_by_id_and_user(
                conversation_id, user_id
            )
            if not conversation:
                return []

            # Get conversation messages
            message_records = await self.message_repo.list_by_conversation(
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
            logger.error(f"Error calling OpenRouter API: {e}")
            return "Xin lỗi, tôi đang gặp sự cố kết nối với dịch vụ AI. Vui lòng thử lại sau."
