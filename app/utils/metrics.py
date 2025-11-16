"""
Metrics and monitoring utilities for SSE streaming.
"""

import logging
import time
from prometheus_client import Counter, Histogram, Gauge

logger = logging.getLogger(__name__)

# Prometheus metrics
sse_connections_total = Counter(
    "sse_connections_total", "Total SSE connections opened", ["user_id", "endpoint"]
)

sse_events_sent_total = Counter(
    "sse_events_sent_total", "Total SSE events sent", ["event_type"]
)

sse_connection_duration_seconds = Histogram(
    "sse_connection_duration_seconds",
    "SSE connection duration in seconds",
    buckets=[1, 5, 10, 30, 60, 120, 300],
)

sse_active_connections = Gauge(
    "sse_active_connections", "Current number of active SSE connections"
)

sse_errors_total = Counter(
    "sse_errors_total", "Total SSE errors", ["error_type", "user_id"]
)

openai_api_calls_total = Counter(
    "openai_api_calls_total", "Total OpenAI API calls", ["status", "model"]
)

openai_tokens_total = Counter(
    "openai_tokens_total", "Total OpenAI tokens used", ["model"]
)


# Structured logging helper
class StructuredLogger:
    """Structured logging for SSE events."""

    @staticmethod
    def log_connection_start(user_id: str, question: str):
        """Log SSE connection start."""
        logger.info(
            "SSE connection started",
            extra={
                "event": "sse_connection_start",
                "user_id": user_id,
                "question_preview": question[:50] + "..."
                if len(question) > 50
                else question,
                "timestamp": time.time(),
            },
        )

    @staticmethod
    def log_connection_end(user_id: str, duration: float, event_count: int):
        """Log SSE connection completion."""
        logger.info(
            "SSE connection completed",
            extra={
                "event": "sse_connection_end",
                "user_id": user_id,
                "duration_seconds": duration,
                "events_sent": event_count,
                "timestamp": time.time(),
            },
        )

    @staticmethod
    def log_disconnect(user_id: str, duration: float):
        """Log SSE client disconnect."""
        logger.warning(
            "SSE client disconnected",
            extra={
                "event": "sse_client_disconnect",
                "user_id": user_id,
                "duration_seconds": duration,
                "timestamp": time.time(),
            },
        )

    @staticmethod
    def log_error(user_id: str, error: str, error_code: str):
        """Log SSE streaming error."""
        logger.error(
            "SSE streaming error",
            extra={
                "event": "sse_streaming_error",
                "user_id": user_id,
                "error": error,
                "error_code": error_code,
                "timestamp": time.time(),
            },
        )

    @staticmethod
    def log_rate_limit(user_id: str, limit_type: str):
        """Log rate limit exceeded."""
        logger.warning(
            "Rate limit exceeded",
            extra={
                "event": "rate_limit_exceeded",
                "user_id": user_id,
                "limit_type": limit_type,
                "timestamp": time.time(),
            },
        )


def increment_sse_events(event_type: str):
    """Increment SSE event counter."""
    sse_events_sent_total.labels(event_type=event_type).inc()


def start_sse_connection():
    """Start tracking a new SSE connection."""
    sse_active_connections.inc()


def end_sse_connection(duration: float):
    """End SSE connection tracking."""
    sse_connection_duration_seconds.observe(duration)
    sse_active_connections.dec()


def record_sse_error(error_type: str, user_id: str):
    """Record SSE error."""
    sse_errors_total.labels(error_type=error_type, user_id=user_id).inc()


def record_openai_api_call(status: str, model: str):
    """Record OpenAI API call."""
    openai_api_calls_total.labels(status=status, model=model).inc()


def record_openai_tokens(model: str, token_count: int):
    """Record OpenAI token usage."""
    openai_tokens_total.labels(model=model).inc(token_count)
