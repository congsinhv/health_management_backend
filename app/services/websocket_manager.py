"""
WebSocket connection manager for real-time chat functionality.
"""

import json
import logging
from typing import Dict, Set, List, Optional, Any
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import WebSocket, WebSocketDisconnect
from enum import Enum

logger = logging.getLogger(__name__)


class WebSocketEventType(str, Enum):
    """WebSocket event types."""

    MESSAGE_CREATED = "message_created"
    MESSAGE_UPDATED = "message_updated"
    MESSAGE_DELETED = "message_deleted"
    USER_TYPING = "user_typing"
    USER_STOPPED_TYPING = "user_stopped_typing"
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    AI_RESPONSE = "ai_response"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


class WebSocketEvent:
    """Standard WebSocket event structure."""

    def __init__(
        self,
        event_type: WebSocketEventType,
        data: Dict[str, Any],
        timestamp: Optional[datetime] = None,
        event_id: Optional[str] = None,
    ):
        self.type = event_type
        self.data = data
        self.timestamp = timestamp or datetime.utcnow()
        self.event_id = event_id or str(uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


class WebSocketConnectionManager:
    """Manages WebSocket connections and message broadcasting."""

    def __init__(self):
        # conversation_id -> user_id -> WebSocket
        self.chat_connections: Dict[str, Dict[str, WebSocket]] = {}

        # user_id -> set of conversation_ids
        self.user_conversations: Dict[str, Set[str]] = {}

        # Connection metadata for monitoring
        self.connection_stats: Dict[str, Dict[str, Any]] = {}

        # Typing indicators
        self.typing_users: Dict[
            str, Set[str]
        ] = {}  # conversation_id -> set of user_ids

    async def connect(
        self,
        conversation_id: str,
        user_id: str,
        websocket: WebSocket,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Connect a user to a conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            websocket: WebSocket connection
            metadata: Optional connection metadata

        Returns:
            True if connected successfully, False if already connected
        """
        try:
            # Initialize conversation connections if needed
            if conversation_id not in self.chat_connections:
                self.chat_connections[conversation_id] = {}

            # Check if user already connected to this conversation
            if user_id in self.chat_connections[conversation_id]:
                logger.warning(
                    f"User {user_id} already connected to conversation {conversation_id}"
                )
                return False

            # Add connection
            self.chat_connections[conversation_id][user_id] = websocket

            # Track user's conversations
            if user_id not in self.user_conversations:
                self.user_conversations[user_id] = set()
            self.user_conversations[user_id].add(conversation_id)

            # Store connection metadata
            connection_key = f"{conversation_id}:{user_id}"
            self.connection_stats[connection_key] = {
                "connected_at": datetime.utcnow(),
                "last_ping": datetime.utcnow(),
                "metadata": metadata or {},
            }

            # Broadcast user joined event
            await self.broadcast_to_conversation(
                conversation_id,
                WebSocketEvent(WebSocketEventType.USER_JOINED, {"user_id": user_id}),
                exclude_user=user_id,
            )

            logger.info(f"User {user_id} connected to conversation {conversation_id}")
            return True

        except Exception as e:
            logger.error(
                f"Error connecting user {user_id} to conversation {conversation_id}: {e}"
            )
            return False

    async def disconnect(self, conversation_id: str, user_id: str) -> None:
        """
        Disconnect a user from a conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
        """
        try:
            # Remove from chat connections
            if conversation_id in self.chat_connections:
                if user_id in self.chat_connections[conversation_id]:
                    del self.chat_connections[conversation_id][user_id]

                # Clean up empty conversation
                if not self.chat_connections[conversation_id]:
                    del self.chat_connections[conversation_id]

            # Remove from user conversations
            if user_id in self.user_conversations:
                self.user_conversations[user_id].discard(conversation_id)
                if not self.user_conversations[user_id]:
                    del self.user_conversations[user_id]

            # Clean up typing indicators
            if conversation_id in self.typing_users:
                self.typing_users[conversation_id].discard(user_id)
                if not self.typing_users[conversation_id]:
                    del self.typing_users[conversation_id]

            # Clean up connection stats
            connection_key = f"{conversation_id}:{user_id}"
            if connection_key in self.connection_stats:
                del self.connection_stats[connection_key]

            # Broadcast user left event
            await self.broadcast_to_conversation(
                conversation_id,
                WebSocketEvent(WebSocketEventType.USER_LEFT, {"user_id": user_id}),
                exclude_user=user_id,
            )

            logger.info(
                f"User {user_id} disconnected from conversation {conversation_id}"
            )

        except Exception as e:
            logger.error(
                f"Error disconnecting user {user_id} from conversation {conversation_id}: {e}"
            )

    async def broadcast_to_conversation(
        self,
        conversation_id: str,
        event: WebSocketEvent,
        exclude_user: Optional[str] = None,
    ) -> int:
        """
        Broadcast event to all users in a conversation.

        Args:
            conversation_id: Conversation ID
            event: Event to broadcast
            exclude_user: Optional user ID to exclude from broadcast

        Returns:
            Number of users the event was sent to
        """
        if conversation_id not in self.chat_connections:
            return 0

        sent_count = 0
        disconnected_users = []

        for user_id, websocket in self.chat_connections[conversation_id].items():
            if exclude_user and user_id == exclude_user:
                continue

            try:
                await self._send_event(websocket, event)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send event to user {user_id}: {e}")
                disconnected_users.append(user_id)

        # Clean up disconnected users
        for user_id in disconnected_users:
            await self.disconnect(conversation_id, user_id)

        return sent_count

    async def send_to_user(
        self, user_id: str, event: WebSocketEvent, conversation_id: Optional[str] = None
    ) -> bool:
        """
        Send event to a specific user.

        Args:
            user_id: User ID
            event: Event to send
            conversation_id: Optional conversation ID for targeted sending

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # If conversation_id specified, send to that specific conversation
            if conversation_id and conversation_id in self.chat_connections:
                if user_id in self.chat_connections[conversation_id]:
                    websocket = self.chat_connections[conversation_id][user_id]
                    await self._send_event(websocket, event)
                    return True
            else:
                # Send to all user connections
                if user_id in self.user_conversations:
                    sent = False
                    for conv_id in self.user_conversations[user_id]:
                        if (
                            conv_id in self.chat_connections
                            and user_id in self.chat_connections[conv_id]
                        ):
                            websocket = self.chat_connections[conv_id][user_id]
                            await self._send_event(websocket, event)
                            sent = True
                    return sent

            return False

        except Exception as e:
            logger.error(f"Error sending event to user {user_id}: {e}")
            return False

    async def set_typing(
        self, conversation_id: str, user_id: str, is_typing: bool
    ) -> None:
        """
        Set typing status for a user in a conversation.

        Args:
            conversation_id: Conversation ID
            user_id: User ID
            is_typing: Whether user is typing
        """
        try:
            if conversation_id not in self.typing_users:
                self.typing_users[conversation_id] = set()

            if is_typing:
                self.typing_users[conversation_id].add(user_id)
                event_type = WebSocketEventType.USER_TYPING
            else:
                self.typing_users[conversation_id].discard(user_id)
                event_type = WebSocketEventType.USER_STOPPED_TYPING

            # Broadcast typing status
            await self.broadcast_to_conversation(
                conversation_id,
                WebSocketEvent(event_type, {"user_id": user_id}),
                exclude_user=user_id,
            )

        except Exception as e:
            logger.error(f"Error setting typing status for user {user_id}: {e}")

    def get_conversation_users(self, conversation_id: str) -> List[str]:
        """
        Get list of connected users in a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            List of user IDs
        """
        if conversation_id in self.chat_connections:
            return list(self.chat_connections[conversation_id].keys())
        return []

    def is_user_connected(self, user_id: str, conversation_id: str) -> bool:
        """
        Check if user is connected to conversation.

        Args:
            user_id: User ID
            conversation_id: Conversation ID

        Returns:
            True if connected, False otherwise
        """
        return (
            conversation_id in self.chat_connections
            and user_id in self.chat_connections[conversation_id]
        )

    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get connection statistics for monitoring.

        Returns:
            Connection statistics
        """
        total_connections = sum(len(conns) for conns in self.chat_connections.values())
        total_conversations = len(self.chat_connections)
        total_users = len(self.user_conversations)

        return {
            "total_connections": total_connections,
            "total_conversations": total_conversations,
            "total_users": total_users,
            "connections_per_conversation": {
                conv_id: len(conns) for conv_id, conns in self.chat_connections.items()
            },
            "conversations_per_user": {
                user_id: len(convs)
                for user_id, convs in self.user_conversations.items()
            },
        }

    async def _send_event(self, websocket: WebSocket, event: WebSocketEvent) -> None:
        """
        Send event to WebSocket connection.

        Args:
            websocket: WebSocket connection
            event: Event to send
        """
        try:
            await websocket.send_json(event.to_dict())
        except Exception as e:
            logger.error(f"Failed to send event to WebSocket: {e}")
            raise

    async def ping_all_connections(self) -> None:
        """Send ping to all connections for health checking."""
        ping_event = WebSocketEvent(
            WebSocketEventType.PING, {"timestamp": datetime.utcnow().isoformat()}
        )

        for conversation_id in list(self.chat_connections.keys()):
            await self.broadcast_to_conversation(conversation_id, ping_event)

    async def cleanup_stale_connections(self, max_idle_minutes: int = 30) -> None:
        """
        Clean up stale connections that haven't sent ping recently.

        Args:
            max_idle_minutes: Maximum idle time before cleanup
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=max_idle_minutes)
        stale_connections = []

        for connection_key, stats in self.connection_stats.items():
            if stats["last_ping"] < cutoff_time:
                conversation_id, user_id = connection_key.split(":", 1)
                stale_connections.append((conversation_id, user_id))

        for conversation_id, user_id in stale_connections:
            logger.info(f"Cleaning up stale connection: {conversation_id}:{user_id}")
            await self.disconnect(conversation_id, user_id)


# Global connection manager instance
connection_manager = WebSocketConnectionManager()
