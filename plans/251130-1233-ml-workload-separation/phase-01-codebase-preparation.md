# Phase 1: Codebase Preparation

**Phase:** 1 of 5
**Duration:** 2-3 days
**Priority:** High
**Status:** Not Started
**Dependencies:** None

## Context

**Research Reports:**
- [FastAPI ML Patterns](./research/researcher-02-fastapi-ml-patterns.md) - Monorepo strategy, shared code patterns
- [Codebase Summary](../../docs/codebase-summary.md) - Current structure
- [Code Standards](../../docs/code-standards.md) - Import guidelines, core package

**Current State:**
- Monolithic FastAPI app with all services in `app/services/`
- Existing decomposed services: `qa/`, `email/`, `pdf/` (Phase 3 pattern)
- New core package structure (Phase 2): `app/core/security.py`, `app/core/utils.py`, etc.
- Shared utilities scattered across `app/helpers.py` (deprecated), `app/core/`, `app/utils/`

## Overview

Prepare codebase for microservices separation by extracting shared utilities into `app/core/shared/` package, creating service interfaces (contracts), updating imports, and restructuring tests for modular architecture. Foundation for clean service boundaries.

## Key Insights from Research

**Monorepo Approach (Researcher-02):**
- Single repository with separate service directories achieves code reuse + deployment isolation
- Shared code in `app/core/shared/` as import-only module - NO circular dependencies
- Dependency injection via FastAPI native DI system

**Code Sharing Pattern:**
- Core shared: Schemas, exceptions, auth utilities, constants
- Service-specific: Business logic isolated in service directories
- Database access: Connection pool initialization shared, repositories stay with Main API

## Requirements

**Shared Package Structure:**
```
app/core/shared/
├── __init__.py
├── schemas.py          # Common Pydantic models (BaseResponse, ErrorResponse)
├── exceptions.py       # VHealthException hierarchy
├── auth.py            # JWT creation/verification, password hashing
├── validators.py      # Common validation functions
├── http_client.py     # Service-to-service HTTP client
└── types.py           # Type aliases and TypeVars
```

**Service Interfaces:**
```
app/interfaces/
├── __init__.py
├── qa_interface.py         # QA service contract
├── predict_interface.py    # Prediction service contract
└── chat_ai_interface.py    # Future: Chat AI interface
```

**Updated Imports:**
```python
# Before
from app.core.security import hash_password
from app.exceptions import ResourceNotFoundException

# After (services use shared)
from app.core.shared.auth import hash_password
from app.core.shared.exceptions import ResourceNotFoundException
```

## Architecture Changes

**Before:**
```
app/
├── core/                   # Internal utilities
│   ├── security.py
│   ├── utils.py
│   └── *_constants.py
├── services/               # All services
├── exceptions.py           # Custom exceptions
└── schemas/               # Schemas (mixed use)
```

**After:**
```
app/
├── core/
│   ├── shared/            # NEW - Shared across microservices
│   │   ├── schemas.py
│   │   ├── exceptions.py
│   │   ├── auth.py
│   │   ├── validators.py
│   │   ├── http_client.py
│   │   └── types.py
│   ├── security.py        # Main API-specific
│   └── utils.py           # Main API-specific
├── interfaces/            # NEW - Service contracts
│   ├── qa_interface.py
│   └── predict_interface.py
├── services/              # Will be split in Phase 2+3
└── schemas/               # Main API-specific schemas
```

## Related Code Files

**To Refactor:**
- `app/core/security.py` → Extract to `app/core/shared/auth.py`
- `app/exceptions.py` → Move to `app/core/shared/exceptions.py`
- `app/schemas/base.py` → Extract base models to `app/core/shared/schemas.py`
- `app/auth/utils.py` → Merge into `app/core/shared/auth.py`

**To Create:**
- `app/core/shared/__init__.py`
- `app/core/shared/http_client.py` (aiohttp-based, IAM token support)
- `app/interfaces/qa_interface.py`
- `app/interfaces/predict_interface.py`

**To Update Imports:**
- All service files in `app/services/`
- All API routers in `app/api/`
- All repositories in `app/db/`
- Test files in `tests/`

## Implementation Steps

### 1. Create Shared Package Structure (Day 1)

**1.1 Create Directory:**
```bash
mkdir -p app/core/shared
touch app/core/shared/__init__.py
```

**1.2 Extract Shared Exceptions:**
```python
# app/core/shared/exceptions.py
"""Shared exception hierarchy for all microservices."""
from typing import Optional, Dict, Any

class VHealthException(Exception):
    """Base exception for VHealth application."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class ResourceNotFoundException(VHealthException):
    """Resource not found (HTTP 404)."""
    pass

class AuthenticationException(VHealthException):
    """Authentication failed (HTTP 401)."""
    pass

# ... copy all exceptions from app/exceptions.py
```

