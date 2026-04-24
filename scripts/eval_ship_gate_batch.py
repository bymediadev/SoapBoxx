#!/usr/bin/env python3
"""
Batch-evaluate ``assess_brief_intelligence_ship`` (and ``alignment_debug``) on saved brief JSON files.

Use this to calibrate thresholds against real episodes: you label outcomes, the script reports
agreement and per-episode metrics. Does **not** change scoring; read-only + reporting.

Per row (JSON):
- ``ship_*`` from ``assess_brief_intelligence_ship``
- ``alignment_*`` from ``alignment_debug``
- ``ship_notes`` — gate note list when present
- ``reason`` — ship notes joined, or a metric fallback when notes are empty
- ``calibration_eval`` — PASS/REVIEW/FAIL from the **harness** rubric (tune ``_C_*`` constants
  at top of this file; default bands match the usual 0.65/0.4/0.5 split)
- ``match`` / ``match_calibration`` — agreement with your human label vs ship vs calibration rubric

Usage:

  # Manifest (see config/eval_manifest.example.json)
  python scripts/eval_ship_gate_batch.py --manifest config/eval_manifest.example.json

  # One or more brief JSON files
  python scripts/eval_ship_gate_batch.py path/to/brief1.json

  # JSON lines to a file
  python scripts/eval_ship_gate_batch.py --manifest man.json --out results.json

  # No disk: built-in minimal briefs (smoke; needs backend imports only)
  python scripts/eval_ship_gate_batch.py --smoke
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Calibrated decision bands for *eval / reporting only* (does not change ship gate code).
# Tune these when comparing harness rows to your human labels.
_C_PASS_ALIGN = 0.65
_C_PASS_SUP = 0.65
_C_PASS_STD_MAX = 0.25
_C_FAIL_ALIGN = 0.5
_C_FAIL_SUP = 0.4
_C_REVIEW_SUP_HIGH = 0.65
_C_DISPERSION_HIGH = 0.35
_C_TOPK_WEAK = 0.6


def _sys_path() -> None:
    backend = os.path.join(_REPO, "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)


def _load_brief(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _run_one(
    brief: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    _sys_path()
    try:
        from intelligence_ship_gate import assess_brief_intelligence_ship  # type: ignore
    except ImportError as e:
        return None, f"import error: {e}"
    try:
        out = assess_brief_intelligence_ship(brief)
    except Exception as e:
        return None, f"assess_brief_intelligence_ship: {e}"
    return out, None


def _normalize_label(x: Any) -> Optional[str]:
    if x is None or x is False:
        return None
    s = str(x).strip().upper()
    if s in ("PASS", "REVIEW", "FAIL"):
        return s
    return None


def calibration_eval_label(
    alignment_score: Any,
    support_ratio: Any,
    std_dev: Any,
) -> str:
    """
    Map metrics to PASS / REVIEW / FAIL for spreadsheet calibration (harness only).

    Rules (default):
    - FAIL: alignment < 0.5 OR support_ratio < 0.4
    - PASS: alignment ≥ 0.65 AND support_ratio ≥ 0.65 AND std_dev ≤ 0.25
    - REVIEW: else (e.g. borderline align/support, or std_dev > 0.25)
    """
    if alignment_score is None or support_ratio is None or std_dev is None:
        return "UNKNOWN"
    try:
        a = float(alignment_score)
        s = float(support_ratio)
        d = float(std_dev)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if a < _C_FAIL_ALIGN or s < _C_FAIL_SUP:
        return "FAIL"
    if a >= _C_PASS_ALIGN and s >= _C_PASS_SUP and d <= _C_PASS_STD_MAX:
        return "PASS"
    if (0.5 <= a < _C_PASS_ALIGN) or (0.4 <= s < _C_REVIEW_SUP_HIGH) or d > _C_PASS_STD_MAX:
        return "REVIEW"
    return "REVIEW"


def _metric_reason(
    a: Any,
    s: Any,
    d: Any,
    tkm: Any,
) -> str:
    try:
        a = float(a) if a is not None else None
        s = float(s) if s is not None else None
        d = float(d) if d is not None else None
        t = float(tkm) if tkm is not None else None
    except (TypeError, ValueError):
        return "Unparseable metrics"
    parts: List[str] = []
    if a is not None and a < 0.5:
        parts.append(f"low alignment score ({a:.2f}, threshold < {_C_FAIL_ALIGN})")
    if s is not None and s < 0.4:
        parts.append(f"low support ratio ({s:.2f}, threshold < {_C_FAIL_SUP})")
    if s is not None and 0.4 <= s < 0.65:
        parts.append(f"borderline support coverage ({s:.2f})")
    if d is not None and d > _C_DISPERSION_HIGH:
        parts.append(f"high claim dispersion (std {d:.2f})")
    elif d is not None and d > _C_PASS_STD_MAX and (s is None or s >= 0.4):
        parts.append(f"elevated dispersion (std {d:.2f} > {_C_PASS_STD_MAX})")
    if t is not None and t < _C_TOPK_WEAK and (s is None or s < 0.5):
        parts.append(f"weak top-claim mean ({t:.2f})")
    if not parts and a is not None and s is not None and d is not None:
        if a >= 0.65 and s >= 0.65 and d <= 0.25:
            return "strong alignment (calibration band)"
        return f"align={a:.2f}, sup={s:.2f}, std={d:.2f} (use ship_notes if empty)"
    return "; ".join(parts) if parts else "no primary reason inferred"


def _enrich_with_reason_and_eval(row: Dict[str, Any], out: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if row.get("error"):
        row["calibration_eval"] = "UNKNOWN"
        row["reason"] = str(row["error"])
        return row
    if row.get("skip_reason"):
        row["calibration_eval"] = "UNKNOWN"
        row["reason"] = f"Skipped: {row['skip_reason']}"
        return row

    ad_notes = (out or {}).get("notes") or []
    row["ship_notes"] = [str(n) for n in ad_notes] if ad_notes else None

    a = row.get("alignment_score")
    s = row.get("alignment_support_ratio")
    d = row.get("alignment_std_dev")
    t = row.get("alignment_top_k_mean")
    row["calibration_eval"] = calibration_eval_label(a, s, d)

    if ad_notes:
        row["reason"] = "; ".join(str(n) for n in ad_notes)
    else:
        row["reason"] = _metric_reason(a, s, d, t)

    lab = _normalize_label(row.get("label"))
    if lab:
        sg = str(row.get("ship_gate") or "").strip().upper()
        if sg in ("PASS", "REVIEW", "FAIL"):
            row["match"] = bool(sg == lab)
        else:
            row["match"] = None
        ce = str(row.get("calibration_eval") or "")
        if ce in ("PASS", "REVIEW", "FAIL"):
            row["match_calibration"] = bool(ce == lab)
        else:
            row["match_calibration"] = None
    return row


def _row_from_result(
    episode_id: str,
    source: str,
    out: Optional[Dict[str, Any]],
    err: Optional[str],
    label: Optional[str],
) -> Dict[str, Any]:
    if err:
        row = {
            "id": episode_id,
            "source": source,
            "error": err,
            "label": label,
        }
        return _enrich_with_reason_and_eval(row, None)
    if out is None:
        row = {
            "id": episode_id,
            "source": source,
            "ship_gate": None,
            "skip_reason": "no_argument_spine",
            "label": label,
        }
        return _enrich_with_reason_and_eval(row, None)
    ad = (out.get("alignment_debug") or {}) if isinstance(out.get("alignment_debug"), dict) else {}
    row: Dict[str, Any] = {
        "id": episode_id,
        "source": source,
        "ship_gate": out.get("ship_gate"),
        "ship_score": out.get("ship_score"),
        "ship_score_weighted": out.get("ship_score_weighted"),
        "label": label,
    }
    if ad:
        for k, v in ad.items():
            if k == "thesis" and v:
                s = str(v)
                v = s[:200] + ("…" if len(s) > 200 else "")
            row[f"alignment_{k}"] = v
    row = _enrich_with_reason_and_eval(row, out)
    return row


def _smoke_briefs() -> List[Tuple[str, str, Dict[str, Any], Optional[str]]]:
    """(id, source label, brief, human label)"""
    good = {
        "argument_spine": {
            "data": {
                "thesis": (
                    "Policy pressure leads public agencies to delay sensitive disclosures until after major "
                    "elections in order to reduce political backlash and protect credibility in office."
                ),
                "claims": [
                    {
                        "claim": (
                            "Elected pressure makes agencies postpone sensitive disclosure until after the "
                            "election season when transparency would be costly to incumbents."
                        ),
                    },
                    {
                        "claim": (
                            "Disclosure and policy transparency timing still tracks electoral incentives after "
                            "major elections for agencies that face public backlash risk in the same cycle."
                        ),
                    },
                ],
            }
        },
        "claims": [],
    }
    tag = {
        "argument_spine": {
            "data": {
                "thesis": "A; B; C; D; E; F; G; H",
                "claims": [{"claim": "Some filler claim text with enough length for alignment scoring only."}],
            }
        },
        "claims": [],
    }
    return [
        ("smoke_ok", "inline:smoke_ok", good, None),
        ("smoke_tag", "inline:smoke_tag", tag, None),
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=str, help="JSON manifest with episodes[] entries")
    ap.add_argument("--out", type=str, help="Write full results as JSON to this path")
    ap.add_argument("--smoke", action="store_true", help="Run two built-in briefs; no manifest/files")
    ap.add_argument("briefs", nargs="*", help="Paths to brief JSON files (label only if manifest absent)")
    args = ap.parse_args()

    jobs: List[Tuple[str, str, Optional[str]]] = []
    if args.smoke:
        for eid, src, brief, lab in _smoke_briefs():
            jobs.append((eid, json.dumps(brief), lab))
    elif args.manifest:
        raw = args.manifest
        if os.path.isfile(raw):
            path_m = os.path.abspath(raw)
        else:
            cand = os.path.join(_REPO, raw)
            path_m = cand if os.path.isfile(cand) else os.path.abspath(raw)
        if not os.path.isfile(path_m):
            print(
                f"Manifest not found: {raw!r}. Copy config/eval_manifest.example.json and set your brief paths.",
                file=sys.stderr,
            )
            return 2
        try:
            with open(path_m, encoding="utf-8") as f:
                m = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"Failed to read manifest {path_m!r}: {e}", file=sys.stderr)
            return 2
        eps = m.get("episodes") or []
        for i, e in enumerate(eps):
            if not isinstance(e, dict):
                continue
            eid = str(e.get("id", f"ep_{i}"))
            bp = e.get("brief") or e.get("path") or e.get("brief_path")
            if not bp:
                print(f"skip: missing brief path: {eid}", file=sys.stderr)
                continue
            path = bp if os.path.isabs(bp) else os.path.join(_REPO, bp)
            lab = _normalize_label(e.get("label") or e.get("expected"))
            jobs.append((eid, path, lab))
    else:
        for p in args.briefs:
            path = p if os.path.isabs(p) else os.path.join(os.getcwd(), p)
            eid = os.path.splitext(os.path.basename(path))[0]
            jobs.append((eid, path, None))

    if not jobs:
        print("No episodes to run. Use --manifest, brief paths, or --smoke.", file=sys.stderr)
        return 2

    rows: List[Dict[str, Any]] = []
    for eid, src, lab in jobs:
        if src.startswith("{"):
            brief = json.loads(src)
            path_display = "inline"
        else:
            path_display = src
            try:
                brief = _load_brief(src)
            except (OSError, json.JSONDecodeError) as e:
                rows.append(_row_from_result(eid, path_display, None, f"load: {e}", lab))
                continue
        out, err = _run_one(brief)
        rows.append(_row_from_result(eid, path_display, out, err, lab))

    labeled = [r for r in rows if r.get("label")]
    matched = [r for r in labeled if r.get("match") is True]
    agreement = (len(matched) / len(labeled)) if labeled else None

    n_match_cal = sum(1 for r in rows if r.get("match_calibration") is True)
    n_labeled_cal = sum(1 for r in rows if r.get("match_calibration") is not None)
    agreement_cal = (n_match_cal / n_labeled_cal) if n_labeled_cal else None

    summary = {
        "n_episodes": len(rows),
        "n_labeled": len(labeled),
        "n_matched": len(matched),
        "agreement": round(agreement, 4) if agreement is not None else None,
        "n_labeled_calibration": n_labeled_cal,
        "n_matched_calibration": n_match_cal,
        "agreement_calibration": round(agreement_cal, 4) if agreement_cal is not None else None,
    }

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "rows": rows}, f, indent=2)

    # Human-readable
    print(json.dumps(summary, indent=2))
    for r in rows:
        gate = r.get("ship_gate") or r.get("error") or r.get("skip_reason") or "?"
        parts = [str(r.get("id")), str(gate)]
        if r.get("alignment_score") is not None:
            parts.append(f"align={r['alignment_score']}")
        if r.get("alignment_support_ratio") is not None:
            parts.append(f"sup={r['alignment_support_ratio']}")
        if r.get("alignment_std_dev") is not None:
            parts.append(f"std={r['alignment_std_dev']}")
        if r.get("alignment_low_support_count") is not None:
            parts.append(f"low_n={r['alignment_low_support_count']}")
        if r.get("label"):
            parts.append(f"label={r['label']}")
        if r.get("match") is not None:
            parts.append(f"match={r['match']}")
        if r.get("calibration_eval"):
            parts.append(f"calib={r['calibration_eval']}")
        if r.get("match_calibration") is not None:
            parts.append(f"match_calib={r['match_calibration']}")
        if r.get("reason"):
            parts.append(f"reason={r['reason'][:120]}")
        print("\t".join(parts))

    if agreement is not None and labeled:
        print(f"\nAgreement with labels: {summary['agreement']:.1%} ({len(matched)}/{len(labeled)})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
