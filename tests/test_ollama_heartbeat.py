"""Tests for opt-in Ollama blocking-call heartbeats."""

from __future__ import annotations

import json
import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from ollama_heartbeat import (  # noqa: E402
    ollama_blocking_heartbeat,
    ollama_heartbeat_enabled,
)


def test_heartbeat_disabled_is_noop(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("SOAPBOXX_OLLAMA_HEARTBEAT", raising=False)
    assert ollama_heartbeat_enabled() is False
    with ollama_blocking_heartbeat("test.stage"):
        pass


def test_heartbeat_emits_lines_when_enabled(monkeypatch: pytest.MonkeyPatch, capsys):
    monkeypatch.setenv("SOAPBOXX_OLLAMA_HEARTBEAT", "1")
    monkeypatch.setenv("SOAPBOXX_OLLAMA_HEARTBEAT_INTERVAL_SEC", "0.05")
    assert ollama_heartbeat_enabled() is True
    with ollama_blocking_heartbeat("test.heartbeat", component="test"):
        time.sleep(0.15)
    err = capsys.readouterr().err
    lines = [ln for ln in err.strip().splitlines() if ln.strip()]
    assert len(lines) >= 2
    payloads = [json.loads(ln) for ln in lines]
    assert any(p.get("status") == "in_progress" for p in payloads)
    assert payloads[-1].get("status") == "completed"


def test_soft_budget_emits_once(monkeypatch: pytest.MonkeyPatch, capsys):
    monkeypatch.setenv("SOAPBOXX_OLLAMA_HEARTBEAT", "1")
    monkeypatch.setenv("SOAPBOXX_OLLAMA_HEARTBEAT_INTERVAL_SEC", "0.05")
    # Soft budget 30ms — should fire after first interval tick (~50ms elapsed).
    monkeypatch.setenv("SOAPBOXX_OLLAMA_HEARTBEAT_SOFT_SEC", "0.03")
    with ollama_blocking_heartbeat("test.soft"):
        time.sleep(0.25)
    err = capsys.readouterr().err
    payloads = [json.loads(ln) for ln in err.strip().splitlines() if ln.strip()]
    soft = [p for p in payloads if p.get("status") == "soft_budget_exceeded"]
    assert len(soft) >= 1


def test_progress_delta_tracked_across_ticks(monkeypatch: pytest.MonkeyPatch, capsys):
    monkeypatch.setenv("SOAPBOXX_OLLAMA_HEARTBEAT", "1")
    monkeypatch.setenv("SOAPBOXX_OLLAMA_HEARTBEAT_INTERVAL_SEC", "0.05")
    counter = [0]

    def bump() -> None:
        for _ in range(40):
            time.sleep(0.02)
            counter[0] += 50

    threading.Thread(target=bump, daemon=True).start()
    with ollama_blocking_heartbeat(
        "test.progress",
        progress_fn=lambda: counter[0],
        progress_kind="test_units",
    ):
        time.sleep(0.22)
    err = capsys.readouterr().err
    payloads = [json.loads(ln) for ln in err.strip().splitlines() if ln.strip()]
    prog = [p for p in payloads if p.get("status") == "in_progress"]
    assert len(prog) >= 2
    assert all("progress_total" in p and "progress_delta" in p for p in prog)
    assert all(p.get("progress_kind") == "test_units" for p in prog)
    assert all("time_since_last_progress_ms" in p and "progress_state" in p for p in prog)
    assert all("first_progress_observed" in p for p in prog)
    assert any(p["first_progress_observed"] for p in prog)
    deltas = [p["progress_delta"] for p in prog]
    assert max(deltas) > 0
    assert any(p.get("progress_state") == "active" for p in prog)
    assert not any("stall_reason_hint" in p for p in prog if p.get("progress_state") != "stalled")
    assert all(p.get("liveness") in ("healthy", "slow", "waiting") for p in prog)
    assert not any("stall_severity" in p for p in prog)


def test_progress_state_stalled_without_forward_progress(
    monkeypatch: pytest.MonkeyPatch, capsys
):
    monkeypatch.setenv("SOAPBOXX_OLLAMA_HEARTBEAT", "1")
    monkeypatch.setenv("SOAPBOXX_OLLAMA_HEARTBEAT_INTERVAL_SEC", "0.05")
    monkeypatch.setenv("SOAPBOXX_OLLAMA_HEARTBEAT_STALL_MS", "100")
    with ollama_blocking_heartbeat(
        "test.stall",
        progress_fn=lambda: 0,
        progress_kind="none",
        progress_stage="http_receive",
    ):
        time.sleep(0.35)
    err = capsys.readouterr().err
    payloads = [json.loads(ln) for ln in err.strip().splitlines() if ln.strip()]
    prog = [p for p in payloads if p.get("status") == "in_progress"]
    stalled = [p for p in prog if p.get("progress_state") == "stalled"]
    assert len(stalled) >= 1
    assert all(p.get("first_progress_observed") is False for p in stalled)
    assert all(p.get("stall_reason_hint") == "no_first_byte" for p in stalled)
    assert all(p.get("liveness") == "stalled" for p in stalled)
    assert all("stall_severity" in p and p["stall_severity"] in ("short", "medium", "long") for p in stalled)
    assert all(p.get("progress_stage") == "http_receive" for p in prog)


def test_stall_reason_no_progress_after_start(monkeypatch: pytest.MonkeyPatch, capsys):
    monkeypatch.setenv("SOAPBOXX_OLLAMA_HEARTBEAT", "1")
    monkeypatch.setenv("SOAPBOXX_OLLAMA_HEARTBEAT_INTERVAL_SEC", "0.05")
    monkeypatch.setenv("SOAPBOXX_OLLAMA_HEARTBEAT_STALL_MS", "100")
    counter = [0]

    def jump_once() -> None:
        time.sleep(0.07)
        counter[0] = 100

    threading.Thread(target=jump_once, daemon=True).start()
    with ollama_blocking_heartbeat("test.after_start", progress_fn=lambda: counter[0]):
        time.sleep(0.45)
    err = capsys.readouterr().err
    payloads = [json.loads(ln) for ln in err.strip().splitlines() if ln.strip()]
    stalled = [p for p in payloads if p.get("progress_state") == "stalled"]
    after = [p for p in stalled if p.get("stall_reason_hint") == "no_progress_after_start"]
    assert len(after) >= 1
    assert all(p.get("first_progress_observed") is True for p in after)
    assert all(p.get("liveness") == "stalled" for p in after)


def test_stall_severity_buckets(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SOAPBOXX_OLLAMA_HEARTBEAT_STALL_MS", "100")
    from ollama_heartbeat import _stall_severity_bucket  # noqa: PLC0415

    assert _stall_severity_bucket(99, 100) == "short"
    assert _stall_severity_bucket(150, 100) == "short"
    assert _stall_severity_bucket(199, 100) == "short"
    assert _stall_severity_bucket(200, 100) == "medium"
    assert _stall_severity_bucket(499, 100) == "medium"
    assert _stall_severity_bucket(500, 100) == "long"

