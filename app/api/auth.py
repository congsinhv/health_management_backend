"""
Enhanced Authentication API endpoints.
"""

from typing_extensions import Annotated
import asyncpg
from fastapi import APIRouter, Depends, status, Query, Request
from app.services.user import UserService
from app.services.auth_log import AuthLogService
from app.services.oauth import google_oauth_service
from app.db.database import get_database_pool
from app.auth.dependencies import get_current_active_user
from app.core.security import verify_refresh_token
from app.core.error_context import ErrorContext
from app.exceptions import (
    AuthenticationException,
    ValidationException,
    ServiceUnavailableException,
    AccountNotVerifiedException,
    InvalidCredentialsException,
    TokenInvalidException,
)
from app.schemas.user import (
    UserInDB,
    UserResponse,
    TokenPair,
    RefreshToken,
    PasswordResetRequest,
    PasswordReset,
    EmailVerification,
    GoogleOAuthRequest,
    UserLogin,
)

router = APIRouter()


async def create_user_service(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> UserService:
    """Dependency to get user service."""
    return UserService(db_pool)


async def create_auth_log_service(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> AuthLogService:
    """Dependency to get auth log service."""
    return AuthLogService(db_pool)


@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    verification_data: EmailVerification,
    request: Request,
    user_service: UserService = Depends(create_user_service),
    auth_log_service: AuthLogService = Depends(create_auth_log_service),
):
    """Verify user email with verification token."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "verify_email")
    ErrorContext.add_context("operation", "email_verification")

    with ErrorContext(
        "verify_email",
        {
            "token_preview": verification_data.token[:20] + "..."
            if len(verification_data.token) > 20
            else verification_data.token
        },
    ):
        success = await user_service.verify_email(verification_data)
        if not success:
            ErrorContext.add_context("reason", "invalid_or_expired_token")
            await auth_log_service.log_email_verification_failed(
                request, reason="Invalid or expired token"
            )
            raise AuthenticationException("Email verification failed")

        # Get user_id from token to log success
        from app.core.security import verify_verification_token

        email = verify_verification_token(verification_data.token, "email_verification")
        if email:
            user = await user_service.get_user_by_email(email)
            if user:
                ErrorContext.add_context("user_id", user.id)
                await auth_log_service.log_email_verified(request, user.id)

        return {"message": "Email verified successfully"}


@router.get("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email_from_link(
    request: Request,
    token: str = Query(..., description="Email verification token"),
    user_service: UserService = Depends(create_user_service),
    auth_log_service: AuthLogService = Depends(create_auth_log_service),
):
    """Verify user email from email link (GET endpoint for email links)."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "verify_email_from_link")
    ErrorContext.add_context("operation", "email_verification")

    with ErrorContext(
        "verify_email_from_link",
        {"token_preview": token[:20] + "..." if len(token) > 20 else token},
    ):
        verification_data = EmailVerification(token=token)
        success = await user_service.verify_email(verification_data)
        if not success:
            ErrorContext.add_context("reason", "invalid_or_expired_token")
            await auth_log_service.log_email_verification_failed(
                request, reason="Invalid or expired token"
            )
            raise AuthenticationException("Email verification failed")

        # Get user_id from token to log success
        from app.core.security import verify_verification_token

        email = verify_verification_token(token, "email_verification")
        if email:
            user = await user_service.get_user_by_email(email)
            if user:
                ErrorContext.add_context("user_id", user.id)
                await auth_log_service.log_email_verified(request, user.id)

        return {"message": "Email verified successfully"}


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_email_verification(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    user_service: UserService = Depends(create_user_service),
    auth_log_service: AuthLogService = Depends(create_auth_log_service),
):
    """Resend email verification for current user."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "resend_verification")
    ErrorContext.add_context("operation", "resend_email_verification")

    with ErrorContext(
        "resend_verification", {"user_id": current_user.id, "email": current_user.email}
    ):
        if current_user.email_verified:
            return {"message": "Email is already verified"}

        first_name = current_user.profile.first_name if current_user.profile else "User"
        await user_service._send_email_verification(
            current_user.id, current_user.email, first_name
        )
        await auth_log_service.log_email_verification_requested(
            request, current_user.id
        )
        return {"message": "Verification email sent"}


@router.post("/request-password-reset", status_code=status.HTTP_200_OK)
async def request_password_reset(
    reset_request: PasswordResetRequest,
    request: Request,
    user_service: UserService = Depends(create_user_service),
    auth_log_service: AuthLogService = Depends(create_auth_log_service),
):
    """Request password reset email."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "request_password_reset")
    ErrorContext.add_context("operation", "password_reset_request")
    ErrorContext.add_context("email", reset_request.email)

    with ErrorContext("request_password_reset", {"email": reset_request.email}):
        await user_service.request_password_reset(reset_request)
        await auth_log_service.log_password_reset_requested(
            request, reset_request.email
        )
        # Always return success to avoid email enumeration
        return {"message": "If the email exists, a password reset link has been sent"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    reset_data: PasswordReset,
    request: Request,
    user_service: UserService = Depends(create_user_service),
    auth_log_service: AuthLogService = Depends(create_auth_log_service),
):
    """Reset password with token."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "reset_password")
    ErrorContext.add_context("operation", "password_reset")

    with ErrorContext(
        "reset_password",
        {
            "token_preview": reset_data.token[:20] + "..."
            if len(reset_data.token) > 20
            else reset_data.token
        },
    ):
        success = await user_service.reset_password(reset_data)
        if not success:
            ErrorContext.add_context("reason", "invalid_or_expired_token")
            await auth_log_service.log_password_reset_failed(
                request, reason="Invalid or expired token"
            )
            raise AuthenticationException("Password reset failed")

        # Get user_id from token to log success
        from app.core.security import verify_verification_token

        email = verify_verification_token(reset_data.token, "password_reset")
        if email:
            user = await user_service.get_user_by_email(email)
            if user:
                ErrorContext.add_context("user_id", user.id)
                await auth_log_service.log_password_reset_success(request, user.id)

        return {"message": "Password reset successfully"}


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    old_password: str,
    new_password: str,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    user_service: UserService = Depends(create_user_service),
    auth_log_service: AuthLogService = Depends(create_auth_log_service),
):
    """Change password for authenticated user."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "change_password")
    ErrorContext.add_context("operation", "password_change")

    with ErrorContext("change_password", {"user_id": current_user.id}):
        success = await user_service.change_password(
            current_user.id, old_password, new_password
        )
        if not success:
            raise AuthenticationException("Password change failed")

        await auth_log_service.log_password_changed(request, current_user.id)
        return {"message": "Password changed successfully"}


# Google OAuth Endpoints


@router.get("/google/login")
async def google_login(
    redirect_url: str = Query(
        default="http://localhost:8000/auth/callback",
        description="Frontend callback URL",
    ),
):
    """Initiate Google OAuth login."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "google_login")
    ErrorContext.add_context("operation", "oauth_initiation")
    ErrorContext.add_context("provider", "google")

    with ErrorContext("google_login", {"redirect_url": redirect_url}):
        if not google_oauth_service.is_configured():
            raise ServiceUnavailableException("Google OAuth is not configured")

        authorization_url, state = google_oauth_service.get_authorization_url()

        # In a real application, you might want to store the state and redirect_url
        # in Redis or database for security validation

        return {
            "authorization_url": authorization_url,
            "state": state,
            "redirect_url": redirect_url,
        }


@router.post("/google/callback", response_model=TokenPair)
async def google_callback(
    oauth_request: GoogleOAuthRequest,
    request: Request,
    user_service: UserService = Depends(create_user_service),
    auth_log_service: AuthLogService = Depends(create_auth_log_service),
):
    """Handle Google OAuth callback and authenticate user."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "google_callback")
    ErrorContext.add_context("operation", "oauth_callback")
    ErrorContext.add_context("provider", "google")

    with ErrorContext(
        "google_callback",
        {"has_code": bool(oauth_request.code), "has_state": bool(oauth_request.state)},
    ):
        if not google_oauth_service.is_configured():
            raise ServiceUnavailableException("Google OAuth is not configured")

        # Verify OAuth code and get user info
        oauth_data = await google_oauth_service.verify_oauth_token(
            oauth_request.code, oauth_request.state
        )

        if not oauth_data:
            ErrorContext.add_context("reason", "invalid_oauth_code")
            await auth_log_service.log_oauth_login_failed(
                request, provider="google", reason="Invalid OAuth authorization code"
            )
            raise AuthenticationException("Invalid OAuth authorization code")

        # Authenticate user and get tokens
        tokens = await user_service.login_with_oauth(oauth_data)

        # Extract user_id from token to log success
        payload = verify_refresh_token(tokens.refresh_token)
        if payload and payload.get("user_id"):
            ErrorContext.add_context("user_id", payload["user_id"])
            await auth_log_service.log_oauth_login_success(
                request, payload["user_id"], provider="google"
            )

        return tokens


# Enhanced login with refresh token
@router.post("/login-with-refresh", response_model=TokenPair)
async def login_with_refresh_token(
    login_data: UserLogin,
    request: Request,
    user_service: UserService = Depends(create_user_service),
    auth_log_service: AuthLogService = Depends(create_auth_log_service),
):
    """Login user and return access and refresh tokens."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "login_with_refresh")
    ErrorContext.add_context("operation", "user_login")
    ErrorContext.add_context("email", login_data.email)

    with ErrorContext("login_with_refresh", {"email": login_data.email}):
        tokens = await user_service.login_with_refresh_token(login_data)

        # Extract user_id from token to log success
        payload = verify_refresh_token(tokens.refresh_token)
        if payload and payload.get("user_id"):
            ErrorContext.add_context("user_id", payload["user_id"])
            await auth_log_service.log_login_success(
                request, payload["user_id"], provider="portal"
            )

        return tokens


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(
    refresh_token_data: RefreshToken,
    request: Request,
    user_service: UserService = Depends(create_user_service),
    auth_log_service: AuthLogService = Depends(create_auth_log_service),
):
    """Refresh access token using a refresh token."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "refresh_token")
    ErrorContext.add_context("operation", "token_refresh")

    with ErrorContext(
        "refresh_token",
        {
            "token_preview": refresh_token_data.refresh_token[:20] + "..."
            if len(refresh_token_data.refresh_token) > 20
            else refresh_token_data.refresh_token
        },
    ):
        tokens = await user_service.refresh_access_token(
            refresh_token_data.refresh_token
        )

        # Extract user_id from token to log success
        payload = verify_refresh_token(tokens.refresh_token)
        if payload and payload.get("user_id"):
            ErrorContext.add_context("user_id", payload["user_id"])
            await auth_log_service.log_token_refresh_success(
                request, payload["user_id"]
            )

        return tokens


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    refresh_token_data: RefreshToken,
    request: Request,
    user_service: UserService = Depends(create_user_service),
    auth_log_service: AuthLogService = Depends(create_auth_log_service),
):
    """Logout user by revoking a refresh token."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.add_context("endpoint", "logout")
    ErrorContext.add_context("operation", "token_revoke")

    with ErrorContext(
        "logout",
        {
            "token_preview": refresh_token_data.refresh_token[:20] + "..."
            if len(refresh_token_data.refresh_token) > 20
            else refresh_token_data.refresh_token
        },
    ):
        # Extract user_id from token before revoking
        payload = verify_refresh_token(refresh_token_data.refresh_token)
        user_id = payload.get("user_id") if payload else None

        if user_id:
            ErrorContext.set_user_id(user_id)

        success = await user_service.revoke_refresh_token(
            refresh_token_data.refresh_token
        )
        if not success:
            raise TokenInvalidException("Failed to revoke token")

        if user_id:
            await auth_log_service.log_logout(request, user_id)

        return {"message": "Logged out successfully"}


@router.post("/logout-all", status_code=status.HTTP_200_OK)
async def logout_all(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    user_service: UserService = Depends(create_user_service),
    auth_log_service: AuthLogService = Depends(create_auth_log_service),
):
    """Logout user from all devices by revoking all refresh tokens."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "logout_all")
    ErrorContext.add_context("operation", "logout_all_devices")

    with ErrorContext("logout_all", {"user_id": current_user.id}):
        success = await user_service.logout_user(current_user.id)
        await auth_log_service.log_logout_all(request, current_user.id)
        return {"message": "Logged out from all devices successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
):
    """Get current authenticated user information."""
    # Set error context for request correlation
    ErrorContext.set_request_id()
    ErrorContext.set_user_id(current_user.id)
    ErrorContext.add_context("endpoint", "get_current_user")
    ErrorContext.add_context("operation", "user_info_retrieval")

    # Return safe user data without sensitive fields
    return UserResponse.model_validate(current_user)
