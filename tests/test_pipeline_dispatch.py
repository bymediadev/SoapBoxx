"""Celery dispatch must verify a live worker — .delay() succeeds with zero workers."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

import backend.services.episode_pipeline_service as eps
from backend.services.episode_pipeline_service import try_dispatch_episode_to_celery


@pytest.fixture(autouse=True)
def _clear_ping_cache():
    eps._worker_ping_cache = None
    yield
    eps._worker_ping_cache = None


def _fake_celery_module(ping_result=None, ping_error=None):
    mod = ModuleType("backend.workers.celery_app")
    app = MagicMock()
    if ping_error is not None:
        app.control.ping.side_effect = ping_error
    else:
        app.control.ping.return_value = ping_result or []
    mod.celery_app = app
    return mod, app


def test_no_worker_means_no_dispatch():
    with patch.object(eps, "celery_worker_available", return_value=False):
        # db is never touched when no worker is alive
        assert try_dispatch_episode_to_celery(None, 1, trigger="test") is False


def test_ping_empty_reply_returns_false():
    mod, app = _fake_celery_module(ping_result=[])
    with patch.dict(sys.modules, {"backend.workers.celery_app": mod}):
        assert eps.celery_worker_available() is False
    assert app.control.ping.call_count == 1


def test_ping_error_returns_false():
    mod, _ = _fake_celery_module(ping_error=ConnectionError("redis down"))
    with patch.dict(sys.modules, {"backend.workers.celery_app": mod}):
        assert eps.celery_worker_available() is False


def test_live_worker_detected_and_cached():
    mod, app = _fake_celery_module(ping_result=[{"worker1": {"ok": "pong"}}])
    with patch.dict(sys.modules, {"backend.workers.celery_app": mod}):
        assert eps.celery_worker_available() is True
        assert eps.celery_worker_available() is True
    assert app.control.ping.call_count == 1
