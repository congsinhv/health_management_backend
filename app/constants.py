from enum import Enum


class UserProviders(str, Enum):
    PORTAL = "portal"
    GOOGLE = "google"


class AuthEventType(str, Enum):
    """Authentication event types for logging."""

    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    LOGOUT_ALL = "logout_all"
    EMAIL_VERIFICATION_REQUESTED = "email_verification_requested"
    EMAIL_VERIFIED = "email_verified"
    EMAIL_VERIFICATION_FAILED = "email_verification_failed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_SUCCESS = "password_reset_success"
    PASSWORD_RESET_FAILED = "password_reset_failed"
    PASSWORD_CHANGED = "password_changed"
    OAUTH_LOGIN_SUCCESS = "oauth_login_success"
    OAUTH_LOGIN_FAILED = "oauth_login_failed"
    TOKEN_REFRESH_SUCCESS = "token_refresh_success"
    TOKEN_REFRESH_FAILED = "token_refresh_failed"
    TOKEN_REVOKED = "token_revoked"
    

