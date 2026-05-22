"""Library shelf + weekly batch queue."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from backend.library import (
    LibraryDB,
    enqueue_episode,
    get_library_tree,
    get_or_create_podcast,
    list_pending_queue,
    run_weekly_batch,
)
from backend.library.batch import _ingest_queue_item


def test_podcast_upsert_and_tree(tmp_path):
    db = LibraryDB(tmp_path / "lib.db")
    db.init_schema()
    pid = get_or_create_podcast(
        category="interview",
        author="Jane Host",
        show_title="The Weekly Show",
        db=db,
    )
    assert pid > 0
    pid2 = get_or_create_podcast(
        category="interview",
        author="Jane Host",
        show_title="The Weekly Show",
        db=db,
    )
    assert pid2 == pid

    eid = db.insert_episode_library(
        podcast_id=pid,
        title="Ep 1",
        category="interview",
        transcript="Host: Welcome. " * 30 + "Guest: Thanks. " * 30,
        author="Jane Host",
    )
    assert eid > 0

    tree = get_library_tree(db)
    assert len(tree) == 1
    assert tree[0]["category"] == "interview"
    assert tree[0]["authors"][0]["author"] == "Jane Host"
    assert tree[0]["authors"][0]["shows"][0]["title"] == "The Weekly Show"
    assert len(tree[0]["authors"][0]["shows"][0]["episodes"]) == 1


def test_enqueue_dedupes(tmp_path):
    db = LibraryDB(tmp_path / "q.db")
    db.init_schema()
    first = enqueue_episode(
        source_type="paste",
        source_ref="unique-ref-1",
        category="business",
        show_title="Biz Pod",
        author="Alex",
        episode_title="E1",
        db=db,
    )
    second = enqueue_episode(
        source_type="paste",
        source_ref="unique-ref-1",
        category="business",
        show_title="Biz Pod",
        author="Alex",
        episode_title="E1",
        db=db,
    )
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert len(list_pending_queue(db)) == 1


def test_weekly_batch_paste(tmp_path):
    db = LibraryDB(tmp_path / "batch.db")
    db.init_schema()
    text = (
        "Host: Today we talk about growth.\n"
        "Guest: Absolutely.\n"
    ) * 40
    enqueue_episode(
        source_type="paste",
        source_ref=text,
        category="general",
        show_title="Batch Show",
        author="Sam Creator",
        episode_title="Batch Ep",
        db=db,
    )
    summary = run_weekly_batch(db=db)
    assert summary["processed"] == 1
    assert summary["failed"] == 0
    assert len(list_pending_queue(db)) == 0
    tree = get_library_tree(db)
    assert any(
        s["title"] == "Batch Show"
        for cat in tree
        for auth in cat["authors"]
        for s in auth["shows"]
    )


def test_ingest_queue_item_paste():
    item = {"source_type": "paste", "source_ref": "hello " * 50}
    out = _ingest_queue_item(item)
    assert "transcript" in out
    assert len(out["transcript"]) > 40
