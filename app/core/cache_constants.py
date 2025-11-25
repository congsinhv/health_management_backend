"""
Cache key prefixes and TTL constants.

This module contains standardized cache key patterns and TTL values
used across different services for consistent caching behavior.
"""

# Key prefixes
QA_ANSWER_PREFIX = "qa:answer:"
QA_SUMMARY_PREFIX = "qa:summary:"
QA_ANSWERS_PREFIX = "qa:answers:"
CONV_LIST_PREFIX = "conv:list:user:"
CONV_DETAIL_PREFIX = "conv:detail:"
CONV_COUNT_PREFIX = "conv:count:"
CONV_PINNED_PREFIX = "conv:pinned:"
CONV_SEARCH_PREFIX = "conv:search:"
CONV_MSGCOUNT_PREFIX = "conv:msgcount:"
USER_PROFILE_PREFIX = "user:profile:"
USER_DETAIL_PREFIX = "user:detail:"
USER_EMAIL_PREFIX = "user:email:"
MSG_LIST_PREFIX = "msg:list:"
MSG_LATEST_PREFIX = "msg:latest:"
MSG_COUNT_PREFIX = "msg:count:"

# TTLs (seconds)
DEFAULT_CACHE_TTL = 300  # 5 minutes
QA_CACHE_TTL = 1800  # 30 minutes
SUMMARY_CACHE_TTL = 2592000  # 30 days
CONV_LIST_TTL = 300  # 5 minutes
CONV_DETAIL_TTL = 600  # 10 minutes
CONV_COUNT_TTL = 300  # 5 minutes
USER_PROFILE_TTL = 600  # 10 minutes
MSG_LIST_TTL = 180  # 3 minutes
MSG_LATEST_TTL = 120  # 2 minutes

# Cache patterns for invalidation
# User patterns
USER_INVALIDATION_PATTERNS = [
    "user:detail:{user_id}",
    "user:email:*",  # All email-based caches
    "conv:list:{user_id}:*",  # All conversation lists
    "conv:count:{user_id}",
    "conv:pinned:{user_id}:*",
    "conv:search:{user_id}:*",
    "msg:list:*:{user_id}:*",  # All message caches
]

# Conversation patterns
CONVERSATION_INVALIDATION_PATTERNS = [
    "conv:list:{user_id}:*",
    "conv:count:{user_id}",
    "conv:pinned:{user_id}:*",
    "conv:search:{user_id}:*",
]

# Message patterns
MESSAGE_INVALIDATION_PATTERNS = [
    "msg:list:{conversation_id}:*",
    "msg:latest:{conversation_id}",
    "msg:count:{conversation_id}",
    "conv:msgcount:{conversation_id}",  # Cross-service cache
]

# Q&A patterns
QA_INVALIDATION_PATTERNS = [
    "qa:answers:{question_hash}:*",
    "qa:summary:{content_hash}",
]
