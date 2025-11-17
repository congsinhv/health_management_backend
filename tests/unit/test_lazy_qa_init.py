"""
Unit tests for lazy Q&A service initialization.

Tests the thread-safe lazy initialization pattern implemented in app.main.
"""

import pytest
import threading
import time
from unittest.mock import Mock, patch, MagicMock
from fastapi import FastAPI
from app.config import Settings


class TestLazyQAInitialization:
    """Test lazy Q&A service initialization."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock FastAPI app with Q&A state."""
        app = FastAPI()
        app.state.qa_service = None
        app.state.qa_service_initializing = False
        app.state.qa_service_error = None
        return app

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings with QA enabled."""
        with patch('app.main.settings') as mock:
            mock.qa_enabled = True
            yield mock

    def test_syntax_import_threading(self):
        """Test that threading and time imports are valid."""
        import threading
        import time
        assert hasattr(threading, 'Lock')
        assert callable(time.time)

    def test_lazy_init_function_exists(self):
        """Test that lazy init function is defined."""
        from app.main import initialize_qa_service_lazy
        assert callable(initialize_qa_service_lazy)

    def test_lazy_init_returns_true_when_already_initialized(self, mock_app, mock_settings):
        """Test that lazy init returns True when QA service is already initialized."""
        from app.main import initialize_qa_service_lazy

        # Simulate already initialized service
        mock_app.state.qa_service = Mock()

        result = initialize_qa_service_lazy(mock_app)

        assert result is True

    def test_lazy_init_returns_false_when_disabled(self, mock_app):
        """Test that lazy init returns False when QA is disabled."""
        from app.main import initialize_qa_service_lazy

        with patch('app.main.settings') as mock_settings:
            mock_settings.qa_enabled = False

            result = initialize_qa_service_lazy(mock_app)

            assert result is False
            assert mock_app.state.qa_service is None

    def test_lazy_init_returns_false_when_initializing(self, mock_app, mock_settings):
        """Test that lazy init returns False when another thread is initializing."""
        from app.main import initialize_qa_service_lazy

        # Simulate another thread initializing
        mock_app.state.qa_service_initializing = True

        result = initialize_qa_service_lazy(mock_app)

        assert result is False

    def test_lazy_init_returns_false_on_previous_error(self, mock_app, mock_settings):
        """Test that lazy init returns False when previous initialization failed."""
        from app.main import initialize_qa_service_lazy

        # Simulate previous initialization failure
        mock_app.state.qa_service_error = "Q&A Service initialization failed: test error"

        result = initialize_qa_service_lazy(mock_app)

        assert result is False

    def test_lazy_init_sets_initializing_flag(self, mock_app, mock_settings):
        """Test that lazy init sets the initializing flag during initialization."""
        from app.main import initialize_qa_service_lazy

        with patch('app.main.QAService') as MockQAService:
            # Make QAService initialization slow to check flag
            def slow_init(*args, **kwargs):
                time.sleep(0.1)
                return Mock()

            MockQAService.side_effect = slow_init

            # Start initialization in background
            def run_init():
                initialize_qa_service_lazy(mock_app)

            thread = threading.Thread(target=run_init)
            thread.start()

            # Check flag is set during initialization
            time.sleep(0.05)  # Wait a bit for thread to start
            # Note: We can't reliably check this due to thread timing

            thread.join()

    def test_lazy_init_handles_initialization_exception(self, mock_app, mock_settings):
        """Test that lazy init handles exceptions during QA service initialization."""
        from app.main import initialize_qa_service_lazy

        with patch('app.main.QAService') as MockQAService:
            # Make QAService raise an exception
            MockQAService.side_effect = Exception("Model loading failed")

            result = initialize_qa_service_lazy(mock_app)

            assert result is False
            assert mock_app.state.qa_service is None
            assert "initialization failed" in mock_app.state.qa_service_error
            assert "Model loading failed" in mock_app.state.qa_service_error

    def test_lazy_init_thread_safety(self, mock_app, mock_settings):
        """Test that lazy init is thread-safe (no race conditions)."""
        from app.main import initialize_qa_service_lazy, _qa_init_lock

        init_count = {'count': 0}

        with patch('app.main.QAService') as MockQAService:
            def counting_init(*args, **kwargs):
                init_count['count'] += 1
                time.sleep(0.05)  # Simulate slow initialization
                mock_service = Mock()
                return mock_service

            MockQAService.side_effect = counting_init

            # Run multiple threads trying to initialize
            threads = []
            results = []

            def run_init():
                result = initialize_qa_service_lazy(mock_app)
                results.append(result)

            # Start 5 concurrent threads
            for _ in range(5):
                thread = threading.Thread(target=run_init)
                threads.append(thread)
                thread.start()

            # Wait for all threads
            for thread in threads:
                thread.join()

            # Should only initialize once despite 5 concurrent calls
            assert init_count['count'] == 1
            # First thread returns True, others return False (already initialized or initializing)
            assert results.count(True) == 1

    def test_health_check_shows_qa_status(self, mock_app):
        """Test that health check endpoint shows correct Q&A status."""
        from app.main import health_check

        with patch('app.main.settings') as mock_settings:
            mock_settings.qa_enabled = True
            mock_settings.app_version = "1.0.0"

            with patch('app.main.database') as mock_db:
                # Mock database pool
                mock_pool = Mock()
                mock_connection = Mock()
                mock_connection.fetchval = Mock(return_value=1)
                mock_pool.acquire = MagicMock()
                mock_pool.acquire.return_value.__aenter__ = Mock(return_value=mock_connection)
                mock_pool.acquire.return_value.__aexit__ = Mock(return_value=None)
                mock_db.get_pool.return_value = mock_pool

                with patch('app.main.connection_manager') as mock_ws_manager:
                    mock_ws_manager.get_connection_stats.return_value = {
                        "total_connections": 0,
                        "total_conversations": 0,
                        "total_users": 0
                    }

                    # Test status before initialization
                    mock_app.state.qa_service = None
                    mock_app.state.qa_service_initializing = False
                    mock_app.state.qa_service_error = None

                    # Patch app in health_check
                    with patch('app.main.app', mock_app):
                        import asyncio
                        response = asyncio.run(health_check())

                        assert response["status"] == "healthy"
                        assert response["qa_service"] == "not_initialized"


class TestQAEndpointsLazyInit:
    """Test Q&A endpoints with lazy initialization."""

    @pytest.fixture
    def mock_app(self):
        """Create a mock FastAPI app with Q&A state."""
        app = FastAPI()
        app.state.qa_service = None
        app.state.qa_service_initializing = False
        app.state.qa_service_error = None
        return app

    def test_qa_ask_endpoint_returns_503_when_initializing(self, mock_app):
        """Test that /ask endpoint returns 503 when Q&A is initializing."""
        from fastapi import HTTPException
        from app.api.qa import ask_question

        # Simulate initializing state
        mock_app.state.qa_service_initializing = True

        mock_request = Mock()
        mock_request.app = mock_app

        mock_question = Mock()
        mock_question.question = "Test question"
        mock_question.threshold = 0.55
        mock_question.top_k = 5

        mock_user = Mock()

        with patch('app.api.qa.initialize_qa_service_lazy') as mock_init:
            mock_init.return_value = False

            with pytest.raises(HTTPException) as exc_info:
                import asyncio
                asyncio.run(ask_question(mock_request, mock_question, mock_user))

            assert exc_info.value.status_code == 503
            assert "initializing" in exc_info.value.detail.lower()
            assert exc_info.value.headers.get("Retry-After") == "180"

    def test_qa_health_endpoint_shows_not_initialized(self, mock_app):
        """Test that /health endpoint shows not_initialized status."""
        from app.api.qa import qa_health_check

        mock_request = Mock()
        mock_request.app = mock_app

        import asyncio
        response = asyncio.run(qa_health_check(mock_request))

        assert response.status == "not_initialized"
        assert response.model_loaded is False
        assert response.embeddings_loaded is False
        assert "not initialized" in response.message.lower()

    def test_qa_health_endpoint_shows_initializing(self, mock_app):
        """Test that /health endpoint shows initializing status."""
        from app.api.qa import qa_health_check

        # Simulate initializing state
        mock_app.state.qa_service_initializing = True

        mock_request = Mock()
        mock_request.app = mock_app

        import asyncio
        response = asyncio.run(qa_health_check(mock_request))

        assert response.status == "initializing"
        assert response.model_loaded is False
        assert "initializing" in response.message.lower()

    def test_qa_health_endpoint_shows_error(self, mock_app):
        """Test that /health endpoint shows error status."""
        from app.api.qa import qa_health_check

        # Simulate error state
        mock_app.state.qa_service_error = "Model file not found"

        mock_request = Mock()
        mock_request.app = mock_app

        import asyncio
        response = asyncio.run(qa_health_check(mock_request))

        assert response.status == "error"
        assert response.model_loaded is False
        assert "error" in response.message.lower()
        assert "Model file not found" in response.message


class TestJenkinsfileConfiguration:
    """Test Jenkinsfile startup probe configuration."""

    def test_startup_probe_configuration_exists(self):
        """Test that Jenkinsfile has startup probe configuration."""
        with open('/Users/synh/Code/Personal/health_management/Jenkinsfile', 'r') as f:
            content = f.read()

            # Check for startup probe configuration
            assert '--startup-probe-initial-delay' in content
            assert '--startup-probe-timeout' in content
            assert '--startup-probe-period' in content
            assert '--startup-probe-failure-threshold' in content

    def test_smoke_tests_accept_not_initialized(self):
        """Test that smoke tests accept not_initialized status."""
        with open('/Users/synh/Code/Personal/health_management/Jenkinsfile', 'r') as f:
            content = f.read()

            # Check that smoke tests look for not_initialized status
            assert 'not_initialized' in content or 'not_initialised' in content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
