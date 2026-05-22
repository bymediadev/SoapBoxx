# backend/argument_rigor.py
"""Deterministic argument-rigor gates for producer-facing episode quality."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

_CAUSAL_PATTERNS = (
    r"\bcauses?\b",
    r"\bleads? to\b",
    r"\bresults? in\b",
    r"\bdrives?\b",
    r"\breduces?\b",
    r"\bincreases?\b",
    r"\bcreates?\b",
    r"\bproduces?\b",
    r"\bshifts?\b",
)

_METRIC_PATTERNS = (
    r"\bmeasured by\b",
    r"\brate\b",
    r"\brates\b",
    r"\bpercent\b",
    r"\bpercentage\b",
    r"\bscore\b",
    r"\bscores\b",
    r"\battendance\b",
    r"\bretention\b",
    r"\bconversion\b",
    r"\bkpi\b",
    r"\bmetric\b",
    r"\bmetrics\b",
    r"\bindex\b",
    r"\btrend\b",
    r"\b\d+(?:\.\d+)?%",
)

_VAGUE_TERMS = {
    "bad",
    "good",
    "better",
    "worse",
    "problem",
    "issues",
    "thing",
    "stuff",
    "influence",
    "system",
    "power",
    "culture",
    "narrative",
    "agenda",
}

_OBSERVABLE_ACTION_VERBS = {
    "check",
    "compare",
    "look",
    "look up",
    "pull",
    "download",
    "review",
    "audit",
    "call",
    "email",
    "read",
    "verify",
    "map",
    "track",
    "collect",
}

_TIME_BOUND_PATTERNS = (
    r"\bthis week\b",
    r"\bwithin\s+7\s+days\b",
    r"\bwithin\s+one\s+week\b",
    r"\btomorrow\b",
    r"\bby\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\bnext\s+7\s+days\b",
)

_COUNTER_WEAK_PATTERNS = (
    r"\bjust haters\b",
    r"\bobviously false\b",
    r"\bonly idiots\b",
    r"\bstraw man\b",
)


def _word_tokens(text: str) -> List[str]:
    return re.findall(r"[a-z]{3,}", (text or "").lower())


def _has_any_pattern(text: str, patterns: Sequence[str]) -> bool:
    low = (text or "").lower()
    return any(re.search(p, low) for p in patterns)


def _grade_claim_strength(claim: str) -> Dict[str, Any]:
    low = (claim or "").strip()
    reasons: List[str] = []
    passed = True
    if not _has_any_pattern(low, _CAUSAL_PATTERNS):
        passed = False
        reasons.append("Claim is not explicitly causal (missing causes/leads to/reduces language).")
    if not _has_any_pattern(low, _METRIC_PATTERNS):
        passed = False
        reasons.append("Claim is not measurable (no metric, rate, score, or explicit measured-by cue).")
    toks = _word_tokens(low)
    vague_hits = [t for t in toks if t in _VAGUE_TERMS]
    if len(vague_hits) >= 2 and len(toks) < 22:
        passed = False
        reasons.append("Claim is too broad/vague for a defensible episode spine.")
    return {
        "id": "claim_strength",
        "label": "Claim strength (causal + measurable + specific)",
        "passed": passed,
        "severity": "critical",
        "message": "PASS" if passed else " ; ".join(reasons),
    }


def _extract_mechanism_steps(report: Dict[str, Any]) -> List[str]:
    pre = report.get("argument_rigor_input")
    if isinstance(pre, dict):
        chain = pre.get("mechanism_chain")
        if isinstance(chain, list):
            out = [str(x).strip() for x in chain if str(x).strip()]
            if out:
                return out[:4]
    nr = report.get("narrative_reconstruction") if isinstance(report.get("narrative_reconstruction"), dict) else {}
    sm = str(nr.get("supporting_mechanism") or "").strip()
    if not sm:
        sm = str((report.get("coach_report") or {}).get("episode_thesis") or "").strip()
    if not sm:
        return []
    if "->" in sm:
        return [x.strip() for x in sm.split("->") if x.strip()][:4]
    parts = re.split(r"\b(?:then|therefore|which\s+leads\s+to|so\s+that)\b", sm, flags=re.I)
    out = [p.strip(" .") for p in parts if p.strip()]
    return out[:4]


def _step_is_too_abstract(step: str) -> bool:
    toks = _word_tokens(step)
    if not toks:
        return True
    content = [t for t in toks if t not in {"the", "and", "that", "this", "with", "from"}]
    if len(content) <= 2:
        return True
    abstract = sum(1 for t in content if t in _VAGUE_TERMS)
    return abstract >= max(2, len(content) // 2)


def _grade_mechanism(report: Dict[str, Any]) -> Dict[str, Any]:
    steps = _extract_mechanism_steps(report)
    reasons: List[str] = []
    passed = True
    if len(steps) < 3:
        passed = False
        reasons.append("Mechanism chain is missing or incomplete (need A -> B -> C).")
    else:
        if any(_step_is_too_abstract(s) for s in steps[:3]):
            passed = False
            reasons.append("Mechanism chain includes abstract steps that are not directly observable.")
    return {
        "id": "mechanism_chain",
        "label": "Mechanism quality (A -> B -> C is concrete)",
        "passed": passed,
        "severity": "critical",
        "message": "PASS" if passed else " ; ".join(reasons),
    }


def _evidence_quality_breakdown(report: Dict[str, Any]) -> Dict[str, bool]:
    rows = [r for r in (report.get("evidence_mapping") or []) if isinstance(r, dict)]
    claims_blob = " ".join(str(r.get("claim") or "") for r in rows).lower()
    ev_blob = " ".join(str(r.get("evidence") or "") for r in rows).lower()
    full = claims_blob + " " + ev_blob

    has_primary = any(
        k in full
        for k in (
            "cdc",
            "nces",
            "department of education",
            "dataset",
            "table",
            "court",
            "statute",
            "form 990",
            "report",
            "doi",
        )
    ) or any(str(r.get("verification_note") or "").strip() for r in rows)

    guest_blob = " ".join(
        str(g.get("role") or "") + " " + str(g.get("title") or "") + " " + str(g.get("guest") or "")
        for g in (report.get("guests") or [])
        if isinstance(g, dict)
    ).lower()
    has_secondary = any(k in guest_blob for k in ("historian", "scholar", "analyst", "research", "author", "professor"))

    has_case = bool(re.search(r"\b(19|20)\d{2}\b", full)) or any(
        k in full
        for k in (
            "district",
            "state",
            "county",
            "school board",
            "classroom",
            "case",
            "example",
        )
    )

    q_blob = " ".join(str(q) for q in ((report.get("coach_report") or {}).get("follow_up_questions") or []))
    q_blob += " " + " ".join(str(v.get("counterpunch") or "") for v in (report.get("engagement_questions") or {}).values() if isinstance(v, dict))
    q_low = q_blob.lower()
    has_counter = any(k in q_low for k in ("counter", "if i'm wrong", "if i am wrong", "other side", "strongest"))

    return {
        "primary": has_primary,
        "secondary": has_secondary,
        "example": has_case,
        "counterexample": has_counter,
    }


def _grade_evidence(report: Dict[str, Any]) -> Dict[str, Any]:
    b = _evidence_quality_breakdown(report)
    missing = [k for k, v in b.items() if not v]
    passed = len(missing) == 0
    msg = "PASS"
    if not passed:
        msg = "Missing evidence types: " + ", ".join(missing)
    return {
        "id": "evidence_quality",
        "label": "Evidence quality (primary + secondary + case + counterexample)",
        "passed": passed,
        "severity": "critical",
        "message": msg,
    }


def _best_counterargument_text(report: Dict[str, Any]) -> str:
    cr = report.get("coach_report") if isinstance(report.get("coach_report"), dict) else {}
    for q in cr.get("follow_up_questions") or []:
        s = str(q).strip()
        if not s:
            continue
        low = s.lower()
        if any(k in low for k in ("counter", "if i'm wrong", "other side", "strongest")):
            return s
    eng = report.get("engagement_questions") or {}
    for tri in eng.values():
        if isinstance(tri, dict):
            s = str(tri.get("counterpunch") or tri.get("contrarian") or "").strip()
            if s:
                return s
    return ""


def _grade_counterargument(report: Dict[str, Any]) -> Dict[str, Any]:
    txt = _best_counterargument_text(report)
    passed = True
    reasons: List[str] = []
    if len(txt.split()) < 8:
        passed = False
        reasons.append("Counterargument is too short or missing.")
    low = txt.lower()
    if any(re.search(p, low) for p in _COUNTER_WEAK_PATTERNS):
        passed = False
        reasons.append("Counterargument appears strawmanned/dismissive.")
    if not any(k in low for k in ("claim", "would", "evidence", "challenge", "wrong", "counter")):
        passed = False
        reasons.append("Counterargument does not directly attack the claim logic.")
    return {
        "id": "counterargument",
        "label": "Counterargument strength",
        "passed": passed,
        "severity": "major",
        "message": "PASS" if passed else " ; ".join(reasons),
    }


def _extract_weekly_action(report: Dict[str, Any]) -> str:
    pre = report.get("argument_rigor_input")
    if isinstance(pre, dict):
        wa = str(pre.get("weekly_action") or "").strip()
        if wa:
            return wa
    cr = report.get("coach_report") if isinstance(report.get("coach_report"), dict) else {}
    steps = [str(x).strip() for x in (cr.get("immediate_fix_plan") or []) if str(x).strip()]
    return steps[0] if steps else ""


def _grade_actionability(report: Dict[str, Any]) -> Dict[str, Any]:
    act = _extract_weekly_action(report)
    passed = True
    reasons: List[str] = []
    low = act.lower()
    if not act:
        passed = False
        reasons.append("No weekly action present.")
    if act and not any(v in low for v in _OBSERVABLE_ACTION_VERBS):
        passed = False
        reasons.append("Action is not observable (missing concrete verb).")
    if act and not _has_any_pattern(low, _TIME_BOUND_PATTERNS):
        passed = False
        reasons.append("Action is not time-bound (this week / tomorrow / by day).")
    if act and len(act.split()) < 7:
        passed = False
        reasons.append("Action is too vague; needs specific object and context.")
    return {
        "id": "weekly_action",
        "label": "Actionability (observable + time-bound)",
        "passed": passed,
        "severity": "major",
        "message": "PASS" if passed else " ; ".join(reasons),
    }


def evaluate_argument_rigor_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate argument rigor and return pass/fail gates with weighted score."""
    cr = report.get("coach_report") if isinstance(report.get("coach_report"), dict) else {}
    thesis = str(cr.get("episode_thesis") or "").strip()
    if not thesis:
        nr = report.get("narrative_reconstruction") if isinstance(report.get("narrative_reconstruction"), dict) else {}
        thesis = str(nr.get("core_thesis") or "").strip()

    gates = [
        _grade_claim_strength(thesis),
        _grade_mechanism(report),
        _grade_evidence(report),
        _grade_counterargument(report),
        _grade_actionability(report),
    ]

    weights = {
        "claim_strength": 30,
        "mechanism_chain": 20,
        "evidence_quality": 25,
        "counterargument": 15,
        "weekly_action": 10,
    }
    score = 0
    for gate in gates:
        if gate.get("passed"):
            score += weights.get(str(gate.get("id")), 0)
    critical_failed = sum(1 for gate in gates if gate.get("severity") == "critical" and not gate.get("passed"))

    status = "PASS"
    if score < 60 or critical_failed >= 2:
        status = "FAIL"
    elif score < 80 or critical_failed >= 1:
        status = "REVIEW"

    notes: List[str] = []
    if status == "FAIL":
        notes.append("Argument rigor gates failed: tighten claim, mechanism, and evidence before distribution.")
    elif status == "REVIEW":
        notes.append("Argument rigor is moderate: strengthen failed gates before external send.")

    return {
        "score": int(score),
        "status": status,
        "critical_failed": critical_failed,
        "gates": gates,
        "notes": notes,
        "thesis_evaluated": thesis,
    }


__all__ = ["evaluate_argument_rigor_report"]
