"""
Shared utilities and schemas for VHealth microservices.

This package contains code shared across all microservices:
- Common Pydantic schemas (BaseResponse, ErrorResponse)
- Exception hierarchy (VHealthException and subclasses)
- Authentication utilities (JWT, password hashing)
- Service-to-service HTTP client with IAM auth
- Common validators and type definitions

Usage:
    from app.core.shared.exceptions import VHealthException, ResourceNotFoundException
    from app.core.shared.auth import hash_password, create_access_token
    from app.core.shared.schemas import BaseResponse
    from app.core.shared.http_client import ServiceClient
"""
