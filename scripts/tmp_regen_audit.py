import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path


def _evaluate_checks(md: str, md_path: Path, out: dict) -> dict:
    low = md.lower()
    checks = {}
    checks["A_markdown_export_present"] = bool(md.strip())
    checks["B_finalizer_applied"] = all(
        x not in md
        for x in (
            "Primary workflow:",
            "Compact brief (v2 filename):",
            "Core Narrative:",
        )
    )
    checks["C_no_8_9_10_meta"] = all(
        x not in md
        for x in (
            "Episode Comparison Graph",
            "What this doesn",
            "If you want more",
            "No-worry publishing standard",
        )
    )
    checks["D_utf8_bom"] = md_path.read_bytes().startswith(b"\xef\xbb\xbf")
    checks["E_genre_not_entertainment_for_title"] = (
        ("**Genre:** Education / Society" in md)
        or ("Genre: Education / Society" in md)
    )

    m = re.search(r"\*\*Thesis \(fixed\):\*\*\s*(.+)", md)
    thesis = m.group(1).strip() if m else ""
    checks["F_thesis_not_quote_like"] = bool(thesis) and (
        not re.match(r"(?i)^(host|guest|speaker)\s*:", thesis)
    ) and ("the core theme of this episode is" not in thesis.lower())

    bad_phrases = (
        "it's like you're just a speck",
        "it made me realize how much of it was",
        "it's like that's another example of like",
    )
    checks["G_followup_filters_hold"] = all(p not in low for p in bad_phrases)
    checks["H_segment_filter_hold"] = all(
        p not in low
        for p in (
            "## 5. segment planning\n- **it's like you're just a speck",
            "## 5. segment planning\n- it's like you're just a speck",
        )
    )

    r3 = out.get("report_v3") if isinstance(out.get("report_v3"), dict) else {}
    from episode_report_v3 import validate_references
    valid = {
        str(c.get("id"))
        for c in (r3.get("claims") or [])
        if isinstance(c, dict) and c.get("id")
    }
    for e in (r3.get("evidence_mapping") or []):
        if isinstance(e, dict) and e.get("id"):
            valid.add(str(e.get("id")))
    ok, errs = validate_references(r3, valid_claim_ids=valid)
    checks["I_reference_validation_ok"] = bool(ok)
    return {"checks": checks, "thesis": thesis, "reference_errors": errs[:3]}


def main() -> int:
    root = Path(r"C:/Users/yasuk/SoapBoxx")
    os.chdir(root)

    # Controlled deterministic run (no Ollama/editorial mutation).
    os.environ.pop("SOAPBOXX_OLLAMA_MODEL", None)
    os.environ["SOAPBOXX_WORKFLOW_USE_AI"] = "0"
    os.environ["SOAPBOXX_EDITORIAL_PASS"] = "0"
    os.environ["SOAPBOXX_MODE"] = "growth"

    sys.path.insert(0, str(root / "backend"))
    from feedback_engine import FeedbackEngine
    from episode_report_v3 import finalize_unified_markdown_export, validate_references

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if len(sys.argv) > 1 and sys.argv[1] == "--existing":
        md_path = root / "reports" / "SoapBoxx_Episode_Report_regenerated.md"
        js_path = root / "reports" / "soapboxx_regenerated_bundle.json"
        md = md_path.read_text(encoding="utf-8", errors="replace")
        out = {}
        if js_path.exists():
            try:
                out = json.loads(js_path.read_text(encoding="utf-8"))
            except Exception:
                out = {}
        ev = _evaluate_checks(md, md_path, out)
        summary = {
            "timestamp": ts,
            "md_path": str(md_path),
            "json_path": str(js_path),
            **ev,
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    md_path = root / "reports" / f"SoapBoxx_Episode_Report_regenerated_audit_{ts}.md"
    js_path = root / "reports" / f"soapboxx_regenerated_bundle_audit_{ts}.json"

    transcript = (root / "reports" / "stub_rockefeller_education_transcript.txt").read_text(
        encoding="utf-8"
    )
    title = (
        "Brainwash! - The Rockefeller School Psyop WORSE Than You Think | Spencer Taylor 410"
    )
    out = FeedbackEngine().generate_network_brief_v3(
        transcript,
        title=title,
        creator="Julian Dorey",
        genre="Entertainment",
        strict_references=True,
        include_v2_markdown=True,
        include_workflow_json=True,
    )
    md = finalize_unified_markdown_export(str(out.get("markdown_export") or ""))
    md_path.write_text(md, encoding="utf-8-sig")

    payload = {
        "report_v3": out.get("report_v3"),
        "workflow_report": out.get("workflow_report"),
        "markdown_export": md,
        "warnings": out.get("warnings"),
        "model": out.get("model"),
    }
    js_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    ev = _evaluate_checks(md, md_path, out)

    summary = {
        "timestamp": ts,
        "md_path": str(md_path),
        "json_path": str(js_path),
        **ev,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
