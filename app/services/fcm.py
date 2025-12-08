"""
Firebase Cloud Messaging service.

Supports:
- Android (native + PWA) via FCM
- iOS native apps via APNs
- iOS PWA (Safari 16.4+) via Web Push
- Desktop browsers via Web Push
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
        """Send notification to multiple devices.
        
        Sends to Android, iOS native, and Web/PWA (including iOS Safari).
        Web Push config is required for iOS PWA notifications to work.
        """
        if not tokens:
            return {"success_count": 0, "failure_count": 0, "invalid_tokens": []}

        # FCM data must be string values
        fcm_data = {k: str(v) for k, v in (data or {}).items()}

        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=fcm_data,
            tokens=tokens,
            # Android configuration
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    icon="ic_workout",
                    color="#4CAF50",
                    sound="default",
                ),
            ),
            # iOS native app configuration (APNs)
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        badge=1,
                        content_available=True,
                    ),
                ),
            ),
            # Web Push configuration (required for iOS PWA / Safari 16.4+)
            webpush=messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    title=title,
                    body=body,
                    icon="/icons/icon-192x192.png",  # PWA icon
                    badge="/icons/badge-72x72.png",   # iOS badge icon
                    tag="workout-reminder",           # Collapse duplicate notifications
                    renotify=True,                    # Re-alert even if tag matches
                    require_interaction=True,         # Don't auto-dismiss on iOS
                ),
                fcm_options=messaging.WebpushFCMOptions(
                    link="/schedules",  # URL to open when notification is clicked
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
