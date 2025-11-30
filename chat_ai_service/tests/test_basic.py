"""
Basic functionality tests for Chat AI service.
"""

import pytest
import os
from unittest.mock import MagicMock

# Set environment variables for testing
os.environ['SECRET_KEY'] = 'test-secret-key'
os.environ['DEBUG'] = 'true'
os.environ['OPENAI_API_KEY'] = 'test-openai-key'


class TestBasicImports:
    """Test basic imports work correctly."""

    def test_config_import(self):
        """Test config imports work."""
        from app.config import Settings
        settings = Settings(
            SECRET_KEY="test-key",
            OPENAI_API_KEY="test-openai-key"
        )
        assert settings.SECRET_KEY == "test-key"
        assert settings.OPENAI_API_KEY == "test-openai-key"

    def test_qa_constants_import(self):
        """Test QA constants import."""
        from app.core.qa_constants import (
            DEFAULT_MODEL_NAME,
            DEFAULT_SIMILARITY_THRESHOLD,
            DEFAULT_TOP_K
        )
        assert DEFAULT_MODEL_NAME is not None
        assert isinstance(DEFAULT_SIMILARITY_THRESHOLD, float)
        assert isinstance(DEFAULT_TOP_K, int)

    def test_schemas_import(self):
        """Test schemas import."""
        from app.schemas.qa import QuestionRequest, QuestionResponse

        # Test QuestionRequest
        request = QuestionRequest(
            question="What is diabetes?",
            threshold=0.55,
            top_k=5
        )
        assert request.question == "What is diabetes?"
        assert request.threshold == 0.55
        assert request.top_k == 5

    def test_exceptions_import(self):
        """Test shared exceptions import."""
        from app.core.shared.exceptions import (
            QAServiceException,
            QAModelNotLoadedException,
            ValidationException,
            ServiceUnavailableException
        )

        # Test exception creation
        exc = QAServiceException(
            message="Test error",
            details={"test": "data"},
            error_code="TestError"
        )
        assert exc.message == "Test error"
        assert exc.error_code == "TestError"
        assert exc.details["test"] == "data"


class TestModelLoaderBasic:
    """Test basic ModelLoader functionality."""

    def test_model_loader_init(self):
        """Test ModelLoader initialization."""
        from app.services.qa.model_loader import ModelLoader

        loader = ModelLoader()
        assert loader.model_path is not None
        assert loader.model is None
        assert loader.onnx_session is None
        assert loader.model_loaded is False

    def test_model_loader_custom_path(self):
        """Test ModelLoader with custom path."""
        from app.services.qa.model_loader import ModelLoader

        custom_path = "/tmp/custom_model"
        loader = ModelLoader(model_path=custom_path, use_onnx=True)
        assert loader.model_path == custom_path
        assert loader.use_onnx is True

    def test_get_model_info_default(self):
        """Test get_model_info with default values."""
        from app.services.qa.model_loader import ModelLoader

        loader = ModelLoader()
        info = loader.get_model_info()

        assert info["loaded"] is False
        assert info["path"] == loader.model_path
        assert "model_name" in info
        assert "onnx_enabled" in info
        assert "onnx_available" in info

    def test_is_model_available_default(self):
        """Test is_model_available default behavior."""
        from app.services.qa.model_loader import ModelLoader

        loader = ModelLoader()
        assert loader.is_model_available() is False


class TestErrorContextBasic:
    """Test basic ErrorContext functionality."""

    def test_error_context_import(self):
        """Test ErrorContext imports."""
        from app.core.error_context import ErrorContext

        # Test basic functionality
        request_id = ErrorContext.set_request_id()
        assert request_id is not None

        # Test adding context
        ErrorContext.add_context("test_key", "test_value")
        context = ErrorContext.get_all()
        assert "test_key" in context
        assert context["test_key"] == "test_value"

    def test_error_context_clear(self):
        """Test ErrorContext clearing."""
        from app.core.error_context import ErrorContext

        # Add some context
        ErrorContext.set_request_id()
        ErrorContext.add_context("test", "value")

        # Clear context
        ErrorContext.clear_context()

        # Verify cleared
        context = ErrorContext.get_all()
        assert len(context) == 0


class TestHttpClientBasic:
    """Test basic HTTP client functionality."""

    def test_service_client_import(self):
        """Test ServiceClient import."""
        from app.core.shared.http_client import ServiceClient

        client = ServiceClient("https://test-service.com")
        assert client.base_url == "https://test-service.com"
        assert client.use_iam is False  # Default

    def test_service_client_iam_enabled(self):
        """Test ServiceClient with IAM enabled."""
        from app.core.shared.http_client import ServiceClient

        client = ServiceClient("https://test-service.com", use_iam=True)
        assert client.base_url == "https://test-service.com"
        assert client.use_iam is True

    def test_service_client_headers(self):
        """Test ServiceClient header methods."""
        from app.core.shared.http_client import ServiceClient

        client = ServiceClient("https://test-service.com")
        headers = client._get_headers()
        assert isinstance(headers, dict)
        assert "Content-Type" in headers

        # Test with additional headers
        headers = client._get_headers({"X-Custom": "value"})
        assert headers["X-Custom"] == "value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])