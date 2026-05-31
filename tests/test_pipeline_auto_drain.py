"""Automatic pipeline drain for ingested-but-unprocessed episodes."""

from __future__ import annotations

from backend.services.episode_pipeline_service import drain_pending_pipeline


class _FakeSession:
    pass


def test_drain_pending_celery_mode(monkeypatch):
    monkeypatch.setattr(
        "backend.services.episode_pipeline_service.find_pending_episode_ids",
        lambda db, limit=10: [5, 6],
    )
    monkeypatch.setattr(
        "backend.services.rss_service.dispatch_processing_for_episodes",
        lambda db, episode_ids, trigger: episode_ids,
    )

    out = drain_pending_pipeline(_FakeSession(), limit=5, trigger="test")
    assert out["mode"] == "celery"
    assert out["dispatched"] == 2
    assert out["episode_ids"] == [5, 6]


def test_drain_pending_sync_fallback(monkeypatch):
    monkeypatch.setattr(
        "backend.services.episode_pipeline_service.find_pending_episode_ids",
        lambda db, limit=10: [7],
    )
    monkeypatch.setattr(
        "backend.services.rss_service.dispatch_processing_for_episodes",
        lambda db, episode_ids, trigger: [],
    )

    calls: list[int] = []

    def _fake_pipeline(db, episode_id, **kwargs):
        calls.append(episode_id)
        from backend.services.episode_pipeline_service import EpisodePipelineResult

        return EpisodePipelineResult(episode_id=episode_id, status="ready")

    monkeypatch.setattr(
        "backend.services.episode_pipeline_service.run_episode_pipeline",
        _fake_pipeline,
    )

    out = drain_pending_pipeline(_FakeSession(), limit=5, trigger="test")
    assert out["mode"] == "sync"
    assert out["processed"] == 1
    assert calls == [7]


def test_drain_pending_respects_exclude(monkeypatch):
    monkeypatch.setattr(
        "backend.services.episode_pipeline_service.find_pending_episode_ids",
        lambda db, limit=10: [1, 2, 3],
    )
    monkeypatch.setattr(
        "backend.services.rss_service.dispatch_processing_for_episodes",
        lambda db, episode_ids, trigger: episode_ids,
    )

    out = drain_pending_pipeline(
        _FakeSession(),
        limit=5,
        trigger="test",
        exclude_episode_ids=[2],
    )
    assert out["episode_ids"] == [1, 3]


def test_drain_pending_none_when_empty(monkeypatch):
    monkeypatch.setattr(
        "backend.services.episode_pipeline_service.find_pending_episode_ids",
        lambda db, limit=10: [],
    )

    out = drain_pending_pipeline(_FakeSession(), limit=5, trigger="test")
    assert out["mode"] == "none"
    assert out["pending"] == 0
