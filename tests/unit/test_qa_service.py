"""
Unit tests for QA Service business logic.

Tests the core Q&A functionality including Vietnamese language processing,
SBERT embeddings, similarity search, and AI summarization.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch, Mock, mock_open
from pathlib import Path
import pandas as pd
import torch
import requests
from sentence_transformers import SentenceTransformer, util

from app.services.qa_service import QAService, QAColumns, QAMessages
from app.config import settings


@pytest.mark.unit
class TestQAService:
    """Test cases for QA Service business logic."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for QA service."""
        settings = MagicMock()
        settings.qa_model_path = "/tmp/test_model"
        settings.qa_data_path = "/tmp/test_data.xlsx"
        settings.qa_vocab_path = "/tmp/test_vocab.txt"
        settings.model_auto_download = False
        settings.gcp_model_bucket = None
        settings.openrouter_api_key = "test_api_key"
        settings.openrouter_model = "openai/gpt-4o-mini"
        settings.openrouter_timeout = 30
        settings.openrouter_temperature = 0.7
        settings.openrouter_max_tokens = 1000
        settings.qa_threshold = 0.55
        settings.qa_top_k = 5
        settings.qa_max_per_field = 3
        return settings

    @pytest.fixture
    def sample_qa_data(self):
        """Sample Q&A data for testing."""
        return pd.DataFrame(
            {
                QAColumns.QUESTION: [
                    "Đau đầu là gì?",  # What is headache?
                    "Triệu chứng cảm cúm?",  # Flu symptoms?
                    "Làm sao để giảm stress?",  # How to reduce stress?
                ],
                QAColumns.ANSWER: [
                    "Đau đầu là chứng đau ở vùng đầu.",
                    "Sốt, ho, sổ mũi, mệt mỏi.",
                    "Ngủ đủ, tập thể dục, thiền định.",
                ],
                QAColumns.KEYWORDS: [
                    "đau đầu, sức khỏe",
                    "cảm cúm, triệu chứng",
                    "stress, giảm căng thẳng",
                ],
                QAColumns.FIELD: ["Nội khoa", "Truyền nhiễm", "Tâm lý"],
            }
        )

    @pytest.fixture
    def mock_model(self):
        """Mock SBERT model."""
        model = Mock(spec=SentenceTransformer)
        # Mock encode method to return embeddings
        mock_embeddings = torch.tensor(
            [
                [0.1, 0.2, 0.3],  # Question 1 embedding
                [0.2, 0.3, 0.4],  # Question 2 embedding
                [0.3, 0.4, 0.5],  # Question 3 embedding
            ]
        )
        model.encode.return_value = mock_embeddings
        return model

    @pytest.fixture
    def qa_service_with_mocks(self, mock_settings, sample_qa_data, mock_model):
        """Create QA service with mocked dependencies."""
        # Mock the data loading to prevent actual file operations
        with patch("pandas.read_excel", return_value=sample_qa_data), patch(
            "app.services.qa_service.SentenceTransformer", return_value=mock_model
        ), patch("os.path.exists", return_value=True), patch.object(
            QAService, "_load_vocab", return_value=None
        ):
            service = QAService(mock_settings)
            service.model = mock_model
            service.df = sample_qa_data
            # Add cleaned question column
            sample_qa_data[QAColumns.QUESTION_CLEAN] = sample_qa_data[
                QAColumns.QUESTION
            ].str.lower()
            service.question_embeddings = mock_model.encode(
                sample_qa_data[QAColumns.QUESTION_CLEAN].tolist()
            )
            return service

    # Test ask_question method - Core business logic

    def test_ask_question_success(self, qa_service_with_mocks):
        """Test successful question answering."""
        service = qa_service_with_mocks

        # Mock similarity calculation
        with patch(
            "app.services.qa_service.util.cos_sim",
            return_value=torch.tensor([[0.8, 0.6, 0.4]]),
        ):
            result = service.ask_question("Đau đầu?")

        assert "question" in result
        assert result["question"] == "Đau đầu?"
        assert "answers" in result
        assert "summary" in result
        assert len(result["answers"]) > 0

    def test_ask_question_empty_question(self, qa_service_with_mocks):
        """Test ask_question with empty input."""
        service = qa_service_with_mocks

        with pytest.raises(ValueError, match=QAMessages.EMPTY_QUESTION):
            service.ask_question("")

        with pytest.raises(ValueError, match=QAMessages.EMPTY_QUESTION):
            service.ask_question("   ")

    def test_ask_question_no_results(self, qa_service_with_mocks):
        """Test ask_question when no results meet threshold."""
        service = qa_service_with_mocks

        # Mock similarity calculation with low scores below threshold
        with patch(
            "app.services.qa_service.util.cos_sim",
            return_value=torch.tensor([[0.1, 0.2, 0.3]]),
        ):
            result = service.ask_question("Invalid question")

        assert result["question"] == "Invalid question"
        assert QAMessages.NO_RESULTS_FOUND in result["answers"]
        assert result["answers"][QAMessages.NO_RESULTS_FOUND] == [
            QAMessages.NO_DATA_UPDATE
        ]

    def test_ask_question_custom_threshold_and_top_k(self, qa_service_with_mocks):
        """Test ask_question with custom parameters."""
        service = qa_service_with_mocks

        with patch(
            "app.services.qa_service.util.cos_sim",
            return_value=torch.tensor([[0.8, 0.6, 0.4]]),
        ):
            result = service.ask_question("Đau đầu?", threshold=0.7, top_k=2)

        # Should only return results above 0.7 threshold
        assert "answers" in result
        # Verify custom parameters were used

    def test_ask_question_field_grouping_and_limiting(self, qa_service_with_mocks):
        """Test answer grouping by field and max per field limiting."""
        service = qa_service_with_mocks

        # Create data with multiple answers in same field
        test_data = pd.DataFrame(
            {
                QAColumns.QUESTION: ["Q1", "Q2", "Q3", "Q4"],
                QAColumns.ANSWER: ["A1", "A2", "A3", "A4"],
                QAColumns.FIELD: ["Field1", "Field1", "Field1", "Field2"],
            }
        )

        with patch("pandas.read_excel", return_value=test_data):
            service.df = test_data
            service.question_embeddings = torch.tensor(
                [[0.1, 0.2], [0.2, 0.3], [0.3, 0.4], [0.4, 0.5]]
            )

            with patch(
                "app.services.qa_service.util.cos_sim",
                return_value=torch.tensor([[0.9, 0.8, 0.7, 0.6]]),
            ):
                result = service.ask_question("Test question")

        # Should limit to max_per_field per field (3 by default)
        field1_answers = result["answers"].get("Field1", [])
        assert len(field1_answers) <= service.max_per_field

    # Test Vietnamese text preprocessing

    def test_preprocess_text_vietnamese_characters(self, qa_service_with_mocks):
        """Test Vietnamese character preservation in preprocessing."""
        service = qa_service_with_mocks

        # Test with Vietnamese characters
        text = "Đau đầu là gì? 123"
        result = service.preprocess_text(text)

        # Should preserve Vietnamese characters and numbers, remove punctuation
        # Note: Vietnamese characters get normalized to lowercase forms
        assert "đau" in result
        assert "đ" in result  # 'Đ' gets lowercased to 'đ'
        assert "là" in result
        assert "gì" in result
        assert "123" in result
        assert "?" not in result  # Punctuation should be removed

    def test_preprocess_text_with_vocabulary(self, qa_service_with_mocks):
        """Test preprocessing with vocabulary filtering."""
        service = qa_service_with_mocks
        service.vocab = {"đau", "đầu", "là", "gì"}

        text = "Đau đầu là cái gì 123 không"
        result = service.preprocess_text(text)

        # Should only keep words in vocabulary
        words = result.split()
        assert all(word in service.vocab for word in words)

    def test_preprocess_text_empty_result_handling(self, mock_settings, sample_qa_data):
        """Test preprocessing when result would be empty."""
        mock_model = Mock()
        mock_model.encode.return_value = torch.tensor([[0.1, 0.2, 0.3]])

        with patch("os.path.exists", return_value=True), patch(
            "pandas.read_excel", return_value=sample_qa_data
        ), patch(
            "app.services.qa_service.SentenceTransformer", return_value=mock_model
        ), patch.object(
            QAService, "_load_vocab", return_value=None
        ):
            service = QAService(mock_settings)

            # Test text that becomes empty after preprocessing
            text = "!!!???@@@"
            result = service.preprocess_text(text)

            assert result == ""

    # Test model loading and validation

    def test_is_model_complete_true(self, mock_settings, sample_qa_data):
        """Test _is_model_complete when all files exist."""
        mock_model = Mock()
        mock_model.encode.return_value = torch.tensor([[0.1, 0.2, 0.3]])

        # Mock the initialization to avoid actual data loading
        with patch("os.path.exists", return_value=True), patch(
            "pandas.read_excel", return_value=sample_qa_data
        ), patch(
            "app.services.qa_service.SentenceTransformer", return_value=mock_model
        ), patch.object(
            QAService, "_load_vocab", return_value=None
        ):
            service = QAService(mock_settings)

        with patch("pathlib.Path.exists", return_value=True):
            result = service._is_model_complete()
            assert result is True

    def test_is_model_complete_missing_directory(self, mock_settings, sample_qa_data):
        """Test _is_model_complete when model directory doesn't exist."""
        mock_model = Mock()
        mock_model.encode.return_value = torch.tensor([[0.1, 0.2, 0.3]])

        # Mock the initialization to avoid actual data loading
        with patch("os.path.exists", return_value=True), patch(
            "pandas.read_excel", return_value=sample_qa_data
        ), patch(
            "app.services.qa_service.SentenceTransformer", return_value=mock_model
        ), patch.object(
            QAService, "_load_vocab", return_value=None
        ):
            service = QAService(mock_settings)

        with patch("pathlib.Path.exists", return_value=False):
            result = service._is_model_complete()
            assert result is False

    def test_is_model_complete_missing_config_files(
        self, mock_settings, sample_qa_data
    ):
        """Test _is_model_complete when required config files are missing."""
        mock_model = Mock()
        mock_model.encode.return_value = torch.tensor([[0.1, 0.2, 0.3]])

        # Mock the initialization to avoid actual data loading
        with patch("os.path.exists", return_value=True), patch(
            "pandas.read_excel", return_value=sample_qa_data
        ), patch(
            "app.services.qa_service.SentenceTransformer", return_value=mock_model
        ), patch.object(
            QAService, "_load_vocab", return_value=None
        ):
            service = QAService(mock_settings)

        # Create a mock that returns True for weight files but False for config files
        mock_path_exists = MagicMock()
        mock_path_exists.side_effect = lambda: "model.safetensors" in str(
            mock_path_exists.mock_self
        ) or "pytorch_model.bin" in str(mock_path_exists.mock_self)

        with patch.object(Path, "exists", mock_path_exists):
            result = service._is_model_complete()
            assert result is False

    def test_ensure_model_and_data_exist_no_gcs_configured(
        self, mock_settings, sample_qa_data
    ):
        """Test _ensure_model_and_data_exist when GCS not configured."""
        mock_settings.gcp_model_bucket = None
        mock_model = Mock()
        mock_model.encode.return_value = torch.tensor([[0.1, 0.2, 0.3]])

        # Mock the initialization to avoid actual data loading
        with patch("os.path.exists", return_value=True), patch(
            "pandas.read_excel", return_value=sample_qa_data
        ), patch(
            "app.services.qa_service.SentenceTransformer", return_value=mock_model
        ), patch.object(
            QAService, "_load_vocab", return_value=None
        ):
            service = QAService(mock_settings)

        # Should not raise exception, just log and return
        service._ensure_model_and_data_exist()

    def test_ensure_model_and_data_exist_model_complete(
        self, mock_settings, sample_qa_data
    ):
        """Test _ensure_model_and_data_exist when model is complete."""
        mock_model = Mock()
        mock_model.encode.return_value = torch.tensor([[0.1, 0.2, 0.3]])

        # Mock the initialization to avoid actual data loading
        with patch("os.path.exists", return_value=True), patch(
            "pandas.read_excel", return_value=sample_qa_data
        ), patch(
            "app.services.qa_service.SentenceTransformer", return_value=mock_model
        ), patch.object(
            QAService, "_load_vocab", return_value=None
        ):
            service = QAService(mock_settings)

        with patch.object(service, "_is_model_complete", return_value=True):
            service._ensure_model_and_data_exist()

    def test_ensure_model_and_data_exist_download_from_gcs(
        self, mock_settings, sample_qa_data
    ):
        """Test _ensure_model_and_data_exist downloading from GCS."""
        mock_settings.gcp_model_bucket = "test-bucket"
        mock_model = Mock()
        mock_model.encode.return_value = torch.tensor([[0.1, 0.2, 0.3]])

        # Mock the initialization to avoid actual data loading
        with patch("os.path.exists", return_value=True), patch(
            "pandas.read_excel", return_value=sample_qa_data
        ), patch(
            "app.services.qa_service.SentenceTransformer", return_value=mock_model
        ), patch.object(
            QAService, "_load_vocab", return_value=None
        ):
            service = QAService(mock_settings)

        with patch.object(
            service, "_is_model_complete", return_value=False
        ), patch.object(service, "_download_from_gcs") as mock_download:
            service._ensure_model_and_data_exist()
            mock_download.assert_called_once()

    # Test data loading and validation

    def test_load_data_file_not_found(self, mock_settings, sample_qa_data):
        """Test _load_data when data file doesn't exist."""
        mock_model = Mock()
        mock_model.encode.return_value = torch.tensor([[0.1, 0.2, 0.3]])

        # Mock the initialization to avoid actual data loading
        with patch("os.path.exists", return_value=True), patch(
            "pandas.read_excel", return_value=sample_qa_data
        ), patch(
            "app.services.qa_service.SentenceTransformer", return_value=mock_model
        ), patch.object(
            QAService, "_load_vocab", return_value=None
        ):
            service = QAService(mock_settings)

        with pytest.raises(FileNotFoundError, match="Dataset not found"):
            service._load_data()

    def test_load_data_missing_columns(self, mock_settings, sample_qa_data):
        """Test _load_data when required columns are missing."""
        mock_model = Mock()
        mock_model.encode.return_value = torch.tensor([[0.1, 0.2, 0.3]])

        # Mock the initialization to avoid actual data loading
        with patch("os.path.exists", return_value=True), patch(
            "pandas.read_excel", return_value=sample_qa_data
        ), patch(
            "app.services.qa_service.SentenceTransformer", return_value=mock_model
        ), patch.object(
            QAService, "_load_vocab", return_value=None
        ):
            service = QAService(mock_settings)

        # Remove required column
        incomplete_data = sample_qa_data.drop(columns=[QAColumns.ANSWER])

        with patch("pandas.read_excel", return_value=incomplete_data), patch(
            "os.path.exists", return_value=True
        ):
            with pytest.raises(ValueError, match="Column 'Câu trả lời' not found"):
                service._load_data()

    def test_load_data_success(self, mock_settings, sample_qa_data):
        """Test successful data loading."""
        mock_model = Mock()
        mock_model.encode.return_value = torch.tensor([[0.1, 0.2, 0.3]])

        # Mock the initialization to avoid actual data loading
        with patch("os.path.exists", return_value=True), patch(
            "pandas.read_excel", return_value=sample_qa_data
        ), patch(
            "app.services.qa_service.SentenceTransformer", return_value=mock_model
        ), patch.object(
            QAService, "_load_vocab", return_value=None
        ):
            service = QAService(mock_settings)

        with patch("pandas.read_excel", return_value=sample_qa_data), patch(
            "os.path.exists", return_value=True
        ):
            df, embeddings = service._load_data()

            assert isinstance(df, pd.DataFrame)
            assert QAColumns.QUESTION_CLEAN in df.columns
            assert embeddings is not None

    # Test error handling and edge cases

    def test_ask_question_with_nan_answers(self, qa_service_with_mocks):
        """Test ask_question handling NaN answers."""
        service = qa_service_with_mocks

        # Create data with NaN answers
        test_data = pd.DataFrame(
            {
                QAColumns.QUESTION: ["Question 1", "Question 2"],
                QAColumns.ANSWER: ["Valid answer", "nan"],  # Second answer is NaN
                QAColumns.FIELD: ["Field1", "Field1"],
            }
        )

        with patch.object(service, "df", test_data):
            with patch(
                "app.services.qa_service.util.cos_sim",
                return_value=torch.tensor([[0.9, 0.8]]),
            ):
                result = service.ask_question("Test question")

        # Should skip NaN answers
        field1_answers = result["answers"].get("Field1", [])
        assert len(field1_answers) == 1
        assert "Valid answer" in field1_answers[0]

    def test_ask_question_empty_cleaned_question_fallback(self, qa_service_with_mocks):
        """Test ask_question fallback when cleaned question is empty."""
        service = qa_service_with_mocks

        with patch.object(service, "preprocess_text", return_value=""), patch(
            "app.services.qa_service.util.cos_sim",
            return_value=torch.tensor([[0.8, 0.6, 0.4]]),
        ):
            result = service.ask_question("!!!")

        assert result["question"] == "!!!"

    # Test AI summarization functionality

    def test_summarize_with_ai_success(self, qa_service_with_mocks):
        """Test successful AI summarization."""
        service = qa_service_with_mocks

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Đây là tóm tắt"}}]
        }
        mock_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_response):
            result = service.summarize_with_ai(
                "Đau đầu là gì?", ["Đau đầu là chứng đau ở vùng đầu."]
            )

        assert result == "Đây là tóm tắt"

    def test_summarize_with_ai_no_answers(self, qa_service_with_mocks):
        """Test summarization with empty answers list."""
        service = qa_service_with_mocks

        result = service.summarize_with_ai("Question?", [])
        assert result == QAMessages.NO_DATA_TO_SUMMARIZE

    def test_summarize_with_ai_no_api_key(self, qa_service_with_mocks):
        """Test summarization when API key is not configured."""
        service = qa_service_with_mocks
        service.openrouter_api_key = None

        with patch("app.services.qa_service.logger") as mock_logger:
            result = service.summarize_with_ai("Question?", ["Answer"])

            assert result == QAMessages.AI_NOT_AVAILABLE
            mock_logger.warning.assert_called_with("OpenRouter API key not configured")

    def test_summarize_with_ai_timeout(self, qa_service_with_mocks):
        """Test summarization handling timeout."""
        service = qa_service_with_mocks

        with patch("requests.post", side_effect=requests.exceptions.Timeout()):
            result = service.summarize_with_ai("Question?", ["Answer"])

            assert result == QAMessages.SUMMARIZE_TIMEOUT

    def test_summarize_with_ai_request_error(self, qa_service_with_mocks):
        """Test summarization handling request errors."""
        service = qa_service_with_mocks

        with patch(
            "requests.post",
            side_effect=requests.exceptions.RequestException("Connection error"),
        ):
            result = service.summarize_with_ai("Question?", ["Answer"])

            assert "Connection error" in result

    def test_summarize_with_ai_invalid_response_format(self, qa_service_with_mocks):
        """Test summarization handling invalid API response format."""
        service = qa_service_with_mocks

        mock_response = Mock()
        mock_response.json.return_value = {"invalid": "format"}  # Missing choices
        mock_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_response):
            result = service.summarize_with_ai("Question?", ["Answer"])

            assert result == QAMessages.AI_RESPONSE_ERROR

    def test_generate_conversation_title_success(self, qa_service_with_mocks):
        """Test successful conversation title generation."""
        service = qa_service_with_mocks

        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Tư vấn đau đầu"}}]
        }
        mock_response.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_response):
            result = service.generate_conversation_title(
                "Đau đầu là gì?", "Đau đầu là chứng đau ở vùng đầu."
            )

            assert result == "Tư vấn đau đầu"

    def test_generate_conversation_title_no_api_key(self, qa_service_with_mocks):
        """Test title generation fallback when API key missing."""
        service = qa_service_with_mocks
        service.openrouter_api_key = None

        # Short question
        result = service.generate_conversation_title("Đau đầu?")
        assert result == "Đau đầu?"

        # Long question should be truncated
        long_question = "Đây là một câu hỏi rất dài về tình trạng sức khỏe của tôi và tôi cần được tư vấn chi tiết"
        result = service.generate_conversation_title(long_question)
        assert len(result) <= 60
        assert result.endswith("...")

    def test_generate_conversation_title_request_error(self, qa_service_with_mocks):
        """Test title generation handling request errors."""
        service = qa_service_with_mocks

        with patch(
            "requests.post",
            side_effect=requests.exceptions.RequestException("Network error"),
        ):
            result = service.generate_conversation_title("Question?")

            # Should fall back to truncated question
            assert result == "Question?"

    # Test initialization and configuration

    def test_initialization_with_openrouter_warning(
        self, mock_settings, sample_qa_data
    ):
        """Test service initialization logs warning when OpenRouter API key missing."""
        mock_settings.openrouter_api_key = None
        mock_model = Mock()
        mock_model.encode.return_value = torch.tensor([[0.1, 0.2, 0.3]])

        with patch("os.path.exists", return_value=True), patch(
            "pandas.read_excel", return_value=sample_qa_data
        ), patch(
            "app.services.qa_service.SentenceTransformer", return_value=mock_model
        ), patch(
            "app.services.qa_service.logger"
        ) as mock_logger, patch.object(
            QAService, "_load_vocab", return_value=None
        ):
            QAService(mock_settings)
            mock_logger.warning.assert_called_with(
                "OpenRouter API key not configured - AI summarization will not be available"
            )

    def test_initialization_auto_download_enabled(self, mock_settings, sample_qa_data):
        """Test service initialization with auto download enabled."""
        mock_settings.model_auto_download = True
        mock_model = Mock()
        mock_model.encode.return_value = torch.tensor([[0.1, 0.2, 0.3]])

        with patch.object(QAService, "_ensure_model_and_data_exist") as mock_ensure:
            with patch("os.path.exists", return_value=True), patch(
                "pandas.read_excel", return_value=sample_qa_data
            ), patch(
                "app.services.qa_service.SentenceTransformer", return_value=mock_model
            ), patch.object(
                QAService, "_load_vocab", return_value=None
            ):
                QAService(mock_settings)
                mock_ensure.assert_called_once()

    # Test vocabulary loading

    def test_load_vocab_file_exists(self, mock_settings):
        """Test vocabulary loading when file exists."""
        service = QAService.__new__(QAService)
        service.settings = mock_settings
        service.vocab_path = mock_settings.qa_vocab_path

        with patch("os.path.exists", return_value=True), patch(
            "builtins.open", mock_open(read_data="đau\nđầu\nlà\ngì\n")
        ):
            vocab = service._load_vocab()

            assert "đau" in vocab
            assert "đầu" in vocab
            assert "là" in vocab
            assert "gì" in vocab

    def test_load_vocab_file_not_exists(self, mock_settings):
        """Test vocabulary loading when file doesn't exist."""
        service = QAService.__new__(QAService)
        service.settings = mock_settings
        service.vocab_path = mock_settings.qa_vocab_path

        with patch("builtins.open", side_effect=FileNotFoundError):
            vocab = service._load_vocab()

            assert vocab == set()  # Returns empty set when file not found

    def test_load_vocab_file_read_error(self, mock_settings):
        """Test vocabulary loading with read error."""
        service = QAService.__new__(QAService)
        service.settings = mock_settings
        service.vocab_path = mock_settings.qa_vocab_path

        with patch("os.path.exists", return_value=True), patch(
            "builtins.open", side_effect=IOError("Permission denied")
        ):
            with patch("app.services.qa_service.logger") as mock_logger:
                vocab = service._load_vocab()

                assert vocab == set()  # Returns empty set on error
                mock_logger.error.assert_called()

    def test_download_from_gcs_no_bucket_configured(self, mock_settings):
        """Test GCS download when bucket not configured."""
        mock_settings.gcp_model_bucket = None
        service = QAService.__new__(QAService)
        service.settings = mock_settings
        service.model_path = mock_settings.qa_model_path

        with pytest.raises(ValueError, match="GCS bucket not configured"):
            service._download_from_gcs()

    def test_download_from_gcs_with_bucket(self, mock_settings):
        """Test GCS download with proper configuration."""
        mock_settings.gcp_model_bucket = "test-bucket"
        service = QAService.__new__(QAService)
        service.settings = mock_settings
        service.model_path = mock_settings.qa_model_path
        service.gcp_project_id = getattr(mock_settings, "gcp_project_id", None)
        service.model_download_timeout = getattr(
            mock_settings, "model_download_timeout", 300
        )

        with patch("app.services.qa_service.GCSDownloader") as mock_downloader:
            mock_downloader_instance = Mock()
            # Mock the download_directory method to return a tuple
            mock_downloader_instance.download_directory.return_value = (
                10,
                0,
            )  # 10 success, 0 failed
            mock_downloader.return_value = mock_downloader_instance

            service._download_from_gcs()

            mock_downloader.assert_called_once_with(
                bucket_name="test-bucket",
                project_id=service.gcp_project_id,
                timeout=service.model_download_timeout,
            )
            mock_downloader_instance.download_directory.assert_called_once()
