"""
Tests for Conversation API endpoints.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from datetime import datetime, timezone

from app.main import app
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationList,
)
from app.api.conversations import create_conversation_service
from app.auth.dependencies import get_current_active_user
from app.exceptions import ValidationException


@pytest.fixture
def mock_current_user():
    """Mock current authenticated user."""
    user = MagicMock()
    user.id = 1
    user.email = "test@example.com"
    user.is_active = True
    user.is_superuser = False
    return user


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


@pytest.fixture
def client(mock_current_user):
    """Create test client with mocked dependencies."""
    # Create mock service
    mock_service = AsyncMock()

    # Override dependencies
    app.dependency_overrides[get_current_active_user] = lambda: mock_current_user
    app.dependency_overrides[create_conversation_service] = lambda: mock_service

    client = TestClient(app)
    yield client, mock_service

    # Clean up overrides
    app.dependency_overrides.clear()


class TestConversationAPI:
    """Test cases for Conversation API endpoints."""

    def test_create_conversation_success(
        self,
        client,
        sample_conversation_response,
        sample_conversation_create,
    ):
        """Test successful conversation creation."""
        # Arrange
        test_client, mock_service = client
        mock_service.create_conversation.return_value = ConversationResponse(
            **sample_conversation_response
        )

        # Act
        response = test_client.post(
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

    def test_create_conversation_user_mismatch(
        self,
        client,
        sample_conversation_create,
    ):
        """Test conversation creation with user ID mismatch."""
        # Arrange
        test_client, mock_service = client
        mock_service.create_conversation.side_effect = ValidationException(
            message="User ID mismatch", details={"field": "user_id"}
        )

        # Modify request to have different user_id
        request_data = sample_conversation_create.copy()
        request_data["user_id"] = 2

        # Act
        response = test_client.post(
            "/api/v1/conversations/",
            json=request_data,
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 422
        # New exception system uses "message" key
        data = response.json()
        assert "User ID mismatch" in data.get("message", "")

    def test_list_conversations_success(
        self,
        client,
        sample_conversation_response,
    ):
        """Test successful conversation listing."""
        # Arrange
        test_client, mock_service = client
        mock_service.list_user_conversations.return_value = ConversationList(
            conversations=[ConversationResponse(**sample_conversation_response)],
            total_count=1,
            has_more=False,
        )

        # Act
        response = test_client.get(
            "/api/v1/conversations/",
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["conversations"]) == 1
        assert data["total_count"] == 1
        assert data["has_more"] is False

    def test_get_conversation_success(
        self,
        client,
        sample_conversation_response,
    ):
        """Test successful conversation retrieval by ID."""
        # Arrange
        conversation_id = 1
        test_client, mock_service = client
        mock_service.get_conversation_by_id.return_value = ConversationResponse(
            **sample_conversation_response
        )

        # Act
        response = test_client.get(
            f"/api/v1/conversations/{conversation_id}",
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == conversation_id
        assert data["title"] == "Test Conversation"

    def test_get_conversation_not_found(
        self,
        client,
    ):
        """Test conversation retrieval when not found."""
        # Arrange
        conversation_id = 999
        test_client, mock_service = client
        mock_service.get_conversation_by_id.return_value = None

        # Act
        response = test_client.get(
            f"/api/v1/conversations/{conversation_id}",
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 404
        # New exception system uses "message" key
        data = response.json()
        assert (
            "not found" in data.get("message", "").lower()
            or "not found" in data.get("detail", "").lower()
        )

    def test_update_conversation_success(
        self,
        client,
        sample_conversation_response,
    ):
        """Test successful conversation update."""
        # Arrange
        conversation_id = 1
        update_data = {"title": "Updated Conversation"}
        updated_response = sample_conversation_response.copy()
        updated_response["title"] = "Updated Conversation"

        test_client, mock_service = client
        mock_service.update_conversation.return_value = ConversationResponse(
            **updated_response
        )

        # Act
        response = test_client.put(
            f"/api/v1/conversations/{conversation_id}",
            json=update_data,
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Conversation"

    def test_update_conversation_not_found(
        self,
        client,
    ):
        """Test conversation update when conversation not found."""
        # Arrange
        conversation_id = 999
        update_data = {"title": "Updated Conversation"}

        test_client, mock_service = client
        mock_service.update_conversation.return_value = None

        # Act
        response = test_client.put(
            f"/api/v1/conversations/{conversation_id}",
            json=update_data,
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 404
        # New exception system uses "message" key
        data = response.json()
        assert (
            "not found" in data.get("message", "").lower()
            or "not found" in data.get("detail", "").lower()
        )

    def test_pin_conversation_success(
        self,
        client,
        sample_conversation_response,
    ):
        """Test successful conversation pinning."""
        # Arrange
        conversation_id = 1
        pin_request = {"is_pinned": True}
        pinned_response = sample_conversation_response.copy()
        pinned_response["is_pinned"] = True

        test_client, mock_service = client
        mock_service.pin_conversation.return_value = ConversationResponse(
            **pinned_response
        )

        # Act
        response = test_client.patch(
            f"/api/v1/conversations/{conversation_id}/pin",
            json=pin_request,
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["is_pinned"] is True

    def test_update_conversation_title_success(
        self,
        client,
        sample_conversation_response,
    ):
        """Test successful conversation title update."""
        # Arrange
        conversation_id = 1
        new_title = "New Title"
        updated_response = sample_conversation_response.copy()
        updated_response["title"] = new_title

        test_client, mock_service = client
        mock_service.update_conversation_title.return_value = ConversationResponse(
            **updated_response
        )

        # Act
        response = test_client.put(
            f"/api/v1/conversations/{conversation_id}/title",
            params={"title": new_title},
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == new_title

    def test_delete_conversation_success(
        self,
        client,
    ):
        """Test successful conversation deletion."""
        # Arrange
        conversation_id = 1

        test_client, mock_service = client
        mock_service.delete_conversation.return_value = True

        # Act
        response = test_client.delete(
            f"/api/v1/conversations/{conversation_id}",
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 204

    def test_delete_conversation_not_found(
        self,
        client,
    ):
        """Test conversation deletion when conversation not found."""
        # Arrange
        conversation_id = 999

        test_client, mock_service = client
        mock_service.delete_conversation.return_value = False

        # Act
        response = test_client.delete(
            f"/api/v1/conversations/{conversation_id}",
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 404
        # New exception system uses "message" key
        data = response.json()
        assert (
            "not found" in data.get("message", "").lower()
            or "not found" in data.get("detail", "").lower()
        )

    def test_get_conversation_message_count_success(
        self,
        client,
    ):
        """Test successful message count retrieval."""
        # Arrange
        conversation_id = 1
        expected_count = 5

        test_client, mock_service = client
        mock_service.get_conversation_message_count.return_value = expected_count

        # Act
        response = test_client.get(
            f"/api/v1/conversations/{conversation_id}/message-count",
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["message_count"] == expected_count

    def test_get_pinned_conversations_success(
        self,
        client,
        sample_conversation_response,
    ):
        """Test successful pinned conversations retrieval."""
        # Arrange
        pinned_response = sample_conversation_response.copy()
        pinned_response["is_pinned"] = True

        test_client, mock_service = client
        mock_service.get_pinned_conversations.return_value = [
            ConversationResponse(**pinned_response)
        ]

        # Act
        response = test_client.get(
            "/api/v1/conversations/pinned",
            headers={"Authorization": "Bearer fake_token"},
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["is_pinned"] is True
