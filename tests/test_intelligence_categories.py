"""Category registry and benchmark fallback."""

from backend.intelligence_v1.categories import (
    category_labels,
    default_benchmarks,
    normalize_category,
    resolve_benchmarks,
)


def test_normalize_category():
    assert normalize_category("business") == "business"
    assert normalize_category("Guest interview") == "interview"
    assert normalize_category("") == "general"
    assert normalize_category("unknown_xyz") == "general"


def test_default_benchmarks_have_hook():
    b = default_benchmarks("interview")
    assert b["hook_time_seconds"]["avg"] > 0


def test_resolve_uses_defaults_when_library_thin():
    computed = {"followup_question_count": {"avg": 2, "p90": 3, "p10": 1}}
    merged, note = resolve_benchmarks("business", computed, sample_size=1)
    assert merged["hook_time_seconds"]["avg"] > 0
    assert "default" in note.lower() or "1 episode" in note.lower()


def test_resolve_live_when_enough_episodes():
    computed = {
        "hook_time_seconds": {"avg": 30, "p90": 40, "p10": 20},
        "followup_question_count": {"avg": 5, "p90": 8, "p10": 2},
    }
    merged, note = resolve_benchmarks("business", computed, sample_size=3)
    assert merged["hook_time_seconds"]["avg"] == 30
    assert "3 episode" in note
