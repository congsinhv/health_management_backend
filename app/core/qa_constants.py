"""
Constants for Q&A service.

This module contains configuration constants, thresholds,
and other values used by the Q&A service.
"""

# File name constants
QA_VOCAB_FILE = "tuvung.txt"  # Vietnamese vocabulary file

# Similarity thresholds
DEFAULT_SIMILARITY_THRESHOLD = 0.55
MIN_SIMILARITY_THRESHOLD = 0.3
MAX_SIMILARITY_THRESHOLD = 0.9

# Result limits
DEFAULT_TOP_K = 7
MAX_RESULTS_PER_FIELD = 5
MAX_TOTAL_RESULTS = 20

# Cache TTLs (seconds)
ANSWER_CACHE_TTL = 1800  # 30 minutes
SUMMARY_CACHE_TTL = 2592000  # 30 days (30 * 24 * 60 * 60)

# Cache key patterns
QA_ANSWERS_KEY_PATTERN = "qa:answers:{question_hash}:{threshold}:{top_k}"
QA_SUMMARY_KEY_PATTERN = "qa:summary:{content_hash}"

# Model configuration
DEFAULT_MODEL_NAME = "keepitreal/vietnamese-sbert"
MODEL_MAX_SEQ_LENGTH = 256

# OpenAI configuration
OPENAI_TEMPERATURE = 0.7

# Required model files for SBERT
REQUIRED_MODEL_FILES = [
    "config.json",
    "modules.json",
    "sentence_bert_config.json",
    "config_sentence_transformers.json",
    "1_Pooling/config.json",
]

# Response data messages
NO_RESULTS_FOUND = "No Results Found"
NO_DATA_UPDATE = "No Content: Data not yet updated for this question"
UNCLASSIFIED_FIELD = "Unclassified"
