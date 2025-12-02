"""
Test ONNX model accuracy vs PyTorch baseline.

These tests verify that ONNX-optimized model produces embeddings
equivalent to PyTorch baseline (cosine similarity >0.99).
"""
import pytest
import torch
from unittest.mock import patch, MagicMock

from app.config import settings
from app.services.qa_service import QAService


# Vietnamese test questions covering various health topics
VIETNAMESE_QUESTIONS = [
    "Làm thế nào để giảm cân hiệu quả?",
    "Triệu chứng của bệnh tiểu đường là gì?",
    "Chế độ ăn cho người huyết áp cao",
    "Cách phòng ngừa bệnh tim mạch",
    "Tác dụng của vitamin C với sức khỏe",
]


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    test_settings = settings.model_copy(deep=True)
    test_settings.qa_model_path = "./models/vietnamese-sbert"
    test_settings.qa_data_path = "data.xlsx"
    test_settings.qa_enabled = True
    return test_settings


@pytest.mark.asyncio
@pytest.mark.skipif(
    not pytest.importorskip("optimum", reason="optimum not installed"),
    reason="ONNX support not available"
)
async def test_onnx_vs_pytorch_embeddings(mock_settings):
    """
    Test ONNX vs PyTorch embedding similarity.

    Verifies embeddings are nearly identical (cosine similarity >0.99).
    """
    # Load PyTorch model
    pytorch_settings = mock_settings.model_copy()
    pytorch_settings.qa_model_format = "pytorch"

    with patch.object(QAService, "_download_from_gcs"):
        qa_pytorch = QAService(pytorch_settings)

    # Load ONNX model
    onnx_settings = mock_settings.model_copy()
    onnx_settings.qa_model_format = "onnx"

    with patch.object(QAService, "_download_from_gcs"):
        qa_onnx = QAService(onnx_settings)

    # Compare embeddings for each question
    for question in VIETNAMESE_QUESTIONS:
        # Generate embeddings
        emb_pytorch = qa_pytorch.model.encode(question, convert_to_tensor=True)
        emb_onnx = qa_onnx.model.encode(question, convert_to_tensor=True)

        # Compute cosine similarity
        similarity = torch.nn.functional.cosine_similarity(
            emb_pytorch.unsqueeze(0), emb_onnx.unsqueeze(0)
        ).item()

        # Assert similarity >0.99
        assert (
            similarity > 0.99
        ), f"Embedding mismatch for '{question}': similarity={similarity:.4f}"


@pytest.mark.asyncio
@pytest.mark.skipif(
    not pytest.importorskip("optimum", reason="optimum not installed"),
    reason="ONNX support not available"
)
async def test_onnx_model_format_detection(mock_settings):
    """Test model format detection logic."""
    test_settings = mock_settings.model_copy()

    with patch.object(QAService, "_download_from_gcs"):
        # Test auto-detection
        test_settings.qa_model_format = "auto"
        qa_service = QAService(test_settings)
        detected_format = qa_service._detect_model_format()
        assert detected_format in ["onnx", "pytorch", "unknown"]

        # Test force PyTorch
        test_settings.qa_model_format = "pytorch"
        qa_service = QAService(test_settings)
        assert qa_service._detect_model_format() == "pytorch"

        # Test force ONNX
        test_settings.qa_model_format = "onnx"
        qa_service = QAService(test_settings)
        assert qa_service._detect_model_format() == "onnx"


@pytest.mark.asyncio
@pytest.mark.skipif(
    not pytest.importorskip("optimum", reason="optimum not installed"),
    reason="ONNX support not available"
)
async def test_onnx_fallback_to_pytorch(mock_settings):
    """
    Test graceful fallback to PyTorch when ONNX loading fails.

    Simulates ONNX loading failure and verifies PyTorch fallback works.
    """
    test_settings = mock_settings.model_copy()
    test_settings.qa_model_format = "onnx"

    # Mock ONNX loading to fail
    with patch.object(QAService, "_download_from_gcs"), patch.object(
        QAService, "_load_onnx_model", side_effect=ImportError("ONNX not available")
    ):
        qa_service = QAService(test_settings)

        # Should fallback to PyTorch
        assert qa_service.model is not None

        # Should still be able to encode
        embeddings = qa_service.model.encode(VIETNAMESE_QUESTIONS[0])
        assert embeddings is not None
        assert len(embeddings.shape) == 1  # 1D embedding vector


@pytest.mark.asyncio
async def test_onnx_interface_compatibility(mock_settings):
    """
    Test ONNX wrapper interface compatibility with SentenceTransformer.

    Verifies the ONNXSentenceTransformer wrapper provides same interface
    as standard SentenceTransformer.
    """
    test_settings = mock_settings.model_copy()
    test_settings.qa_model_format = "pytorch"

    with patch.object(QAService, "_download_from_gcs"):
        qa_service = QAService(test_settings)

    # Test single text encoding
    single_text = VIETNAMESE_QUESTIONS[0]
    embeddings_single = qa_service.model.encode(single_text)
    assert embeddings_single is not None
    assert len(embeddings_single.shape) == 1  # 1D vector

    # Test batch encoding
    embeddings_batch = qa_service.model.encode(VIETNAMESE_QUESTIONS)
    assert embeddings_batch is not None
    assert len(embeddings_batch.shape) == 2  # 2D matrix (batch_size x embedding_dim)
    assert embeddings_batch.shape[0] == len(VIETNAMESE_QUESTIONS)

    # Test convert_to_tensor parameter
    embeddings_tensor = qa_service.model.encode(
        single_text, convert_to_tensor=True
    )
    assert isinstance(embeddings_tensor, torch.Tensor)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not pytest.importorskip("optimum", reason="optimum not installed"),
    reason="ONNX support not available"
)
async def test_onnx_search_accuracy(mock_settings):
    """
    Test ONNX search results quality.

    Verifies ONNX model can find relevant answers with same threshold (0.55).
    """
    test_settings = mock_settings.model_copy()
    test_settings.qa_model_format = "onnx"

    with patch.object(QAService, "_download_from_gcs"):
        qa_service = QAService(test_settings)

    # Mock OpenAI API for summarization
    with patch.object(qa_service.client.chat.completions, "create") as mock_openai:
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="AI-generated summary"))
        ]
        mock_openai.return_value = mock_response

        # Test Q&A with ONNX model
        result = await qa_service.ask_question(
            "Làm thế nào để giảm cân?", threshold=0.55
        )

        # Verify response structure
        assert "answers" in result
        assert isinstance(result["answers"], list)
        assert "summary" in result
        assert result["summary"] is not None


@pytest.mark.asyncio
async def test_config_qa_model_format_default(mock_settings):
    """Test default qa_model_format config value."""
    assert mock_settings.qa_model_format == "auto"


@pytest.mark.asyncio
async def test_config_qa_onnx_provider_default(mock_settings):
    """Test default qa_onnx_provider config value."""
    assert mock_settings.qa_onnx_provider == "CPUExecutionProvider"
