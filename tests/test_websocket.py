"""
WebSocket functionality tests.
"""

import pytest
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch

from fastapi.testclient import TestClient
from fastapi import WebSocket
from asyncpg import Pool

from app.main import app
from app.services.websocket_manager import (
    WebSocketConnectionManager,
    WebSocketEvent,
    WebSocketEventType,
)
from app.api.websocket import (
    verify_websocket_token,
    verify_conversation_access,
    handle_websocket_message,
    handle_new_message,
    handle_message_update,
    handle_message_delete,
)
from app.schemas.message import MessageResponse, MessageCreate
from app.schemas.conversation import ConversationResponse
from app.schemas.user import UserInDB


@pytest.fixture
def test_user():
    """Create test user."""
    return UserInDB(
        id=1,
        email="test@example.com",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def test_conversation():
    """Create test conversation."""
    return ConversationResponse(
        id=1,
        user_id=1,
        title="Test Conversation",
        is_pinned=False,
        is_archived=False,
        metadata={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def test_message():
    """Create test message."""
    return MessageResponse(
        id=1,
        conversation_id=1,
        user_id=1,
        content="Test message",
        content_type="text",
        metadata={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def connection_manager():
    """Create WebSocket connection manager instance."""
    return WebSocketConnectionManager()


class TestWebSocketConnectionManager:
    """Test WebSocket connection manager functionality."""

    @pytest.mark.asyncio
    async def test_connect_user_to_conversation(self, connection_manager):
        """Test connecting a user to a conversation."""
        mock_websocket = Mock(spec=WebSocket)

        # Connect user
        result = await connection_manager.connect(
            "1", "1", mock_websocket, {"user_email": "test@example.com"}
        )

        assert result is True
        assert connection_manager.is_user_connected("1", "1")
        assert "1" in connection_manager.chat_connections
        assert "1" in connection_manager.chat_connections["1"]
        assert "1" in connection_manager.user_conversations

    @pytest.mark.asyncio
    async def test_connect_user_already_connected(self, connection_manager):
        """Test connecting user who is already connected to conversation."""
        mock_websocket = Mock(spec=WebSocket)

        # First connection
        await connection_manager.connect("1", "1", mock_websocket)

        # Second connection should fail
        result = await connection_manager.connect("1", "1", mock_websocket)

        assert result is False

    @pytest.mark.asyncio
    async def test_disconnect_user_from_conversation(self, connection_manager):
        """Test disconnecting a user from a conversation."""
        mock_websocket = Mock(spec=WebSocket)

        # Connect then disconnect
        await connection_manager.connect("1", "1", mock_websocket)
        await connection_manager.disconnect("1", "1")

        assert not connection_manager.is_user_connected("1", "1")
        assert "1" not in connection_manager.user_conversations

    @pytest.mark.asyncio
    async def test_broadcast_to_conversation(self, connection_manager):
        """Test broadcasting event to conversation."""
        mock_websocket1 = Mock(spec=WebSocket)
        mock_websocket2 = Mock(spec=WebSocket)

        # Connect users
        await connection_manager.connect("1", "1", mock_websocket1)
        await connection_manager.connect("2", "1", mock_websocket2)

        # Create event
        event = WebSocketEvent(
            WebSocketEventType.MESSAGE_CREATED, {"content": "Test message"}
        )

        # Mock the send_json method
        mock_websocket1.send_json = AsyncMock()
        mock_websocket2.send_json = AsyncMock()

        # Broadcast (exclude user 1)
        sent_count = await connection_manager.broadcast_to_conversation(
            "1", event, exclude_user="1"
        )

        assert sent_count == 1
        mock_websocket1.send_json.assert_not_called()
        mock_websocket2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_typing_status(self, connection_manager):
        """Test setting typing status."""
        mock_websocket = Mock(spec=WebSocket)

        # Connect user
        await connection_manager.connect("1", "1", mock_websocket)
        mock_websocket.send_json = AsyncMock()

        # Set typing
        await connection_manager.set_typing("1", "1", True)

        assert "1" in connection_manager.typing_users["1"]

    def test_get_connection_stats(self, connection_manager):
        """Test getting connection statistics."""
        stats = connection_manager.get_connection_stats()

        assert "total_connections" in stats
        assert "total_conversations" in stats
        assert "total_users" in stats
        assert "connections_per_conversation" in stats
        assert "conversations_per_user" in stats

    def test_get_conversation_users(self, connection_manager):
        """Test getting list of users in conversation."""
        # Should return empty list for non-existent conversation
        users = connection_manager.get_conversation_users("999")
        assert users == []


class TestWebSocketEvents:
    """Test WebSocket event creation and serialization."""

    def test_websocket_event_creation(self):
        """Test creating a WebSocket event."""
        event = WebSocketEvent(
            WebSocketEventType.MESSAGE_CREATED, {"content": "Test message"}
        )

        assert event.type == WebSocketEventType.MESSAGE_CREATED
        assert event.data == {"content": "Test message"}
        assert event.event_id is not None
        assert event.timestamp is not None

    def test_websocket_event_to_dict(self):
        """Test converting WebSocket event to dictionary."""
        event = WebSocketEvent(
            WebSocketEventType.MESSAGE_CREATED, {"content": "Test message"}
        )

        event_dict = event.to_dict()

        assert "event_id" in event_dict
        assert "type" in event_dict
        assert "data" in event_dict
        assert "timestamp" in event_dict
        assert event_dict["type"] == "message_created"
        assert event_dict["data"] == {"content": "Test message"}


class TestWebSocketAuthentication:
    """Test WebSocket authentication functionality."""

    @pytest.mark.asyncio
    async def test_verify_websocket_token_success(self):
        """Test successful WebSocket token verification."""
        mock_pool = Mock(spec=Pool)

        with patch("app.api.websocket.verify_access_token") as mock_verify:
            with patch("app.services.user.UserService") as mock_user_service:
                # Mock successful token verification
                mock_verify.return_value = {"user_id": 1}

                # Mock user service
                mock_user_instance = AsyncMock()
                mock_user_instance.get_user_by_id.return_value = test_user
                mock_user_service.return_value = mock_user_instance

                # Test function
                result = await verify_websocket_token("valid_token", mock_pool)

                assert result == test_user
                mock_verify.assert_called_once_with("valid_token")
                mock_user_instance.get_user_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_verify_websocket_token_invalid(self):
        """Test WebSocket token verification with invalid token."""
        mock_pool = Mock(spec=Pool)

        with patch("app.api.websocket.verify_access_token") as mock_verify:
            # Mock failed token verification
            mock_verify.return_value = None

            with pytest.raises(WebSocketException) as exc_info:
                await verify_websocket_token("invalid_token", mock_pool)

            assert exc_info.value.code == 1008  # WS_1008_POLICY_VIOLATION
            assert "Invalid authentication token" in str(exc_info.value.reason)

    @pytest.mark.asyncio
    async def test_verify_conversation_access_success(self):
        """Test successful conversation access verification."""
        mock_pool = Mock(spec=Pool)

        with patch("app.api.websocket.ConversationRepository") as mock_repo_class:
            # Mock successful conversation lookup
            mock_repo = AsyncMock()
            mock_repo.get_by_id_and_user.return_value = test_conversation
            mock_repo_class.return_value = mock_repo

            result = await verify_conversation_access(1, 1, mock_pool)

            assert result is True
            mock_repo.get_by_id_and_user.assert_called_once_with(1, 1)

    @pytest.mark.asyncio
    async def test_verify_conversation_access_denied(self):
        """Test conversation access verification when access is denied."""
        mock_pool = Mock(spec=Pool)

        with patch("app.api.websocket.ConversationRepository") as mock_repo_class:
            # Mock failed conversation lookup
            mock_repo = AsyncMock()
            mock_repo.get_by_id_and_user.return_value = None
            mock_repo_class.return_value = mock_repo

            result = await verify_conversation_access(1, 1, mock_pool)

            assert result is False


class TestWebSocketMessageHandling:
    """Test WebSocket message handling functionality."""

    @pytest.mark.asyncio
    async def test_handle_ping_message(self, test_user):
        """Test handling ping message."""
        mock_websocket = Mock(spec=WebSocket)
        mock_pool = Mock(spec=Pool)

        data = {"type": "ping", "data": {}}

        with patch("app.api.websocket.connection_manager") as mock_manager:
            await handle_websocket_message(
                mock_websocket, data, 1, test_user, mock_pool
            )

            # Should send pong response
            mock_manager.send_to_user.assert_called_once()
            call_args = mock_manager.send_to_user.call_args
            assert call_args[0][0] == "1"  # user_id
            assert call_args[0][1].type.value == "pong"

    @pytest.mark.asyncio
    async def test_handle_typing_message(self, test_user):
        """Test handling typing indicator message."""
        mock_websocket = Mock(spec=WebSocket)
        mock_pool = Mock(spec=Pool)

        data = {"type": "typing", "data": {"is_typing": True}}

        with patch("app.api.websocket.connection_manager") as mock_manager:
            await handle_websocket_message(
                mock_websocket, data, 1, test_user, mock_pool
            )

            # Should set typing status
            mock_manager.set_typing.assert_called_once_with("1", "1", True)

    @pytest.mark.asyncio
    async def test_handle_new_message_success(self, test_user, test_message):
        """Test successful new message creation via WebSocket."""
        mock_pool = Mock(spec=Pool)

        message_data = {"content": "Test message", "metadata": {"source": "websocket"}}

        with patch("app.api.websocket.MessageService") as mock_service_class:
            # Mock message service
            mock_service = AsyncMock()
            mock_service.create_message.return_value = test_message
            mock_service_class.return_value = mock_service

            with patch("app.api.websocket.connection_manager") as mock_manager:
                await handle_new_message(message_data, 1, test_user, mock_pool)

                # Should create message
                mock_service.create_message.assert_called_once()

                # Should broadcast message
                mock_manager.broadcast_to_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_new_message_empty_content(self, test_user):
        """Test handling new message with empty content."""
        mock_pool = Mock(spec=Pool)

        message_data = {"content": "   "}  # Whitespace only

        with patch("app.api.websocket.connection_manager") as mock_manager:
            await handle_new_message(message_data, 1, test_user, mock_pool)

            # Should send error event
            mock_manager.send_to_user.assert_called_once()
            call_args = mock_manager.send_to_user.call_args
            assert call_args[0][1].type.value == "error"

    @pytest.mark.asyncio
    async def test_handle_message_update_success(self, test_user, test_message):
        """Test successful message update via WebSocket."""
        mock_pool = Mock(spec=Pool)

        message_data = {"message_id": 1, "content": "Updated message", "metadata": {}}

        with patch("app.api.websocket.MessageService") as mock_service_class:
            # Mock message service
            mock_service = AsyncMock()
            mock_service.update_message.return_value = test_message
            mock_service_class.return_value = mock_service

            with patch("app.api.websocket.connection_manager") as mock_manager:
                await handle_message_update(message_data, 1, test_user, mock_pool)

                # Should update message
                mock_service.update_message.assert_called_once_with(1, 1, 1, mock.ANY)

                # Should broadcast update
                mock_manager.broadcast_to_conversation.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_delete_success(self, test_user):
        """Test successful message deletion via WebSocket."""
        mock_pool = Mock(spec=Pool)

        message_data = {"message_id": 1}

        with patch("app.api.websocket.MessageService") as mock_service_class:
            # Mock message service
            mock_service = AsyncMock()
            mock_service.delete_message.return_value = True
            mock_service_class.return_value = mock_service

            with patch("app.api.websocket.connection_manager") as mock_manager:
                await handle_message_delete(message_data, 1, test_user, mock_pool)

                # Should delete message
                mock_service.delete_message.assert_called_once_with(1, 1, 1)

                # Should broadcast deletion
                mock_manager.broadcast_to_conversation.assert_called_once()


class TestWebSocketIntegration:
    """Test WebSocket integration with conversation and message services."""

    @pytest.mark.asyncio
    async def test_message_service_broadcast_on_create(self):
        """Test that message service broadcasts on message creation."""
        with patch("app.services.message.MessageRepository") as mock_repo_class:
            with patch(
                "app.services.message.ConversationRepository"
            ) as mock_conv_repo_class:
                with patch(
                    "app.services.message.broadcast_message_created"
                ) as mock_broadcast:
                    # Mock repositories
                    mock_conv_repo = AsyncMock()
                    mock_conv_repo.get_by_id_and_user.return_value = test_conversation
                    mock_conv_repo_class.return_value = mock_conv_repo

                    mock_repo = AsyncMock()
                    mock_repo.create.return_value = Mock(
                        id=1,
                        conversation_id=1,
                        user_id=1,
                        content="Test message",
                        content_type="text",
                        metadata={},
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                    mock_repo_class.return_value = mock_repo

                    # Import and create service
                    from app.services.message import MessageService

                    service = MessageService(Mock(spec=Pool))

                    # Create message
                    message_create = MessageCreate(
                        conversation_id=1,
                        user_id=1,
                        content="Test message",
                        content_type="text",
                        metadata={},
                    )

                    result = await service.create_message(1, 1, message_create)

                    # Should broadcast message creation
                    assert mock_broadcast.call_count == 1  # Called once in service

    @pytest.mark.asyncio
    async def test_conversation_service_broadcast_on_create(self):
        """Test that conversation service broadcasts on conversation creation."""
        with patch(
            "app.services.conversation.ConversationRepository"
        ) as mock_repo_class:
            with patch(
                "app.services.conversation.send_conversation_update"
            ) as mock_broadcast:
                # Mock repository
                mock_repo = AsyncMock()
                mock_repo.create.return_value = Mock(
                    id=1,
                    user_id=1,
                    title="Test Conversation",
                    is_pinned=False,
                    is_archived=False,
                    metadata={},
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                mock_repo_class.return_value = mock_repo

                # Import and create service
                from app.services.conversation import ConversationService

                service = ConversationService(Mock(spec=Pool))

                # Create conversation
                from app.schemas.conversation import ConversationCreate

                conv_create = ConversationCreate(title="Test Conversation", metadata={})

                result = await service.create_conversation(1, conv_create)

                # Should broadcast conversation update
                mock_broadcast.assert_called_once()


# Global test fixtures reused across tests
test_user = UserInDB(
    id=1,
    email="test@example.com",
    is_active=True,
    created_at=datetime.now(timezone.utc),
    updated_at=datetime.now(timezone.utc),
)

test_conversation = ConversationResponse(
    id=1,
    user_id=1,
    title="Test Conversation",
    is_pinned=False,
    is_archived=False,
    metadata={},
    created_at=datetime.now(timezone.utc),
    updated_at=datetime.now(timezone.utc),
)

test_message = MessageResponse(
    id=1,
    conversation_id=1,
    user_id=1,
    content="Test message",
    content_type="text",
    metadata={},
    created_at=datetime.now(timezone.utc),
    updated_at=datetime.now(timezone.utc),
)
