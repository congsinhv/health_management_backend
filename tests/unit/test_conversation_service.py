"""
Tests for ConversationService.

Tests conversation business logic including CRUD operations, search,
tags management, caching, and integration with QA service.
"""

import pytest
import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from app.services.conversation import ConversationService
from app.schemas.conversation import (
    ConversationDetail,
    ConversationListResponse,
    ConversationSearchParams,
)
from app.schemas.search import ConversationSearchResponse


@pytest.mark.service
@pytest.mark.unit
class TestConversationService:
    """Test cases for ConversationService."""

    @pytest.fixture
    def service(
        self, mock_db_pool, mock_qa_service, mock_conversation_repo, mock_message_repo
    ):
        """Create service instance with mocked dependencies."""
        service = ConversationService(mock_db_pool, mock_qa_service)
        # Replace real repositories with mocked ones
        service.conversation_repo = mock_conversation_repo
        service.message_repo = mock_message_repo
        return service

    @pytest.fixture
    def mock_conversation_data(self, test_user_id):
        """Mock conversation data from database."""
        return {
            "id": 1,
            "user_id": test_user_id,
            "title": "Test Conversation",
            "question": "What is testing?",
            "answer": "Testing is important",
            "is_pinned": False,
            "is_deleted": False,
            "tags": ["test", "python"],
            "metadata": {"source": "manual"},
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    # ========================================================================
    # CREATE CONVERSATION TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_create_conversation_success(
        self, service, test_user_id, mock_conversation_data
    ):
        """Test creating a conversation successfully."""
        # Arrange
        service.conversation_repo.create_conversation = AsyncMock(return_value=1)
        service.conversation_repo.get_conversation_by_user = AsyncMock(
            return_value=mock_conversation_data
        )

        # Act
        result = await service.create_conversation(
            user_id=test_user_id,
            title="Test Conversation",
            question="What is testing?",
            tags=["test", "python"],
        )

        # Assert
        assert isinstance(result, ConversationDetail)
        assert result.title == "Test Conversation"
        service.conversation_repo.create_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_conversation_with_first_message(
        self, service, test_user_id, mock_conversation_data
    ):
        """Test creating a conversation with a first message."""
        # Arrange
        service.conversation_repo.create_conversation = AsyncMock(return_value=1)
        service.conversation_repo.get_conversation_by_user = AsyncMock(
            return_value=mock_conversation_data
        )
        service.message_repo.create_message = AsyncMock(return_value="msg-1")

        # Act
        result = await service.create_conversation(
            user_id=test_user_id, title="Test", first_message="Hello, how are you?"
        )

        # Assert
        assert isinstance(result, ConversationDetail)
        service.message_repo.create_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_conversation_minimal_data(
        self, service, test_user_id, mock_conversation_data
    ):
        """Test creating a conversation with minimal data."""
        # Arrange
        service.conversation_repo.create_conversation = AsyncMock(return_value=1)
        service.conversation_repo.get_conversation_by_user = AsyncMock(
            return_value=mock_conversation_data
        )

        # Act
        result = await service.create_conversation(user_id=test_user_id)

        # Assert
        assert isinstance(result, ConversationDetail)

    @pytest.mark.asyncio
    async def test_create_conversation_failure(self, service, test_user_id):
        """Test handling conversation creation failure."""
        # Arrange
        service.conversation_repo.create_conversation = AsyncMock(return_value=1)
        service.conversation_repo.get_conversation_by_user = AsyncMock(
            return_value=None
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Failed to create conversation"):
            await service.create_conversation(user_id=test_user_id)

    @pytest.mark.asyncio
    async def test_create_conversation_db_error(self, service, test_user_id):
        """Test handling database error during creation."""
        # Arrange
        service.conversation_repo.create_conversation = AsyncMock(
            side_effect=Exception("Database error")
        )

        # Act & Assert
        with pytest.raises(Exception):
            await service.create_conversation(user_id=test_user_id, title="Test")

    # ========================================================================
    # GET CONVERSATION TESTS
    # ========================================================================

    @pytest.mark.asyncio
    @patch("app.services.conversation.conversation_cache")
    async def test_get_conversation_from_cache(
        self, mock_cache, service, test_user_id, mock_conversation_data
    ):
        """Test getting conversation from cache."""
        # Arrange
        mock_cache.get_conversation.return_value = mock_conversation_data

        # Act
        result = await service.get_conversation(1, test_user_id)

        # Assert
        assert isinstance(result, ConversationDetail)
        mock_cache.get_conversation.assert_called_once_with(test_user_id, 1)
        service.conversation_repo.get_conversation_by_user.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.conversation.conversation_cache")
    async def test_get_conversation_from_db(
        self, mock_cache, service, test_user_id, mock_conversation_data
    ):
        """Test getting conversation from database when not cached."""
        # Arrange
        mock_cache.get_conversation.return_value = None
        service.conversation_repo.get_conversation_by_user = AsyncMock(
            return_value=mock_conversation_data
        )

        # Act
        result = await service.get_conversation(1, test_user_id)

        # Assert
        assert isinstance(result, ConversationDetail)
        service.conversation_repo.get_conversation_by_user.assert_called_once()
        mock_cache.set_conversation.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.conversation.conversation_cache")
    async def test_get_conversation_not_found(self, mock_cache, service, test_user_id):
        """Test getting non-existent conversation."""
        # Arrange
        mock_cache.get_conversation.return_value = None
        service.conversation_repo.get_conversation_by_user = AsyncMock(
            return_value=None
        )

        # Act
        result = await service.get_conversation(999, test_user_id)

        # Assert
        assert result is None

    # ========================================================================
    # UPDATE CONVERSATION TESTS
    # ========================================================================

    @pytest.mark.asyncio
    @patch("app.services.conversation.conversation_cache")
    async def test_update_conversation_success(
        self, mock_cache, service, test_user_id, mock_conversation_data
    ):
        """Test updating conversation successfully."""
        # Arrange
        updated_data = mock_conversation_data.copy()
        updated_data["title"] = "Updated Title"

        service.conversation_repo.update_conversation = AsyncMock(return_value=True)
        service.conversation_repo.get_conversation_by_user = AsyncMock(
            return_value=updated_data
        )
        mock_cache.get_conversation.return_value = None

        # Act
        result = await service.update_conversation(
            1, test_user_id, title="Updated Title"
        )

        # Assert
        assert isinstance(result, ConversationDetail)
        assert result.title == "Updated Title"
        mock_cache.delete_conversation.assert_called_once()
        mock_cache.delete_pattern.assert_called()

    @pytest.mark.asyncio
    async def test_update_conversation_invalid_fields(self, service, test_user_id):
        """Test updating with invalid fields."""
        # Act & Assert
        with pytest.raises(ValueError, match="No valid fields to update"):
            await service.update_conversation(1, test_user_id, invalid_field="value")

    @pytest.mark.asyncio
    async def test_update_conversation_pin_limit_exceeded(self, service, test_user_id):
        """Test pinning when limit is exceeded."""
        # Arrange
        service.conversation_repo.get_pinned_conversations = AsyncMock(
            return_value=[{"id": i} for i in range(10)]
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Maximum .* conversations can be pinned"):
            await service.update_conversation(1, test_user_id, is_pinned=True)

    @pytest.mark.asyncio
    @patch("app.services.conversation.conversation_cache")
    async def test_update_conversation_not_found(
        self, mock_cache, service, test_user_id
    ):
        """Test updating non-existent conversation."""
        # Arrange
        service.conversation_repo.update_conversation = AsyncMock(return_value=False)

        # Act
        result = await service.update_conversation(999, test_user_id, title="New Title")

        # Assert
        assert result is None

    # ========================================================================
    # DELETE CONVERSATION TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_delete_conversation_success(self, service, test_user_id):
        """Test deleting conversation successfully."""
        # Arrange
        service.conversation_repo.delete_conversation = AsyncMock(return_value=True)

        # Act
        result = await service.delete_conversation(1, test_user_id)

        # Assert
        assert result is True
        service.conversation_repo.delete_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, service, test_user_id):
        """Test deleting non-existent conversation."""
        # Arrange
        service.conversation_repo.delete_conversation = AsyncMock(return_value=False)

        # Act
        result = await service.delete_conversation(999, test_user_id)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_conversation_db_error(self, service, test_user_id):
        """Test handling database error during deletion."""
        # Arrange
        service.conversation_repo.delete_conversation = AsyncMock(
            side_effect=Exception("Database error")
        )

        # Act & Assert
        with pytest.raises(Exception):
            await service.delete_conversation(1, test_user_id)

    # ========================================================================
    # LIST CONVERSATIONS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    @patch("app.services.conversation.conversation_cache")
    async def test_list_conversations_from_cache(
        self, mock_cache, service, test_user_id
    ):
        """Test listing conversations from cache."""
        # Arrange
        cached_response = {
            "conversations": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "total_pages": 0,
        }
        mock_cache.get_conversation_list.return_value = cached_response

        # Act
        result = await service.list_conversations(test_user_id)

        # Assert
        assert isinstance(result, ConversationListResponse)
        mock_cache.get_conversation_list.assert_called_once()
        service.conversation_repo.get_user_conversations.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.conversation.conversation_cache")
    async def test_list_conversations_from_db(
        self, mock_cache, service, test_user_id, sample_conversation_list
    ):
        """Test listing conversations from database."""
        # Arrange
        mock_cache.get_conversation_list.return_value = None
        service.conversation_repo.get_user_conversations = AsyncMock(
            return_value=sample_conversation_list
        )
        service.conversation_repo.count_user_conversations = AsyncMock(return_value=5)

        # Act
        result = await service.list_conversations(test_user_id, page=1, page_size=20)

        # Assert
        assert isinstance(result, ConversationListResponse)
        assert result.total == 5
        assert len(result.conversations) == 5
        mock_cache.set_conversation_list.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.conversation.conversation_cache")
    async def test_list_conversations_pagination(
        self, mock_cache, service, test_user_id, sample_conversation_list
    ):
        """Test conversation list pagination."""
        # Arrange
        mock_cache.get_conversation_list.return_value = None
        service.conversation_repo.get_user_conversations = AsyncMock(
            return_value=sample_conversation_list[:2]
        )
        service.conversation_repo.count_user_conversations = AsyncMock(return_value=5)

        # Act
        result = await service.list_conversations(test_user_id, page=2, page_size=2)

        # Assert
        assert result.page == 2
        assert result.page_size == 2
        assert len(result.conversations) == 2

    @pytest.mark.asyncio
    @patch("app.services.conversation.conversation_cache")
    async def test_list_conversations_empty(self, mock_cache, service, test_user_id):
        """Test listing when user has no conversations."""
        # Arrange
        mock_cache.get_conversation_list.return_value = None
        service.conversation_repo.get_user_conversations = AsyncMock(return_value=[])
        service.conversation_repo.count_user_conversations = AsyncMock(return_value=0)

        # Act
        result = await service.list_conversations(test_user_id)

        # Assert
        assert result.total == 0
        assert len(result.conversations) == 0

    # ========================================================================
    # PIN CONVERSATION TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_pin_conversation_success(self, service, test_user_id):
        """Test pinning conversation successfully."""
        # Arrange
        service.conversation_repo.get_pinned_conversations = AsyncMock(return_value=[])
        service.conversation_repo.pin_conversation = AsyncMock(return_value=True)

        # Act
        result = await service.pin_conversation(1, test_user_id, is_pinned=True)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_unpin_conversation_success(self, service, test_user_id):
        """Test unpinning conversation successfully."""
        # Arrange
        service.conversation_repo.pin_conversation = AsyncMock(return_value=True)

        # Act
        result = await service.pin_conversation(1, test_user_id, is_pinned=False)

        # Assert
        assert result is True
        service.conversation_repo.get_pinned_conversations.assert_not_called()

    @pytest.mark.asyncio
    async def test_pin_conversation_limit_exceeded(self, service, test_user_id):
        """Test pinning when limit is exceeded."""
        # Arrange
        service.conversation_repo.get_pinned_conversations = AsyncMock(
            return_value=[{"id": i} for i in range(10)]
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Maximum .* conversations can be pinned"):
            await service.pin_conversation(1, test_user_id, is_pinned=True)

    # ========================================================================
    # UPDATE TAGS TESTS
    # ========================================================================

    @pytest.mark.asyncio
    @patch("app.services.conversation.conversation_cache")
    async def test_update_tags_success(
        self, mock_cache, service, test_user_id, mock_conversation_data
    ):
        """Test updating conversation tags successfully."""
        # Arrange
        updated_data = mock_conversation_data.copy()
        updated_data["tags"] = ["new", "tags"]

        service.conversation_repo.update_tags = AsyncMock(return_value=True)
        service.conversation_repo.get_conversation_by_user = AsyncMock(
            return_value=updated_data
        )
        mock_cache.get_conversation.return_value = None

        # Act
        result = await service.update_tags(1, test_user_id, ["new", "tags"])

        # Assert
        assert isinstance(result, ConversationDetail)
        assert result.tags == ["new", "tags"]

    @pytest.mark.asyncio
    async def test_update_tags_empty_list(
        self, service, test_user_id, mock_conversation_data
    ):
        """Test updating tags with empty list."""
        # Arrange
        service.conversation_repo.update_tags = AsyncMock(return_value=True)
        service.conversation_repo.get_conversation_by_user = AsyncMock(
            return_value=mock_conversation_data
        )

        # Act
        result = await service.update_tags(1, test_user_id, [])

        # Assert
        assert isinstance(result, ConversationDetail)

    # ========================================================================
    # EDGE CASES AND ERROR HANDLING
    # ========================================================================

    @pytest.mark.asyncio
    @pytest.mark.edge_case
    async def test_create_conversation_with_very_long_title(
        self, service, test_user_id, mock_conversation_data
    ):
        """Test creating conversation with very long title."""
        # Arrange
        long_title = "A" * 10000
        service.conversation_repo.create_conversation = AsyncMock(return_value=1)
        service.conversation_repo.get_conversation_by_user = AsyncMock(
            return_value=mock_conversation_data
        )

        # Act
        result = await service.create_conversation(
            user_id=test_user_id, title=long_title
        )

        # Assert
        assert isinstance(result, ConversationDetail)

    @pytest.mark.asyncio
    @pytest.mark.edge_case
    async def test_create_conversation_with_special_characters(
        self, service, test_user_id, mock_conversation_data
    ):
        """Test creating conversation with special characters."""
        # Arrange
        service.conversation_repo.create_conversation = AsyncMock(return_value=1)
        service.conversation_repo.get_conversation_by_user = AsyncMock(
            return_value=mock_conversation_data
        )

        # Act
        result = await service.create_conversation(
            user_id=test_user_id,
            title="Test <script>alert('xss')</script>",
            question="What's up? 你好 🎉",
        )

        # Assert
        assert isinstance(result, ConversationDetail)

    @pytest.mark.asyncio
    @pytest.mark.edge_case
    async def test_list_conversations_with_large_page_size(self, service, test_user_id):
        """Test listing conversations with very large page size."""
        # Arrange
        service.conversation_repo.get_user_conversations = AsyncMock(return_value=[])
        service.conversation_repo.count_user_conversations = AsyncMock(return_value=0)

        # Act
        result = await service.list_conversations(test_user_id, page=1, page_size=1000)

        # Assert
        assert isinstance(result, ConversationListResponse)

    @pytest.mark.asyncio
    @pytest.mark.edge_case
    @patch("app.services.conversation.conversation_cache")
    async def test_update_conversation_with_many_tags(
        self, mock_cache, service, test_user_id, mock_conversation_data
    ):
        """Test updating conversation with many tags."""
        # Arrange
        many_tags = [f"tag{i}" for i in range(100)]
        service.conversation_repo.update_conversation = AsyncMock(return_value=True)
        service.conversation_repo.get_conversation_by_user = AsyncMock(
            return_value=mock_conversation_data
        )
        mock_cache.get_conversation.return_value = None

        # Act
        result = await service.update_conversation(1, test_user_id, tags=many_tags)

        # Assert
        assert isinstance(result, ConversationDetail)

    @pytest.mark.asyncio
    async def test_service_handles_repository_exceptions(self, service, test_user_id):
        """Test that service properly propagates repository exceptions."""
        # Arrange
        service.conversation_repo.get_conversation_by_user = AsyncMock(
            side_effect=Exception("Repository error")
        )

        # Act & Assert
        with pytest.raises(Exception, match="Repository error"):
            await service.get_conversation(1, test_user_id)

    # ========================================================================
    # SEARCH FUNCTIONALITY TESTS
    # ========================================================================

    @pytest.mark.asyncio
    async def test_search_conversations_full_text(self, service, test_user_id):
        """Test full-text search across conversations."""
        # Arrange
        query = "health symptoms"
        search_results = [
            {
                "id": 1,
                "title": "Health Consultation",
                "question": "What are common flu symptoms?",
                "answer": "Common flu symptoms include...",
                "rank": 0.95,
            }
        ]

        # Add required fields for search results
        full_search_results = []
        for result in search_results:
            result.update(
                {
                    "is_pinned": False,
                    "tags": [],
                    "message_count": 1,
                    "last_message_at": datetime.now(timezone.utc),
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )
            full_search_results.append(result)

        service.conversation_repo.full_text_search = AsyncMock(
            return_value=(full_search_results, 1)
        )

        # Act
        result = await service.search_conversations(
            test_user_id, ConversationSearchParams(query=query, page=1, page_size=10)
        )

        # Assert
        assert isinstance(result, ConversationSearchResponse)
        assert len(result.results) == 1
        assert result.results[0].title == "Health Consultation"
        assert result.results[0].relevance_score == 0.95

    @pytest.mark.asyncio
    async def test_search_conversations_with_filters(self, service, test_user_id):
        """Test search with multiple filters."""
        # Arrange
        search_params = ConversationSearchParams(
            query="medicine",
            tags=["health", "prescription"],
            date_from="2024-01-01",
            date_to="2024-12-31",
            is_pinned=False,
            page=1,
            page_size=20,
        )

        # Add required fields for search results
        filtered_results = [
            {
                "id": 2,
                "title": "Prescription Information",
                "tags": ["health", "prescription"],
                "is_pinned": False,
                "question": "What medicines are available?",
                "rank": 0.85,
                "message_count": 1,
                "last_message_at": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        ]

        service.conversation_repo.full_text_search = AsyncMock(
            return_value=(filtered_results, 1)
        )

        # Act
        result = await service.search_conversations(test_user_id, search_params)

        # Assert
        assert len(result.results) == 1
        assert "health" in result.results[0].tags
        assert "prescription" in result.results[0].tags

    @pytest.mark.asyncio
    async def test_get_search_suggestions(self, service, test_user_id):
        """Test getting search suggestions based on user history."""
        # Arrange
        suggestions = [
            "symptoms",
            "symptom checker",
            "symptoms list",
            "medical symptoms",
        ]
        service.conversation_repo.get_search_suggestions = AsyncMock(
            return_value=suggestions
        )

        # Act
        result = await service.get_search_suggestions(test_user_id, "sym")

        # Assert
        assert isinstance(result, list)
        assert len(result) == 4
        assert all("sym" in suggestion.lower() for suggestion in result)

    @pytest.mark.asyncio
    async def test_get_popular_search_terms(self, service, test_user_id):
        """Test getting popular search terms for a user."""
        # Arrange
        popular_terms = [
            {"term": "covid symptoms", "count": 150},
            {"term": "headache treatment", "count": 120},
            {"term": "blood pressure", "count": 100},
        ]

        service.conversation_repo.get_popular_search_terms = AsyncMock(
            return_value=popular_terms
        )

        # Act
        result = await service.get_popular_search_terms(test_user_id, limit=10)

        # Assert
        assert len(result) == 3
        assert result[0]["term"] == "covid symptoms"
        assert result[0]["count"] == 150
