"""
WebSocket API endpoints for real-time chat functionality.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import (
    WebSocket,
    WebSocketException,
    WebSocketDisconnect,
    status,
    Query,
    Depends,
    HTTPException,
    APIRouter,
)
from asyncpg import Pool

from app.auth.dependencies import get_current_active_user
from app.db.database import get_database_pool
from app.db.conversation import ConversationRepository
from app.schemas.user import UserInDB
from app.services.websocket_manager import (
    connection_manager,
    WebSocketEvent,
    WebSocketEventType,
)

logger = logging.getLogger(__name__)


async def verify_websocket_token(
    token: str = Query(..., description="JWT access token"),
    pool: Pool = Depends(get_database_pool),
) -> UserInDB:
    """
    Authenticate WebSocket connection via JWT token.

    Args:
        token: JWT access token from query parameters
        pool: Database connection pool

    Returns:
        Authenticated user

    Raises:
        WebSocketException: If authentication fails
    """
    try:
        # Import here to avoid circular imports
        from app.helpers import verify_access_token

        # Verify JWT token
        payload = verify_access_token(token)
        if not payload:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid authentication token",
            )

        # Get user from database
        from app.services.user import UserService

        user_service = UserService(pool)
        user_record = await user_service.get_user_by_id(payload.get("user_id"))

        if not user_record or not user_record.is_active:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="User not found or inactive",
            )

        return user_record

    except WebSocketException:
        raise
    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed"
        )


async def verify_conversation_access(
    conversation_id: int, user_id: int, pool: Pool
) -> bool:
    """
    Verify user has access to conversation.

    Args:
        conversation_id: Conversation ID
        user_id: User ID
        pool: Database connection pool

    Returns:
        True if user has access, False otherwise
    """
    try:
        conversation_repo = ConversationRepository(pool)
        conversation = await conversation_repo.get_by_id_and_user(
            conversation_id, user_id
        )
        return conversation is not None
    except Exception as e:
        logger.error(f"Error verifying conversation access: {e}")
        return False


async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: int,
    user: UserInDB = Depends(verify_websocket_token),
    pool: Pool = Depends(get_database_pool),
) -> None:
    """
    WebSocket endpoint for real-time chat.

    Args:
        websocket: WebSocket connection
        conversation_id: Conversation ID
        user: Authenticated user
        pool: Database connection pool
    """
    await websocket.accept()

    # Verify user access to conversation
    if not await verify_conversation_access(conversation_id, user.id, pool):
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Access to conversation denied"
        )
        return

    # Connect to conversation
    connected = await connection_manager.connect(
        str(conversation_id),
        str(user.id),
        websocket,
        metadata={"user_email": user.email, "connected_at": datetime.utcnow()},
    )

    if not connected:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Already connected to this conversation",
        )
        return

    logger.info(
        f"WebSocket connection established for user {user.id} in conversation {conversation_id}"
    )

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()

            # Process message
            await handle_websocket_message(websocket, data, conversation_id, user, pool)

    except WebSocketDisconnect:
        logger.info(
            f"WebSocket disconnected for user {user.id} in conversation {conversation_id}"
        )
    except Exception as e:
        logger.error(
            f"WebSocket error for user {user.id} in conversation {conversation_id}: {e}"
        )
        # Send error event to user
        error_event = WebSocketEvent(
            WebSocketEventType.ERROR,
            {"message": "Connection error occurred", "error": str(e)},
        )
        await connection_manager.send_to_user(
            str(user.id), error_event, str(conversation_id)
        )
    finally:
        # Cleanup connection
        await connection_manager.disconnect(str(conversation_id), str(user.id))


async def handle_websocket_message(
    websocket: WebSocket,
    data: Dict[str, Any],
    conversation_id: int,
    user: UserInDB,
    pool: Pool,
) -> None:
    """
    Handle incoming WebSocket message.

    Args:
        websocket: WebSocket connection
        data: Message data
        conversation_id: Conversation ID
        user: Authenticated user
        pool: Database connection pool
    """
    try:
        message_type = data.get("type")
        message_data = data.get("data", {})

        if message_type == "ping":
            # Respond to ping with pong
            pong_event = WebSocketEvent(
                WebSocketEventType.PONG, {"timestamp": datetime.utcnow().isoformat()}
            )
            await connection_manager.send_to_user(
                str(user.id), pong_event, str(conversation_id)
            )

        elif message_type == "typing":
            # Handle typing indicator
            is_typing = message_data.get("is_typing", False)
            await connection_manager.set_typing(
                str(conversation_id), str(user.id), is_typing
            )

        elif message_type == "message":
            # Handle new message
            await handle_new_message(message_data, conversation_id, user, pool)

        elif message_type == "message_update":
            # Handle message update
            await handle_message_update(message_data, conversation_id, user, pool)

        elif message_type == "message_delete":
            # Handle message deletion
            await handle_message_delete(message_data, conversation_id, user, pool)

        else:
            # Unknown message type
            error_event = WebSocketEvent(
                WebSocketEventType.ERROR,
                {"message": f"Unknown message type: {message_type}"},
            )
            await connection_manager.send_to_user(
                str(user.id), error_event, str(conversation_id)
            )

    except Exception as e:
        logger.error(f"Error handling WebSocket message: {e}")
        error_event = WebSocketEvent(
            WebSocketEventType.ERROR,
            {"message": "Failed to process message", "error": str(e)},
        )
        await connection_manager.send_to_user(
            str(user.id), error_event, str(conversation_id)
        )


async def handle_new_message(
    message_data: Dict[str, Any], conversation_id: int, user: UserInDB, pool: Pool
) -> None:
    """
    Handle new message creation.

    Args:
        message_data: Message data
        conversation_id: Conversation ID
        user: Authenticated user
        pool: Database connection pool
    """
    try:
        from app.services.message import MessageService
        from app.schemas.message import MessageCreate

        content = message_data.get("content", "").strip()
        if not content:
            raise ValueError("Message content cannot be empty")

        # Create message using service
        message_service = MessageService(pool)
        message_create = MessageCreate(
            conversation_id=conversation_id,
            user_id=user.id,
            content=content,
            content_type="text",
            metadata={"source": "websocket"},
        )

        message_response = await message_service.create_message(
            user.id, conversation_id, message_create
        )

        # Broadcast message to conversation
        message_event = WebSocketEvent(
            WebSocketEventType.MESSAGE_CREATED, message_response.model_dump()
        )
        await connection_manager.broadcast_to_conversation(
            str(conversation_id), message_event
        )

        logger.info(
            f"New message created by user {user.id} in conversation {conversation_id}"
        )

    except ValueError as e:
        # Validation error
        error_event = WebSocketEvent(
            WebSocketEventType.ERROR, {"message": str(e), "field": "content"}
        )
        await connection_manager.send_to_user(
            str(user.id), error_event, str(conversation_id)
        )
    except Exception as e:
        logger.error(f"Error creating new message: {e}")
        error_event = WebSocketEvent(
            WebSocketEventType.ERROR, {"message": "Failed to create message"}
        )
        await connection_manager.send_to_user(
            str(user.id), error_event, str(conversation_id)
        )


async def handle_message_update(
    message_data: Dict[str, Any], conversation_id: int, user: UserInDB, pool: Pool
) -> None:
    """
    Handle message update.

    Args:
        message_data: Message data
        conversation_id: Conversation ID
        user: Authenticated user
        pool: Database connection pool
    """
    try:
        from app.services.message import MessageService
        from app.schemas.message import MessageEditRequest

        message_id = message_data.get("message_id")
        content = message_data.get("content", "").strip()

        if not message_id or not content:
            raise ValueError("Message ID and content are required")

        # Update message using service
        message_service = MessageService(pool)
        edit_request = MessageEditRequest(
            content=content, metadata=message_data.get("metadata", {})
        )

        message_response = await message_service.update_message(
            message_id, conversation_id, user.id, edit_request
        )

        if message_response:
            # Broadcast message update to conversation
            update_event = WebSocketEvent(
                WebSocketEventType.MESSAGE_UPDATED, message_response.model_dump()
            )
            await connection_manager.broadcast_to_conversation(
                str(conversation_id), update_event
            )

            logger.info(
                f"Message {message_id} updated by user {user.id} in conversation {conversation_id}"
            )
        else:
            raise ValueError("Message not found or update failed")

    except ValueError as e:
        # Validation error
        error_event = WebSocketEvent(
            WebSocketEventType.ERROR,
            {
                "message": str(e),
                "field": "content" if "content" in str(e).lower() else "message_id",
            },
        )
        await connection_manager.send_to_user(
            str(user.id), error_event, str(conversation_id)
        )
    except Exception as e:
        logger.error(f"Error updating message: {e}")
        error_event = WebSocketEvent(
            WebSocketEventType.ERROR, {"message": "Failed to update message"}
        )
        await connection_manager.send_to_user(
            str(user.id), error_event, str(conversation_id)
        )


async def handle_message_delete(
    message_data: Dict[str, Any], conversation_id: int, user: UserInDB, pool: Pool
) -> None:
    """
    Handle message deletion.

    Args:
        message_data: Message data
        conversation_id: Conversation ID
        user: Authenticated user
        pool: Database connection pool
    """
    try:
        from app.services.message import MessageService

        message_id = message_data.get("message_id")
        if not message_id:
            raise ValueError("Message ID is required")

        # Delete message using service
        message_service = MessageService(pool)
        success = await message_service.delete_message(
            message_id, conversation_id, user.id
        )

        if success:
            # Broadcast message deletion to conversation
            delete_event = WebSocketEvent(
                WebSocketEventType.MESSAGE_DELETED, {"message_id": message_id}
            )
            await connection_manager.broadcast_to_conversation(
                str(conversation_id), delete_event
            )

            logger.info(
                f"Message {message_id} deleted by user {user.id} in conversation {conversation_id}"
            )
        else:
            raise ValueError("Message not found or deletion failed")

    except ValueError as e:
        # Validation error
        error_event = WebSocketEvent(
            WebSocketEventType.ERROR, {"message": str(e), "field": "message_id"}
        )
        await connection_manager.send_to_user(
            str(user.id), error_event, str(conversation_id)
        )
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        error_event = WebSocketEvent(
            WebSocketEventType.ERROR, {"message": "Failed to delete message"}
        )
        await connection_manager.send_to_user(
            str(user.id), error_event, str(conversation_id)
        )


# Create WebSocket router
router = APIRouter()

# Add WebSocket endpoint
router.websocket("/ws/chat/{conversation_id}")(websocket_endpoint)
