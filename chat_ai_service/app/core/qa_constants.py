"""
Q&A service constants and configuration.

Centralized constants for model names, thresholds, cache TTLs,
and other Q&A service configuration.
"""

# Default model name for Vietnamese SBERT
DEFAULT_MODEL_NAME = "keepitreal/vietnamese-sbert"

# Q&A search defaults
DEFAULT_SIMILARITY_THRESHOLD = 0.55
DEFAULT_TOP_K = 7
DEFAULT_MAX_PER_FIELD = 5

# Cache TTL settings (in seconds)
ANSWER_CACHE_TTL = 1800  # 30 minutes
SUMMARY_CACHE_TTL = 2592000  # 30 days
MODEL_INFO_CACHE_TTL = 3600  # 1 hour

# OpenAI configuration
OPENAI_TEMPERATURE = 0.7
OPENAI_MAX_TOKENS = 150
OPENAI_TIMEOUT = 30

# File and path constants
QA_VOCAB_FILE = "tuvung.txt"
DEFAULT_QA_DATA_FILE = "data.xlsx"

# Model validation constants
REQUIRED_MODEL_FILES = [
    "config.json",
    "modules.json",
    "sentence_bert_config.json",
    "config_sentence_transformers.json",
    "1_Pooling/config.json",
]

# ONNX optimization settings
ONNX_OPTIMIZED_MODEL_FILE = "model.onnx"
ONNX_INPUT_TYPES = ["input_ids", "attention_mask"]
ONNX_OUTPUT_TYPES = ["last_hidden_state", "pooler_output"]

# Rate limiting constants
RATE_LIMIT_REQUESTS_PER_MINUTE = 30
RATE_LIMIT_CONCURRENT_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60

# Response messages
class QAMessages:
    """Standard Q&A service response messages."""

    # Error messages
    EMPTY_QUESTION = "Câu hỏi không được để trống"
    MODEL_NOT_LOADED = "Mô hình chưa được tải"
    SERVICE_UNAVAILABLE = "Dịch vụ Q&A tạm thời không khả dụng"
    NO_RESULTS_FOUND = "Không tìm thấy kết quả phù hợp"
    PROCESSING_ERROR = "Lỗi khi xử lý câu hỏi"

    # Success messages
    RESULTS_FOUND = "Đã tìm thấy kết quả"
    PROCESSING_COMPLETE = "Đã xử lý xong câu hỏi"

    # AI messages
    AI_SUMMARIZING = "Đang tổng hợp câu trả lời..."
    AI_SUMMARY_READY = "Đã tổng hợp xong câu trả lời"

# Column names for Q&A dataset (supports Vietnamese Excel files)
class QAColumns:
    """Column names for Q&A dataset."""

    QUESTION = "Câu hỏi"
    ANSWER = "Câu trả lời"
    KEYWORDS = "Từ khóa"
    FIELD = "Lĩnh vực"
    QUESTION_CLEAN = "Câu hỏi_clean"

# HTTP status codes for Q&A responses
class QAStatusCodes:
    """HTTP status codes for Q&A responses."""

    OK = 200
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    TOO_MANY_REQUESTS = 429
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503

# Event types for Server-Sent Events
class QAEventTypes:
    """Event types for Q&A streaming responses."""

    QUESTION_RECEIVED = "question_received"
    ANSWERS_FOUND = "answers_found"
    SUMMARY_CHUNK = "summary_chunk"
    STREAM_COMPLETE = "stream_complete"
    ERROR = "error"
    HEALTH_CHECK = "health_check"

# Cache key prefixes
class QACacheKeys:
    """Cache key prefixes for Q&A service."""

    QUESTION_PREFIX = "qa:question"
    ANSWER_PREFIX = "qa:answers"
    SUMMARY_PREFIX = "qa:summary"
    MODEL_INFO_PREFIX = "qa:model_info"
    DATASET_INFO_PREFIX = "qa:dataset_info"

# Service health status
class QAHealthStatus:
    """Health status values for Q&A service."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    INITIALIZING = "initializing"