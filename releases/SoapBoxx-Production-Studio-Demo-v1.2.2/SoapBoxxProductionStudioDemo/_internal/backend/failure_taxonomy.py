"""Stable string codes for transport and evaluation failures (single taxonomy surface)."""

from __future__ import annotations

# Transport / Ollama HTTP
FAILURE_TIMEOUT_FIRST_BYTE = "timeout_first_byte"
FAILURE_TIMEOUT_READ_BODY = "timeout_read_body"
RETRY_CLASS_CONNECT_FAILURE = "connect_failure"
RETRY_CLASS_READ_TIMEOUT = "read_timeout"
RETRY_CLASS_HTTP_5XX = "http_5xx"

# Execution
FAILURE_CANCELLED = "cancelled"

# Evaluation / export (finalizer-aligned)
FAILURE_DEGRADED = "degraded"
FAILURE_EVALUATION_FAILED = "evaluation_failed"
