"""
DEPRECATED: This module is deprecated. Use the following instead:
- app.core.security for password and JWT functions
- app.auth.utils for authentication helpers
- app.core.utils for general utilities

This module provides backward compatibility through redirect imports
with deprecation warnings. Please update your imports to use the new modules.

Migration guide:
- from app.helpers import hash_password → from app.core.security import hash_password
- from app.helpers import verify_password → from app.core.security import verify_password
- from app.helpers import create_access_token → from app.core.security import create_access_token
- from app.helpers import verify_access_token → from app.core.security import verify_access_token
- from app.helpers import create_refresh_token → from app.core.security import create_refresh_token
- from app.helpers import verify_refresh_token → from app.core.security import verify_refresh_token
- from app.helpers import hash_refresh_token → from app.core.security import hash_refresh_token
- from app.helpers import create_verification_token → from app.core.security import create_verification_token
- from app.helpers import verify_verification_token → from app.core.security import verify_verification_token
"""

import warnings


def hash_password(*args, **kwargs):
    warnings.warn(
        "helpers.hash_password is deprecated. Use app.core.shared.auth.hash_password",
        DeprecationWarning,
        stacklevel=2,
    )
    from app.core.shared.auth import hash_password as _hash_password

    return _hash_password(*args, **kwargs)


def verify_password(*args, **kwargs):
    warnings.warn(
        "helpers.verify_password is deprecated. Use app.core.shared.auth.verify_password",
        DeprecationWarning,
        stacklevel=2,
    )
    from app.core.shared.auth import verify_password as _verify_password

    return _verify_password(*args, **kwargs)


def create_access_token(*args, **kwargs):
    warnings.warn(
        "helpers.create_access_token is deprecated. Use app.core.shared.auth.create_access_token",
        DeprecationWarning,
        stacklevel=2,
    )
    from app.core.shared.auth import create_access_token as _create_access_token

    return _create_access_token(*args, **kwargs)


def verify_access_token(*args, **kwargs):
    warnings.warn(
        "helpers.verify_access_token is deprecated. Use app.core.shared.auth.verify_access_token",
        DeprecationWarning,
        stacklevel=2,
    )
    from app.core.shared.auth import verify_access_token as _verify_access_token

    return _verify_access_token(*args, **kwargs)


def create_refresh_token(*args, **kwargs):
    warnings.warn(
        "helpers.create_refresh_token is deprecated. Use app.core.shared.auth.create_refresh_token",
        DeprecationWarning,
        stacklevel=2,
    )
    from app.core.shared.auth import create_refresh_token as _create_refresh_token

    return _create_refresh_token(*args, **kwargs)


def verify_refresh_token(*args, **kwargs):
    warnings.warn(
        "helpers.verify_refresh_token is deprecated. Use app.core.shared.auth.verify_refresh_token",
        DeprecationWarning,
        stacklevel=2,
    )
    from app.core.shared.auth import verify_refresh_token as _verify_refresh_token

    return _verify_refresh_token(*args, **kwargs)


def hash_refresh_token(*args, **kwargs):
    warnings.warn(
        "helpers.hash_refresh_token is deprecated. Use app.core.shared.auth.hash_refresh_token",
        DeprecationWarning,
        stacklevel=2,
    )
    from app.core.shared.auth import hash_refresh_token as _hash_refresh_token

    return _hash_refresh_token(*args, **kwargs)


def create_verification_token(*args, **kwargs):
    warnings.warn(
        "helpers.create_verification_token is deprecated. Use app.core.shared.auth.create_verification_token",
        DeprecationWarning,
        stacklevel=2,
    )
    from app.core.shared.auth import (
        create_verification_token as _create_verification_token,
    )

    return _create_verification_token(*args, **kwargs)


def verify_verification_token(*args, **kwargs):
    warnings.warn(
        "helpers.verify_verification_token is deprecated. Use app.core.shared.auth.verify_verification_token",
        DeprecationWarning,
        stacklevel=2,
    )
    from app.core.shared.auth import (
        verify_verification_token as _verify_verification_token,
    )

    return _verify_verification_token(*args, **kwargs)
