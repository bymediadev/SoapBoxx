"""
Opt-in liveness telemetry for blocking Ollama HTTP calls.

Without streaming, we cannot observe token-level progress; this emits periodic structured
lines on stderr so long runs are distinguishable from deadlocks.

Enable: SOAPBOXX_OLLAMA_HEARTBEAT=1
Interval: SOAPBOXX_OLLAMA_HEARTBEAT_INTERVAL_SEC (default 30)
Optional soft budget warning once: SOAPBOXX_OLLAMA_HEARTBEAT_SOFT_SEC (e.g. 180)

Optional forward-progress (caller supplies ``progress_fn`` returning a monotonic counter, e.g. bytes
received while streaming a response): emits ``progress_total``, ``progress_delta``,
``time_since_last_progress_ms``, derived ``progress_state`` (``active`` | ``idle`` | ``stalled``),
``first_progress_observed``, when stalled ``stall_reason_hint`` (``no_first_byte`` |
``no_progress_after_start``), derived ``liveness`` (``healthy`` | ``slow`` | ``waiting`` | ``stalled``),
and when stalled ``stall_severity`` (``short`` | ``medium`` | ``long`` vs threshold multiples).

Optional ``progress_stage`` (e.g. ``http_receive`` vs future ``model_stream``) disambiguates the signal.
Stall threshold: ``SOAPBOXX_OLLAMA_HEARTBEAT_STALL_MS`` (default 45000).
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, Optional


def ollama_heartbeat_enabled() -> bool:
    raw = (os.getenv("SOAPBOXX_OLLAMA_HEARTBEAT") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _interval_sec() -> float:
    raw = (os.getenv("SOAPBOXX_OLLAMA_HEARTBEAT_INTERVAL_SEC") or "30").strip()
    try:
        v = float(raw)
    except ValueError:
        return 30.0
    # Floor avoids a busy spin on 0; sub-second values are allowed for tests / tight telemetry.
    return max(0.01, v)


def _soft_budget_ms() -> Optional[int]:
    raw = (os.getenv("SOAPBOXX_OLLAMA_HEARTBEAT_SOFT_SEC") or "").strip()
    if not raw:
        return None
    try:
        return int(float(raw) * 1000)
    except ValueError:
        return None


def _stall_threshold_ms() -> int:
    raw = (os.getenv("SOAPBOXX_OLLAMA_HEARTBEAT_STALL_MS") or "45000").strip()
    try:
        return max(1, int(float(raw)))
    except ValueError:
        return 45000


def _stall_severity_bucket(time_since_ms: int, stall_ms: int) -> str:
    """Bucket stall depth: ratio of time_since to threshold (<2 short, 2–5 medium, else long)."""
    r = time_since_ms / float(stall_ms)
    if r < 2.0:
        return "short"
    if r < 5.0:
        return "medium"
    return "long"


def _emit_line(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False), file=sys.stderr, flush=True)


@contextmanager
def ollama_blocking_heartbeat(
    stage: str,
    *,
    component: str = "soapboxx",
    expected_duration_ms: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
    progress_fn: Optional[Callable[[], int]] = None,
    progress_kind: Optional[str] = None,
    progress_stage: Optional[str] = None,
) -> Iterator[None]:
    """
    While the wrapped block runs, periodically emit in_progress heartbeats on stderr.

    If ``progress_fn`` is set, each tick includes ``progress_total`` and ``progress_delta`` (change
    since the previous tick), ``time_since_last_progress_ms`` (time since last tick with
    ``progress_delta > 0``, or elapsed time waiting for first forward progress), and
    ``progress_state``: ``active`` if this tick's delta is positive, ``stalled`` if there has been no
    forward progress for at least ``SOAPBOXX_OLLAMA_HEARTBEAT_STALL_MS``, else ``idle``.
    ``first_progress_observed`` is true after any tick with ``progress_delta > 0``. When ``stalled``,
    ``stall_reason_hint`` distinguishes waiting for the first byte vs no bytes after data started.
    ``liveness`` collapses state for dashboards: ``healthy`` (active), ``waiting`` (idle, pre-first
    progress), ``slow`` (idle after progress), ``stalled``. ``stall_severity`` buckets how deep the
    stall is vs the configured threshold.

    On exit (success or failure), emits one completed line with total elapsed_ms.
    """
    if not ollama_heartbeat_enabled():
        yield
        return

    interval = _interval_sec()
    soft_ms = _soft_budget_ms()
    stop = threading.Event()
    start = time.monotonic()
    soft_emitted = False

    base: Dict[str, Any] = {
        "component": component,
        "stage": stage,
        "kind": "ollama_http_block",
    }
    if expected_duration_ms is not None:
        base["expected_duration_ms"] = int(expected_duration_ms)
    if extra:
        base["extra"] = extra
    if progress_kind:
        base["progress_kind"] = progress_kind
    if progress_stage:
        base["progress_stage"] = progress_stage

    # Shared across heartbeat worker and final "completed" line (last tick vs final sample).
    progress_snap: Dict[str, Optional[int]] = {"prev": None}
    # Monotonic time when we last saw progress_delta > 0; None until first such tick.
    diag: Dict[str, Any] = {"last_forward_mono": None, "saw_forward": False}

    stall_ms = _stall_threshold_ms()

    def _fill_progress_diagnostics(line: Dict[str, Any]) -> None:
        if progress_fn is None:
            return
        now = time.monotonic()
        try:
            total = int(progress_fn())
        except Exception:
            return
        prev = progress_snap["prev"]
        delta = 0 if prev is None else total - prev
        line["progress_total"] = total
        line["progress_delta"] = delta
        progress_snap["prev"] = total

        if delta > 0:
            diag["last_forward_mono"] = now
            diag["saw_forward"] = True

        if diag["last_forward_mono"] is None:
            time_since = int((now - start) * 1000)
        else:
            time_since = int((now - diag["last_forward_mono"]) * 1000)
        line["time_since_last_progress_ms"] = time_since

        if delta > 0:
            line["progress_state"] = "active"
        elif time_since >= stall_ms:
            line["progress_state"] = "stalled"
        else:
            line["progress_state"] = "idle"

        line["first_progress_observed"] = bool(diag["saw_forward"])
        ps = line["progress_state"]
        if ps == "stalled":
            line["stall_reason_hint"] = (
                "no_first_byte"
                if not diag["saw_forward"]
                else "no_progress_after_start"
            )
            line["stall_severity"] = _stall_severity_bucket(time_since, stall_ms)
            line["liveness"] = "stalled"
        elif ps == "active":
            line["liveness"] = "healthy"
        elif not diag["saw_forward"]:
            line["liveness"] = "waiting"
        else:
            line["liveness"] = "slow"

    def _copy_progress_snapshot(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
        for k in (
            "progress_total",
            "progress_delta",
            "time_since_last_progress_ms",
            "progress_state",
            "first_progress_observed",
            "stall_reason_hint",
            "liveness",
            "stall_severity",
        ):
            if k in src:
                dst[k] = src[k]

    def _worker() -> None:
        nonlocal soft_emitted
        while True:
            if stop.is_set():
                return
            elapsed_ms = int((time.monotonic() - start) * 1000)
            line = dict(base)
            line.update(
                {
                    "status": "in_progress",
                    "elapsed_ms": elapsed_ms,
                }
            )
            _fill_progress_diagnostics(line)
            _emit_line(line)
            if soft_ms is not None and not soft_emitted and elapsed_ms >= soft_ms:
                soft_emitted = True
                warn = dict(base)
                warn.update(
                    {
                        "status": "soft_budget_exceeded",
                        "elapsed_ms": elapsed_ms,
                        "soft_budget_ms": soft_ms,
                    }
                )
                _copy_progress_snapshot(warn, line)
                _emit_line(warn)
            if stop.wait(interval):
                return

    t = threading.Thread(target=_worker, daemon=True, name=f"ollama-heartbeat-{stage}")
    t.start()
    try:
        yield
    finally:
        stop.set()
        t.join(timeout=min(2.0, interval + 1.0))
        elapsed_ms = int((time.monotonic() - start) * 1000)
        done = dict(base)
        done.update({"status": "completed", "elapsed_ms": elapsed_ms})
        _fill_progress_diagnostics(done)
        _emit_line(done)
