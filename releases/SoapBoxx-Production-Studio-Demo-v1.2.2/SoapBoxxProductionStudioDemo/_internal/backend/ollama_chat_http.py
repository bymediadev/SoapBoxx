"""
Shared Ollama /api/chat HTTP client: split timeouts, classified errors, bounded retries, cancellation.

Used by soapboxx_v3_workflow and episode_intelligence. Does not change evaluation snapshot shape.
"""

from __future__ import annotations

import contextvars
import http.client
import json
import os
import socket
import ssl
import threading
import time
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

try:
    from .failure_taxonomy import (
        FAILURE_CANCELLED,
        FAILURE_TIMEOUT_FIRST_BYTE,
        FAILURE_TIMEOUT_READ_BODY,
        RETRY_CLASS_CONNECT_FAILURE,
        RETRY_CLASS_HTTP_5XX,
        RETRY_CLASS_READ_TIMEOUT,
    )
except ImportError:  # pragma: no cover - script / flat imports
    from failure_taxonomy import (
        FAILURE_CANCELLED,
        FAILURE_TIMEOUT_FIRST_BYTE,
        FAILURE_TIMEOUT_READ_BODY,
        RETRY_CLASS_CONNECT_FAILURE,
        RETRY_CLASS_HTTP_5XX,
        RETRY_CLASS_READ_TIMEOUT,
    )

_transport_log: contextvars.ContextVar[Optional[List[Dict[str, Any]]]] = contextvars.ContextVar(
    "ollama_transport_log", default=None
)

_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("soapboxx_trace_id", default="")


def set_trace_id(tid: str) -> None:
    _trace_id.set(str(tid or ""))


def get_trace_id() -> str:
    return str(_trace_id.get() or "")


def reset_transport_log() -> None:
    """Call at the start of a top-level workflow run (clears per-context event list)."""
    _transport_log.set([])


def _log_append(entry: Dict[str, Any]) -> None:
    log = _transport_log.get()
    if log is None:
        log = []
        _transport_log.set(log)
    log.append(dict(entry))


def get_transport_log() -> List[Dict[str, Any]]:
    log = _transport_log.get()
    return list(log) if log else []


