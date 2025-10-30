"""
Tests for Q&A API endpoints.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import HTTPException
from app.services.qa_service import QAService


@pytest.fixture
def mock_qa_service():
    """Create a mock QA service."""
    mock_service = Mock(spec=QAService)
    mock_service.model = Mock()
    mock_service.df = Mock()
    mock_service.df.__len__ = Mock(return_value=100)
    mock_service.settings = Mock()
    mock_service.settings.qa_threshold = 0.55
    mock_service.settings.qa_top_k = 7
    mock_service.preprocess_text = Mock(return_value="cleaned question")
    return mock_service


@pytest.fixture
def sample_qa_response():
    """Sample Q&A response."""
    return {
        "question": "What is diabetes?",
        "answers": {
            "Nutrition": [
                "Q: What is diabetes?\nA: Diabetes is a chronic disease... (Nutrition)"
            ]
        },
        "summary": "Diabetes is a chronic disease that affects blood sugar levels.",
    }


class TestQAHealthEndpoint:
    """Tests for Q&A health check endpoint."""

    @pytest.mark.asyncio
    async def test_qa_health_check_available(self, client, mock_qa_service):
        """Test health check when Q&A service is available."""
        client.app.state.qa_service = mock_qa_service

        response = client.get("/api/v1/qa/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["model_loaded"] is True
        assert data["data_loaded"] is True

    @pytest.mark.asyncio
    async def test_qa_health_check_unavailable(self, client):
        """Test health check when Q&A service is unavailable."""
        client.app.state.qa_service = None

        response = client.get("/api/v1/qa/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unavailable"


class TestAskQuestionEndpoint:
    """Tests for ask question endpoint."""

    @pytest.mark.asyncio
    async def test_ask_question_success(
        self, client, mock_qa_service, sample_qa_response
    ):
        """Test successful question asking."""
        client.app.state.qa_service = mock_qa_service
        mock_qa_service.ask_question = Mock(return_value=sample_qa_response)

        with patch(
            "app.api.qa.qa_db.create_conversation", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = 1

            response = client.post(
                "/api/v1/qa/ask",
                json={"question": "What is diabetes?", "threshold": 0.55, "top_k": 7},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["question"] == "What is diabetes?"
            assert "answers" in data
            assert "summary" in data
            assert data.get("conversation_id") == 1

    @pytest.mark.asyncio
    async def test_ask_question_service_unavailable(self, client):
        """Test question asking when service is unavailable."""
        client.app.state.qa_service = None

        response = client.post("/api/v1/qa/ask", json={"question": "What is diabetes?"})

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_ask_question_empty_question(self, client, mock_qa_service):
        """Test question asking with empty question."""
        client.app.state.qa_service = mock_qa_service
        mock_qa_service.ask_question = Mock(side_effect=ValueError("Question is empty"))

        response = client.post("/api/v1/qa/ask", json={"question": ""})

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_ask_question_default_params(
        self, client, mock_qa_service, sample_qa_response
    ):
        """Test question asking with default parameters."""
        client.app.state.qa_service = mock_qa_service
        mock_qa_service.ask_question = Mock(return_value=sample_qa_response)

        with patch(
            "app.api.qa.qa_db.create_conversation", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = 1

            response = client.post(
                "/api/v1/qa/ask", json={"question": "What is diabetes?"}
            )

            assert response.status_code == 200
            # Verify service was called with default params
            call_args = mock_qa_service.ask_question.call_args
            assert call_args[1]["threshold"] is None
            assert call_args[1]["top_k"] is None


class TestConversationEndpoints:
    """Tests for conversation management endpoints."""

    @pytest.mark.asyncio
    async def test_get_conversation_success(self, client):
        """Test getting a conversation by ID."""
        mock_conversation = {
            "id": 1,
            "user_id": None,
            "question": "What is diabetes?",
            "question_cleaned": "diabetes",
            "answers": {"Nutrition": ["Some answer"]},
            "summary": "Summary text",
            "threshold": 0.55,
            "top_k": 7,
            "created_at": "2025-10-30T10:00:00",
        }

        with patch(
            "app.api.qa.qa_db.get_conversation_by_id", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_conversation

            response = client.get("/api/v1/qa/conversations/1")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == 1
            assert data["question"] == "What is diabetes?"

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, client):
        """Test getting a non-existent conversation."""
        with patch(
            "app.api.qa.qa_db.get_conversation_by_id", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            response = client.get("/api/v1/qa/conversations/999")

            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_conversations_default(self, client):
        """Test listing conversations with default parameters."""
        mock_conversations = [
            {
                "id": 1,
                "question": "Question 1",
                "summary": "Summary 1",
                "threshold": 0.55,
                "top_k": 7,
                "created_at": "2025-10-30T10:00:00",
            }
        ]

        with patch(
            "app.api.qa.qa_db.get_recent_conversations", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_conversations

            response = client.get("/api/v1/qa/conversations")

            assert response.status_code == 200
            data = response.json()
            assert "conversations" in data
            assert data["page"] == 1
            assert data["page_size"] == 20

    @pytest.mark.asyncio
    async def test_list_conversations_with_pagination(self, client):
        """Test listing conversations with pagination."""
        with patch(
            "app.api.qa.qa_db.get_recent_conversations", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = []

            response = client.get("/api/v1/qa/conversations?page=2&page_size=10")

            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 2
            assert data["page_size"] == 10

    @pytest.mark.asyncio
    async def test_list_conversations_with_search(self, client):
        """Test listing conversations with search query."""
        with patch(
            "app.api.qa.qa_db.search_conversations", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = []

            response = client.get("/api/v1/qa/conversations?search=diabetes")

            assert response.status_code == 200
            mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_conversation_success(self, client):
        """Test deleting a conversation."""
        mock_conversation = {
            "id": 1,
            "user_id": None,
            "question": "What is diabetes?",
            "question_cleaned": "diabetes",
            "answers": {},
            "summary": "",
            "threshold": 0.55,
            "top_k": 7,
            "created_at": "2025-10-30T10:00:00",
        }

        with patch(
            "app.api.qa.qa_db.get_conversation_by_id", new_callable=AsyncMock
        ) as mock_get, patch(
            "app.api.qa.qa_db.delete_conversation", new_callable=AsyncMock
        ) as mock_delete:
            mock_get.return_value = mock_conversation
            mock_delete.return_value = True

            response = client.delete("/api/v1/qa/conversations/1")

            assert response.status_code == 200
            data = response.json()
            assert "message" in data

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, client):
        """Test deleting a non-existent conversation."""
        with patch(
            "app.api.qa.qa_db.get_conversation_by_id", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            response = client.delete("/api/v1/qa/conversations/999")

            assert response.status_code == 404
