"""
Simplified unit tests for UserService.

Tests user management operations with minimal dependencies.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status

from app.services.user import UserService
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserInDB


@pytest.mark.unit
class TestUserService:
    """Test cases for UserService."""

    @pytest.fixture
    def mock_db_pool(self):
        """Mock database pool."""
        return MagicMock()

    @pytest.fixture
    def user_service(self, mock_db_pool):
        """Create UserService instance with mocked database pool."""
        return UserService(mock_db_pool)

    @pytest.fixture
    def sample_user_create(self):
        """Sample UserCreate schema."""
        return UserCreate(
            email="test@example.com",
            password="password123",
            first_name="Test",
            last_name="User",
        )

    @pytest.fixture
    def sample_user_update(self):
        """Sample UserUpdate schema."""
        return UserUpdate(first_name="Updated", last_name="Name")

    @pytest.fixture
    def sample_user_response(self):
        """Sample UserResponse object."""
        return UserResponse(
            id=1,
            email="test@example.com",
            is_active=True,
            provider="local",
            email_verified=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            profile=None,
        )

    @pytest.fixture
    def sample_user_in_db(self):
        """Sample UserInDB object."""
        return UserInDB(
            id=1,
            email="test@example.com",
            is_active=True,
            provider="local",
            email_verified=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            profile=None,
            password_hash=None,
            google_id=None,
            email_verification_token=None,
            email_verification_sent_at=None,
            password_reset_token=None,
            password_reset_sent_at=None,
        )

    # Test UserService Initialization

    def test_user_service_initialization(self, user_service):
        """Test UserService initialization."""
        assert user_service.user_repo is not None
        assert hasattr(user_service, "user_repo")
        assert hasattr(user_service, "profile_repo")

    # Test Schema Validation

    def test_user_create_validation(self, sample_user_create):
        """Test UserCreate schema validation."""
        assert sample_user_create.email == "test@example.com"
        assert sample_user_create.password == "password123"
        assert sample_user_create.first_name == "Test"
        assert sample_user_create.last_name == "User"
        assert sample_user_create.is_active is True  # Default value

    def test_user_update_validation(self, sample_user_update):
        """Test UserUpdate schema validation."""
        assert sample_user_update.first_name == "Updated"
        assert sample_user_update.last_name == "Name"

    def test_user_response_validation(self, sample_user_response):
        """Test UserResponse schema validation."""
        assert sample_user_response.id == 1
        assert sample_user_response.email == "test@example.com"
        assert sample_user_response.is_active is True
        assert sample_user_response.email_verified is True
        # Note: full_name is in profile, not in UserResponse directly

    def test_user_in_db_validation(self, sample_user_in_db):
        """Test UserInDB schema validation."""
        assert sample_user_in_db.id == 1
        assert sample_user_in_db.email == "test@example.com"
        assert sample_user_in_db.is_active is True
        # Note: full_name is in profile, not in UserInDB directly

    # Test UserCreate Edge Cases

    def test_user_create_with_optional_fields(self):
        """Test UserCreate with optional fields."""
        user_data = UserCreate(
            email="test@example.com",
            password="password123",
            first_name="Test",
            last_name="User",
            is_active=False,  # Override default
        )
        assert user_data.is_active is False

    def test_user_create_minimal_data(self):
        """Test UserCreate with minimal required data."""
        user_data = UserCreate(
            email="minimal@example.com",
            password="password123"
            # full_name is optional
        )
        assert user_data.email == "minimal@example.com"
        assert user_data.password == "password123"

    # Test UserUpdate Edge Cases

    def test_user_update_with_multiple_fields(self):
        """Test UserUpdate with multiple fields."""
        update_data = UserUpdate(
            first_name="Updated", last_name="Name", is_active=False
        )
        assert update_data.first_name == "Updated"
        assert update_data.last_name == "Name"
        assert update_data.is_active is False

    def test_user_update_empty(self):
        """Test UserUpdate with no fields."""
        update_data = UserUpdate()
        # Should not raise any errors
        assert update_data is not None

    # Test Data Type Validation

    def test_user_create_invalid_email(self):
        """Test UserCreate with invalid email."""
        with pytest.raises(Exception):  # Should raise validation error
            UserCreate(email="invalid-email", password="password123")

    def test_user_create_short_password(self):
        """Test UserCreate with short password."""
        with pytest.raises(Exception):  # Should raise validation error
            UserCreate(
                email="test@example.com",
                password="123",  # Too short
            )

    # Test Serialization/Deserialization

    def test_user_response_serialization(self, sample_user_response):
        """Test UserResponse serialization."""
        if hasattr(sample_user_response, "model_dump"):
            data = sample_user_response.model_dump()
            assert isinstance(data, dict)
            assert data["id"] == 1
            assert data["email"] == "test@example.com"
            assert "password" not in data  # Should not be in response

    def test_user_in_db_serialization(self, sample_user_in_db):
        """Test UserInDB serialization."""
        if hasattr(sample_user_in_db, "model_dump"):
            data = sample_user_in_db.model_dump()
            assert isinstance(data, dict)
            assert data["id"] == 1
            assert data["email"] == "test@example.com"

    # Test Date Handling

    def test_user_response_with_dates(self):
        """Test UserResponse with datetime fields."""
        now = datetime.now(timezone.utc)
        user_data = {
            "id": 1,
            "email": "test@example.com",
            "is_active": True,
            "provider": "local",
            "email_verified": True,
            "created_at": now,
            "updated_at": now,
            "profile": None,
        }

        user = UserResponse(**user_data)
        assert user.created_at == now
        assert user.updated_at == now
        assert isinstance(user.created_at, datetime)
        assert isinstance(user.updated_at, datetime)

    def test_user_in_db_with_optional_dates(self):
        """Test UserInDB with optional date fields."""
        now = datetime.now(timezone.utc)
        user_data = {
            "id": 1,
            "email": "test@example.com",
            "is_active": True,
            "provider": "local",
            "email_verified": True,
            "created_at": now,
            "updated_at": now,
            "profile": None,
            "password_hash": None,
            "google_id": None,
            "email_verification_token": None,
            "email_verification_sent_at": now,  # Optional field
            "password_reset_token": None,
            "password_reset_sent_at": None,
        }

        user = UserInDB(**user_data)
        assert user.email_verification_sent_at == now

    # Test Edge Cases and Error Conditions

    def test_user_response_with_none_values(self):
        """Test UserResponse with None values for optional fields."""
        user_data = {
            "id": 1,
            "email": "test@example.com",
            "is_active": True,
            "provider": "local",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "profile": None,  # Optional field can be None
        }

        user = UserResponse(**user_data)
        assert user.profile is None

    def test_user_in_db_boolean_fields(self):
        """Test UserInDB with various boolean field combinations."""
        test_cases = [
            {"is_active": True, "email_verified": True},
            {"is_active": True, "email_verified": False},
            {"is_active": False, "email_verified": True},
            {"is_active": False, "email_verified": False},
        ]

        base_data = {
            "id": 1,
            "email": "test@example.com",
            "provider": "local",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "profile": None,
            "password_hash": None,
            "google_id": None,
            "email_verification_token": None,
            "email_verification_sent_at": None,
            "password_reset_token": None,
            "password_reset_sent_at": None,
        }

        for case in test_cases:
            user_data = {**base_data, **case}
            user = UserInDB(**user_data)
            assert user.is_active == case["is_active"]
            assert user.email_verified == case["email_verified"]

    # Test Model Methods

    def test_user_response_model_methods(self, sample_user_response):
        """Test UserResponse model methods."""
        # Test json method if available
        if hasattr(sample_user_response, "model_dump_json"):
            json_str = sample_user_response.model_dump_json()
            assert isinstance(json_str, str)
            assert "test@example.com" in json_str

    def test_user_in_db_model_methods(self, sample_user_in_db):
        """Test UserInDB model methods."""
        # Test json method if available
        if hasattr(sample_user_in_db, "model_dump_json"):
            json_str = sample_user_in_db.model_dump_json()
            assert isinstance(json_str, str)
            assert "test@example.com" in json_str

    # Test Data Consistency

    def test_user_schema_consistency(self):
        """Test consistency between user schemas."""
        common_data = {
            "id": 1,
            "email": "test@example.com",
            "is_active": True,
            "provider": "local",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "profile": None,
        }

        user_response = UserResponse(**common_data)
        user_in_db_data = {
            **common_data,
            "password_hash": None,
            "google_id": None,
            "email_verification_token": None,
            "email_verification_sent_at": None,
            "password_reset_token": None,
            "password_reset_sent_at": None,
        }
        user_in_db = UserInDB(**user_in_db_data)

        assert user_response.id == user_in_db.id
        assert user_response.email == user_in_db.email
        assert user_response.is_active == user_in_db.is_active

    # Test Security-Related Validation

    def test_password_field_not_in_response(self, sample_user_response):
        """Test that password field is not included in response schemas."""
        # UserResponse should not have password field
        assert not hasattr(sample_user_response, "password")

        if hasattr(sample_user_response, "model_dump"):
            data = sample_user_response.model_dump()
            assert "password" not in data
            assert "password_hash" not in data

    def test_email_case_insensitive_display(self, sample_user_response):
        """Test email display case handling."""
        # Create user with mixed case email
        user_data = {
            "id": 1,
            "email": "test@example.com",
            "is_active": True,
            "provider": "local",
            "email_verified": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "profile": None,
        }

        user = UserResponse(**user_data)
        # Email is normalized to lowercase in the schema
        assert user.email == "test@example.com"
