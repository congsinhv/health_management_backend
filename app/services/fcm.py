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
        web_tokens: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Send notification to multiple devices.

        Args:
            tokens: List of mobile tokens (Android/iOS native)
            title: Notification title
            body: Notification body
            data: Additional data payload
            web_tokens: List of web/PWA tokens (optional, for data-only messages)

        For mobile tokens: Sends notification message (system handles display)
        For web tokens: Sends data-only message (service worker handles display)
        This prevents duplicate notifications on web/PWA.
        """
        total_success = 0
        total_failure = 0
        all_invalid_tokens = []

        # FCM data must be string values
        fcm_data = {k: str(v) for k, v in (data or {}).items()}

        # Send to mobile tokens (with notification field)
        if tokens:
            mobile_result = await self._send_mobile_notification(
                tokens, title, body, fcm_data
            )
            total_success += mobile_result.get("success_count", 0)
            total_failure += mobile_result.get("failure_count", 0)
            all_invalid_tokens.extend(mobile_result.get("invalid_tokens", []))

        # Send to web tokens (data-only for full control)
        if web_tokens:
            web_result = await self._send_web_notification(
                web_tokens, title, body, fcm_data
            )
            total_success += web_result.get("success_count", 0)
            total_failure += web_result.get("failure_count", 0)
            all_invalid_tokens.extend(web_result.get("invalid_tokens", []))

        return {
            "success_count": total_success,
            "failure_count": total_failure,
            "invalid_tokens": all_invalid_tokens,
        }

    async def _send_mobile_notification(
        self,
        tokens: List[str],
        title: str,
        body: str,
        fcm_data: Dict[str, str],
    ) -> Dict[str, Any]:
        """Send notification message to mobile devices (Android/iOS).

        Uses notification field so system handles display automatically.
        """
        if not tokens:
            return {"success_count": 0, "failure_count": 0, "invalid_tokens": []}

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

        return await self._send_multicast(message, tokens)

    async def _send_web_notification(
        self,
        tokens: List[str],
        title: str,
        body: str,
        fcm_data: Dict[str, str],
    ) -> Dict[str, Any]:
        """Send data-only message to web/PWA devices.

        No notification field - service worker handles display.
        This prevents duplicate notifications on web browsers.
        """
        if not tokens:
            return {"success_count": 0, "failure_count": 0, "invalid_tokens": []}

        # Include title and body in data for service worker to display
        web_data = {
            "title": title,
            "body": body,
            **fcm_data,
        }

        message = messaging.MulticastMessage(
            # NO notification field - data only for web
            data=web_data,
            tokens=tokens,
            webpush=messaging.WebpushConfig(
                headers={
                    "Urgency": "high",
                    "TTL": "86400",  # 24 hours
                },
            ),
        )

        return await self._send_multicast(message, tokens)

    async def _send_multicast(
        self,
        message: messaging.MulticastMessage,
        tokens: List[str],
    ) -> Dict[str, Any]:
        """Send multicast message and process response."""
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
        is_web_token: bool = False,
    ) -> bool:
        """Send notification to single device.

        Args:
            token: Device token
            title: Notification title
            body: Notification body
            data: Additional data payload
            is_web_token: If True, sends data-only message for web/PWA
        """
        if is_web_token:
            result = await self.send_notification(
                tokens=[], title=title, body=body, data=data, web_tokens=[token]
            )
        else:
            result = await self.send_notification(
                tokens=[token], title=title, body=body, data=data
            )
        return result.get("success_count", 0) > 0

    async def send_to_all(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send data-only notification to all tokens (unified approach).

        This method treats ALL tokens as web tokens, sending data-only messages.
        Use this when you want consistent behavior across all platforms
        where the client app handles notification display.
        """
        if not tokens:
            return {"success_count": 0, "failure_count": 0, "invalid_tokens": []}

        fcm_data = {k: str(v) for k, v in (data or {}).items()}
        return await self._send_web_notification(tokens, title, body, fcm_data)
