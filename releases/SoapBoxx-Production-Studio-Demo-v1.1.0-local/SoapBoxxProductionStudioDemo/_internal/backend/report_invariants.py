"""
Explicit **invariant contracts** for the v3 report (post-build checks).

These are documentation made executable: violations are listed, not necessarily fatal.
Use ``validate_v3_invariants`` for CI or export gates; tune strictness via ``fail_on_soft``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

INVARIANT_CONTRACT_VERSION = "1"


def _word_bag(text: str) -> set:
    return {w for w in str(text or "").lower().split() if len(w) > 2}


def _claim_union_bag(claims: List[Dict[str, Any]]) -> set:
    bag: set = set()
    for c in claims:
        if not isinstance(c, dict):
            continue
        bag |= _word_bag(str(c.get("text") or ""))
    return bag


def _sgv_execution_strings(report: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    cr = report.get("coach_report")
    if not isinstance(cr, dict):
        return out
    ch = cr.get("contrarian_hook")
    if isinstance(ch, dict):
        b = str(ch.get("body") or "").strip()
        if b:
            out.append(b)
    opp = cr.get("opportunities")
    if isinstance(opp, dict):
        for k in ("spinoff_title", "spinoff_structure", "segment_idea"):
            s = str(opp.get(k) or "").strip()
            if s:
                out.append(s)
        for cm in opp.get("clip_moments") or []:
            s = str(cm).strip()
            if s:
                out.append(s)
    return out


def validate_v3_invariants(
    report: Dict[str, Any],
    *,
    fail_on_soft: bool = False,
) -> Dict[str, Any]:
    """
    Returns a result dict:

    - ``ok``: True if no hard (and soft if ``fail_on_soft``) violations
    - ``violations``: list of ``{code, severity, detail}``
    - ``invariant_contract_version``
    """
    violations: List[Dict[str, Any]] = []

    claims = [c for c in (report.get("claims") or []) if isinstance(c, dict)]
    claim_texts = [str(c.get("text") or "").strip() for c in claims if str(c.get("text") or "").strip()]
    bag = _claim_union_bag(claims)

    # Claim invariant: non-empty claim set for full synthesis (soft if diagnostic / empty brief)
    if not claim_texts:
        violations.append(
            {
                "code": "CLAIM_SET_EMPTY",
                "severity": "soft",
                "detail": "No non-empty claims — SGV and claim-quality substrate are degraded.",
            }
        )

    # Decision invariant: exactly one primary cause when trace present
    tr = report.get("_guest_decision_trace")
    if tr is None:
        violations.append(
            {
                "code": "GUEST_DECISION_TRACE_MISSING",
                "severity": "soft",
                "detail": "Expected _guest_decision_trace on built v3 reports.",
            }
        )
    elif isinstance(tr, dict):
        pc = tr.get("decision_primary_cause")
        if pc is None or not str(pc).strip():
            violations.append(
                {
                    "code": "PRIMARY_CAUSE_MISSING",
                    "severity": "hard",
                    "detail": "decision_primary_cause must be a non-empty string when trace exists.",
                }
            )
    else:
        violations.append(
            {"code": "GUEST_DECISION_TRACE_TYPE", "severity": "hard", "detail": "Trace must be a dict."}
        )

    # Identity invariant: core_thesis overlaps claim cluster (lexical)
    nr = report.get("narrative_reconstruction")
    if isinstance(nr, dict) and claim_texts:
        ct = str(nr.get("core_thesis") or "").strip()
        if ct:
            if not (_word_bag(ct) & bag):
                violations.append(
                    {
                        "code": "IDENTITY_THESIS_CLAIM_OVERLAP",
                        "severity": "soft",
                        "detail": "core_thesis shares no content words with claim set (identity vs claims drift).",
                    }
                )

    # SGV invariant: non-empty execution strings touch claim word bag (post-SGV they should)
    if report.get("_sgv_applied") and bag:
        for s in _sgv_execution_strings(report):
            if not (_word_bag(s) & bag):
                violations.append(
                    {
                        "code": "SGV_EXECUTION_UNGROUNDED",
                        "severity": "soft",
                        "detail": f"Execution line has no claim token overlap: {_snippet(s)}",
                    }
                )

    hard = [v for v in violations if v.get("severity") == "hard"]
    soft = [v for v in violations if v.get("severity") == "soft"]
    bad = hard + (soft if fail_on_soft else [])

    return {
        "ok": len(hard) == 0,
        "contract_satisfied": len(violations) == 0,
        "violations": violations,
        "invariant_contract_version": INVARIANT_CONTRACT_VERSION,
        "fail_on_soft_applied": fail_on_soft,
        "all_checks_pass": len(bad) == 0,
    }


def _snippet(s: str, n: int = 80) -> str:
    s = str(s).replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"
