"""Storage pull API and coach persistence."""

from __future__ import annotations

from backend.library.db import LibraryDB
from backend.storage import export_library_snapshot, pull_episode, pull_podcast


def test_pull_episode_with_coach_and_source(tmp_path):
    db = LibraryDB(tmp_path / "pull.db")
    db.init_schema()
    pid = db.upsert_podcast(
        category="business", author="Host", title="Test Show"
    )
    eid = db.insert_episode_library(
        podcast_id=pid,
        title="Ep 1",
        category="business",
        transcript="Host: Hi. " * 50 + "Guest: Hey. " * 50,
        author="Host",
    )
    db.update_episode_storage(
        eid,
        source_type="youtube",
        source_ref="https://youtube.com/watch?v=demo",
        metadata={"video_id": "demo"},
    )
    db.save_metrics(
        eid,
        {
            "hook_time_seconds": 10,
            "guest_talk_percentage": 40,
            "host_talk_percentage": 60,
            "question_count": 3,
            "followup_question_count": 1,
            "story_count": 0,
            "interruptions": 0,
            "topic_changes": 2,
            "cta_present": False,
        },
    )
    db.save_coach_report(eid, markdown="# Coach\n\nDone.", report={"ok": True})

    pulled = pull_episode(eid, db=db)
    assert pulled is not None
    assert pulled["source"]["type"] == "youtube"
    assert pulled["source"]["metadata"]["video_id"] == "demo"
    assert pulled["coach_report"]["markdown"].startswith("# Coach")
    assert pulled["podcast"]["title"] == "Test Show"

    show = pull_podcast(pid, db=db)
    assert show and len(show["episodes"]) == 1

    snap = export_library_snapshot(db=db)
    assert snap["counts"]["episodes"] == 1
    assert snap["counts"]["with_coach"] == 1
