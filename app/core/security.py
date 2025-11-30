"""
DEPRECATED: Use app.core.shared.auth instead.

This module provides backward compatibility for authentication utilities.
All security functions have been moved to app.core.shared.auth to support
microservices separation.

Please update your imports:
    OLD: from app.core.security import hash_password, create_access_token
    NEW: from app.core.shared.auth import hash_password, create_access_token

This compatibility shim will be removed in Phase 3.
"""

import warnings
from app.core.shared.auth import *  # noqa: F401,F403

# Issue deprecation warning for any import from this module
warnings.warn(
    "app.core.security is deprecated. Use app.core.shared.auth instead. "
    "This compatibility shim will be removed in Phase 3.",
    DeprecationWarning,
    stacklevel=2
)
