"""Phase 1 intelligence loop — DB, benchmarks, predictor (no live LLM/STT)."""

import tempfile
from pathlib import Path

import pytest

from backend.intelligence_v1.analyzer import compute_category_benchmarks
from backend.intelligence_v1.db import IntelligenceDB
from backend.intelligence_v1.metrics_extractor import _normalize_metrics, extract_metrics
from backend.intelligence_v1.pipeline import process_transcript_only
from backend.intelligence_v1.predictor import predict_tier


SAMPLE = """
Host: Why did Spirit Airlines fail?
Guest: They chased growth over unit economics. Ultra-low fares stopped covering fuel spikes.
Host: What was the first sign?
Guest: Cancellations spiked in 2022. Crew shortages made it worse.
Host: Would you fly them today?
Guest: No — the brand lost trust. Subscribe for our next deep dive on regional carriers.
""" * 5


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test.db"
        db = IntelligenceDB(p)
        db.init_schema()
        yield db


def test_db_roundtrip(temp_db):
    eid = temp_db.insert_episode(
        title="Test Ep",
        category="business",
        transcript=SAMPLE,
    )
    metrics = _normalize_metrics(
        {
            "hook_time_seconds": 30,
            "guest_talk_percentage": 55,
            "host_talk_percentage": 45,
            "question_count": 4,
            "followup_question_count": 2,
            "story_count": 1,
            "interruptions": 0,
            "topic_changes": 1,
            "cta_present": True,
        }
    )
    temp_db.save_metrics(eid, metrics)
    temp_db.save_prediction(eid, tier="B", confidence=0.7, reasoning=["ok"])
    bundle = temp_db.get_episode_bundle(eid)
    assert bundle["episode"]["title"] == "Test Ep"
    assert bundle["metrics"]["followup_count"] == 2


def test_benchmarks_and_predictor(temp_db):
    for i in range(3):
        eid = temp_db.insert_episode(
            title=f"Ep {i}",
            category="business",
            transcript=SAMPLE,
        )
        m = _normalize_metrics(
            {
                "hook_time_seconds": 40 + i * 10,
                "guest_talk_percentage": 50,
                "host_talk_percentage": 50,
                "question_count": 5,
                "followup_question_count": 1 + i,
                "story_count": 1,
                "interruptions": 0,
                "topic_changes": 2,
                "cta_present": True,
            }
        )
        temp_db.save_metrics(eid, m)

    benches, n = compute_category_benchmarks("business", db=temp_db)
    assert n == 3
    assert "hook_time_seconds" in benches
    assert benches["followup_question_count"]["avg"] >= 1

    pred = predict_tier(
        {
            "hook_time_seconds": 25,
            "guest_talk_percentage": 52,
            "host_talk_percentage": 48,
            "question_count": 6,
            "followup_question_count": 3,
            "story_count": 2,
            "interruptions": 0,
            "topic_changes": 1,
            "cta_present": True,
        },
        benches,
    )
    assert pred["tier"] in ("A", "B", "C")
    assert 0 < pred["confidence"] <= 1


def test_pipeline_transcript_only(monkeypatch, temp_db):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SOAPBOXX_OLLAMA_MODEL", raising=False)
    report = process_transcript_only(
        SAMPLE,
        "business",
        title="Spirit Airlines",
        db=temp_db,
    )
    assert report["episode_id"]
    assert "Category comparison" in report["markdown"]
    assert "Measured structure" in report["markdown"]
    assert "Suggested focus" in report["markdown"]
    assert report["metrics"].get("feature_source") == "rule_based"
    assert report["metrics"]["question_count"] >= 0


def test_extract_metrics_heuristic(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SOAPBOXX_OLLAMA_MODEL", raising=False)
    m = extract_metrics(SAMPLE)
    assert m["cta_present"] is True
    assert m["question_count"] >= 1
