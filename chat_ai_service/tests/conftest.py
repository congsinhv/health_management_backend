"""
Test configuration and fixtures for Chat AI service tests.
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

# Import from the parent directory
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.main import create_qa_app
from app.config import Settings, get_settings
from app.services.qa.model_loader import ModelLoader


@pytest.fixture
def temp_model_dir():
    """Create temporary directory for model files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    return Settings(
        DEBUG=True,
        LOG_LEVEL="DEBUG",
        qa_model_path=tempfile.gettempdir(),
        model_auto_download=False,
        OPENAI_API_KEY="test-key",
        CORS_ORIGINS=["http://localhost:3000"],
        ENABLE_REDIS_CACHE=False,
        qa_enabled=True,
        GCP_PROJECT_ID="test-project",
        GCP_MODEL_BUCKET="test-bucket"
    )


@pytest.fixture
def mock_model_loader():
    """Mock model loader for testing."""
    loader = MagicMock()
    loader.model = MagicMock()
    loader.model_loaded = True
    loader.onnx_session = MagicMock()
    loader.load_model = MagicMock(return_value=MagicMock())
    loader.get_embeddings = MagicMock(return_value=[[0.1, 0.2, 0.3]])
    loader.is_model_available = MagicMock(return_value=True)
    loader.get_model_info = MagicMock(return_value={
        "loaded": True,
        "model_name": "test-model",
        "onnx_enabled": False,
        "dimension": 768
    })
    return loader


