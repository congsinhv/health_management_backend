"""Fixtures for SBERT optimization testing."""
import pytest
from unittest.mock import AsyncMock, MagicMock
import numpy as np


@pytest.fixture
def sample_vietnamese_questions():
    """20 Vietnamese test questions for accuracy validation."""
    return [
        "Làm thế nào để giảm cân hiệu quả?",
        "Triệu chứng của bệnh tiểu đường là gì?",
        "Chế độ ăn cho ngườihuyết áp cao",
        "Cách phòng ngừa bệnh tim mạch",
        "Tác dụng của vitamin C với sức khỏe",
        "Làm thế nào để tăng cường hệ miễn dịch?",
        "Nguyên nhân gây bệnh trào ngược dạ dày",
        "Cách điều trị viêm họng tại nhà",
        "Chế độ ăn cho ngườibị gout",
        "Triệu chứng của bệnh xơ gan",
        "Làm thế nào để ngủ ngon hơn?",
        "Cách phòng ngừa loãng xương",
        "Triệu chứng của bệnh ung thư",
        "Chế độ ăn cho ngườibị viêm đại tràng",
        "Cách giảm stress hiệu quả",
        "Triệu chứng của bệnh Alzheimer",
        "Cách phòng ngừa đột quỵ",
        "Chế độ ăn cho ngườibị gan nhiễm mỡ",
        "Triệu chứng của bệnh trầm cảm",
        "Cách tăng cường trí nhớ",
    ]


@pytest.fixture
def baseline_performance_metrics():
    """Pre-optimization baseline metrics."""
    return {
        "pytorch": {
            "inference_ms": 50.0,
            "memory_mb": 1200,
            "load_time_s": 12.5,
            "model_size_mb": 500,
        },
        "thresholds": {
            "onnx_speedup_min": 2.0,
            "memory_reduction_min": 2.5,
            "embedding_similarity_min": 0.99,
        },
    }


@pytest.fixture
def mock_qa_service_onnx():
    """Mock QA service with ONNX model."""
    service = AsyncMock()
    service.model = MagicMock()
    service._model_format = "onnx"
    service._model_loaded = True
    service.settings = MagicMock()
    service.settings.qa_model_format = "auto"
    return service


@pytest.fixture
def mock_cache_service_with_embeddings():
    """Mock cache service with embedding support."""
    service = AsyncMock()
    service.enabled = True
    service.get_embedding = AsyncMock(return_value=None)
    service.set_embedding = AsyncMock()
    service.get = AsyncMock(return_value=None)
    service.set = AsyncMock()
    service.stats = {"hits": 0, "misses": 0}
    return service


@pytest.fixture
def sample_embedding():
    """Sample 768-dim SBERT embedding."""
    return np.random.rand(768).astype(np.float32)


@pytest.fixture
def load_test_config():
    """Load test configuration presets."""
    return {
        "light": {"concurrent_users": 5, "requests_per_user": 10, "duration": 300},
        "medium": {"concurrent_users": 15, "requests_per_user": 10, "duration": 600},
        "heavy": {"concurrent_users": 30, "requests_per_user": 5, "duration": 600},
        "stress": {"concurrent_users": 50, "requests_per_user": 10, "duration": 1800},
    }