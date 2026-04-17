#!/usr/bin/env python3
"""
Print guest-related workflow signals from the **report artifact** (pipeline JSON).

**Canonical resolution** (stable across bundle shape changes)::

    report = data.get("workflow_report") or data.get("report") or data

**Recommended (ops):** pass a **file path** from ``episode_brief.py --v3 --json-out``.
Stdin is supported for quick hacks; prefer files to avoid shell/pipe truncation issues.

Production loop::

  python scripts/episode_brief.py ... --v3 --json-out reports/sanity.json
  python scripts/print_workflow_guest_signals.py reports/sanity.json

One-line tuple (flag, first guest rows, outreach non-empty)::

  python scripts/print_workflow_guest_signals.py reports/sanity.json --one-line
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict


def _load_json_raw(text: str) -> Any:
    text = text.strip()
    if not text:
        raise ValueError("empty input")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def _resolve_workflow_report(data: Any) -> Dict[str, Any]:
    """
    Resolve the workflow body from a bundle or a bare workflow dict.

    Contract: ``workflow_report`` → ``report`` → root (same dict if already the workflow).
    """
    if not isinstance(data, dict):
        return {}
    report = data.get("workflow_report") or data.get("report") or data
    if not isinstance(report, dict):
        return {}
    return report


def _workflow_guest_rows(wf: Dict[str, Any]) -> list:
    """Prefer ``guests``, then legacy ``guest_recommendations``."""
    g = wf.get("guests")
    if isinstance(g, list):
        return g
    gr = wf.get("guest_recommendations")
    return gr if isinstance(gr, list) else []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print guests (canonical), guest_outreach_targets, guests_from_subject_fallback"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="",
        help="JSON file (bundle or workflow). Prefer this over stdin for reliable ops.",
    )
    parser.add_argument(
        "--one-line",
        action="store_true",
        help="Single line: flag, guest count, outreach present (bool).",
    )
    args = parser.parse_args()

    if args.path:
        with open(args.path, encoding="utf-8") as f:
            raw = f.read()
    else:
        raw = sys.stdin.read()

    try:
        obj = _load_json_raw(raw)
    except Exception as e:
        print(f"NO VALID JSON: {e}", file=sys.stderr)
        return 1

    wf = _resolve_workflow_report(obj)
    if not wf:
        print(
            "NO WORKFLOW OBJECT FOUND (expected workflow_report, report, or root workflow dict).",
            file=sys.stderr,
        )
        return 1

    gr = _workflow_guest_rows(wf)
    oo = wf.get("guest_outreach_targets")
    flag = wf.get("guests_from_subject_fallback")

    if args.one_line:
        n = len(gr) if isinstance(gr, list) else 0
        has_oo = bool(oo)
        print(flag, gr[:5] if isinstance(gr, list) else gr, has_oo)
        return 0

    print("\n=== GUESTS (up to 5) ===")
    print(json.dumps(gr[:5] if isinstance(gr, list) else gr, indent=2, ensure_ascii=False))

    print("\n=== OUTREACH TARGETS ===")
    print(json.dumps(oo if oo is not None else {}, indent=2, ensure_ascii=False))

    print("\n=== SUBJECT FALLBACK FLAG ===")
    print(json.dumps(flag, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
