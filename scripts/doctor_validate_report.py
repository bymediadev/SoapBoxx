#!/usr/bin/env python3
"""
Validate a v3 workflow JSON report (doctor.ps1 / CI).

Checks:
  - `summary` exists and is non-empty
  - `score` is an integer in 0–100
  - Core sections are non-empty (highlights, evidence_map, follow_up_questions)
  - analytics (if present) has at least one non-empty string across standard keys
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def _nonempty_str(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def validate_report(data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["Root must be a JSON object"]

    md = data.get("metadata")
    if isinstance(md, dict) and md.get("export_status") == "insufficient_signal":
        if "summary" not in data or not _nonempty_str(data.get("summary")):
            errors.append("Missing or empty 'summary' field (insufficient_signal export)")
        sc = data.get("score")
        if not isinstance(sc, int) or sc < 0 or sc > 100:
            errors.append(
                "'score' must be an integer between 0 and 100 inclusive (use 0 when export is withheld)"
            )
        if not _nonempty_str(data.get("markdown_export")):
            errors.append("insufficient_signal export requires non-empty 'markdown_export'")
        return errors

    if "summary" not in data or not _nonempty_str(data.get("summary")):
        errors.append("Missing or empty 'summary' field")

    sc = data.get("score")
    if not isinstance(sc, int) or sc < 0 or sc > 100:
        errors.append("'score' must be an integer between 0 and 100 inclusive")

    hl = data.get("highlights")
    if not isinstance(hl, list) or len(hl) == 0:
        errors.append("'highlights' must be a non-empty list")
    else:
        if not any(
            isinstance(h, dict) and _nonempty_str(h.get("insight")) for h in hl
        ):
            errors.append("'highlights' must contain at least one non-empty insight")

    em = data.get("evidence_map")
    if not isinstance(em, list) or len(em) == 0:
        errors.append("'evidence_map' must be a non-empty list")
    else:
        bad = False
        for e in em:
            if not isinstance(e, dict):
                bad = True
                break
            if not _nonempty_str(e.get("claim")) or not _nonempty_str(e.get("evidence")):
                bad = True
                break
        if bad:
            errors.append(
                "'evidence_map' entries must be objects with non-empty 'claim' and 'evidence'"
            )

    fuq = data.get("follow_up_questions")
    if not isinstance(fuq, list) or len(fuq) == 0:
        errors.append("'follow_up_questions' must be a non-empty list")

    an = data.get("analytics")
    if isinstance(an, dict):
        has_any = False
        for k in ("storylines", "topic_signals", "actionable_steps"):
            arr = an.get(k)
            if isinstance(arr, list) and any(_nonempty_str(x) for x in arr):
                has_any = True
                break
        if not has_any:
            errors.append(
                "'analytics' should have at least one non-empty entry in "
                "storylines, topic_signals, or actionable_steps"
            )

    return errors


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: doctor_validate_report.py <report.json>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        return 2
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print("Root must be a JSON object", file=sys.stderr)
        return 1
    errs = validate_report(data)
    if errs:
        for e in errs:
            print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
