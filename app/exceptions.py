"""
DEPRECATED: Use app.core.shared.exceptions instead.

This module provides backward compatibility for the VHealth exception hierarchy.
All exceptions have been moved to app.core.shared.exceptions to support
microservices separation.

Please update your imports:
    OLD: from app.exceptions import ResourceNotFoundException, ValidationException
    NEW: from app.core.shared.exceptions import ResourceNotFoundException, ValidationException

This compatibility shim will be removed in Phase 3.
"""

import warnings
from app.core.shared.exceptions import *  # noqa: F401,F403

# Issue deprecation warning for any import from this module
warnings.warn(
    "app.exceptions is deprecated. Use app.core.shared.exceptions instead. "
    "This compatibility shim will be removed in Phase 3.",
    DeprecationWarning,
    stacklevel=2
)