class OllamaTransportError(RuntimeError):
    """Non-retryable or terminal Ollama HTTP failure with taxonomy codes."""

    def __init__(
        self,
        message: str,
        *,
        failure_code: str,
        retry_class: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.failure_code = failure_code
        self.retry_class = retry_class


class OllamaRetryableTransportError(OllamaTransportError):
    """Retryable failure (connect, read stall, 5xx)."""

    pass


class OllamaCancelledError(OllamaTransportError):
    """Cooperative cancellation — not retried."""

    def __init__(self, message: str = "Ollama request cancelled") -> None:
        super().__init__(message, failure_code=FAILURE_CANCELLED, retry_class=None)


def _max_retries() -> int:
    raw = (os.getenv("SOAPBOXX_OLLAMA_MAX_RETRIES") or "3").strip()
    try:
        return max(1, min(10, int(raw)))
    except ValueError:
        return 3


def _timeout_first_byte() -> float:
    raw = (os.getenv("SOAPBOXX_OLLAMA_FIRST_BYTE_TIMEOUT") or "").strip()
    if raw:
        try:
            return max(1.0, float(raw))
        except ValueError:
            pass
    return float(os.getenv("SOAPBOXX_OLLAMA_HTTP_TIMEOUT", "900") or "900")


def _timeout_read_body() -> float:
    raw = (os.getenv("SOAPBOXX_OLLAMA_READ_BODY_TIMEOUT") or "").strip()
    if raw:
        try:
            return max(1.0, float(raw))
        except ValueError:
            pass
    return float(os.getenv("SOAPBOXX_OLLAMA_HTTP_TIMEOUT", "900") or "900")


def _parse_ollama_host(host_raw: str) -> tuple[str, int, str]:
    h = (host_raw or "").strip()
    if not h:
        h = "http://127.0.0.1:11434"
    if "://" not in h:
        h = "http://" + h
    u = urlparse(h)
    hostname = u.hostname or "127.0.0.1"
    port = u.port
    scheme = (u.scheme or "http").lower()
    if port is None:
        port = 443 if scheme == "https" else 80
    return hostname, int(port), scheme


def _single_http_chat(
    *,
    hostname: str,
    port: int,
    scheme: str,
    body: bytes,
    headers: Dict[str, str],
    first_byte_s: float,
    read_body_s: float,
    response_buf: bytearray,
    cancel_event: Optional[threading.Event],
    attempt: int,
) -> Dict[str, Any]:
    if scheme == "https":
        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(hostname, port, timeout=first_byte_s, context=ctx)
    else:
        conn = http.client.HTTPConnection(hostname, port, timeout=first_byte_s)

    try:
        try:
            conn.request("POST", "/api/chat", body=body, headers=headers)
            resp = conn.getresponse()
        except (socket.timeout, TimeoutError) as e:
            raise OllamaRetryableTransportError(
                f"Ollama timeout waiting for response (first byte): {e}",
                failure_code=FAILURE_TIMEOUT_FIRST_BYTE,
                retry_class=RETRY_CLASS_READ_TIMEOUT,
            ) from e
        except OSError as e:
            raise OllamaRetryableTransportError(
                f"Ollama connection failed: {e}",
                failure_code="connect_error",
                retry_class=RETRY_CLASS_CONNECT_FAILURE,
            ) from e

        if conn.sock:
            conn.sock.settimeout(read_body_s)

        status = int(resp.status)
        if status >= 500:
            raw_err = resp.read() or b""
            conn.close()
            raise OllamaRetryableTransportError(
                f"Ollama HTTP {status}: {raw_err[:500]!r}",
                failure_code="http_5xx",
                retry_class=RETRY_CLASS_HTTP_5XX,
            )
        if status >= 400:
            raw_err = resp.read() or b""
            conn.close()
            raise OllamaTransportError(
                f"Ollama HTTP {status}: {raw_err[:800].decode('utf-8', errors='replace')}",
                failure_code=f"http_{status}",
                retry_class=None,
            )

        while True:
            if cancel_event is not None and cancel_event.is_set():
                conn.close()
                raise OllamaCancelledError()
            try:
                chunk = resp.read(65536)
            except (socket.timeout, TimeoutError) as e:
                conn.close()
                raise OllamaRetryableTransportError(
                    f"Ollama timeout reading response body: {e}",
                    failure_code=FAILURE_TIMEOUT_READ_BODY,
                    retry_class=RETRY_CLASS_READ_TIMEOUT,
                ) from e
            if not chunk:
                break
            response_buf += chunk

        conn.close()
        return json.loads(bytes(response_buf).decode("utf-8"))
    except OllamaTransportError:
        try:
            conn.close()
        except Exception:
            pass
        raise
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        raise


def ollama_api_chat(
    host: str,
    payload: Dict[str, Any],
    *,
    stage: str,
    component: str,
    heartbeat_cm: Callable[..., Any],
    cancel_event: Optional[threading.Event] = None,
) -> Dict[str, Any]:
    """
    POST JSON to Ollama /api/chat with split timeouts and retries.

    ``heartbeat_cm`` is ``ollama_blocking_heartbeat`` (injected to avoid circular imports).
    """
    hostname, port, scheme = _parse_ollama_host(host)
    body = json.dumps(payload).encode("utf-8")
    hdrs = {"Content-Type": "application/json", "Content-Length": str(len(body))}
    first_byte_s = _timeout_first_byte()
    read_body_s = _timeout_read_body()
    n = _max_retries()
    exp_cap = 8.0

    trace_extra: Dict[str, Any] = {}
    tid = get_trace_id().strip() or (os.getenv("SOAPBOXX_TRACE_ID") or "").strip()
    if tid:
        trace_extra["trace_id"] = tid

    last_retryable: Optional[OllamaRetryableTransportError] = None
    for attempt in range(1, n + 1):
        response_buf = bytearray()

        def _progress() -> int:
            return len(response_buf)

        try:
            with heartbeat_cm(
                stage,
                component=component,
                expected_duration_ms=int(max(first_byte_s, read_body_s) * 1000),
                extra={
                    "endpoint": "/api/chat",
                    "model": str(payload.get("model") or ""),
                    "attempt": attempt,
                    **trace_extra,
                },
                progress_fn=_progress,
                progress_kind="response_bytes",
                progress_stage="http_receive",
            ):
                data = _single_http_chat(
                    hostname=hostname,
                    port=port,
                    scheme=scheme,
                    body=body,
                    headers=hdrs,
                    first_byte_s=first_byte_s,
                    read_body_s=read_body_s,
                    response_buf=response_buf,
                    cancel_event=cancel_event,
                    attempt=attempt,
                )
            _log_append(
                {
                    "attempt": attempt,
                    "ok": True,
                    "failure_code": None,
                    "retry_class": None,
                }
            )
            return data
        except OllamaCancelledError as e:
            _log_append(
                {
                    "attempt": attempt,
                    "ok": False,
                    "failure_code": e.failure_code,
                    "retry_class": None,
                }
            )
            raise
        except OllamaRetryableTransportError as e:
            last_retryable = e
            _log_append(
                {
                    "attempt": attempt,
                    "ok": False,
                    "failure_code": e.failure_code,
                    "retry_class": e.retry_class,
                }
            )
            if attempt >= n:
                raise
            time.sleep(min(exp_cap, float(2 ** (attempt - 1))))
        except OllamaTransportError as e:
            _log_append(
                {
                    "attempt": attempt,
                    "ok": False,
                    "failure_code": e.failure_code,
                    "retry_class": getattr(e, "retry_class", None),
                }
            )
            raise

    if last_retryable is not None:
        raise last_retryable
    raise RuntimeError("ollama_api_chat: exhausted retries without exception")
