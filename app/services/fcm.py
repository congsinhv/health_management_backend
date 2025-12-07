"""
Firebase Cloud Messaging service.
"""

import logging
from typing import List, Dict, Any, Optional

import firebase_admin
from firebase_admin import credentials, messaging

from app.config import settings

logger = logging.getLogger(__name__)


class FCMService:
    """Firebase Cloud Messaging service for push notifications."""

    _initialized = False

    def __init__(self, credentials_dict: Optional[Dict] = None):
        if not FCMService._initialized and credentials_dict:
            try:
                cred = credentials.Certificate(credentials_dict)
                firebase_admin.initialize_app(cred)
                FCMService._initialized = True
                logger.info("Firebase Admin SDK initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Firebase: {e}")

    async def send_notification(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send notification to multiple devices."""
        if not tokens:
            return {"success_count": 0, "failure_count": 0, "invalid_tokens": []}

        # FCM data must be string values
        fcm_data = {k: str(v) for k, v in (data or {}).items()}

        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=fcm_data,
            tokens=tokens,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    icon="ic_workout",
                    color="#4CAF50",
                    sound="default",
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        badge=1,
                        content_available=True,
                    ),
                ),
            ),
        )

        try:
            response = messaging.send_each_for_multicast(message)

            # Collect invalid tokens
            invalid_tokens = []
            for idx, send_response in enumerate(response.responses):
                if not send_response.success:
                    error = send_response.exception
                    if error and hasattr(error, "code"):
                        if error.code in ("UNREGISTERED", "INVALID_ARGUMENT"):
                            invalid_tokens.append(tokens[idx])

            logger.info(
                f"FCM sent: {response.success_count} success, "
                f"{response.failure_count} failures, {len(invalid_tokens)} invalid"
            )

            return {
                "success_count": response.success_count,
                "failure_count": response.failure_count,
                "invalid_tokens": invalid_tokens,
            }

        except Exception as e:
            logger.error(f"FCM send failed: {e}")
            return {
                "success_count": 0,
                "failure_count": len(tokens),
                "error": str(e),
                "invalid_tokens": [],
            }

    async def send_single(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send notification to single device."""
        result = await self.send_notification([token], title, body, data)
        return result.get("success_count", 0) > 0
