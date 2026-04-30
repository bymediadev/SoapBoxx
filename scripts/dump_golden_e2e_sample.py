"""Write reports/pytest_golden_e2e_sample.md from the golden E2E test fixture."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("SOAPBOXX_V3_ATOMIC_GROUND_TRUTH", "0")
os.environ.setdefault("SOAPBOXX_V3_FRAMING", "full")

import episode_report_v3 as v3  # noqa: E402

brief = {
    "episode_snapshot": {
        "title": "Systems vs Goals",
        "creator": "Test",
        "genre": "Education",
        "primary_topic": "habit systems",
        "why_it_matters": "w",
    },
    "narrative": [
        "Systems outperform goals when motivation is unreliable.",
        "Friction design determines whether routines stick.",
        "Test one routine change next week.",
    ],
    "claims": [
        {
            "id": "c1",
            "text": "Systems beat goals when motivation drops.",
            "claim_type": "interpretation",
            "confidence": "medium",
            "why_it_matters": "m",
        },
        {
            "id": "c2",
            "text": "Habits survive low motivation because routines automate behavior.",
            "claim_type": "interpretation",
            "confidence": "high",
            "why_it_matters": "m",
        },
        {
            "id": "c3",
            "text": "Remove friction for good actions and add friction for bad ones.",
            "claim_type": "interpretation",
            "confidence": "high",
            "why_it_matters": "m",
        },
        {
            "id": "c4",
            "text": "Systems break in chaotic environments with adverse social pressure.",
            "claim_type": "interpretation",
            "confidence": "medium",
            "why_it_matters": "m",
        },
    ],
    "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
    "production_moves": {
        "segment_to_run": {"name": "s", "goal": "g"},
        "host_questions": [],
        "clip_candidates": [],
        "risk_note": "",
    },
    "guests": [],
    "action_plan_7d": [],
}
transcript = (
    "Host: Systems beat goals when motivation drops. "
    "Guest: Habits survive low motivation because routines automate behavior. "
    "Host: What should listeners do tomorrow? "
    "Guest: Remove friction for good actions and add friction for bad ones. "
    "Host: Where does this break? "
    "Guest: It breaks in chaotic environments where social pressure rewards old behavior."
)


def main() -> None:
    r = v3.build_v3_report(brief, transcript, metadata={})
    om = r.get("output_mode")
    sm = r.get("signal_mode")
    parts = [
        "# Golden E2E fixture (mirrors test_golden_e2e_report_quality_assertions)\n\n",
        f"**output_mode:** `{om}` &nbsp; **signal_mode:** `{sm}`\n\n",
        "---\n\n## render_episode_report_v3_markdown\n\n",
        v3.render_episode_report_v3_markdown(r),
        "\n\n---\n\n## render_unified_episode_export_markdown (SOAPBOXX_STRICT_EXPORT=0)\n\n",
    ]
    old = os.environ.get("SOAPBOXX_STRICT_EXPORT")
    os.environ["SOAPBOXX_STRICT_EXPORT"] = "0"
    try:
        parts.append(v3.render_unified_episode_export_markdown({"report_v3": r}))
    finally:
        if old is None:
            os.environ.pop("SOAPBOXX_STRICT_EXPORT", None)
        else:
            os.environ["SOAPBOXX_STRICT_EXPORT"] = old

    out = ROOT / "reports" / "pytest_golden_e2e_sample.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(parts), encoding="utf-8")
    print(out.resolve())


if __name__ == "__main__":
    main()
