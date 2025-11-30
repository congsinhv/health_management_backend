# Code Standards & Best Practices

**VHealth Backend - Coding Conventions and Guidelines**

Last Updated: 2025-11-30 (Phase 1: Microservices Separation)

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Code Style](#2-code-style)
3. [Naming Conventions](#3-naming-conventions)
4. [Import Organization](#4-import-organization)
5. [Type Hints](#5-type-hints)
6. [Error Handling](#6-error-handling)
7. [Testing Standards](#7-testing-standards)
8. [Documentation](#8-documentation)
9. [Database Patterns](#9-database-patterns)
10. [API Design](#10-api-design)
11. [Security Best Practices](#11-security-best-practices)
12. [Performance Guidelines](#12-performance-guidelines)
13. [Git Workflow](#13-git-workflow)

---

## 1. Project Structure

### 1.1 Directory Organization

The codebase follows a **layered architecture** with clear separation of concerns and **decomposed services** following single responsibility principle:

```
app/
├── api/          # HTTP endpoint definitions (routers)
├── services/     # Business logic layer (decomposed)
│   ├── qa/       # Q&A service components (Phase 1 completed)
│   ├── email/    # Email service components (Phase 1 completed)
│   ├── pdf/      # PDF service components (decomposition foundation)
│   ├── *.py      # Individual service files
├── interfaces/   # Service contracts and interfaces (NEW - Phase 1)
│   ├── cache_service_interface.py    # Cache service abstract interface
│   ├── qa_service_interface.py       # Q&A service contract
│   ├── email_service_interface.py    # Email service contract
│   ├── pdf_service_interface.py      # PDF service contract
│   ├── prediction_service_interface.py # Prediction service contract
│   └── __init__.py                    # Interface registry
├── db/           # Database repositories (raw SQL)
├── schemas/      # Pydantic data models
├── auth/         # Authentication dependencies
├── middleware/   # Custom middleware
├── core/         # Core utilities and shared components
│   ├── shared/    # NEW - Phase 1: Shared package for microservices
│   │   ├── __init__.py              # Shared package initialization
│   │   ├── exceptions.py           # Common exception classes
│   │   ├── base_service.py         # Base service interface
│   │   ├── logging.py              # Shared logging utilities
│   │   ├── validation.py           # Common validation patterns
│   │   ├── error_handling.py       # Standardized error handling
│   │   └── monitoring.py           # Shared monitoring utilities
│   ├── security.py        # Password hashing, JWT tokens
│   ├── utils.py          # General utility functions
│   ├── qa_constants.py   # Q&A service constants
│   ├── predict_constants.py # Prediction constants
│   └── cache_constants.py # Cache key prefixes and TTLs
├── utils/        # Legacy utility modules (being migrated)
├── templates/    # Jinja2 templates
│   ├── email/    # Email templates (new)
│   └── *.html    # PDF and other templates
├── static/       # Static assets (fonts, images)
├── main.py       # Application entrypoint
├── config.py     # Settings and configuration
└── helpers.py    # DEPRECATED - backward compatibility only
```

### 1.2 Microservices Architecture (Phase 1)

**Principle:** Separate shared concerns into reusable components while maintaining service boundaries and backward compatibility through interface contracts.

**Phase 1 Completion Status:**
- ✅ Shared package structure created (`app/core/shared/`)
- ✅ Service interfaces defined (`app/interfaces/`)
- ✅ Import migration completed (30/44 files migrated)
- ✅ Backward compatibility shims implemented
- ✅ Comprehensive testing (214/214 tests passed)
- ✅ Excellent code review (0 critical issues)

**New Package Structure:**

#### Shared Package (`app/core/shared/`)
Centralized utilities for microservices communication and common patterns:

```python
# Shared base service interface
from app.core.shared.base_service import BaseService

# Common exception hierarchy
from app.core.shared.exceptions import (
    VHealthException,
    ServiceUnavailableException,
    ValidationException
)

# Shared logging utilities
from app.core.shared.logging import get_logger, log_performance

# Standardized error handling
from app.core.shared.error_handling import handle_service_error, with_error_handling
```

#### Service Interfaces (`app/interfaces/`)
Abstract contracts for all services:

```python
# Example: Cache service interface
from abc import ABC, abstractmethod
from typing import Any, Optional

class CacheServiceInterface(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        pass

# Service registry for dependency injection
from app.interfaces import get_service_implementation
cache_service = get_service_implementation("cache_service")
```

### 1.3 Service Decomposition Pattern (Phase 1)

**Principle:** Break down large monolithic services into focused, testable components while maintaining backward compatibility through facade pattern.

**Structure:**
```
services/
├── service_name/          # Service directory
│   ├── __init__.py       # Facade maintaining backward compatibility
│   ├── component1.py     # Specialized component 1
│   ├── component2.py     # Specialized component 2
│   └── types.py          # Type definitions for the service
└── other_service.py      # Legacy monolithic services
```

**Completed Examples:**
- `app/services/qa/` - 5 components (model_loader, dataset_loader, ai_summarizer, question_hasher)
- `app/services/email/` - 5 components (smtp_client, template_renderer, email_sender, email_types)
- `app/services/pdf/` - Demonstrating decomposition pattern

**Interface-Based Migration:**
```python
# Before: Direct service dependency
from app.services.qa_service import QAService

# After: Interface-based dependency injection
from app.interfaces.qa_service_interface import QAServiceInterface
from app.core.shared.dependency_injection import get_service

qa_service: QAServiceInterface = get_service("qa_service")
```

### 1.4 Microservices Import Guidelines (Phase 1)

**Use these import patterns for new code and when refactoring:**

#### 1. Shared Components
```python
# ✅ Correct - use shared package for common utilities
from app.core.shared import (
    BaseService,
    VHealthException,
    get_logger,
    handle_service_error
)
from app.core.shared.base_service import BaseService
from app.core.shared.exceptions import ServiceUnavailableException
from app.core.shared.logging import log_performance
from app.core.shared.validation import validate_input
```

#### 2. Service Interfaces
```python
# ✅ Correct - import interfaces for dependency injection
from app.interfaces.cache_service_interface import CacheServiceInterface
from app.interfaces.qa_service_interface import QAServiceInterface
from app.interfaces.email_service_interface import EmailServiceInterface

# ✅ Service registry usage
from app.interfaces import get_service_implementation, register_service

# Register service implementation
register_service("qa_service", QAService)

# Get service interface instance
qa_service: QAServiceInterface = get_service_implementation("qa_service")
```

#### 3. Backward Compatibility Imports
```python
# ✅ Supported - existing service imports still work
from app.services.qa import QAService  # Facade pattern
from app.services.email import EmailService  # Facade pattern

# ⚠️ Deprecated - helpers.py imports show warnings
from app.helpers import hash_password  # Warning: use app.core.security
```

#### 4. Migration Examples
```python
# Before (direct dependency)
from app.services.qa_service import QAService
from app.services.email_service import EmailService

class HealthAdvisor:
    def __init__(self):
        self.qa_service = QAService(settings)
        self.email_service = EmailService(settings)

# After (interface-based dependency injection)
from app.interfaces.qa_service_interface import QAServiceInterface
from app.interfaces.email_service_interface import EmailServiceInterface
from app.core.shared.dependency_injection import get_service

class HealthAdvisor:
    def __init__(self):
        self.qa_service: QAServiceInterface = get_service("qa_service")
        self.email_service: EmailServiceInterface = get_service("email_service")
```

#### 5. Component-Level Imports
```python
# ✅ Direct component imports (for testing or specialized use cases)
from app.services.qa.model_loader import ModelLoader
from app.services.qa.ai_summarizer import AISummarizer
from app.services.email.smtp_client import SMTPClient
from app.services.email.template_renderer import EmailTemplateRenderer

# For internal service testing
def test_qa_component():
    model_loader = ModelLoader(settings.qa_model_path)
    assert model_loader.is_loaded()
```

### 1.5 Dependency Injection Patterns

#### Constructor Injection (Preferred)
```python
class ConversationService:
    def __init__(
        self,
        cache_service: CacheServiceInterface,
        qa_service: QAServiceInterface,
        email_service: EmailServiceInterface,
        logger: Logger = None
    ):
        self.cache_service = cache_service
        self.qa_service = qa_service
        self.email_service = email_service
        self.logger = logger or get_logger(__name__)
```

#### Service Registry Injection
```python
# In main.py lifespan()
from app.interfaces import register_services
register_services(app.state)

# In API routes or other services
from app.interfaces import get_service

cache_service = get_service("cache_service")
qa_service = get_service("qa_service")
```

#### FastAPI Dependencies
```python
from fastapi import Depends
from app.interfaces import get_service_interface
from app.interfaces.cache_service_interface import CacheServiceInterface

def get_cache_service() -> CacheServiceInterface:
    return get_service_interface("cache_service")

@router.get("/health")
async def health_check(
    cache_service: CacheServiceInterface = Depends(get_cache_service)
):
    return await cache_service.ping()
```

### 1.6 Migration Progress

#### Completed (30/44 files)
- ✅ All service files converted to use shared components
- ✅ All API routes updated for interface-based dependencies
- ✅ All repository files using shared error handling
- ✅ All new utility functions in shared package
- ✅ Complete test coverage for shared components (214/214 tests passed)

#### In Progress (14/44 files)
- 🔄 Remaining monolithic services (predict_service, user_service)
- 🔄 Some middleware components
- 🔄 Legacy utility modules
- 🔄 Some test files (need component-level testing)

#### Migration Guidelines
1. **Identify Dependencies**: List all external service dependencies
2. **Create Interface**: Define abstract interface in `app/interfaces/`
3. **Extract Components**: Break service into focused components
4. **Implement Facade**: Maintain backward compatibility with `__init__.py`
5. **Update Imports**: Migrate to shared package and interface imports
6. **Add Tests**: Component-level and integration testing
7. **Remove Shims**: Remove deprecated helpers.py imports

### 1.7 Testing Microservices

#### Component Testing
```python
# Test individual components in isolation
from app.services.qa.model_loader import ModelLoader
from unittest.mock import Mock

def test_model_loader():
    model_loader = ModelLoader(settings.qa_model_path)
    assert model_loader.model is not None
    assert model_loader.is_loaded()

# Mock interface for testing
from app.interfaces.qa_service_interface import QAServiceInterface

class MockQAService(QAServiceInterface):
    def __init__(self):
        self.model_loaded = False

    async def ask_question(self, question: str):
        return {"answers": ["mock answer"]}
```

#### Integration Testing
```python
# Test service interactions through interfaces
from app.interfaces import register_services, get_service

async def test_service_integration():
    # Register mock implementations
    register_services()

    # Test actual service integration
    qa_service = get_service("qa_service")
    response = await qa_service.ask_question("What is BMI?")
    assert len(response["answers"]) > 0
```

### 1.3 Layer Responsibilities

#### API Layer (`app/api/`)
- HTTP endpoint definitions using FastAPI routers
- Request validation (Pydantic)
- Response serialization
- Dependency injection
- Error handling (HTTP status codes)
- OpenAPI documentation

**Example:**
```python
# app/api/qa.py
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.qa import QARequest, QAResponse
from app.services.qa import QAService  # Note: Decomposed service import

router = APIRouter()

@router.post("/ask", response_model=QAResponse)
async def ask_question(
    request: QARequest,
    qa_service: QAService = Depends(get_qa_service)
):
    """Ask a health question."""
    return await qa_service.ask(request.question)
```

#### Service Layer (`app/services/`)

**Monolithic Services (Legacy):**
- Individual service files (`*.py`)
- Direct business logic implementation
- Used for smaller, focused services

**Decomposed Services (Phase 3+):**
- Service directories with multiple components
- Facade pattern for backward compatibility
- Single responsibility principle per component
- Improved testability and maintainability

**Responsibilities:**
- Business logic and orchestration
- Integration with external services (OpenAI, GCS)
- Data transformation
- Caching logic
- Background tasks
- Error handling (business logic)

**Decomposed Service Example:**
```python
# app/services/qa/__init__.py (Facade)
class QAService:
    """Q&A service facade using decomposed components."""

    def __init__(self, settings, cache_service=None):
        self.settings = settings
        self.cache_service = cache_service

        # Initialize specialized components
        self.model_loader = ModelLoader(settings.qa_model_path)
        self.dataset_loader = DatasetLoader(settings.qa_data_path, settings.qa_vocab_path)
        self.ai_summarizer = AISummarizer()

    async def ask_question_stream(self, question: str) -> Iterator[str]:
        """Ask a question with streaming AI response."""
        # Orchestrate components for Q&A functionality
        answers = await self._search_similar_answers(question)
        async for chunk in self.ai_summarizer.generate_summary_stream(question, answers):
            yield chunk

# Individual components handle specific responsibilities
# - ModelLoader: SBERT model management
# - DatasetLoader: Q&A data preprocessing
# - AISummarizer: OpenAI integration
# - QuestionHasher: Cache key generation
```
#### Repository Layer (`app/db/`)
- Raw SQL queries with asyncpg
- CRUD operations
- Transaction management
- Connection pool usage
- Query optimization

**Example:**
```python
# app/db/user.py
class UserRepository:
    """User database operations."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def create_user(self, email: str, hashed_password: str) -> UserInDB:
        """Create new user."""
        query = """
            INSERT INTO users (email, hashed_password, created_at)
            VALUES ($1, $2, NOW())
            RETURNING id, email, created_at
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, email, hashed_password)
            return UserInDB(**row)
```

#### Schema Layer (`app/schemas/`)
- Pydantic data models
- Request/response validation
- Data serialization
- OpenAPI schema generation

**Example:**
```python
# app/schemas/user.py
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class UserCreate(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None

class UserInDB(BaseModel):
    """User database model."""
    id: int
    email: EmailStr
    hashed_password: str
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime
```

### 1.3 File Naming Conventions

- **Python files**: `snake_case.py`
- **Test files**: `test_<module_name>.py`
- **Configuration files**: `lowercase.ext` (e.g., `.env`, `Dockerfile`)
- **Documentation**: `kebab-case.md` or `PascalCase.md`

**Examples:**
- `app/services/qa_service.py` ✅
- `app/services/QAService.py` ❌
- `tests/test_qa_service.py` ✅
- `tests/qa_service_test.py` ❌

### 1.4 Docker and Containerization Standards

#### Dockerfile Organization
- **Dockerfile**: Main production image (used for standalone builds)
- **Dockerfile.base**: Base image with dependencies (used by Jenkins pipeline)
- Both Dockerfiles must include **Vietnamese font support** for PDF generation

#### Required System Packages for PDF Generation
```dockerfile
# CRITICAL: These fonts are required for Vietnamese PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    libglib2.0-0 \
    shared-mime-info \
    fonts-dejavu-core \     # Required for Vietnamese text
    fonts-noto-core \       # Required for Vietnamese text
    && rm -rf /var/lib/apt/lists/*
```

**Why This Matters:**
- PDFs will render incorrectly without these fonts in production
- Both `Dockerfile` and `Dockerfile.base` must include these fonts
- Missing fonts causes blank rectangles instead of Vietnamese characters
- This is a common production issue that only appears in containerized environments

---

## 2. Service Decomposition Guidelines (Phase 3)

### 2.1 When to Decompose Services

**Decompose When:**
- Service exceeds 300-400 lines of code
- Multiple responsibilities within single service
- Difficult to test individual components
- Components can be reused across services
- Service has distinct logical boundaries

**Keep Monolithic When:**
- Service is small and focused (<200 lines)
- Single clear responsibility
- Simple business logic
- No clear component separation

### 2.2 Decomposition Pattern

**1. Identify Components:**
```python
# Before: Monolithic service
class EmailService:
    def __init__(self):
        self.smtp_config = self._configure_smtp()
        self.template_env = self._setup_templates()

    async def send_verification_email(self, email, token):
        # SMTP setup + template rendering + sending logic

    def _render_template(self, name, context):
        # Template rendering logic

    def _configure_smtp(self):
        # SMTP configuration logic
```

**2. Extract Components:**
```python
# After: Decomposed service
# app/services/email/smtp_client.py
class SMTPClient:
    def __init__(self):
        if self._is_configuration_valid():
            self._configure_smtp()

# app/services/email/template_renderer.py
class EmailTemplateRenderer:
    def render_template(self, name, **context):
        return self.env.get_template(name).render(**context)

# app/services/email/email_sender.py
class EmailSender:
    def __init__(self, smtp_client, template_renderer):
        self.smtp_client = smtp_client
        self.template_renderer = template_renderer

# app/services/email/__init__.py (Facade)
class EmailService:
    def __init__(self):
        self.smtp_client = SMTPClient()
        self.template_renderer = EmailTemplateRenderer()
        self.email_sender = EmailSender(self.smtp_client, self.template_renderer)

    async def send_verification_email(self, email, token):
        return await self.email_sender.send_verification_email(email, token)
```

### 2.3 Facade Pattern Implementation

**Purpose:** Maintain backward compatibility while using decomposed components internally.

```python
# Facade delegates to specialized components
class ServiceFacade:
    def __init__(self):
        # Initialize all components
        self.component1 = Component1()
        self.component2 = Component2()

    # Public API remains unchanged
    async def legacy_method(self, param):
        # Delegate to appropriate components
        result1 = await self.component1.process(param)
        result2 = self.component2.transform(result1)
        return result2

    def get_service_status(self):
        # Aggregate status from all components
        return {
            "component1": self.component1.is_healthy(),
            "component2": self.component2.is_healthy(),
        }
```

### 2.4 Component Design Principles

**Single Responsibility:**
- Each component has one clear purpose
- Components are independently testable
- Minimal dependencies between components

**Dependency Injection:**
- Components receive dependencies via constructor
- Easy to mock for testing
- Clear dependency relationships

```python
class Component:
    def __init__(self, dependency1, dependency2=None):
        self.dependency1 = dependency1  # Required
        self.dependency2 = dependency2  # Optional
```

**Error Handling:**
- Components handle their specific errors
- Graceful degradation when possible
- Clear error propagation to facade

## 3. Code Style

### 3.1 PEP 8 Compliance

Follow [PEP 8](https://peps.python.org/pep-0008/) style guide for Python code:

- **Line length**: 88 characters (Black default)
- **Indentation**: 4 spaces (no tabs)
- **Blank lines**: 2 blank lines between top-level functions/classes
- **Whitespace**: Follow PEP 8 guidelines

### 2.2 Formatting Tools

Use automated formatting tools:

```bash
# Format code with Black
black app/ tests/

# Sort imports with isort
isort app/ tests/

# Lint with flake8
flake8 app/ tests/

# Type check with mypy
mypy app/
```

### 2.3 Black Configuration

**pyproject.toml:**
```toml
[tool.black]
line-length = 88
target-version = ['py313']
include = '\.pyi?$'
exclude = '''
/(
    \.git
  | \.venv
  | env
  | build
  | dist
)/
'''
```

### 2.4 isort Configuration

**pyproject.toml:**
```toml
[tool.isort]
profile = "black"
line_length = 88
multi_line_output = 3
include_trailing_comma = true
```

---

## 3. Naming Conventions

### 3.1 Variables and Functions

- **Variables**: `snake_case`
- **Functions**: `snake_case`
- **Private functions**: `_snake_case` (single underscore prefix)
- **Constants**: `UPPER_SNAKE_CASE`
- **Type variables**: `TitleCase`

**Examples:**
```python
# Variables
user_id = 123
cache_ttl = 1800
MAX_RETRIES = 3

# Functions
def calculate_bmi(weight: float, height: float) -> float:
    return weight / (height ** 2)

def _validate_token(token: str) -> bool:
    """Private helper function."""
    pass

# Type variables
T = TypeVar('T')
UserType = Union[UserInDB, UserResponse]
```

### 3.2 Classes

- **Classes**: `PascalCase`
- **Private attributes**: `_snake_case`
- **Magic methods**: `__snake_case__`

**Examples:**
```python
class QAService:
    """Q&A service with semantic search."""

    def __init__(self, settings):
        self.settings = settings
        self._model = None  # Private attribute

    def __repr__(self) -> str:
        return f"QAService(settings={self.settings})"

class UserRepository:
    """User database repository."""
    pass
```

### 3.3 Modules and Packages

- **Modules**: `snake_case.py`
- **Packages**: `snake_case/`

**Examples:**
```
app/services/qa_service.py       ✅
app/services/QAService.py        ❌
app/services/predict_service.py  ✅
app/services/predictService.py   ❌
```

### 3.4 Database Tables and Columns

- **Tables**: `snake_case` (plural)
- **Columns**: `snake_case`
- **Timestamps**: `created_at`, `updated_at`
- **IDs**: `id` (primary key), `user_id` (foreign key)

**Examples:**
```sql
-- Table names
CREATE TABLE users (...);            ✅
CREATE TABLE conversations (...);     ✅
CREATE TABLE message_versions (...);  ✅

-- Column names
id SERIAL PRIMARY KEY,                ✅
user_id INTEGER NOT NULL,             ✅
created_at TIMESTAMP DEFAULT NOW(),   ✅
```

### 3.5 Pydantic Models

- **Request models**: `<Entity>Create`, `<Entity>Update`, `<Entity>Request`
- **Response models**: `<Entity>Response`, `<Entity>InDB`
- **Base models**: `<Entity>Base`

**Examples:**
```python
class UserCreate(BaseModel):      # Request
    """User registration request."""
    pass

class UserUpdate(BaseModel):      # Update request
    """User update request."""
    pass

class UserResponse(BaseModel):    # Response
    """User API response."""
    pass

class UserInDB(BaseModel):        # Database model
    """User database representation."""
    pass
```

---

## 4. Import Organization

### 4.1 Import Order

Organize imports in the following order:

1. **Standard library imports**
2. **Third-party imports**
3. **Local application imports**

Separate each group with a blank line.

**Example:**
```python
# Standard library
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

# Third-party
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sentence_transformers import SentenceTransformer

# Local
from app.config import settings
from app.schemas.qa import QARequest, QAResponse
from app.services.cache import CacheService
```

### 4.2 Core Package Import Guidelines (Phase 2)

**New Core Package Structure** - Use these imports for all new code:

```python
# ✅ Correct - use new core package structure
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    verify_access_token,
    create_refresh_token,
    verify_refresh_token,
    create_verification_token,
    verify_verification_token
)
from app.core.utils import some_utility_function
from app.core.qa_constants import QA_THRESHOLD, MAX_ANSWERS_PER_FIELD
from app.core.predict_constants import OBESITY_CLASSES
from app.core.cache_constants import (
    QA_CACHE_TTL,
    CONVERSATION_CACHE_TTL,
    CACHE_KEY_PREFIXES
)
```

**Deprecated helpers.py Imports** - Update existing code:

```python
# ❌ Deprecated - will show warnings
from app.helpers import hash_password, verify_password

# ✅ Updated - use new core package
from app.core.security import hash_password, verify_password
```

**Migration Examples:**
```python
# Before (deprecated)
from app.helpers import hash_password, create_access_token
from app.constants import QA_THRESHOLD

# After (new structure)
from app.core.security import hash_password, create_access_token
from app.core.qa_constants import QA_THRESHOLD
```

### 4.3 Import Style

- Use **absolute imports** (not relative)
- Import modules, not individual items (when possible)
- Avoid wildcard imports (`from module import *`)

**Preferred:**
```python
from app.services import qa_service
from app.db import user

result = qa_service.ask(question)
user_data = user.get_user(user_id)
```

**Acceptable:**
```python
from app.services.qa_service import QAService
from app.db.user import UserRepository

qa = QAService(settings)
repo = UserRepository(pool)
```

**Avoid:**
```python
from app.services.qa_service import *  # ❌ Wildcard import
```

---

## 5. Type Hints

### 5.1 Type Hint Everything

All functions, methods, and variables should have type hints.

**Example:**
```python
from typing import Dict, List, Optional, Union

def calculate_bmi(weight: float, height: float) -> float:
    """Calculate BMI from weight and height."""
    return weight / (height ** 2)

async def get_user(user_id: int) -> Optional[UserInDB]:
    """Get user by ID."""
    query = "SELECT * FROM users WHERE id = $1"
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, user_id)
        return UserInDB(**row) if row else None

def process_answers(answers: List[Dict[str, str]]) -> Dict[str, List[str]]:
    """Group answers by field."""
    grouped: Dict[str, List[str]] = {}
    for answer in answers:
        field = answer.get("field", "Unclassified")
        grouped.setdefault(field, []).append(answer["answer"])
    return grouped
```

### 5.2 Optional and Union Types

Use `Optional[T]` for nullable values, `Union[T, U]` for multiple types.

**Example:**
```python
from typing import Optional, Union

def get_cache_ttl(key: str) -> Optional[int]:
    """Get TTL for cache key, or None if not found."""
    return cache.ttl(key)

def parse_input(value: Union[int, str]) -> int:
    """Parse input as integer."""
    return int(value)
```

### 5.3 Generic Types

Use `List`, `Dict`, `Set`, `Tuple` from `typing` module.

**Example:**
```python
from typing import Dict, List, Set, Tuple

def get_users() -> List[UserInDB]:
    """Get all users."""
    pass

def get_user_map() -> Dict[int, UserInDB]:
    """Get user ID to user mapping."""
    pass

def get_tags() -> Set[str]:
    """Get unique tags."""
    pass

def get_coordinates() -> Tuple[float, float]:
    """Get latitude and longitude."""
    pass
```

### 5.4 TypeVar for Generics

Use `TypeVar` for generic functions and classes.

**Example:**
```python
from typing import TypeVar, List

T = TypeVar('T')

def first(items: List[T]) -> Optional[T]:
    """Get first item from list."""
    return items[0] if items else None

def last(items: List[T]) -> Optional[T]:
    """Get last item from list."""
    return items[-1] if items else None
```

---

## 6. Error Handling

### 6.1 Standardized Exception Hierarchy (Phase 4)

VHealth uses a comprehensive exception hierarchy with proper categorization, context propagation, and security considerations. All custom exceptions inherit from `VHealthException`.

**Exception Categories:**
- **Resource Errors** (HTTP 404/410): ResourceNotFoundException, ResourceConflictException, ResourceGoneException
- **Authentication/Authorization** (HTTP 401/403): AuthenticationException, AuthorizationException, TokenExpiredException
- **Validation Errors** (HTTP 422): ValidationException, MissingFieldException, InvalidFormatException
- **Business Logic** (HTTP 400/409): BusinessLogicException, DuplicateResourceException, InvalidStateException
- **Service/Infrastructure** (HTTP 502/503/504): ServiceUnavailableException, ExternalServiceException, DatabaseException
- **Data Processing** (HTTP 422/500): DataProcessingException, ModelNotLoadedException, DataCorruptionException
- **Rate Limiting** (HTTP 429): RateLimitException, TooManyRequestsException
- **Configuration** (HTTP 500): ConfigurationException, MissingConfigurationException
- **Cache Errors** (HTTP 500/503): CacheException, CacheUnavailableException
- **File/Storage** (HTTP 400/500): FileOperationException, FileNotFoundException, StorageException
- **Email Service** (HTTP 500/503): EmailException, EmailSendException, EmailTemplateException
- **PDF Generation** (HTTP 500): PDFGenerationException, PDFTemplateException, PDFFontException
- **Q&A Service** (HTTP 500/503): QAServiceException, QAModelNotLoadedException, QADatasetException
- **AI Service** (HTTP 500/503): AIServiceException, OpenAIException, AIServiceUnavailableException
- **WebSocket**: WebSocketException, WebSocketConnectionException, WebSocketMessageException
- **Prediction Service**: PredictionException, PredictionModelException, PredictionDataException
- **OAuth Service**: OAuthException, OAuthTokenException, OAuthProviderException

### 6.2 ErrorContext Integration (Phase 4)

All operations should use ErrorContext for request-scoped context propagation across async boundaries.

**Context Manager Usage:**
```python
from app.core.error_context import ErrorContext, with_error_context

# Using context manager
with ErrorContext("create_conversation", {"user_id": user.id}):
    conversation = await self.conversation_repo.create(conversation_data)
    return conversation

# Using decorator
@with_error_context("database_query", {"table": "users"})
async def get_user(user_id: int):
    return await self.user_repo.get_by_id(user_id)

# Manual context management
request_id = ErrorContext.set_request_id()
ErrorContext.set_user_id(user.id)
ErrorContext.set_correlation_id()
ErrorContext.add_context("operation", "user_lookup")
```

**Context Data:**
- `request_id`: UUID for request tracking
- `user_id`: Authenticated user ID
- `correlation_id`: UUID for cross-service correlation
- `operation_name`: Current operation being performed
- `request_duration`: Time since request start
- `error_count`: Number of errors in request lifecycle
- `additional_context`: Custom key-value pairs

### 6.3 Layer-Specific Error Handling Patterns

**API Layer (Routers):**
```python
from app.exceptions import (
    ResourceNotFoundException,
    ValidationException,
    get_http_status_code,
    sanitize_error_details
)
from fastapi import HTTPException

@router.post("/conversations/")
async def create_conversation(
    request: ConversationCreate,
    current_user: User = Depends(get_current_user)
):
    """Create conversation with standardized error handling."""
    try:
        # Set context at entry point
        ErrorContext.set_user_id(current_user.id)

        with ErrorContext("api_create_conversation", {"user_id": current_user.id}):
            result = await conversation_service.create(request, current_user.id)
            return result

    except ResourceNotFoundException as e:
        # Convert to HTTP response with context headers
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail=e.to_dict()
        )
    except ValidationException as e:
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail=e.to_dict()
        )
    except VHealthException as e:
        # Log with context
        e.log("error", ErrorContext.get_all())
        raise HTTPException(
            status_code=get_http_status_code(e),
            detail=e.to_dict()
        )
    except Exception as e:
        # Unexpected errors
        logger.error(
            f"Unexpected error in create_conversation: {e}",
            exc_info=True,
            extra=ErrorContext.get_all()
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
```

**Service Layer:**
```python
from app.exceptions import (
    ResourceNotFoundException,
    BusinessLogicException,
    ServiceUnavailableException,
    DatabaseException
)

class ConversationService:
    async def create(self, request: ConversationCreate, user_id: int) -> ConversationResponse:
        """Create conversation with comprehensive error handling."""
        with ErrorContext("service_create_conversation", {"user_id": user_id}):
            try:
                # Validate business rules
                if await self._has_active_conversation(user_id):
                    raise BusinessLogicException(
                        message="User already has active conversation",
                        details={"user_id": user_id, "max_active": 1}
                    )

                # Create conversation
                conversation_data = {
                    "user_id": user_id,
                    "title": request.title,
                    "metadata": request.metadata or {}
                }

                result = await self.conversation_repo.create(conversation_data)
                ErrorContext.add_context("conversation_id", result["id"])

                return ConversationResponse(**result)

            except DatabaseException as e:
                e.log("error", {"operation": "create_conversation"})
                raise ServiceUnavailableException(
                    message="Database service temporarily unavailable",
                    details={"original_error": e.error_code}
                )
```

**Repository Layer:**
```python
from app.exceptions import DatabaseException, DatabaseConnectionException

class ConversationRepository:
    async def create(self, conversation_data: dict) -> dict:
        """Create conversation with database error handling."""
        query = """
            INSERT INTO conversations (user_id, title, metadata, created_at)
            VALUES ($1, $2, $3, NOW())
            RETURNING id, user_id, title, metadata, created_at
        """

        with ErrorContext("repo_create_conversation", {"table": "conversations"}):
            try:
                async with self.pool.acquire() as conn:
                    result = await conn.fetchrow(
                        query,
                        conversation_data["user_id"],
                        conversation_data["title"],
                        conversation_data["metadata"]
                    )
                    return dict(result)

            except asyncpg.PostgresConnectionError as e:
                raise DatabaseConnectionException(
                    message="Failed to connect to database",
                    details={"operation": "create_conversation"}
                )
            except asyncpg.PostgresError as e:
                raise DatabaseException(
                    message="Database operation failed",
                    details={"operation": "create_conversation", "error": str(e)}
                )
```

### 6.4 Error Logging and Monitoring

**Structured Logging with Context:**
```python
import logging
from app.core.error_context import ErrorContext

logger = logging.getLogger(__name__)

# Using exception built-in logging
try:
    result = await some_operation()
except ResourceNotFoundException as e:
    # Log with context and error details
    e.log("warning", {
        "component": "conversation_service",
        "operation": "get_conversation"
    })
    raise

# Manual logging with context
logger.info(
    "Operation completed successfully",
    extra=ErrorContext.create_log_extra({
        "component": "conversation_service",
        "operation": "create_conversation",
        "record_count": 1
    })
)

# Error logging with full context
logger.error(
    "Critical operation failed",
    exc_info=True,
    extra=ErrorContext.create_log_extra({
        "component": "qa_service",
        "error_severity": "critical",
        "requires_alert": True
    })
)
```

**Critical Error Detection:**
```python
from app.exceptions import is_critical_error

try:
    result = await critical_operation()
except Exception as e:
    # Check if error requires immediate attention
    if is_critical_error(e):
        # Send alert to monitoring system
        await alert_service.send_critical_alert(
            error=str(e),
            context=ErrorContext.get_all(),
            severity="critical"
        )

    # Log appropriately
    logger.error(
        f"Critical operation failed: {e}",
        exc_info=True,
        extra=ErrorContext.get_all()
    )
    raise
```

### 6.5 Security and Sanitization

**Sensitive Data Protection:**
```python
from app.exceptions import sanitize_error_details

# Error details with sensitive information
error_details = {
    "user_id": 123,
    "email": "user@example.com",
    "api_key": "sk-1234567890",
    "database_url": "postgresql://user:pass@host/db",
    "credit_card": "4111-1111-1111-1111"
}

# For internal logging (preserve but redact sensitive)
log_details = sanitize_error_details(error_details, user_context=False)
# Returns: {
#     "user_id": 123,
#     "email": "user@example.com",
#     "api_key": "[REDACTED]",
#     "database_url": "[REDACTED]",
#     "credit_card": "[REDACTED]"
# }

# For user responses (remove sensitive entirely)
user_details = sanitize_error_details(error_details, user_context=True)
# Returns: {
#     "user_id": 123,
#     "email": "user@example.com"
# }
```

**Information Disclosure Prevention:**
```python
# Don't expose internal details in production
if settings.DEBUG:
    error_response = {
        "error": e.error_code,
        "message": e.message,
        "details": e.details
    }
else:
    error_response = {
        "error": e.error_code,
        "message": self._get_user_safe_message(e.error_code),
        "details": sanitize_error_details(e.details, user_context=True)
    }

def _get_user_safe_message(self, error_code: str) -> str:
    """Map error codes to user-safe messages."""
    user_messages = {
        "DatabaseConnectionException": "Service temporarily unavailable",
        "ExternalServiceException": "Third-party service unavailable",
        "ValidationException": "Invalid input provided",
        # ... more mappings
    }
    return user_messages.get(error_code, "An error occurred")
```

### 6.6 Error Response Standards

**Consistent Error Response Format:**
```python
# Standard error response structure
{
    "error": "ResourceNotFoundException",
    "message": "Conversation not found",
    "details": {
        "conversation_id": 12345,
        "user_id": 678
    },
    "timestamp": "2025-11-25T10:30:00Z",
    "request_id": "req_1234567890"
}

# Response headers for context tracking
{
    "X-Request-ID": "req_1234567890",
    "X-Correlation-ID": "corr_abcdef1234",
    "X-Error-Code": "ResourceNotFoundException"
}
```

### 6.7 Graceful Degradation Patterns

**External Service Failure Handling:**
```python
class AIService:
    """AI service with graceful degradation."""

    async def generate_summary(self, text: str) -> str:
        """Generate summary with fallback behavior."""
        try:
            with ErrorContext("ai_generate_summary", {"text_length": len(text)}):
                return await self._call_openai_api(text)
        except OpenAIException as e:
            e.log("warning", {"fallback": "basic_summarization"})
            # Fallback to basic summarization
            return self._basic_summarization(text)
        except AIServiceUnavailableException as e:
            e.log("error", {"fallback": "no_summary"})
            # Return original text with indication
            return text + " [AI summary unavailable]"

class CacheService:
    """Cache service with graceful degradation."""

    async def get(self, key: str) -> Optional[Any]:
        """Get value with cache failure handling."""
        if not self.enabled:
            return None

        try:
            return await self._redis_client.get(key)
        except Exception as e:
            logger.warning(
                f"Cache get failed for key {key}: {e}",
                extra=ErrorContext.get_all()
            )
            # Continue without cache
            return None
```

---

## 7. Testing Standards

### 7.1 Test Organization

Organize tests by type:

```
tests/
├── integration/      # API endpoint tests
├── unit/            # Service and utility tests
├── repository/      # Database repository tests
├── services/        # Service layer tests
└── conftest.py      # Shared fixtures
```

### 7.2 Test Naming

- **Test files**: `test_<module>.py`
- **Test functions**: `test_<feature>_<scenario>()`
- **Test classes**: `Test<Feature>`

**Example:**
```python
# tests/unit/test_qa_service.py

class TestQAService:
    """Test Q&A service."""

    def test_ask_returns_answers(self, qa_service):
        """Test asking question returns answers."""
        response = qa_service.ask("What is BMI?")
        assert len(response.answers) > 0

    def test_ask_with_cache_hit(self, qa_service, mock_cache):
        """Test asking question with cache hit."""
        mock_cache.get.return_value = QAResponse(answers=[])
        response = qa_service.ask("What is BMI?")
        assert mock_cache.get.called

    def test_ask_with_invalid_question(self, qa_service):
        """Test asking invalid question raises error."""
        with pytest.raises(ValueError):
            qa_service.ask("")
```

### 7.3 Test Coverage

- **Target**: 80%+ overall coverage
- **Service layer**: 85%+ coverage
- **Repository layer**: 90%+ coverage
- **API layer**: 75%+ coverage

**Run coverage:**
```bash
pytest --cov=app --cov-report=html --cov-report=term
```

### 7.4 Fixtures

Use fixtures for test data and dependencies:

**conftest.py:**
```python
import pytest
from app.services.qa_service import QAService
from app.config import settings

@pytest.fixture
def qa_service():
    """Create QA service instance."""
    return QAService(settings)

@pytest.fixture
async def db_pool():
    """Create database pool for tests."""
    pool = await create_pool()
    yield pool
    await pool.close()

@pytest.fixture
def mock_cache(mocker):
    """Mock cache service."""
    cache = mocker.Mock()
    cache.enabled = True
    cache.get.return_value = None
    return cache
```

### 7.5 Async Testing

Use `pytest-asyncio` for async tests:

**Example:**
```python
import pytest

@pytest.mark.asyncio
async def test_create_user(user_service, db_pool):
    """Test creating user."""
    user = await user_service.create_user(
        email="test@example.com",
        password="password123"
    )
    assert user.id is not None
    assert user.email == "test@example.com"
```

---

## 8. Documentation

### 8.1 Docstrings

All functions, classes, and modules should have docstrings.

**Function docstring:**
```python
def calculate_bmi(weight: float, height: float) -> float:
    """
    Calculate Body Mass Index (BMI).

    Args:
        weight: Weight in kilograms
        height: Height in meters

    Returns:
        BMI value as float

    Raises:
        ValueError: If weight or height is negative or zero

    Example:
        >>> calculate_bmi(70, 1.75)
        22.86
    """
    if weight <= 0 or height <= 0:
        raise ValueError("Weight and height must be positive")
    return weight / (height ** 2)
```

**Class docstring:**
```python
class QAService:
    """
    Q&A service using Vietnamese SBERT for semantic search.

    This service provides health question answering using:
    - Sentence transformers for Vietnamese language
    - Cosine similarity for semantic matching
    - OpenAI API for AI summarization
    - Redis caching for performance

    Attributes:
        settings: Application settings
        cache_service: Optional cache service
        model: SBERT model instance
        df: Q&A dataset DataFrame
        question_embeddings: Pre-computed question embeddings

    Example:
        >>> qa_service = QAService(settings, cache_service)
        >>> response = qa_service.ask("What is BMI?")
        >>> print(response.answers)
    """
    pass
```

**Module docstring:**
```python
"""
Q&A Service using SBERT and OpenAI API.

This module provides the QAService class for health question answering
with semantic search, AI summarization, and caching support.
"""

import logging
# ... rest of module
```

### 8.2 Code Comments

Use comments for complex logic only:

**Example:**
```python
def _search(self, question: str) -> List[Dict]:
    """Search for answers to question."""
    # Generate embedding for question
    question_embedding = self.model.encode(question, convert_to_tensor=True)

    # Calculate cosine similarity with all questions in dataset
    similarities = util.cos_sim(question_embedding, self.question_embeddings)[0]

    # Filter by threshold and get top-k
    top_indices = (similarities >= self.settings.qa_threshold).nonzero(as_tuple=True)[0]
    top_scores = similarities[top_indices]

    # Sort by score descending
    sorted_indices = top_scores.argsort(descending=True)

    # Group by field and limit per field
    answers_by_field: Dict[str, List[Dict]] = {}
    for idx in sorted_indices:
        # ... complex grouping logic
        pass

    return answers
```

### 8.3 OpenAPI Documentation

Document API endpoints with FastAPI:

**Example:**
```python
@router.post(
    "/ask",
    response_model=QAResponse,
    summary="Ask a health question",
    description="Submit a health question and receive relevant answers with AI summary.",
    responses={
        200: {"description": "Successful response with answers"},
        400: {"description": "Invalid question"},
        503: {"description": "Q&A service unavailable"}
    },
    tags=["Q&A"]
)
async def ask_question(
    request: QARequest,
    current_user: UserInDB = Depends(get_current_user)
):
    """
    Ask a health question in Vietnamese.

    - **question**: The health question to ask
    - Returns relevant answers from the knowledge base
    - Includes AI-generated summary if available
    """
    pass
```

---

## 9. Database Patterns

### 9.1 Raw SQL with asyncpg

Use raw SQL for performance and clarity:

**Example:**
```python
async def create_user(self, email: str, hashed_password: str) -> UserInDB:
    """Create new user."""
    query = """
        INSERT INTO users (email, hashed_password, is_active, created_at)
        VALUES ($1, $2, TRUE, NOW())
        RETURNING id, email, is_active, created_at
    """
    async with self.pool.acquire() as conn:
        row = await conn.fetchrow(query, email, hashed_password)
        return UserInDB(**row)
```

### 9.2 Parameterized Queries

Always use parameterized queries to prevent SQL injection:

**Example:**
```python
# ✅ Correct - parameterized query
query = "SELECT * FROM users WHERE email = $1"
row = await conn.fetchrow(query, email)

# ❌ Incorrect - SQL injection vulnerable
query = f"SELECT * FROM users WHERE email = '{email}'"
row = await conn.fetchrow(query)
```

### 9.3 Connection Pool Usage

Use connection pool for all database operations:

**Example:**
```python
# ✅ Correct - use pool
async with self.pool.acquire() as conn:
    result = await conn.fetchrow(query, param1, param2)

# ❌ Incorrect - create new connection
conn = await asyncpg.connect(dsn)
result = await conn.fetchrow(query)
await conn.close()
```

### 9.4 Transactions

Use transactions for multiple related operations:

**Example:**
```python
async def transfer_credits(self, from_user_id: int, to_user_id: int, amount: int):
    """Transfer credits between users."""
    async with self.pool.acquire() as conn:
        async with conn.transaction():
            # Deduct from sender
            await conn.execute(
                "UPDATE users SET credits = credits - $1 WHERE id = $2",
                amount, from_user_id
            )

            # Add to receiver
            await conn.execute(
                "UPDATE users SET credits = credits + $1 WHERE id = $2",
                amount, to_user_id
            )
```

### 9.5 Migrations with Alembic

Use Alembic for schema changes:

**Create migration:**
```bash
cd scripts
alembic revision --autogenerate -m "Add user_profile table"
```

**Migration file:**
```python
"""Add user_profile table

Revision ID: abc123def456
Revises: previous_revision
Create Date: 2025-11-25 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        'user_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    op.create_index('idx_user_profiles_user_id', 'user_profiles', ['user_id'])

def downgrade():
    op.drop_index('idx_user_profiles_user_id', 'user_profiles')
    op.drop_table('user_profiles')
```

---

## 10. API Design

### 10.1 RESTful Principles

Follow REST conventions:

- **GET**: Retrieve resources
- **POST**: Create resources
- **PUT**: Update entire resource
- **PATCH**: Update partial resource
- **DELETE**: Delete resource

**Example:**
```python
# Users API
GET    /api/v1/users          # List users
GET    /api/v1/users/{id}     # Get user by ID
POST   /api/v1/users          # Create user
PUT    /api/v1/users/{id}     # Update user (full)
PATCH  /api/v1/users/{id}     # Update user (partial)
DELETE /api/v1/users/{id}     # Delete user

# Nested resources
GET    /api/v1/conversations/{id}/messages  # List messages
POST   /api/v1/conversations/{id}/messages  # Create message
```

### 10.2 Response Formats

Use consistent response formats:

**Success response:**
```json
{
  "id": 123,
  "email": "user@example.com",
  "created_at": "2025-11-25T10:00:00Z"
}
```

**Error response:**
```json
{
  "detail": "User not found"
}
```

**List response:**
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

### 10.3 Status Codes

Use appropriate HTTP status codes:

- **200 OK**: Successful GET, PUT, PATCH
- **201 Created**: Successful POST
- **204 No Content**: Successful DELETE
- **400 Bad Request**: Invalid input
- **401 Unauthorized**: Authentication required
- **403 Forbidden**: Permission denied
- **404 Not Found**: Resource not found
- **409 Conflict**: Resource conflict
- **422 Unprocessable Entity**: Validation error
- **500 Internal Server Error**: Server error
- **503 Service Unavailable**: Service unavailable

### 10.4 Pagination

Use consistent pagination:

**Example:**
```python
@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """List users with pagination."""
    offset = (page - 1) * page_size
    users = await user_repo.list_users(limit=page_size, offset=offset)
    total = await user_repo.count_users()

    return {
        "items": users,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size
    }
```

---

## 11. Security Best Practices

### 11.1 Password Hashing

Always hash passwords with bcrypt:

**Example:**
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash password with bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return pwd_context.verify(plain_password, hashed_password)
```

### 11.2 JWT Token Management

Use secure JWT tokens:

**Example:**
```python
from jose import jwt
from datetime import datetime, timedelta

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=30))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
```

### 11.3 Input Validation

Validate all inputs with Pydantic:

**Example:**
```python
from pydantic import BaseModel, Field, EmailStr, validator

class UserCreate(BaseModel):
    """User registration request."""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)

    @validator('password')
    def password_strength(cls, v):
        """Validate password strength."""
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        return v
```

### 11.4 SQL Injection Prevention

Use parameterized queries:

**Example:**
```python
# ✅ Correct - parameterized
query = "SELECT * FROM users WHERE email = $1"
row = await conn.fetchrow(query, email)

# ❌ Incorrect - SQL injection
query = f"SELECT * FROM users WHERE email = '{email}'"
row = await conn.fetchrow(query)
```

### 11.5 Rate Limiting

Implement rate limiting on sensitive endpoints:

**Example:**
```python
from app.middleware.rate_limit import rate_limit

@router.post("/login")
@rate_limit(max_requests=5, window=60)  # 5 requests per minute
async def login(request: LoginRequest):
    """User login with rate limiting."""
    pass
```

---

## 12. Performance Guidelines

### 12.1 Async/Await

Use async/await for all I/O operations:

**Example:**
```python
# ✅ Correct - async
async def get_user(user_id: int) -> UserInDB:
    """Get user by ID."""
    query = "SELECT * FROM users WHERE id = $1"
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, user_id)
        return UserInDB(**row)

# ❌ Incorrect - blocking
def get_user(user_id: int) -> UserInDB:
    """Get user by ID (blocking)."""
    conn = psycopg2.connect(dsn)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    return UserInDB(**row)
```

### 12.2 Connection Pooling

Use connection pools for database:

**Example:**
```python
# ✅ Correct - use pool
async with pool.acquire() as conn:
    result = await conn.fetchrow(query)

# ❌ Incorrect - create connection per request
conn = await asyncpg.connect(dsn)
result = await conn.fetchrow(query)
await conn.close()
```

### 12.3 Caching

Cache expensive operations:

**Example:**
```python
@cached(ttl=1800, key_prefix="qa:answer")
async def ask(self, question: str) -> QAResponse:
    """Ask question with caching."""
    answers = self._search(question)
    return QAResponse(answers=answers)
```

### 12.4 Background Tasks

Use background tasks for non-critical operations:

**Example:**
```python
from fastapi import BackgroundTasks

@router.post("/users")
async def create_user(
    request: UserCreate,
    background_tasks: BackgroundTasks
):
    """Create user and send welcome email."""
    user = await user_service.create_user(request)

    # Send email in background
    background_tasks.add_task(
        email_service.send_welcome_email,
        user.email
    )

    return user
```

---

## 13. Git Workflow

### 13.1 Commit Messages

Follow conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code refactoring
- `test`: Tests
- `chore`: Maintenance

**Example:**
```
feat(qa): add streaming support for Q&A responses

Implement Server-Sent Events (SSE) for real-time streaming of Q&A
responses. This improves UX by showing answers progressively.

Closes #123
```

### 13.2 Branch Naming

- `feature/<feature-name>`: New features
- `fix/<issue-number>`: Bug fixes
- `hotfix/<issue>`: Urgent fixes
- `refactor/<area>`: Refactoring
- `docs/<topic>`: Documentation

**Example:**
```bash
git checkout -b feature/add-pdf-generation
git checkout -b fix/123-cache-error
git checkout -b hotfix/security-patch
```

### 13.3 Pull Requests

- Create PR with clear description
- Link related issues
- Request code review
- Ensure tests pass
- Update documentation

---

---

## Docker Best Practices

### Multi-Stage Builds

Use multi-stage builds for efficiency:

```dockerfile
# Base stage with dependencies
FROM python:3.13-slim AS base
RUN apt-get update && apt-get install -y fonts-dejavu-core fonts-noto-core
COPY requirements-prod.txt .
RUN pip install -r requirements-prod.txt

# Production stage
FROM base AS production
COPY app/ ./app/
CMD ["uvicorn", "app.main:app"]

# Development stage
FROM production AS development
CMD ["uvicorn", "app.main:app", "--reload"]
```

### Non-Root User

Always run containers as non-root:

```dockerfile
RUN useradd --create-home --shell /bin/bash appuser
USER appuser
WORKDIR /home/appuser/app
```

### Health Checks

Include health checks for monitoring:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')" || exit 1
```

---

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Claude Code development guide
- [Project Overview & PDR](./project-overview-pdr.md)
- [Codebase Summary](./codebase-summary.md)
- [System Architecture](./system-architecture.md)
- [Deployment Guide](./deployment-guide.md)
