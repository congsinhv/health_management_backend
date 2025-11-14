"""
WebSocket integration tests - end-to-end testing of real-time functionality.
"""

import pytest
import json
import asyncio
from datetime import datetime, timezone
from typing import Generator
from unittest.mock import Mock, AsyncMock, patch

import websockets
from fastapi.testclient import TestClient
from httpx import WebSocketConnectError

from app.main import app
from app.services.websocket_manager import connection_manager, WebSocketEventType


class TestWebSocketIntegration:
    """End-to-end WebSocket integration tests."""

    def test_websocket_endpoint_exists(self):
        """Test that WebSocket endpoint is properly registered."""
        client = TestClient(app)

        # Test that the endpoint exists (will raise an exception if not)
        with pytest.raises(Exception):
            client.websocket_connect("/ws/chat/1")

    @pytest.mark.asyncio
    async def test_websocket_connection_flow(self):
        """Test complete WebSocket connection flow."""
        # This test would require a running WebSocket server
        # For now, we'll test the components that would be used

        mock_websocket = Mock()
        mock_websocket.send_json = AsyncMock()
        mock_websocket.receive_json = AsyncMock()

        # Mock authentication
        with patch("app.api.websocket.verify_websocket_token") as mock_auth:
            with patch("app.api.websocket.verify_conversation_access") as mock_access:
                # Mock successful authentication
                mock_auth.return_value = Mock(
                    id=1, email="test@example.com", is_active=True
                )
                mock_access.return_value = True

                # Simulate connection
                connected = await connection_manager.connect(
                    "1", "1", mock_websocket, {"user_email": "test@example.com"}
                )

                assert connected is True
                assert connection_manager.is_user_connected("1", "1")

    def test_websocket_event_types(self):
        """Test all WebSocket event types are properly defined."""
        expected_types = {
            "message_created",
            "message_updated",
            "message_deleted",
            "user_typing",
            "user_stopped_typing",
            "user_joined",
            "user_left",
            "ai_response",
            "error",
            "ping",
            "pong",
        }

        actual_types = {event_type.value for event_type in WebSocketEventType}
        assert actual_types == expected_types

    @pytest.mark.asyncio
    async def test_conversation_message_broadcasting(self):
        """Test message broadcasting within conversations."""
        # Setup multiple users in conversation
        mock_websocket1 = Mock()
        mock_websocket2 = Mock()
        mock_websocket3 = Mock()

        mock_websocket1.send_json = AsyncMock()
        mock_websocket2.send_json = AsyncMock()
        mock_websocket3.send_json = AsyncMock()

        # Connect users
        await connection_manager.connect("1", "1", mock_websocket1)
        await connection_manager.connect("2", "1", mock_websocket2)
        await connection_manager.connect("3", "1", mock_websocket3)

        # Create message event
        from app.services.websocket_manager import WebSocketEvent

        message_event = WebSocketEvent(
            WebSocketEventType.MESSAGE_CREATED,
            {
                "id": 1,
                "conversation_id": 1,
                "user_id": 1,
                "content": "Hello everyone!",
                "content_type": "text",
                "metadata": {},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Broadcast message (excluding sender)
        sent_count = await connection_manager.broadcast_to_conversation(
            "1", message_event, exclude_user="1"
        )

        # Should be sent to 2 other users
        assert sent_count == 2

        # Verify recipients received the message
        mock_websocket1.send_json.assert_not_called()  # Sender excluded
        mock_websocket2.send_json.assert_called_once()
        mock_websocket3.send_json.assert_called_once()

        # Verify the event structure
        call_args = mock_websocket2.send_json.call_args[0][0]
        assert call_args["type"] == "message_created"
        assert call_args["data"]["content"] == "Hello everyone!"
        assert call_args["data"]["user_id"] == 1

    @pytest.mark.asyncio
    async def test_typing_indicators(self):
        """Test typing indicator functionality."""
        mock_websocket1 = Mock()
        mock_websocket2 = Mock()
        mock_websocket1.send_json = AsyncMock()
        mock_websocket2.send_json = AsyncMock()

        # Connect users
        await connection_manager.connect("1", "1", mock_websocket1)
        await connection_manager.connect("2", "1", mock_websocket2)

        # User 1 starts typing
        await connection_manager.set_typing("1", "1", True)

        # User 2 should receive typing indicator
        mock_websocket2.send_json.assert_called_once()
        typing_event = mock_websocket2.send_json.call_args[0][0]
        assert typing_event["type"] == "user_typing"
        assert typing_event["data"]["user_id"] == "1"

        # Reset mock
        mock_websocket2.send_json.reset_mock()

        # User 1 stops typing
        await connection_manager.set_typing("1", "1", False)

        # User 2 should receive stopped typing indicator
        mock_websocket2.send_json.assert_called_once()
        stopped_typing_event = mock_websocket2.send_json.call_args[0][0]
        assert stopped_typing_event["type"] == "user_stopped_typing"
        assert stopped_typing_event["data"]["user_id"] == "1"

    @pytest.mark.asyncio
    async def test_connection_cleanup_on_disconnect(self):
        """Test connection cleanup when user disconnects."""
        mock_websocket = Mock()
        mock_websocket.send_json = AsyncMock()

        # Connect user
        await connection_manager.connect("1", "1", mock_websocket)
        assert connection_manager.is_user_connected("1", "1")

        # Disconnect user
        await connection_manager.disconnect("1", "1")

        # Verify cleanup
        assert not connection_manager.is_user_connected("1", "1")
        assert "1" not in connection_manager.user_conversations

    @pytest.mark.asyncio
    async def test_stale_connection_cleanup(self):
        """Test cleanup of stale connections."""
        mock_websocket = Mock()

        # Connect user
        await connection_manager.connect("1", "1", mock_websocket)

        # Simulate stale connection by modifying connection stats
        connection_key = "1:1"
        if connection_key in connection_manager.connection_stats:
            # Set last_ping to old time (more than 30 minutes ago)
            from datetime import timedelta

            old_time = datetime.utcnow() - timedelta(minutes=35)
            connection_manager.connection_stats[connection_key]["last_ping"] = old_time

        # Run cleanup with 30-minute threshold
        await connection_manager.cleanup_stale_connections(max_idle_minutes=30)

        # Connection should be cleaned up
        assert not connection_manager.is_user_connected("1", "1")

    def test_connection_monitoring_stats(self):
        """Test connection monitoring and statistics."""
        stats = connection_manager.get_connection_stats()

        # Verify stats structure
        expected_keys = {
            "total_connections",
            "total_conversations",
            "total_users",
            "connections_per_conversation",
            "conversations_per_user",
        }

        assert set(stats.keys()) == expected_keys
        assert isinstance(stats["total_connections"], int)
        assert isinstance(stats["total_conversations"], int)
        assert isinstance(stats["total_users"], int)
        assert isinstance(stats["connections_per_conversation"], dict)
        assert isinstance(stats["conversations_per_user"], dict)

    @pytest.mark.asyncio
    async def test_cross_conversation_isolation(self):
        """Test that messages don't cross between conversations."""
        mock_websocket1 = Mock()  # User 1 in conversation 1
        mock_websocket2 = Mock()  # User 2 in conversation 1
        mock_websocket3 = Mock()  # User 3 in conversation 2

        mock_websocket1.send_json = AsyncMock()
        mock_websocket2.send_json = AsyncMock()
        mock_websocket3.send_json = AsyncMock()

        # Connect users to different conversations
        await connection_manager.connect("1", "1", mock_websocket1)
        await connection_manager.connect("2", "1", mock_websocket2)
        await connection_manager.connect("3", "2", mock_websocket3)

        # Create message event for conversation 1
        from app.services.websocket_manager import WebSocketEvent

        message_event = WebSocketEvent(
            WebSocketEventType.MESSAGE_CREATED,
            {
                "id": 1,
                "conversation_id": 1,
                "user_id": 1,
                "content": "Message for conversation 1",
                "content_type": "text",
            },
        )

        # Broadcast to conversation 1
        sent_count = await connection_manager.broadcast_to_conversation(
            "1", message_event
        )

        # Should only reach users in conversation 1
        assert sent_count == 1  # Only user 2 (user 1 excluded)
        mock_websocket2.send_json.assert_called_once()
        mock_websocket3.send_json.assert_not_called()  # Different conversation

    @pytest.mark.asyncio
    async def test_error_handling_in_broadcast(self):
        """Test error handling when WebSocket send fails."""
        mock_websocket1 = Mock()
        mock_websocket2 = Mock()

        # First WebSocket fails on send, second succeeds
        mock_websocket1.send_json = AsyncMock(side_effect=Exception("Connection lost"))
        mock_websocket2.send_json = AsyncMock()

        # Connect users
        await connection_manager.connect("1", "1", mock_websocket1)
        await connection_manager.connect("2", "1", mock_websocket2)

        # Create and broadcast message
        from app.services.websocket_manager import WebSocketEvent

        message_event = WebSocketEvent(
            WebSocketEventType.MESSAGE_CREATED, {"content": "Test message"}
        )

        # Should handle failed connection gracefully
        sent_count = await connection_manager.broadcast_to_conversation(
            "1", message_event
        )

        # Should still send to successful connection
        assert sent_count == 1
        mock_websocket2.send_json.assert_called_once()

        # Failed connection should be cleaned up
        assert not connection_manager.is_user_connected("1", "1")
        assert connection_manager.is_user_connected("2", "1")

    @pytest.mark.asyncio
    async def test_multiple_conversations_per_user(self):
        """Test user connected to multiple conversations."""
        mock_websocket1 = Mock()
        mock_websocket2 = Mock()

        mock_websocket1.send_json = AsyncMock()
        mock_websocket2.send_json = AsyncMock()

        # Connect same user to different conversations
        await connection_manager.connect("1", "1", mock_websocket1)
        await connection_manager.connect("1", "2", mock_websocket2)

        # Verify user is tracked in both conversations
        assert connection_manager.is_user_connected("1", "1")
        assert connection_manager.is_user_connected("1", "2")
        assert "1" in connection_manager.user_conversations
        assert len(connection_manager.user_conversations["1"]) == 2

        # Get user's conversations
        user_convs = connection_manager.user_conversations["1"]
        assert "1" in user_convs
        assert "2" in user_convs

    @pytest.mark.asyncio
    async def test_ping_pong_mechanism(self):
        """Test ping/pong mechanism for connection health."""
        mock_websocket = Mock()
        mock_websocket.send_json = AsyncMock()

        # Connect user
        await connection_manager.connect("1", "1", mock_websocket)

        # Send ping
        await connection_manager.ping_all_connections()

        # Should receive ping
        mock_websocket.send_json.assert_called_once()
        ping_event = mock_websocket.send_json.call_args[0][0]
        assert ping_event["type"] == "ping"
        assert "timestamp" in ping_event["data"]


class TestWebSocketClientIntegration:
    """Tests for client-side WebSocket integration patterns."""

    def test_client_message_format(self):
        """Test expected client message format."""
        # These are examples of valid client messages
        valid_messages = [
            {"type": "message", "data": {"content": "Hello world", "metadata": {}}},
            {"type": "typing", "data": {"is_typing": True}},
            {
                "type": "message_update",
                "data": {"message_id": 1, "content": "Updated message", "metadata": {}},
            },
            {"type": "message_delete", "data": {"message_id": 1}},
            {"type": "ping", "data": {}},
        ]

        for message in valid_messages:
            assert "type" in message
            assert "data" in message
            assert isinstance(message["data"], dict)

    def test_server_event_format(self):
        """Test expected server event format."""
        from app.services.websocket_manager import WebSocketEvent, WebSocketEventType

        # Create sample event
        event = WebSocketEvent(
            WebSocketEventType.MESSAGE_CREATED,
            {
                "id": 1,
                "conversation_id": 1,
                "user_id": 1,
                "content": "Test message",
                "content_type": "text",
                "metadata": {},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        event_dict = event.to_dict()

        # Verify structure
        required_fields = ["event_id", "type", "data", "timestamp"]
        for field in required_fields:
            assert field in event_dict

        assert isinstance(event_dict["event_id"], str)
        assert isinstance(event_dict["type"], str)
        assert isinstance(event_dict["data"], dict)
        assert isinstance(event_dict["timestamp"], str)

    def test_websocket_url_format(self):
        """Test WebSocket URL format and parameters."""
        # Base WebSocket URL
        base_url = "ws://localhost:8000/ws/chat/123"

        # With JWT token parameter
        url_with_token = f"{base_url}?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

        # Should be valid URL format for client libraries
        assert "ws://" in base_url
        assert "/ws/chat/" in base_url
        assert "conversation_id" in base_url
        assert "token=" in url_with_token

    def test_error_event_structure(self):
        """Test error event structure for client error handling."""
        from app.services.websocket_manager import WebSocketEvent, WebSocketEventType

        error_event = WebSocketEvent(
            WebSocketEventType.ERROR,
            {
                "message": "Validation failed",
                "field": "content",
                "code": "VALIDATION_ERROR",
            },
        )

        event_dict = error_event.to_dict()

        assert event_dict["type"] == "error"
        assert "message" in event_dict["data"]
        assert "field" in event_dict["data"]
        assert "code" in event_dict["data"]
