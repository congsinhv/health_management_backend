"""Test lazy loading behavior of QAService."""
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.services.qa_service import QAService


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock(spec=Settings)
    settings.qa_model_path = "./models/test-model"
    settings.qa_data_path = "test_data.xlsx"
    settings.qa_vocab_path = "test_vocab.txt"
    settings.qa_lazy_loading = True
    settings.qa_model_format = "auto"
    settings.qa_onnx_provider = "CPUExecutionProvider"
    settings.model_auto_download = False
    settings.qa_max_per_field = 3
    settings.openai_api_key = "test-key"
    settings.qa_threshold = 0.55
    settings.qa_top_k = 7
    return settings


@pytest.fixture
def mock_settings_eager():
    """Create mock settings with eager loading."""
    settings = MagicMock(spec=Settings)
    settings.qa_model_path = "./models/test-model"
    settings.qa_data_path = "test_data.xlsx"
    settings.qa_vocab_path = "test_vocab.txt"
    settings.qa_lazy_loading = False
    settings.qa_model_format = "auto"
    settings.qa_onnx_provider = "CPUExecutionProvider"
    settings.model_auto_download = False
    settings.qa_max_per_field = 3
    settings.openai_api_key = "test-key"
    settings.qa_threshold = 0.55
    settings.qa_top_k = 7
    return settings


@pytest.mark.asyncio
async def test_lazy_loading_initialization(mock_settings):
    """Test that initialization is instant with lazy loading."""
    with patch.object(QAService, "_load_all_sync"):
        start = time.time()
        qa_service = QAService(mock_settings)
        elapsed = time.time() - start

        assert elapsed < 0.5, f"Initialization took {elapsed}s, expected <0.5s"
        assert not qa_service._model_loaded, "Model should not be loaded during init"
        assert qa_service._model is None, "Model should be None"
        assert qa_service._df is None, "DataFrame should be None"


@pytest.mark.asyncio
async def test_eager_loading_initialization(mock_settings_eager):
    """Test that eager loading calls _load_all_sync."""
    with patch.object(QAService, "_load_all_sync") as mock_load:
        qa_service = QAService(mock_settings_eager)

        mock_load.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_model_loaded_once():
    """Test that _ensure_model_loaded only loads once."""
    mock_settings = MagicMock()
    mock_settings.qa_lazy_loading = True
    mock_settings.model_auto_download = False
    mock_settings.qa_max_per_field = 3
    mock_settings.openai_api_key = "test-key"

    with patch.object(QAService, "_load_vocab") as mock_vocab, patch.object(
        QAService, "_load_model"
    ) as mock_model, patch.object(QAService, "_load_data") as mock_data:
        mock_vocab.return_value = set()
        mock_model.return_value = MagicMock()
        mock_data.return_value = (MagicMock(), MagicMock())

        qa_service = QAService(mock_settings)

        # First call should load
        await qa_service._ensure_model_loaded()
        assert qa_service._model_loaded
        assert mock_vocab.call_count == 1
        assert mock_model.call_count == 1
        assert mock_data.call_count == 1

        # Second call should not load again
        await qa_service._ensure_model_loaded()
        assert mock_vocab.call_count == 1  # Still 1
        assert mock_model.call_count == 1  # Still 1
        assert mock_data.call_count == 1  # Still 1


@pytest.mark.asyncio
async def test_concurrent_lazy_load():
    """Test that concurrent requests don't load model multiple times."""
    mock_settings = MagicMock()
    mock_settings.qa_lazy_loading = True
    mock_settings.model_auto_download = False
    mock_settings.qa_max_per_field = 3
    mock_settings.openai_api_key = "test-key"

    load_count = 0

    def mock_load_model():
        nonlocal load_count
        load_count += 1
        time.sleep(0.1)  # Simulate slow load
        return MagicMock()

    with patch.object(QAService, "_load_vocab", return_value=set()), patch.object(
        QAService, "_load_model", side_effect=mock_load_model
    ), patch.object(QAService, "_load_data", return_value=(MagicMock(), MagicMock())):
        qa_service = QAService(mock_settings)

        # Simulate 5 concurrent requests
        tasks = [qa_service._ensure_model_loaded() for _ in range(5)]
        await asyncio.gather(*tasks)

        # Model should only load once
        assert load_count == 1, f"Model loaded {load_count} times, expected 1"
        assert qa_service._model_loaded


@pytest.mark.asyncio
async def test_property_accessors_before_load():
    """Test that property accessors raise error before model is loaded."""
    mock_settings = MagicMock()
    mock_settings.qa_lazy_loading = True
    mock_settings.model_auto_download = False
    mock_settings.qa_max_per_field = 3
    mock_settings.openai_api_key = "test-key"

    with patch.object(QAService, "_load_all_sync"):
        qa_service = QAService(mock_settings)

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Model not loaded"):
            _ = qa_service.model

        with pytest.raises(RuntimeError, match="Vocab not loaded"):
            _ = qa_service.vocab

        with pytest.raises(RuntimeError, match="Data not loaded"):
            _ = qa_service.df

        with pytest.raises(RuntimeError, match="Embeddings not loaded"):
            _ = qa_service.question_embeddings


@pytest.mark.asyncio
async def test_property_accessors_after_load():
    """Test that property accessors work after model is loaded."""
    mock_settings = MagicMock()
    mock_settings.qa_lazy_loading = True
    mock_settings.model_auto_download = False
    mock_settings.qa_max_per_field = 3
    mock_settings.openai_api_key = "test-key"

    mock_model = MagicMock()
    mock_vocab = set(["test"])
    mock_df = MagicMock()
    mock_embeddings = MagicMock()

    with patch.object(QAService, "_load_vocab", return_value=mock_vocab), patch.object(
        QAService, "_load_model", return_value=mock_model
    ), patch.object(QAService, "_load_data", return_value=(mock_df, mock_embeddings)):
        qa_service = QAService(mock_settings)
        await qa_service._ensure_model_loaded()

        # Should work fine
        assert qa_service.model is mock_model
        assert qa_service.vocab is mock_vocab
        assert qa_service.df is mock_df
        assert qa_service.question_embeddings is mock_embeddings


@pytest.mark.asyncio
async def test_load_error_handling():
    """Test that loading errors are properly handled."""
    mock_settings = MagicMock()
    mock_settings.qa_lazy_loading = True
    mock_settings.model_auto_download = False
    mock_settings.qa_max_per_field = 3
    mock_settings.openai_api_key = "test-key"

    with patch.object(QAService, "_load_vocab", side_effect=Exception("Load failed")):
        qa_service = QAService(mock_settings)

        with pytest.raises(RuntimeError, match="Q&A service unavailable"):
            await qa_service._ensure_model_loaded()

        # Model should not be marked as loaded
        assert not qa_service._model_loaded
