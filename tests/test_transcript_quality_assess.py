import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from transcript_quality_assess import (  # noqa: E402
    assess_transcript_quality,
    pick_better_transcript_report,
)


def test_assess_transcript_quality_pass_on_clean_text():
    tx = "\n".join(
        [
            "Host: Systems beat goals when motivation drops in real projects.",
            "Guest: Habits survive low motivation because routines automate behavior.",
            "Host: Where does this break under pressure and social incentives?",
            "Guest: It breaks when social pressure rewards old behavior and shortcuts.",
        ]
    )
    # Repeat clean content to avoid short-text penalties.
    tx = "\n".join([tx] * 8)
    out = assess_transcript_quality(tx, source="asr")
    assert out["verdict"] in ("pass", "degraded")
    assert float(out["score"]) >= 0.55
    assert int((out.get("metrics") or {}).get("word_count") or 0) >= 120


def test_assess_transcript_quality_fail_on_noisy_fragments():
    tx = "\n".join(
        [
            "[Music]",
            "[Applause]",
            "yeah",
            "okay",
            "you know",
            "00:12",
            "00:13",
            "[Music]",
        ]
        * 8
    )
    out = assess_transcript_quality(tx, source="captions")
    assert out["verdict"] == "fail"
    assert any("noise" in r or "fragment" in r or "low_word_count" in r for r in out.get("reasons") or [])


def test_pick_better_transcript_report_prefers_verdict_then_score():
    cap = {"source": "captions", "verdict": "degraded", "score": 0.68}
    asr = {"source": "asr", "verdict": "pass", "score": 0.61}
    pick = pick_better_transcript_report([cap, asr])
    assert pick["source"] == "asr"