**1.3 Extract Shared Auth Utilities:**
```python
# app/core/shared/auth.py
"""Shared authentication utilities."""
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, secret: str, expires_delta: timedelta) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret, algorithm="HS256")

def verify_access_token(token: str, secret: str) -> dict:
    """Verify and decode JWT token."""
    return jwt.decode(token, secret, algorithms=["HS256"])
```

**1.4 Extract Shared Schemas:**
```python
# app/core/shared/schemas.py
"""Shared Pydantic models."""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class BaseResponse(BaseModel):
    """Base response model."""
    status: str = "success"
    timestamp: datetime = datetime.utcnow()
    request_id: Optional[str] = None

class ErrorResponse(BaseResponse):
    """Error response model."""
    status: str = "error"
    error: str
    details: Optional[dict] = None
```

**1.5 Create Service-to-Service HTTP Client:**
```python
# app/core/shared/http_client.py
"""Service-to-service HTTP client with IAM auth."""
import aiohttp
from typing import Optional, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2 import id_token

class ServiceClient:
    """HTTP client for service-to-service communication."""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def _get_iam_token(self) -> str:
        """Get IAM identity token for service-to-service auth."""
        # For Cloud Run: Use Compute Metadata Server
        request = Request()
        token = id_token.fetch_id_token(request, self.base_url)
        return token

    async def post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """POST request with IAM auth."""
        session = await self._get_session()
        token = await self._get_iam_token()

        req_headers = headers or {}
        req_headers["Authorization"] = f"Bearer {token}"
        req_headers["Content-Type"] = "application/json"

        url = f"{self.base_url}{path}"
        async with session.post(url, json=json, headers=req_headers) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """GET request with IAM auth."""
        session = await self._get_session()
        token = await self._get_iam_token()

        req_headers = headers or {}
        req_headers["Authorization"] = f"Bearer {token}"

        url = f"{self.base_url}{path}"
        async with session.get(url, params=params, headers=req_headers) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
```

### 2. Create Service Interfaces (Day 1-2)

**2.1 QA Service Interface:**
```python
# app/interfaces/qa_interface.py
"""Q&A service interface contract."""
from abc import ABC, abstractmethod
from typing import AsyncIterator
from app.core.shared.schemas import BaseResponse

class QARequest(BaseModel):
    """Q&A request."""
    question: str

class QAResponse(BaseResponse):
    """Q&A response."""
    answers: list
    summary: Optional[str] = None

class IQAService(ABC):
    """Q&A service interface."""

    @abstractmethod
    async def ask_question(self, question: str) -> QAResponse:
        """Ask question and get answers."""
        pass

    @abstractmethod
    async def ask_question_stream(self, question: str) -> AsyncIterator[str]:
        """Ask question with streaming response."""
        pass

    @abstractmethod
    async def health_check(self) -> dict:
        """Check service health."""
        pass
```

**2.2 Prediction Service Interface:**
```python
# app/interfaces/predict_interface.py
"""Prediction service interface contract."""
from abc import ABC, abstractmethod
from app.core.shared.schemas import BaseResponse

class PredictionRequest(BaseModel):
    """Prediction request."""
    # User health data fields
    pass

class PredictionResponse(BaseResponse):
    """Prediction response."""
    obesity_level: str
    bmi: float
    # Additional fields
    pass

class IPredictionService(ABC):
    """Prediction service interface."""

    @abstractmethod
    async def predict(self, data: PredictionRequest) -> PredictionResponse:
        """Generate health prediction."""
        pass

    @abstractmethod
    async def health_check(self) -> dict:
        """Check service health."""
        pass
```

### 3. Update Imports Across Codebase (Day 2)

**3.1 Update Service Imports:**
```bash
# Find all files importing from old locations
grep -r "from app.core.security import" app/services/
grep -r "from app.exceptions import" app/services/

# Update to new shared package
# app/services/user.py
- from app.core.security import hash_password, create_access_token
- from app.exceptions import AuthenticationException
+ from app.core.shared.auth import hash_password, create_access_token
+ from app.core.shared.exceptions import AuthenticationException
```

**3.2 Update API Router Imports:**
```bash
# app/api/auth.py, app/api/user.py, etc.
- from app.exceptions import ValidationException
+ from app.core.shared.exceptions import ValidationException
```