@pytest.fixture
def mock_qa_service():
    """Mock QA service for testing."""
    service = AsyncMock()
    service.model = MagicMock()
    service.question_embeddings = MagicMock()
    service.openai_client = MagicMock()
    service.df = MagicMock()
    service.ai_summarizer = MagicMock()
    service.initialize = AsyncMock()
    service.get_health_check = MagicMock(return_value={
        "status": "healthy",
        "components": {
            "model_loaded": True,
            "embeddings_ready": True,
            "ai_available": True
        }
    })
    service.get_service_status = MagicMock(return_value={
        "status": "healthy",
        "model_loaded": True,
        "embeddings_ready": True,
        "streaming_enabled": True,
        "openai_configured": True,
        "model_info": {
            "name": "test-model",
            "dimension": 768,
            "max_seq_length": 512
        }
    })
    service.ask_question_stream = AsyncMock()
    return service


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for testing."""
    client = MagicMock()
    chat = MagicMock()
    completions = MagicMock()
    chat.completions = completions

    # Mock streaming response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].delta.content = "Test response chunk"
    mock_response.choices[0].delta.finish_reason = None

    completions.create = MagicMock(return_value=mock_response)
    client.chat = chat
    return client


@pytest.fixture
def async_qa_app(mock_qa_service, mock_settings):
    """Create AsyncClient for testing QA endpoints."""
    # Create test app
    app = create_qa_app()

    # Mock the QA service on app state
    app.state.qa_service = mock_qa_service

    # Create client
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    yield client

    # Cleanup
    app.state.qa_service = None


@pytest.fixture
def mock_sentence_transformer():
    """Mock sentence transformer for testing."""
    model = MagicMock()
    model.encode = MagicMock(return_value=[[0.1, 0.2, 0.3]])
    model.get_sentence_embedding_dimension = MagicMock(return_value=768)
    model.max_seq_length = 512
    model.tokenizer = MagicMock()
    model.tokenizer = MagicMock()
    model.tokenizer.return_value = {
        "input_ids": [[1, 2, 3, 4, 5]],
        "attention_mask": [[1, 1, 1, 1, 1]]
    }
    return model


@pytest.fixture
def mock_dataset():
    """Mock dataset for Q&A service."""
    import pandas as pd
    df = pd.DataFrame({
        'Question': ['What is diabetes?', 'How to prevent diabetes?'],
        'Answer': ['Diabetes is a metabolic disease...', 'To prevent diabetes...'],
        'Field': ['health', 'health']
    })
    return df


@pytest.fixture
def sample_question_request():
    """Sample question request for testing."""
    from app.schemas.qa import QuestionRequest
    return QuestionRequest(
        question="What is diabetes?",
        threshold=0.55,
        top_k=5
    )


@pytest.fixture
def sample_question_response():
    """Sample question response for testing."""
    from app.schemas.qa import QuestionResponse
    return QuestionResponse(
        question="What is diabetes?",
        answers={
            "health": ["Diabetes is a metabolic disease that affects blood sugar levels."]
        },
        summary="Diabetes is a metabolic disease that affects blood sugar levels."
    )


@pytest.fixture
def mock_onnx_session():
    """Mock ONNX Runtime session."""
    session = MagicMock()
    session.run = MagicMock(return_value=[
        # Mock last_hidden_state
        [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    ])
    session.get_inputs = MagicMock(return_value=[MagicMock()])
    session.get_inputs.return_value = [MagicMock(name="input_ids"), MagicMock(name="attention_mask")]
    return session


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# Mock patches for testing
@pytest.fixture(autouse=True)
def mock_environment():
    """Mock environment variables for testing."""
    with patch.dict(os.environ, {
        'DEBUG': 'true',
        'LOG_LEVEL': 'DEBUG',
        'OPENAI_API_KEY': 'test-key',
        'QA_ENABLED': 'true',
        'MODEL_AUTO_DOWNLOAD': 'false'
    }):
        yield


@pytest.fixture
def mock_torch():
    """Mock torch for testing."""
    torch_mock = MagicMock()
    torch_mock.cuda.is_available.return_value = False
    torch_mock.onnx.export = MagicMock()

    with patch.dict('sys.modules', {'torch': torch_mock}):
        yield torch_mock


@pytest.fixture
def mock_numpy():
    """Mock numpy for testing."""
    np_mock = MagicMock()
    np_mock.sum = MagicMock(return_value=1.0)
    np_mock.clip = MagicMock(return_value=1.0)

    with patch.dict('sys.modules', {'numpy': np_mock}):
        yield np_mock


@pytest.fixture
def mock_sentence_transformers():
    """Mock sentence_transformers for testing."""
    st_mock = MagicMock()
    st_mock.SentenceTransformer = MagicMock()

    with patch.dict('sys.modules', {'sentence_transformers': st_mock}):
        yield st_mock


@pytest.fixture
def mock_onnxruntime():
    """Mock onnxruntime for testing."""
    ort_mock = MagicMock()
    ort_mock.InferenceSession = MagicMock()

    with patch.dict('sys.modules', {'onnxruntime': ort_mock}):
        yield ort_mock


# Error testing fixtures
@pytest.fixture
def mock_model_load_error():
    """Mock model loader that raises an error."""
    loader = MagicMock()
    loader.load_model = MagicMock(side_effect=Exception("Model loading failed"))
    loader.is_model_available = MagicMock(return_value=False)
    loader.model_loaded = False
    return loader


@pytest.fixture
def mock_openai_error():
    """Mock OpenAI client that raises an error."""
    client = MagicMock()
    client.chat.completions.create.side_effect = Exception("OpenAI API error")
    return client


@pytest.fixture
def mock_dataset_error():
    """Mock dataset loading error."""
    with patch('pandas.read_csv', side_effect=Exception("Dataset loading failed")):
        yield


# Performance testing fixtures
@pytest.fixture
def performance_timer():
    """Timer for performance testing."""
    import time

    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.time()

        def stop(self):
            self.end_time = time.time()

        @property
        def duration(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return 0

    return Timer()


@pytest.fixture
def large_batch_questions():
    """Large batch of questions for performance testing."""
    return [
        f"Test question {i}: What is the health benefit of {['exercise', 'diet', 'sleep', 'meditation', 'hydration'][i % 5]}?"
        for i in range(100)
    ]