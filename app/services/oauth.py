"""
OAuth service for handling Google OAuth authentication.
"""

import secrets
from typing import Optional, Dict, Any
from google.auth.transport import requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from app.config import settings
from app.schemas.user import GoogleOAuthCallback


class GoogleOAuthService:
    """Service for Google OAuth authentication."""

    def __init__(self):
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.redirect_uri = settings.google_redirect_uri

    def is_configured(self) -> bool:
        """Check if Google OAuth is properly configured."""
        return all(
            [
                self.client_id,
                self.client_secret,
                self.redirect_uri,
            ]
        )

    def get_authorization_url(self, state: Optional[str] = None) -> tuple[str, str]:
        """Generate Google OAuth authorization URL."""
        if not self.is_configured():
            raise ValueError("Google OAuth is not configured")

        # Generate state if not provided
        if not state:
            state = secrets.token_urlsafe(32)

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            },
            scopes=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
            ],
            redirect_uri=self.redirect_uri,
        )

        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            state=state,
        )

        return authorization_url, state

    async def verify_oauth_token(
        self, authorization_code: str, state: Optional[str] = None
    ) -> Optional[GoogleOAuthCallback]:
        """Verify OAuth authorization code and get user info."""
        if not self.is_configured():
            raise ValueError("Google OAuth is not configured")

        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.redirect_uri],
                    }
                },
                scopes=[
                    "openid",
                    "https://www.googleapis.com/auth/userinfo.email",
                    "https://www.googleapis.com/auth/userinfo.profile",
                ],
                redirect_uri=self.redirect_uri,
            )

            # Exchange authorization code for tokens
            flow.fetch_token(code=authorization_code)

            # Get user info from ID token
            credentials = flow.credentials
            id_info = id_token.verify_oauth2_token(
                credentials.id_token,
                requests.Request(),
                self.client_id,
            )

            # Validate the issuer
            if id_info["iss"] not in [
                "accounts.google.com",
                "https://accounts.google.com",
            ]:
                raise ValueError("Invalid issuer")

            # Create user data from Google response
            return GoogleOAuthCallback(
                id=id_info["sub"],
                email=id_info["email"],
                given_name=id_info.get("given_name", ""),
                family_name=id_info.get("family_name", ""),
                picture=id_info.get("picture"),
                email_verified=id_info.get("email_verified", True),
            )

        except Exception as e:
            print(f"OAuth verification failed: {e}")
            return None

    async def verify_id_token_only(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify Google ID token directly."""
        if not self.is_configured():
            raise ValueError("Google OAuth is not configured")

        try:
            id_info = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                self.client_id,
            )

            if id_info["iss"] not in [
                "accounts.google.com",
                "https://accounts.google.com",
            ]:
                raise ValueError("Invalid issuer")

            return id_info

        except Exception as e:
            print(f"ID token verification failed: {e}")
            return None


# Global OAuth service instance
google_oauth_service = GoogleOAuthService()
