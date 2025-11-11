"""
Integration tests for Message API endpoints.

Tests cover CRUD operations, branching, tree structure, and version management.
"""

import pytest
from unittest.mock import AsyncMock
from fastapi import status
from datetime import datetime, timezone


@pytest.mark.integration
@pytest.mark.api
class TestMessageAPI:
    """Integration tests for message API endpoints."""

    @pytest.fixture
    def app(self):
        """Get the real FastAPI app."""
        from app.main import app as real_app

        return real_app

    @pytest.fixture
    def mock_message_service(self, app):
        """Mock MessageService and override dependency."""
        service = type(
            "MockMessageService",
            (),
            {
                "add_message": AsyncMock(),
                "list_messages": AsyncMock(),
                "get_message": AsyncMock(),
                "update_message": AsyncMock(),
                "delete_message": AsyncMock(),
                "create_branch": AsyncMock(),
                "get_conversation_tree": AsyncMock(),
                "get_message_path": AsyncMock(),
                "get_message_children": AsyncMock(),
            },
        )()

        from app.api.message import get_message_service as dep_get_service

        app.dependency_overrides[dep_get_service] = lambda: service
        return service

    @pytest.fixture
    def mock_version_service(self, app):
        """Mock MessageVersionService and override dependency."""
        service = type(
            "MockVersionService",
            (),
            {
                "get_versions": AsyncMock(),
                "get_version": AsyncMock(),
                "compare_versions": AsyncMock(),
                "rollback_to_version": AsyncMock(),
                "cleanup_old_versions": AsyncMock(),
            },
        )()

        from app.api.message import get_version_service as dep_get_version_service

        app.dependency_overrides[dep_get_version_service] = lambda: service
        return service

    @pytest.fixture
    def authed_client(
        self,
        app,
        auth_headers,
        override_dependencies,
        override_authenticated_user,
        mock_message_service,
    ):
        """Authenticated test client."""
        from fastapi.testclient import TestClient

        client = TestClient(app)
        client.headers.update(auth_headers)
        return client

    @pytest.fixture
    def plain_client(self, app, override_dependencies):
        """Unauthenticated test client."""
        from fastapi.testclient import TestClient

        return TestClient(app)

    # ========== CREATE MESSAGE TESTS ==========

    def test_add_message_success(
        self, authed_client, mock_message_service, test_user_id
    ):
        """Test adding a message successfully."""
        mock_message_service.add_message.return_value = {
            "id": 1,
            "conversation_id": 1,
            "user_id": test_user_id,
            "role": "user",
            "content": "Test message",
            "content_cleaned": "Test message",
            "answers": None,
            "parent_message_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "version_count": 0,
            "child_count": 0,
            "metadata": {},
        }

        payload = {"content": "Test message", "metadata": {}}
        resp = authed_client.post("/api/v1/conversations/1/messages", json=payload)

        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["content"] == "Test message"
        assert data["id"] == 1

    def test_add_message_with_parent(
        self, authed_client, mock_message_service, test_user_id
    ):
        """Test adding a message with parent (branching)."""
        mock_message_service.add_message.return_value = {
            "id": 2,
            "conversation_id": 1,
            "user_id": test_user_id,
            "role": "user",
            "content": "Branched message",
            "content_cleaned": "Branched message",
            "answers": None,
            "parent_message_id": 5,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {},
        }

        payload = {
            "content": "Branched message",
            "content_cleaned": "Branched message",
            "answers": None,
            "parent_message_id": 5,
            "metadata": {},
        }
        resp = authed_client.post("/api/v1/conversations/1/messages", json=payload)

        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["parent_message_id"] == 5

    def test_add_message_validation_error(self, authed_client):
        """Test adding message with validation error (missing required field)."""
        # Send payload without required 'content' field
        payload = {}
        resp = authed_client.post("/api/v1/conversations/1/messages", json=payload)

        # FastAPI validation returns 422
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_add_message_unauthorized(self, plain_client):
        """Test adding message without authentication."""
        payload = {"content": "Test message"}
        resp = plain_client.post("/api/v1/conversations/1/messages", json=payload)

        # HTTPBearer returns 403 for missing credentials
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_add_message_server_error(self, authed_client, mock_message_service):
        """Test server error handling."""
        mock_message_service.add_message.side_effect = Exception("Database error")

        payload = {"content": "Test message"}
        resp = authed_client.post("/api/v1/conversations/1/messages", json=payload)

        assert resp.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    # ========== LIST MESSAGES TESTS ==========

    def test_list_messages_success(self, authed_client, mock_message_service):
        """Test listing messages successfully."""
        mock_message_service.list_messages.return_value = {
            "messages": [
                {
                    "id": 1,
                    "conversation_id": 1,
                    "content": "Test message",
                    "content_cleaned": "Test message",
                    "answers": None,
                    "parent_message_id": None,
                    "created_at": "2025-11-10T00:00:00+00:00",
                    "updated_at": "2025-11-10T00:00:00+00:00",
                    "role": "user",
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 50,
        }

        resp = authed_client.get("/api/v1/conversations/1/messages")

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "messages" in data
        assert data["total"] == 1

    def test_list_messages_with_pagination(self, authed_client, mock_message_service):
        """Test listing messages with pagination."""
        mock_message_service.list_messages.return_value = {
            "messages": [],
            "total": 0,
            "page": 2,
            "page_size": 10,
        }

        resp = authed_client.get("/api/v1/conversations/1/messages?page=2&page_size=10")

        assert resp.status_code == status.HTTP_200_OK

    def test_list_messages_with_ordering(self, authed_client, mock_message_service):
        """Test listing messages with custom ordering."""
        mock_message_service.list_messages.return_value = {
            "messages": [],
            "total": 0,
            "page": 1,
            "page_size": 50,
        }

        resp = authed_client.get("/api/v1/conversations/1/messages?order_by=updated_at")

        assert resp.status_code == status.HTTP_200_OK

    def test_list_messages_invalid_order_by(self, authed_client):
        """Test listing messages with invalid order_by parameter."""
        resp = authed_client.get(
            "/api/v1/conversations/1/messages?order_by=invalid_field"
        )

        # FastAPI validation error
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # ========== GET MESSAGE TESTS ==========

    def test_get_message_success(
        self, authed_client, mock_message_service, test_user_id
    ):
        """Test getting a specific message."""
        mock_message_service.get_message.return_value = {
            "id": 1,
            "conversation_id": 1,
            "user_id": test_user_id,
            "content": "Test message",
            "content_cleaned": "Test message",
            "answers": None,
            "parent_message_id": None,
            "created_at": "2025-11-10T00:00:00+00:00",
            "updated_at": "2025-11-10T00:00:00+00:00",
            "role": "user",
        }

        resp = authed_client.get("/api/v1/conversations/messages/1")

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["id"] == 1

    def test_get_message_not_found(self, authed_client, mock_message_service):
        """Test getting non-existent message."""
        mock_message_service.get_message.return_value = None

        resp = authed_client.get("/api/v1/conversations/messages/999")

        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in resp.text.lower()

    # ========== UPDATE MESSAGE TESTS ==========

    def test_update_message_success(
        self, authed_client, mock_message_service, test_user_id
    ):
        """Test updating a message successfully."""
        mock_message_service.update_message.return_value = {
            "id": 1,
            "conversation_id": 1,
            "user_id": test_user_id,
            "content": "Updated content",
            "content_cleaned": "Updated content",
            "answers": None,
            "parent_message_id": None,
            "created_at": "2025-11-10T00:00:00+00:00",
            "updated_at": "2025-11-10T00:00:00+00:00",
            "version_count": 0,
            "child_count": 0,
            "role": "user",
        }

        payload = {"content": "Updated content", "create_version": True}
        resp = authed_client.patch("/api/v1/conversations/messages/1", json=payload)

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["content"] == "Updated content"

    def test_update_message_not_found(self, authed_client, mock_message_service):
        """Test updating non-existent message."""
        mock_message_service.update_message.side_effect = ValueError(
            "Message not found"
        )

        payload = {"content": "Updated content"}
        resp = authed_client.patch("/api/v1/conversations/messages/999", json=payload)

        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # ========== DELETE MESSAGE TESTS ==========

    def test_delete_message_success(self, authed_client, mock_message_service):
        """Test deleting a message successfully."""
        mock_message_service.delete_message.return_value = True

        resp = authed_client.delete("/api/v1/conversations/messages/1")

        assert resp.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_message_not_found(self, authed_client, mock_message_service):
        """Test deleting non-existent message."""
        mock_message_service.delete_message.return_value = False

        resp = authed_client.delete("/api/v1/conversations/messages/999")

        assert resp.status_code == status.HTTP_404_NOT_FOUND

    # ========== BRANCHING TESTS ==========

    def test_create_branch_success(
        self, authed_client, mock_message_service, test_user_id
    ):
        """Test creating a message branch."""
        mock_message_service.create_branch.return_value = {
            "id": 2,
            "conversation_id": 1,
            "user_id": test_user_id,
            "content": "Branched content",
            "content_cleaned": "Branched content",
            "answers": None,
            "parent_message_id": 1,
            "created_at": "2025-11-10T00:00:00+00:00",
            "updated_at": "2025-11-10T00:00:00+00:00",
            "version_count": 0,
            "child_count": 0,
            "role": "user",
        }

        payload = {"content": "Branched content", "metadata": {}}
        resp = authed_client.post(
            "/api/v1/conversations/messages/1/branch", json=payload
        )

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["content"] == "Branched content"

    def test_create_branch_parent_not_found(self, authed_client, mock_message_service):
        """Test creating branch from non-existent parent."""
        mock_message_service.create_branch.side_effect = ValueError(
            "Parent message not found"
        )

        payload = {"content": "Branched content"}
        resp = authed_client.post(
            "/api/v1/conversations/messages/999/branch", json=payload
        )

        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # ========== TREE STRUCTURE TESTS ==========

    @pytest.mark.skip(reason="Tree endpoint needs object-like mock, not dict")
    def test_get_conversation_tree_success(self, authed_client, mock_message_service):
        """Test getting conversation tree."""
        # Return a complete MessageTreeNode with all required fields
        mock_message_service.get_conversation_tree.return_value = {
            "id": 1,
            "conversation_id": 1,
            "user_id": 123,
            "role": "user",
            "content": "Root message",
            "content_cleaned": "Root message",
            "answers": None,
            "parent_message_id": None,
            "created_at": "2025-11-10T00:00:00+00:00",
            "updated_at": "2025-11-10T00:00:00+00:00",
            "version_count": 0,
            "child_count": 0,
            "metadata": {},
            "level": 0,
            "is_leaf": True,
            "children": [],
        }

        resp = authed_client.get("/api/v1/conversations/1/tree")

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "tree" in data
        assert data["success"] is True

    def test_get_message_path_success(self, authed_client, mock_message_service):
        """Test getting message path."""
        # MessagePathResponse expects path: List[MessageDetail]
        # The service returns MessagePathResponse, endpoint returns it directly
        mock_message_service.get_message_path.return_value = {
            "path": [
                {
                    "id": 1,
                    "conversation_id": 1,
                    "user_id": 123,
                    "role": "user",
                    "content": "Root",
                    "content_cleaned": "Root",
                    "answers": None,
                    "parent_message_id": None,
                    "created_at": "2025-11-10T00:00:00+00:00",
                    "updated_at": "2025-11-10T00:00:00+00:00",
                    "version_count": 0,
                    "child_count": 1,
                    "metadata": {},
                },
                {
                    "id": 2,
                    "conversation_id": 1,
                    "user_id": 123,
                    "role": "user",
                    "content": "Child",
                    "content_cleaned": "Child",
                    "answers": None,
                    "parent_message_id": 1,
                    "created_at": "2025-11-10T00:00:00+00:00",
                    "updated_at": "2025-11-10T00:00:00+00:00",
                    "version_count": 0,
                    "child_count": 0,
                    "metadata": {},
                },
            ],
            "branch_points": [1],
            "total_length": 2,
        }

        resp = authed_client.get("/api/v1/conversations/messages/2/path")

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "path" in data
        assert len(data["path"]) == 2

    def test_get_message_children_success(self, authed_client, mock_message_service):
        """Test getting message children."""
        mock_message_service.get_message_children.return_value = []

        resp = authed_client.get("/api/v1/conversations/messages/1/children")

        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.json(), list)

    # ========== VERSION MANAGEMENT TESTS ==========

    def test_get_message_versions_success(
        self, authed_client, app, mock_version_service
    ):
        """Test getting message versions."""
        # Setup version service override
        from app.api.message import get_version_service

        app.dependency_overrides[get_version_service] = lambda: mock_version_service

        # MessageVersionListResponse expects MessageVersionDetail items
        mock_version_service.get_versions.return_value = {
            "success": True,
            "message": "Versions retrieved",
            "versions": [
                {
                    "id": 1,
                    "message_id": 1,
                    "version_number": 1,
                    "content": "Version 1",
                    "content_cleaned": "Version 1",
                    "answers": None,
                    "metadata": {},
                    "created_at": "2025-11-10T00:00:00+00:00",
                }
            ],
            "total": 1,
            "current_version": 1,
        }

        resp = authed_client.get("/api/v1/conversations/messages/1/versions")

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "versions" in data

    def test_get_specific_version_success(
        self, authed_client, app, mock_version_service
    ):
        """Test getting a specific version."""
        from app.api.message import get_version_service

        app.dependency_overrides[get_version_service] = lambda: mock_version_service

        # get_version returns MessageVersionDetail, but the endpoint expects MessageDetail
        # So we need to return a full message structure
        mock_version_service.get_version.return_value = {
            "id": 1,
            "conversation_id": 1,
            "user_id": 123,
            "role": "user",
            "content": "Version 1",
            "content_cleaned": "Version 1",
            "answers": None,
            "parent_message_id": None,
            "created_at": "2025-11-10T00:00:00+00:00",
            "updated_at": "2025-11-10T00:00:00+00:00",
            "version_count": 1,
            "child_count": 0,
            "metadata": {},
        }

        resp = authed_client.get("/api/v1/conversations/messages/1/versions/1")

        assert resp.status_code == status.HTTP_200_OK

    def test_get_version_not_found(self, authed_client, app, mock_version_service):
        """Test getting non-existent version."""
        from app.api.message import get_version_service

        app.dependency_overrides[get_version_service] = lambda: mock_version_service

        mock_version_service.get_version.return_value = None

        resp = authed_client.get("/api/v1/conversations/messages/1/versions/999")

        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_compare_versions_success(self, authed_client, app, mock_version_service):
        """Test comparing two versions."""
        from app.api.message import get_version_service

        app.dependency_overrides[get_version_service] = lambda: mock_version_service

        # MessageVersionCompareResponse expects MessageVersionDetail for version1 and version2
        mock_version_service.compare_versions.return_value = {
            "success": True,
            "message": "Versions compared",
            "version1": {
                "id": 1,
                "message_id": 1,
                "version_number": 1,
                "content": "Old content",
                "content_cleaned": "Old content",
                "answers": None,
                "metadata": {},
                "created_at": "2025-11-10T00:00:00+00:00",
            },
            "version2": {
                "id": 2,
                "message_id": 1,
                "version_number": 2,
                "content": "New content",
                "content_cleaned": "New content",
                "answers": None,
                "metadata": {},
                "created_at": "2025-11-10T00:01:00+00:00",
            },
            "differences": {"content": "Content changed"},
        }

        resp = authed_client.post(
            "/api/v1/conversations/messages/1/versions/compare?version1=1&version2=2"
        )

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "differences" in data

    def test_rollback_version_success(self, authed_client, app, mock_version_service):
        """Test rolling back to a version."""
        from app.api.message import get_version_service

        app.dependency_overrides[get_version_service] = lambda: mock_version_service

        # MessageVersionRollbackResponse expects rolled_back_message (MessageDetail)
        # Service returns the response directly
        mock_version_service.rollback_to_version.return_value = {
            "rolled_back_message": {
                "id": 1,
                "conversation_id": 1,
                "user_id": 123,
                "role": "user",
                "content": "Rolled back content",
                "content_cleaned": "Rolled back content",
                "answers": None,
                "parent_message_id": None,
                "created_at": "2025-11-10T00:00:00+00:00",
                "updated_at": "2025-11-10T00:00:00+00:00",
                "version_count": 2,
                "child_count": 0,
                "metadata": {},
            },
            "rollback_version": 1,
            "backup_version_created": 3,
        }

        payload = {"version_number": 1, "create_backup_version": True}
        resp = authed_client.post(
            "/api/v1/conversations/messages/1/rollback", json=payload
        )

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "rolled_back_message" in data
        assert data["rollback_version"] == 1

    def test_cleanup_versions_success(self, authed_client, app, mock_version_service):
        """Test cleaning up old versions."""
        from app.api.message import get_version_service

        app.dependency_overrides[get_version_service] = lambda: mock_version_service

        mock_version_service.cleanup_old_versions.return_value = 5

        resp = authed_client.post(
            "/api/v1/conversations/messages/1/versions/cleanup?keep_latest=10"
        )

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        # MessageBaseResponse has success, message, and data fields
        assert "cleaned_count" in data["data"]
