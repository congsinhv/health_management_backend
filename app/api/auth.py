"""
Enhanced Authentication API endpoints.
"""

from typing_extensions import Annotated
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import RedirectResponse
from app.services.user import UserService
from app.services.auth_log import AuthLogService
from app.services.oauth import google_oauth_service
from app.db.database import get_database_pool
from app.auth.dependencies import get_current_active_user
from app.helpers import verify_refresh_token
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


async def get_user_service(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> UserService:
    """Dependency to get user service."""
    return UserService(db_pool)


async def get_auth_log_service(
    db_pool: asyncpg.Pool = Depends(get_database_pool),
) -> AuthLogService:
    """Dependency to get auth log service."""
    return AuthLogService(db_pool)


@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    verification_data: EmailVerification,
    request: Request,
    user_service: UserService = Depends(get_user_service),
    auth_log_service: AuthLogService = Depends(get_auth_log_service),
):
    """Verify user email with verification token."""
    try:
        success = await user_service.verify_email(verification_data)
        if not success:
            await auth_log_service.log_email_verification_failed(
                request, reason="Invalid or expired token"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email verification failed",
            )

        # Get user_id from token to log success
        from app.helpers import verify_verification_token

        email = verify_verification_token(verification_data.token, "email_verification")
        if email:
            user = await user_service.get_user_by_email(email)
            if user:
                await auth_log_service.log_email_verified(request, user.id)

        return {"message": "Email verified successfully"}
    except ValueError as e:
        await auth_log_service.log_email_verification_failed(request, reason=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        await auth_log_service.log_email_verification_failed(request, reason=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email verification failed",
        )


@router.get("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email_from_link(
    request: Request,
    token: str = Query(..., description="Email verification token"),
    user_service: UserService = Depends(get_user_service),
    auth_log_service: AuthLogService = Depends(get_auth_log_service),
):
    """Verify user email from email link (GET endpoint for email links)."""
    try:
        verification_data = EmailVerification(token=token)
        success = await user_service.verify_email(verification_data)
        if not success:
            await auth_log_service.log_email_verification_failed(
                request, reason="Invalid or expired token"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email verification failed",
            )

        # Get user_id from token to log success
        from app.helpers import verify_verification_token

        email = verify_verification_token(token, "email_verification")
        if email:
            user = await user_service.get_user_by_email(email)
            if user:
                await auth_log_service.log_email_verified(request, user.id)

        return {"message": "Email verified successfully"}
    except ValueError as e:
        await auth_log_service.log_email_verification_failed(request, reason=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        await auth_log_service.log_email_verification_failed(request, reason=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email verification failed",
        )


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_email_verification(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    user_service: UserService = Depends(get_user_service),
    auth_log_service: AuthLogService = Depends(get_auth_log_service),
):
    """Resend email verification for current user."""
    try:
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email",
        )


@router.post("/request-password-reset", status_code=status.HTTP_200_OK)
async def request_password_reset(
    reset_request: PasswordResetRequest,
    request: Request,
    user_service: UserService = Depends(get_user_service),
    auth_log_service: AuthLogService = Depends(get_auth_log_service),
):
    """Request password reset email."""
    try:
        await user_service.request_password_reset(reset_request)
        await auth_log_service.log_password_reset_requested(
            request, reset_request.email
        )
        # Always return success to avoid email enumeration
        return {"message": "If the email exists, a password reset link has been sent"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset request failed",
        )


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    reset_data: PasswordReset,
    request: Request,
    user_service: UserService = Depends(get_user_service),
    auth_log_service: AuthLogService = Depends(get_auth_log_service),
):
    """Reset password with token."""
    try:
        success = await user_service.reset_password(reset_data)
        if not success:
            await auth_log_service.log_password_reset_failed(
                request, reason="Invalid or expired token"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password reset failed",
            )

        # Get user_id from token to log success
        from app.helpers import verify_verification_token

        email = verify_verification_token(reset_data.token, "password_reset")
        if email:
            user = await user_service.get_user_by_email(email)
            if user:
                await auth_log_service.log_password_reset_success(request, user.id)

        return {"message": "Password reset successfully"}
    except ValueError as e:
        await auth_log_service.log_password_reset_failed(request, reason=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        await auth_log_service.log_password_reset_failed(request, reason=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed",
        )


@router.post("/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    old_password: str,
    new_password: str,
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    user_service: UserService = Depends(get_user_service),
    auth_log_service: AuthLogService = Depends(get_auth_log_service),
):
    """Change password for authenticated user."""
    try:
        success = await user_service.change_password(
            current_user.id, old_password, new_password
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password change failed",
            )
        await auth_log_service.log_password_changed(request, current_user.id)
        return {"message": "Password changed successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed",
        )


# Google OAuth Endpoints


@router.get("/google/login")
async def google_login(
    redirect_url: str = Query(
        default="http://localhost:8000/auth/callback",
        description="Frontend callback URL",
    ),
):
    """Initiate Google OAuth login."""
    try:
        if not google_oauth_service.is_configured():
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Google OAuth is not configured",
            )

        authorization_url, state = google_oauth_service.get_authorization_url()

        # In a real application, you might want to store the state and redirect_url
        # in Redis or database for security validation

        return {
            "authorization_url": authorization_url,
            "state": state,
            "redirect_url": redirect_url,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate Google OAuth",
        )


