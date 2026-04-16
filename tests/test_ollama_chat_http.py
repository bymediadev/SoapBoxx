"""Unit tests for Ollama HTTP transport — mocked I/O."""

from __future__ import annotations

import json
import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from failure_taxonomy import FAILURE_TIMEOUT_READ_BODY  # noqa: E402
from ollama_chat_http import (  # noqa: E402
    OllamaRetryableTransportError,
    reset_transport_log,
    set_trace_id,
)


class _FakeResp:
    def __init__(self, status: int, body: bytes, read_timeout: bool = False):
        self.status = status
        self._body = body
        self._read_timeout = read_timeout

    def read(self, n: int = 65536) -> bytes:
        if self._read_timeout:
            raise TimeoutError("simulated read timeout")
        if not self._body:
            return b""
        out, self._body = self._body[:n], self._body[n:]
        return out


class _FakeConn:
    def __init__(self, resp: _FakeResp):
        self.sock = mock.MagicMock()
        self._resp = resp
        self.closed = False

    def request(self, *args, **kwargs) -> None:
        pass

    def getresponse(self) -> _FakeResp:
        return self._resp

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def monkey_ollama_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SOAPBOXX_OLLAMA_MAX_RETRIES", "2")
    monkeypatch.setenv("SOAPBOXX_OLLAMA_FIRST_BYTE_TIMEOUT", "30")
    monkeypatch.setenv("SOAPBOXX_OLLAMA_READ_BODY_TIMEOUT", "30")


def test_read_body_timeout_classified(monkeypatch: pytest.MonkeyPatch, monkey_ollama_env):
    import ollama_chat_http as och  # noqa: PLC0415

    payload = {"model": "m", "messages": []}
    body_json = json.dumps({"message": {"content": "ok"}}).encode("utf-8")
    fake_resp = _FakeResp(200, body_json, read_timeout=True)

    def fake_conn(*a, **kw):
        return _FakeConn(fake_resp)

    def fake_hb(*args, **kwargs):
        class CM:
            def __enter__(self):
                return None

            def __exit__(self, *x):
                return None

        return CM()

    monkeypatch.setattr(och.http.client, "HTTPConnection", fake_conn)
    reset_transport_log()
    set_trace_id("trace-test-1")
    with pytest.raises(OllamaRetryableTransportError) as ei:
        och.ollama_api_chat(
            "http://127.0.0.1:11434",
            payload,
            stage="t",
            component="test",
            heartbeat_cm=fake_hb,
        )
    assert ei.value.failure_code == FAILURE_TIMEOUT_READ_BODY


def test_trace_id_in_heartbeat_extra(monkeypatch: pytest.MonkeyPatch, monkey_ollama_env):
    import ollama_chat_http as och  # noqa: PLC0415

    payload = {"model": "m", "messages": []}
    body_json = json.dumps({"message": {"content": "x"}}).encode("utf-8")
    fake_resp = _FakeResp(200, body_json, read_timeout=False)
    captured: dict = {}

    def fake_conn(*a, **kw):
        return _FakeConn(fake_resp)

    def fake_hb(*args, **kwargs):
        captured.update(kwargs)

        class CM:
            def __enter__(self):
                return None

            def __exit__(self, *x):
                return None

        return CM()

    monkeypatch.setattr(och.http.client, "HTTPConnection", fake_conn)
    reset_transport_log()
    set_trace_id("tid-xyz")
    och.ollama_api_chat(
        "http://127.0.0.1:11434",
        payload,
        stage="s",
        component="c",
        heartbeat_cm=fake_hb,
    )
    ex = captured.get("extra") or {}
    assert ex.get("trace_id") == "tid-xyz"