**3.3 Create Import Compatibility Shim:**
```python
# app/exceptions.py (temporary backward compatibility)
"""DEPRECATED: Use app.core.shared.exceptions instead."""
import warnings
from app.core.shared.exceptions import *  # noqa

warnings.warn(
    "app.exceptions is deprecated. Use app.core.shared.exceptions",
    DeprecationWarning,
    stacklevel=2
)
```

### 4. Restructure Tests (Day 2-3)

**4.1 Update Test Fixtures:**
```python
# tests/conftest.py
import pytest
from app.core.shared.http_client import ServiceClient

@pytest.fixture
def mock_service_client(mocker):
    """Mock service client for testing."""
    client = mocker.Mock(spec=ServiceClient)
    client.post.return_value = {"status": "success"}
    client.get.return_value = {"status": "success"}
    return client
```

**4.2 Create Shared Test Utilities:**
```python
# tests/shared_utils.py
"""Shared test utilities."""
from app.core.shared.schemas import BaseResponse

def assert_success_response(response: BaseResponse):
    """Assert response is successful."""
    assert response.status == "success"
    assert response.timestamp is not None
```

**4.3 Update Service Tests:**
```bash
# Update imports in all test files
- from app.exceptions import ResourceNotFoundException
+ from app.core.shared.exceptions import ResourceNotFoundException
```

### 5. Validation and Documentation (Day 3)

**5.1 Run Tests:**
```bash
pytest tests/ --cov=app.core.shared --cov-report=term
pytest tests/unit/ -v
pytest tests/integration/ -v
```

**5.2 Type Checking:**
```bash
mypy app/core/shared/
mypy app/interfaces/
```

**5.3 Update Documentation:**
```markdown
# Add to docs/code-standards.md

## Microservices Import Guidelines

**Shared Package (app/core/shared/):**
Use for code shared across all microservices:
- Exceptions: `from app.core.shared.exceptions import VHealthException`
- Auth: `from app.core.shared.auth import hash_password`
- Schemas: `from app.core.shared.schemas import BaseResponse`
- HTTP Client: `from app.core.shared.http_client import ServiceClient`

**Service-Specific:**
Keep service-specific logic in service directories:
- Main API: `app/core/`, `app/services/user.py`, etc.
- Chat AI: `chat_ai_service/` (Phase 2)
- Prediction: `prediction_service/` (Phase 3)
```

## Todo List

- [ ] Create `app/core/shared/` directory structure
- [ ] Extract shared exceptions to `app/core/shared/exceptions.py`
- [ ] Extract shared auth utilities to `app/core/shared/auth.py`
- [ ] Extract shared schemas to `app/core/shared/schemas.py`
- [ ] Create service-to-service HTTP client in `app/core/shared/http_client.py`
- [ ] Create `app/interfaces/` directory
- [ ] Define QA service interface in `app/interfaces/qa_interface.py`
- [ ] Define Prediction service interface in `app/interfaces/predict_interface.py`
- [ ] Update imports in `app/services/` (all files)
- [ ] Update imports in `app/api/` (all routers)
- [ ] Update imports in `app/db/` (all repositories)
- [ ] Update imports in `tests/` (all test files)
- [ ] Create backward compatibility shims for old imports
- [ ] Update test fixtures in `tests/conftest.py`
- [ ] Create shared test utilities in `tests/shared_utils.py`
- [ ] Run full test suite and verify 80%+ coverage
- [ ] Run mypy type checking on new modules
- [ ] Update `docs/code-standards.md` with microservices import guidelines
- [ ] Document shared package structure in `README.md`

## Success Criteria

**Code Quality:**
- All tests passing (80%+ coverage maintained)
- No type errors (mypy clean)
- No circular dependencies
- Backward compatibility maintained

**Architecture:**
- Shared package has zero service-specific logic
- Clear service boundaries defined via interfaces
- Service-to-service HTTP client tested and documented

**Documentation:**
- Import guidelines updated
- Shared package structure documented
- Migration guide for future services

## Risk Assessment

**Import Circular Dependencies:**
- Mitigation: Shared package imports NOTHING from services
- Validation: Static analysis with `import-linter`

**Breaking Existing Functionality:**
- Mitigation: Backward compatibility shims
- Validation: Full test suite before/after

**Developer Confusion:**
- Mitigation: Clear documentation + examples
- Validation: Code review checklist

## Security Considerations

**IAM Token Management:**
- HTTP client caches tokens (5min TTL)
- Token refresh handled by metadata server
- No token logging/storage

**Shared Secrets:**
- Secret key NOT in shared package
- Each service loads from Secret Manager
- No hardcoded credentials

## Next Steps

**After Phase 1 Completion:**
- Phase 2: Extract Chat AI service using shared package
- Phase 2: Implement SBERT ONNX optimization
- Phase 2: Deploy Chat AI service separately