@router.post("/google/callback", response_model=TokenPair)
async def google_callback(
    oauth_request: GoogleOAuthRequest,
    request: Request,
    user_service: UserService = Depends(get_user_service),
    auth_log_service: AuthLogService = Depends(get_auth_log_service),
):
    """Handle Google OAuth callback and authenticate user."""
    try:
        if not google_oauth_service.is_configured():
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Google OAuth is not configured",
            )

        # Verify OAuth code and get user info
        oauth_data = await google_oauth_service.verify_oauth_token(
            oauth_request.code, oauth_request.state
        )

        if not oauth_data:
            await auth_log_service.log_oauth_login_failed(
                request, provider="google", reason="Invalid OAuth authorization code"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid OAuth authorization code",
            )

        # Authenticate user and get tokens
        tokens = await user_service.login_with_oauth(oauth_data)

        # Extract user_id from token to log success
        payload = verify_refresh_token(tokens.refresh_token)
        if payload and payload.get("user_id"):
            await auth_log_service.log_oauth_login_success(
                request, payload["user_id"], provider="google"
            )

        return tokens

    except ValueError as e:
        await auth_log_service.log_oauth_login_failed(
            request, provider="google", reason=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        await auth_log_service.log_oauth_login_failed(
            request, provider="google", reason=str(e)
        )
        print(f"OAuth authentication failed {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OAuth authentication failed {e}",
        )


@router.get("/google/callback")
async def google_callback_redirect(
    request: Request,
    code: str = Query(..., description="OAuth authorization code"),
    state: str = Query(None, description="OAuth state parameter"),
    error: str = Query(None, description="OAuth error"),
    auth_log_service: AuthLogService = Depends(get_auth_log_service),
):
    """Handle Google OAuth callback redirect (for direct browser redirects)."""
    if error:
        await auth_log_service.log_oauth_login_failed(
            request, provider="google", reason=f"OAuth error: {error}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth error: {error}",
        )

    # This endpoint can redirect to frontend with the code
    # Frontend then calls the POST callback endpoint
    frontend_url = "http://localhost:3000/auth/callback"  # This should be configurable
    return RedirectResponse(
        url=f"{frontend_url}?code={code}&state={state}",
        status_code=status.HTTP_302_FOUND,
    )


# Enhanced login with refresh token
@router.post("/login-with-refresh", response_model=TokenPair)
async def login_with_refresh_token(
    login_data: UserLogin,
    request: Request,
    user_service: UserService = Depends(get_user_service),
    auth_log_service: AuthLogService = Depends(get_auth_log_service),
):
    """Login user and return access and refresh tokens."""
    try:
        tokens = await user_service.login_with_refresh_token(login_data)

        # Extract user_id from token to log success
        payload = verify_refresh_token(tokens.refresh_token)
        if payload and payload.get("user_id"):
            await auth_log_service.log_login_success(
                request, payload["user_id"], provider="portal"
            )

        return tokens
    except ValueError as e:
        await auth_log_service.log_login_failed(
            request, email=login_data.email, reason=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        await auth_log_service.log_login_failed(
            request, email=login_data.email, reason=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to login"
        )


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(
    refresh_token_data: RefreshToken,
    request: Request,
    user_service: UserService = Depends(get_user_service),
    auth_log_service: AuthLogService = Depends(get_auth_log_service),
):
    """Refresh access token using a refresh token."""
    try:
        tokens = await user_service.refresh_access_token(
            refresh_token_data.refresh_token
        )

        # Extract user_id from token to log success
        payload = verify_refresh_token(tokens.refresh_token)
        if payload and payload.get("user_id"):
            await auth_log_service.log_token_refresh_success(
                request, payload["user_id"]
            )

        return tokens
    except ValueError as e:
        await auth_log_service.log_token_refresh_failed(request, reason=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        await auth_log_service.log_token_refresh_failed(request, reason=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh token",
        )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    refresh_token_data: RefreshToken,
    request: Request,
    user_service: UserService = Depends(get_user_service),
    auth_log_service: AuthLogService = Depends(get_auth_log_service),
):
    """Logout user by revoking a refresh token."""
    try:
        # Extract user_id from token before revoking
        payload = verify_refresh_token(refresh_token_data.refresh_token)
        user_id = payload.get("user_id") if payload else None

        success = await user_service.revoke_refresh_token(
            refresh_token_data.refresh_token
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to revoke token",
            )

        if user_id:
            await auth_log_service.log_logout(request, user_id)

        return {"message": "Logged out successfully"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to logout",
        )


@router.post("/logout-all", status_code=status.HTTP_200_OK)
async def logout_all(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    request: Request,
    user_service: UserService = Depends(get_user_service),
    auth_log_service: AuthLogService = Depends(get_auth_log_service),
):
    """Logout user from all devices by revoking all refresh tokens."""
    try:
        success = await user_service.logout_user(current_user.id)
        await auth_log_service.log_logout_all(request, current_user.id)
        return {"message": "Logged out from all devices successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to logout",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
):
    """Get current authenticated user information."""
    # Return safe user data without sensitive fields
    return UserResponse.model_validate(current_user)
