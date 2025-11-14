"""
Tests for Conversation API endpoints.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.main import app
from app.schemas.conversation import ConversationCreate, ConversationResponse


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_current_user():
    """Mock current authenticated user."""
    return {
        "id": 1,
        "email": "test@example.com",
        "is_active": True,
        "is_superuser": False,
    }


@pytest.fixture
def sample_conversation_response():
    """Sample conversation response."""
    return {
        "id": 1,
        "user_id": 1,
        "title": "Test Conversation",
        "is_pinned": False,
        "is_archived": False,
        "metadata": {"theme": "health"},
        "message_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@pytest.fixture
def sample_conversation_create():
    """Sample conversation creation request."""
    return {
        "title": "Test Conversation",
        "is_pinned": False,
        "metadata": {"theme": "health"},
        "user_id": 1,
    }


class TestConversationAPI:
    """Test cases for Conversation API endpoints."""

    @patch("app.api.conversations.get_conversation_service")
    @patch("app.api.conversations.get_current_active_user")
    def test_create_conversation_success(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_current_user,
        sample_conversation_response,
        sample_conversation_create,
    ):
        """Test successful conversation creation."""
        # Arrange
        mock_get_user.return_value = mock_current_user
        mock_service = AsyncMock()
        mock_service.create_conversation.return_value = ConversationResponse(
            **sample_conversation_response
        )
        mock_get_service.return_value = mock_service

        # Act
        response = client.post(
            "/api/v1/conversations/",
            json=sample_conversation_create,
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == 1
        assert data["title"] == "Test Conversation"
        assert data["user_id"] == 1

    @patch("app.api.conversations.get_conversation_service")
    @patch("app.api.conversations.get_current_active_user")
    def test_create_conversation_user_mismatch(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_current_user,
        sample_conversation_create,
    ):
        """Test conversation creation with user ID mismatch."""
        # Arrange
        mock_get_user.return_value = mock_current_user
        mock_service = AsyncMock()
        mock_service.create_conversation.side_effect = ValueError("User ID mismatch")
        mock_get_service.return_value = mock_service

        # Modify request to have different user_id
        request_data = sample_conversation_create.copy()
        request_data["user_id"] = 2

        # Act
        response = client.post(
            "/api/v1/conversations/",
            json=request_data,
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 400
        assert "User ID mismatch" in response.json()["detail"]

    @patch("app.api.conversations.get_conversation_service")
    @patch("app.api.conversations.get_current_active_user")
    def test_list_conversations_success(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_current_user,
        sample_conversation_response,
    ):
        """Test successful conversation listing."""
        # Arrange
        mock_get_user.return_value = mock_current_user
        mock_service = AsyncMock()
        mock_service.list_user_conversations.return_value = {
            "conversations": [ConversationResponse(**sample_conversation_response)],
            "total_count": 1,
            "has_more": False,
        }
        mock_get_service.return_value = mock_service

        # Act
        response = client.get(
            "/api/v1/conversations/",
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 1
        assert data["total_count"] == 1
        assert data["has_more"] is False

    @patch("app.api.conversations.get_conversation_service")
    @patch("app.api.conversations.get_current_active_user")
    def test_get_conversation_success(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_current_user,
        sample_conversation_response,
    ):
        """Test successful conversation retrieval by ID."""
        # Arrange
        conversation_id = 1
        mock_get_user.return_value = mock_current_user
        mock_service = AsyncMock()
        mock_service.get_conversation_by_id.return_value = ConversationResponse(
            **sample_conversation_response
        )
        mock_get_service.return_value = mock_service

        # Act
        response = client.get(
            f"/api/v1/conversations/{conversation_id}",
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == conversation_id
        assert data["title"] == "Test Conversation"

    @patch("app.api.conversations.get_conversation_service")
    @patch("app.api.conversations.get_current_active_user")
    def test_get_conversation_not_found(
        self, mock_get_user, mock_get_service, client, mock_current_user
    ):
        """Test conversation retrieval when not found."""
        # Arrange
        conversation_id = 999
        mock_get_user.return_value = mock_current_user
        mock_service = AsyncMock()
        mock_service.get_conversation_by_id.return_value = None
        mock_get_service.return_value = mock_service

        # Act
        response = client.get(
            f"/api/v1/conversations/{conversation_id}",
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("app.api.conversations.get_conversation_service")
    @patch("app.api.conversations.get_current_active_user")
    def test_update_conversation_success(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_current_user,
        sample_conversation_response,
    ):
        """Test successful conversation update."""
        # Arrange
        conversation_id = 1
        update_data = {"title": "Updated Conversation"}
        updated_response = sample_conversation_response.copy()
        updated_response["title"] = "Updated Conversation"

        mock_get_user.return_value = mock_current_user
        mock_service = AsyncMock()
        mock_service.update_conversation.return_value = ConversationResponse(
            **updated_response
        )
        mock_get_service.return_value = mock_service

        # Act
        response = client.put(
            f"/api/v1/conversations/{conversation_id}",
            json=update_data,
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Conversation"

    @patch("app.api.conversations.get_conversation_service")
    @patch("app.api.conversations.get_current_active_user")
    def test_update_conversation_not_found(
        self, mock_get_user, mock_get_service, client, mock_current_user
    ):
        """Test conversation update when conversation not found."""
        # Arrange
        conversation_id = 999
        update_data = {"title": "Updated Conversation"}

        mock_get_user.return_value = mock_current_user
        mock_service = AsyncMock()
        mock_service.update_conversation.return_value = None
        mock_get_service.return_value = mock_service

        # Act
        response = client.put(
            f"/api/v1/conversations/{conversation_id}",
            json=update_data,
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("app.api.conversations.get_conversation_service")
    @patch("app.api.conversations.get_current_active_user")
    def test_pin_conversation_success(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_current_user,
        sample_conversation_response,
    ):
        """Test successful conversation pinning."""
        # Arrange
        conversation_id = 1
        pin_request = {"is_pinned": True}
        pinned_response = sample_conversation_response.copy()
        pinned_response["is_pinned"] = True

        mock_get_user.return_value = mock_current_user
        mock_service = AsyncMock()
        mock_service.pin_conversation.return_value = ConversationResponse(
            **pinned_response
        )
        mock_get_service.return_value = mock_service

        # Act
        response = client.patch(
            f"/api/v1/conversations/{conversation_id}/pin",
            json=pin_request,
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["is_pinned"] is True

    @patch("app.api.conversations.get_conversation_service")
    @patch("app.api.conversations.get_current_active_user")
    def test_update_conversation_title_success(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_current_user,
        sample_conversation_response,
    ):
        """Test successful conversation title update."""
        # Arrange
        conversation_id = 1
        new_title = "New Title"
        updated_response = sample_conversation_response.copy()
        updated_response["title"] = new_title

        mock_get_user.return_value = mock_current_user
        mock_service = AsyncMock()
        mock_service.update_conversation_title.return_value = ConversationResponse(
            **updated_response
        )
        mock_get_service.return_value = mock_service

        # Act
        response = client.put(
            f"/api/v1/conversations/{conversation_id}/title",
            params={"title": new_title},
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == new_title

    @patch("app.api.conversations.get_conversation_service")
    @patch("app.api.conversations.get_current_active_user")
    def test_delete_conversation_success(
        self, mock_get_user, mock_get_service, client, mock_current_user
    ):
        """Test successful conversation deletion."""
        # Arrange
        conversation_id = 1

        mock_get_user.return_value = mock_current_user
        mock_service = AsyncMock()
        mock_service.delete_conversation.return_value = True
        mock_get_service.return_value = mock_service

        # Act
        response = client.delete(
            f"/api/v1/conversations/{conversation_id}",
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 204

    @patch("app.api.conversations.get_conversation_service")
    @patch("app.api.conversations.get_current_active_user")
    def test_delete_conversation_not_found(
        self, mock_get_user, mock_get_service, client, mock_current_user
    ):
        """Test conversation deletion when conversation not found."""
        # Arrange
        conversation_id = 999

        mock_get_user.return_value = mock_current_user
        mock_service = AsyncMock()
        mock_service.delete_conversation.return_value = False
        mock_get_service.return_value = mock_service

        # Act
        response = client.delete(
            f"/api/v1/conversations/{conversation_id}",
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("app.api.conversations.get_conversation_service")
    @patch("app.api.conversations.get_current_active_user")
    def test_get_conversation_message_count_success(
        self, mock_get_user, mock_get_service, client, mock_current_user
    ):
        """Test successful message count retrieval."""
        # Arrange
        conversation_id = 1
        expected_count = 5

        mock_get_user.return_value = mock_current_user
        mock_service = AsyncMock()
        mock_service.get_conversation_message_count.return_value = expected_count
        mock_get_service.return_value = mock_service

        # Act
        response = client.get(
            f"/api/v1/conversations/{conversation_id}/message-count",
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["message_count"] == expected_count

    @patch("app.api.conversations.get_conversation_service")
    @patch("app.api.conversations.get_current_active_user")
    def test_get_pinned_conversations_success(
        self,
        mock_get_user,
        mock_get_service,
        client,
        mock_current_user,
        sample_conversation_response,
    ):
        """Test successful pinned conversations retrieval."""
        # Arrange
        pinned_response = sample_conversation_response.copy()
        pinned_response["is_pinned"] = True

        mock_get_user.return_value = mock_current_user
        mock_service = AsyncMock()
        mock_service.get_pinned_conversations.return_value = [
            ConversationResponse(**pinned_response)
        ]
        mock_get_service.return_value = mock_service

        # Act
        response = client.get(
            "/api/v1/conversations/pinned",
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["is_pinned"] is True
