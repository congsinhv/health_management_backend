"""
WebSocket utility functions for event broadcasting and integration.
"""

import logging
from typing import Optional, Dict, Any

from app.services.websocket_manager import (
    connection_manager,
    WebSocketEvent,
    WebSocketEventType,
)
from app.schemas.message import MessageResponse
from app.schemas.conversation import ConversationResponse

logger = logging.getLogger(__name__)


async def broadcast_message_created(
    message: MessageResponse, conversation_id: int, exclude_user: Optional[str] = None
) -> None:
    """
    Broadcast message creation event to conversation.

    Args:
        message: Created message
        conversation_id: Conversation ID
        exclude_user: Optional user ID to exclude
    """
    try:
        event = WebSocketEvent(WebSocketEventType.MESSAGE_CREATED, message.model_dump())
        await connection_manager.broadcast_to_conversation(
            str(conversation_id), event, exclude_user=exclude_user
        )
    except Exception as e:
        logger.error(f"Error broadcasting message creation: {e}")


async def broadcast_message_updated(
    message: MessageResponse, conversation_id: int, exclude_user: Optional[str] = None
) -> None:
    """
    Broadcast message update event to conversation.

    Args:
        message: Updated message
        conversation_id: Conversation ID
        exclude_user: Optional user ID to exclude
    """
    try:
        event = WebSocketEvent(WebSocketEventType.MESSAGE_UPDATED, message.model_dump())
        await connection_manager.broadcast_to_conversation(
            str(conversation_id), event, exclude_user=exclude_user
        )
    except Exception as e:
        logger.error(f"Error broadcasting message update: {e}")


async def broadcast_message_deleted(
    message_id: int, conversation_id: int, exclude_user: Optional[str] = None
) -> None:
    """
    Broadcast message deletion event to conversation.

    Args:
        message_id: Deleted message ID
        conversation_id: Conversation ID
        exclude_user: Optional user ID to exclude
    """
    try:
        event = WebSocketEvent(
            WebSocketEventType.MESSAGE_DELETED, {"message_id": message_id}
        )
        await connection_manager.broadcast_to_conversation(
            str(conversation_id), event, exclude_user=exclude_user
        )
    except Exception as e:
        logger.error(f"Error broadcasting message deletion: {e}")


async def broadcast_ai_response(message: MessageResponse, conversation_id: int) -> None:
    """
    Broadcast AI-generated message to conversation.

    Args:
        message: AI-generated message
        conversation_id: Conversation ID
    """
    try:
        event = WebSocketEvent(WebSocketEventType.AI_RESPONSE, message.model_dump())
        await connection_manager.broadcast_to_conversation(str(conversation_id), event)
    except Exception as e:
        logger.error(f"Error broadcasting AI response: {e}")


async def send_conversation_update(
    user_id: str, conversation: ConversationResponse
) -> None:
    """
    Send conversation update to specific user.

    Args:
        user_id: User ID
        conversation: Updated conversation
    """
    try:
        event = WebSocketEvent(
            "conversation_updated", conversation.model_dump()  # Custom event type
        )
        await connection_manager.send_to_user(user_id, event)
    except Exception as e:
        logger.error(f"Error sending conversation update: {e}")


async def send_user_notification(
    user_id: str, notification_type: str, data: Dict[str, Any]
) -> None:
    """
    Send notification to specific user.

    Args:
        user_id: User ID
        notification_type: Type of notification
        data: Notification data
    """
    try:
        event = WebSocketEvent(
            "notification",  # Custom event type
            {"type": notification_type, "data": data},
        )
        await connection_manager.send_to_user(user_id, event)
    except Exception as e:
        logger.error(f"Error sending user notification: {e}")


def get_connection_stats() -> Dict[str, Any]:
    """
    Get WebSocket connection statistics.

    Returns:
        Connection statistics
    """
    return connection_manager.get_connection_stats()


async def cleanup_websocket_connections() -> None:
    """Clean up stale WebSocket connections."""
    try:
        await connection_manager.cleanup_stale_connections()
    except Exception as e:
        logger.error(f"Error cleaning up WebSocket connections: {e}")


def is_user_connected_to_conversation(user_id: str, conversation_id: str) -> bool:
    """
    Check if user is connected to a conversation.

    Args:
        user_id: User ID
        conversation_id: Conversation ID

    Returns:
        True if connected, False otherwise
    """
    return connection_manager.is_user_connected(user_id, conversation_id)


def get_connected_users_in_conversation(conversation_id: str) -> list:
    """
    Get list of connected users in a conversation.

    Args:
        conversation_id: Conversation ID

    Returns:
        List of user IDs
    """
    return connection_manager.get_conversation_users(conversation_id)
