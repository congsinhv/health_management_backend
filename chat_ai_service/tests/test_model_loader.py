"""
Tests for ModelLoader class - handles SBERT model loading and ONNX optimization.
"""

import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock, mock_open
from pathlib import Path

# Import from parent directory
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.services.qa.model_loader import ModelLoader
from app.config import Settings
from app.core.shared.exceptions import (
    QAModelException,
    QAModelNotLoadedException,
    ServiceUnavailableException,
)


class TestModelLoader:
    """Test ModelLoader functionality."""

    def test_init_default(self):
        """Test ModelLoader initialization with default values."""
        loader = ModelLoader()
        assert loader.model_path is not None
        assert loader.use_onnx in [True, False]  # Depends on ONNX availability
        assert loader.model is None
        assert loader.onnx_session is None
        assert loader.model_loaded is False

    def test_init_custom(self):
        """Test ModelLoader initialization with custom values."""
        model_path = "/custom/path"
        loader = ModelLoader(model_path=model_path, use_onnx=True)
        assert loader.model_path == model_path
        assert loader.use_onnx is True

    @patch("app.services.qa.model_loader.SentenceTransformer")
    @patch("app.services.qa.model_loader.Path")
    def test_load_model_success(self, mock_path, mock_sentence_transformer):
        """Test successful model loading from local."""
        # Setup mocks
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.is_dir.return_value = True
        mock_path.return_value = mock_path_instance

        mock_model = MagicMock()
        mock_sentence_transformer.return_value = mock_model

        loader = ModelLoader()
        loader._is_model_complete = MagicMock(return_value=True)

        # Test
        result = loader.load_model()

        assert result == mock_model
        assert loader.model_loaded is True
        assert loader.model == mock_model

    @patch("app.services.qa.model_loader.SentenceTransformer")
    def test_load_model_no_library(self, mock_sentence_transformer):
        """Test model loading when sentence_transformers not available."""
        mock_sentence_transformer.side_effect = ImportError(
            "No module named 'sentence_transformers'"
        )

        loader = ModelLoader()

        with pytest.raises(ImportError, match="sentence_transformers is required"):
            loader.load_model()

    def test_load_model_already_loaded(self):
        """Test that load_model returns cached model if already loaded."""
        loader = ModelLoader()
        mock_model = MagicMock()
        loader.model = mock_model
        loader.model_loaded = True

        result = loader.load_model()
        assert result == mock_model

    @patch("app.services.qa.model_loader.Path")
    @patch("app.services.qa.model_loader.SentenceTransformer")
    def test_load_local_model_success(self, mock_sentence_transformer, mock_path):
        """Test loading model from local directory."""
        # Setup mocks
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.is_dir.return_value = True
        mock_path.return_value = mock_path_instance

        mock_model = MagicMock()
        mock_sentence_transformer.return_value = mock_model

        loader = ModelLoader()
        loader._is_model_complete = MagicMock(return_value=True)

        # Test
        result = loader._load_local_model()

        assert result is True
        assert loader.model_loaded is True
        assert loader.model == mock_model

    @patch("app.services.qa.model_loader.Path")
    def test_load_local_model_not_found(self, mock_path):
        """Test loading model when local model not found."""
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = False
        mock_path.return_value = mock_path_instance

        loader = ModelLoader()
        result = loader._load_local_model()

        assert result is False
        assert loader.model_loaded is False

    @patch("app.services.qa.model_loader.Path")
    @patch("app.services.qa.model_loader.SentenceTransformer")
    def test_load_local_model_incomplete(self, mock_sentence_transformer, mock_path):
        """Test loading model when local model is incomplete."""
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.is_dir.return_value = True
        mock_path.return_value = mock_path_instance

        loader = ModelLoader()
        loader._is_model_complete = MagicMock(return_value=False)

        result = loader._load_local_model()

        assert result is False
        assert loader.model_loaded is False

    def test_is_model_complete_success(self):
        """Test complete model validation."""
        # Create temporary directory with required files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create required files
            required_files = ["config.json", "pytorch_model.bin", "tokenizer.json"]
            for file in required_files:
                Path(temp_dir).joinpath(file).touch()

            loader = ModelLoader(model_path=temp_dir)
            result = loader._is_model_complete()

            assert result is True

    def test_is_model_complete_missing_files(self):
        """Test complete model validation when files are missing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create only some files
            Path(temp_dir).joinpath("config.json").touch()

            loader = ModelLoader(model_path=temp_dir)
            result = loader._is_model_complete()

            assert result is False

    def test_is_model_complete_no_directory(self):
        """Test complete model validation when directory doesn't exist."""
        loader = ModelLoader(model_path="/nonexistent/path")
        result = loader._is_model_complete()

        assert result is False

    @patch("app.services.qa.model_loader.SentenceTransformer")
    def test_download_from_huggingface_success(self, mock_sentence_transformer):
        """Test successful model download from Hugging Face."""
        mock_model = MagicMock()
        mock_sentence_transformer.return_value = mock_model

        loader = ModelLoader()
        loader._save_model_locally = MagicMock(return_value=True)

        result = loader._download_from_huggingface()

        assert result is True
        assert loader.model_loaded is True
        assert loader.model == mock_model
        mock_sentence_transformer.assert_called_once()

    @patch("app.services.qa.model_loader.SentenceTransformer")
    def test_download_from_huggingface_failure(self, mock_sentence_transformer):
        """Test failed model download from Hugging Face."""
        mock_sentence_transformer.side_effect = Exception("Download failed")

        loader = ModelLoader()
        result = loader._download_from_huggingface()

        assert result is False
        assert loader.model_loaded is False

    def test_save_model_locally_success(self):
        """Test successful model saving to local directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_model = MagicMock()
            loader = ModelLoader(model_path=temp_dir)
            loader.model = mock_model

            result = loader._save_model_locally()

            assert result is True
            mock_model.save.assert_called_once_with(temp_dir)

    def test_save_model_locally_no_model(self):
        """Test model saving when no model is loaded."""
        loader = ModelLoader()
        loader.model = None

        result = loader._save_model_locally()

        assert result is False

    def test_save_model_locally_failure(self):
        """Test model saving when saving fails."""
        mock_model = MagicMock()
        mock_model.save.side_effect = Exception("Save failed")

        loader = ModelLoader()
        loader.model = mock_model

        result = loader._save_model_locally()

        assert result is False

    def test_get_model_info_not_loaded(self):
        """Test get_model_info when model is not loaded."""
        loader = ModelLoader()
        info = loader.get_model_info()

        assert info["loaded"] is False
        assert info["path"] == loader.model_path
        assert info["model_name"] is not None
        assert "onnx_enabled" in info

    def test_get_model_info_loaded(self):
        """Test get_model_info when model is loaded."""
        mock_model = MagicMock()
        mock_model.max_seq_length = 512
        mock_model.get_sentence_embedding_dimension.return_value = 768

        loader = ModelLoader()
        loader.model = mock_model
        loader.model_loaded = True

        info = loader.get_model_info()

        assert info["loaded"] is True
        assert info["max_seq_length"] == 512
        assert info["dimension"] == 768

    def test_is_model_available_pytorch(self):
        """Test is_model_available with PyTorch backend."""
        mock_model = MagicMock()
        loader = ModelLoader(use_onnx=False)
        loader.model = mock_model
        loader.model_loaded = True

        assert loader.is_model_available() is True

    def test_is_model_available_onnx(self):
        """Test is_model_available with ONNX backend."""
        mock_session = MagicMock()
        loader = ModelLoader(use_onnx=True)
        loader.onnx_session = mock_session

        assert loader.is_model_available() is True

    def test_is_model_available_not_available(self):
        """Test is_model_available when model is not available."""
        loader = ModelLoader()
        loader.model = None
        loader.onnx_session = None
        loader.model_loaded = False

        assert loader.is_model_available() is False

    def test_get_embeddings_pytorch_success(self):
        """Test successful embedding generation with PyTorch."""
        mock_model = MagicMock()
        mock_embeddings = [[0.1, 0.2, 0.3]]
        mock_model.encode.return_value = mock_embeddings

        loader = ModelLoader(use_onnx=False)
        loader.model = mock_model
        loader.model_loaded = True

        sentences = ["Test sentence"]
        result = loader.get_embeddings(sentences)

        assert result == mock_embeddings
        mock_model.encode.assert_called_once_with(sentences)

    def test_get_embeddings_model_not_loaded(self):
        """Test embedding generation when model is not loaded."""
        loader = ModelLoader()
        loader.model_loaded = False

        with pytest.raises(QAModelException, match="Model not loaded"):
            loader.get_embeddings(["Test sentence"])

    def test_get_embeddings_failure(self):
        """Test embedding generation when embedding fails."""
        mock_model = MagicMock()
        mock_model.encode.side_effect = Exception("Embedding failed")

        loader = ModelLoader()
        loader.model = mock_model
        loader.model_loaded = True

        with pytest.raises(Exception, match="Embedding failed"):
            loader.get_embeddings(["Test sentence"])

    @patch("app.services.qa.model_loader.ort")
    @patch("app.services.qa.model_loader.np")
    @patch("app.services.qa.model_loader.torch")
    def test_load_onnx_model_success(self, mock_torch, mock_np, mock_ort):
        """Test successful ONNX model loading."""
        # Setup mocks
        mock_torch.cuda.is_available.return_value = False
        mock_session = MagicMock()
        mock_session.get_inputs.return_value = [MagicMock()]
        mock_ort.InferenceSession.return_value = mock_session

        with tempfile.TemporaryDirectory() as temp_dir:
            onnx_path = Path(temp_dir) / "model.onnx"
            onnx_path.touch()

            loader = ModelLoader(use_onnx=True)
            result = loader._load_onnx_model(onnx_path)

            assert result == mock_session
            mock_ort.InferenceSession.assert_called_once()

    @patch("app.services.qa.model_loader.ort")
    def test_load_onnx_model_failure(self, mock_ort):
        """Test ONNX model loading failure."""
        mock_ort.InferenceSession.side_effect = Exception("ONNX loading failed")

        with tempfile.TemporaryDirectory() as temp_dir:
            onnx_path = Path(temp_dir) / "model.onnx"
            onnx_path.touch()

            loader = ModelLoader(use_onnx=True)
            result = loader._load_onnx_model(onnx_path)

            assert result is None

    @patch("app.services.qa.model_loader.torch")
    @patch("app.services.qa.model_loader.ort")
    def test_try_optimize_to_onnx_success(self, mock_ort, mock_torch):
        """Test successful model optimization to ONNX."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_model = MagicMock()
            mock_tokenizer = MagicMock()
            mock_tokenizer.return_value = {
                "input_ids": [[1, 2, 3, 4, 5]],
                "attention_mask": [[1, 1, 1, 1, 1]],
            }
            mock_model.tokenizer = mock_tokenizer

            loader = ModelLoader(use_onnx=True)
            loader._try_optimize_to_onnx(mock_model, Path(temp_dir))

            # Check that ONNX file was created
            onnx_path = Path(temp_dir) / "model.onnx"
            assert onnx_path.exists()

    @patch("app.services.qa.model_loader.torch")
    @patch("app.services.qa.model_loader.ort")
    def test_try_optimize_to_onnx_already_exists(self, mock_ort, mock_torch):
        """Test ONNX optimization when ONNX model already exists."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create existing ONNX file
            onnx_path = Path(temp_dir) / "model.onnx"
            onnx_path.touch()

            mock_model = MagicMock()

            loader = ModelLoader(use_onnx=True)
            result = loader._try_optimize_to_onnx(mock_model, Path(temp_dir))

            assert result is True

    @patch("app.services.qa.model_loader.torch")
    def test_try_optimize_to_onnx_no_onnx(self, mock_torch):
        """Test ONNX optimization when ONNX is not available."""
        # Mock ONNX as not available
        with patch("app.services.qa.model_loader.ONNX_AVAILABLE", False):
            mock_model = MagicMock()

            with tempfile.TemporaryDirectory() as temp_dir:
                loader = ModelLoader(use_onnx=True)
                result = loader._try_optimize_to_onnx(mock_model, Path(temp_dir))

                assert result is False

    @patch("app.services.qa.model_loader.np")
    @patch("app.services.qa.model_loader.torch")
    @patch("app.services.qa.model_loader.ort")
    def test_get_embeddings_onnx_success(self, mock_ort, mock_torch, mock_np):
        """Test successful ONNX embedding generation."""
        # Setup mocks
        mock_session = MagicMock()
        mock_outputs = [
            # last_hidden_state
            [[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]]
        ]
        mock_session.run.return_value = mock_outputs
        mock_ort.InferenceSession.return_value = mock_session

        mock_model = MagicMock()
        mock_tokenizer = MagicMock()
        mock_tokenizer.return_value = {
            "input_ids": [[1, 2, 3, 4, 5]],
            "attention_mask": [[1, 1, 1, 1, 1]],
        }
        mock_model.tokenizer = mock_tokenizer

        mock_np.sum.return_value = 1.0
        mock_np.clip.return_value = 1.0

        loader = ModelLoader(use_onnx=True)
        loader.model = mock_model
        loader.onnx_session = mock_session

        sentences = ["Test sentence"]
        result = loader._get_embeddings_onnx(sentences)

        assert isinstance(result, list)

    @patch("app.services.qa.model_loader.SentenceTransformer")
    def test_get_embeddings_onnx_fallback_to_pytorch(self, mock_sentence_transformer):
        """Test ONNX embedding generation falling back to PyTorch."""
        mock_model = MagicMock()
        mock_embeddings = [[0.1, 0.2, 0.3]]
        mock_model.encode.return_value = mock_embeddings
        mock_sentence_transformer.return_value = mock_model

        loader = ModelLoader(use_onnx=True)
        loader.model = mock_model
        loader.onnx_session = None  # ONNX not loaded

        sentences = ["Test sentence"]
        result = loader._get_embeddings_onnx(sentences)

        assert result == mock_embeddings

    def test_get_embeddings_onnx_no_fallback(self):
        """Test ONNX embedding generation with no PyTorch fallback."""
        loader = ModelLoader(use_onnx=True)
        loader.model = None  # No PyTorch model
        loader.onnx_session = None  # No ONNX session

        with pytest.raises(RuntimeError, match="PyTorch model not available"):
            loader._get_embeddings_onnx(["Test sentence"])


class TestModelLoaderEdgeCases:
    """Test edge cases and error conditions."""

    def test_multiple_load_calls(self):
        """Test multiple calls to load_model with caching."""
        mock_model = MagicMock()

        with patch("app.services.qa.model_loader.SentenceTransformer") as mock_st:
            mock_st.return_value = mock_model

            loader = ModelLoader()
            loader._is_model_complete = MagicMock(return_value=True)
            loader._load_local_model = MagicMock(return_value=True)

            # First call
            result1 = loader.load_model()
            assert result1 == mock_model

            # Second call should use cached model
            result2 = loader.load_model()
            assert result2 == mock_model

            # _load_local_model should only be called once
            assert loader._load_local_model.call_count == 1

    def test_path_with_spaces(self):
        """Test model loading with path containing spaces."""
        with tempfile.TemporaryDirectory(suffix=" with spaces") as temp_dir:
            loader = ModelLoader(model_path=temp_dir)
            assert loader.model_path == temp_dir

    def test_empty_model_path(self):
        """Test initialization with empty model path."""
        loader = ModelLoader(model_path="")
        # Should use default path from settings
        assert loader.model_path is not None

    def test_onnx_disabled_but_available(self):
        """Test when ONNX is available but disabled."""
        loader = ModelLoader(use_onnx=False)
        assert loader.use_onnx is False
        assert loader.onnx_session is None
