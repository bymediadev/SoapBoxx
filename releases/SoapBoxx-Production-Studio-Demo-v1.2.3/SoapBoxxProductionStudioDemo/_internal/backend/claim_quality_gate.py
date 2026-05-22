"""
Lightweight **substrate** check on ``claims`` before SGV: fragments, near-duplicates, specificity.

Does not judge factual truth — only whether the claim set looks worth snapping synthesis to.
Stamps ``_claim_quality`` on the report; SGV may relax lexical strictness when ``warning`` is true
(fewer forced rewrites onto weak claim text — see :mod:`semantic_grounding_validator`).
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Sequence, Tuple

# Tunable via code review; keep intentionally simple.
_MIN_CHARS = 32
_MIN_WORDS = 6
_MIN_CONTENT_WORDS = 3  # len>2, not stopword-like
_DUPLICATE_JACCARD = 0.82
_WARN_SCORE_BELOW = 0.52

_STOP_LIKE = frozenset(
    "the a an and or but if to of in on for with as at by from is are was were be been being "
    "has have had do does did will would could should may might must this that these those it its "
    "we you they he she i my our your their not no yes so than then there here when what which who".split()
)


def _sgv_enabled() -> bool:
    v = os.environ.get("SOAPBOXX_CLAIM_QUALITY_GATE", "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    return True


def _words(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9']+", (text or "").lower())


def _content_words(text: str) -> List[str]:
    return [w for w in _words(text) if len(w) > 2 and w not in _STOP_LIKE]


def _is_fragment(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < _MIN_CHARS:
        return True
    ws = _words(t)
    if len(ws) < _MIN_WORDS:
        return True
    if len(_content_words(t)) < _MIN_CONTENT_WORDS:
        return True
    return False


def _jaccard_bags(a: str, b: str) -> float:
    sa = set(_content_words(a))
    sb = set(_content_words(b))
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def _has_redundant_pair(texts: List[str]) -> bool:
    n = len(texts)
    for i in range(n):
        for j in range(i + 1, n):
            if _jaccard_bags(texts[i], texts[j]) >= _DUPLICATE_JACCARD:
                return True
    return False


def _has_specificity(texts: List[str]) -> bool:
    """At least one claim looks like a concrete proposition (verb-ish or numeric, enough content)."""
    for t in texts:
        s = (t or "").strip()
        if not s:
            continue
        if re.search(r"\d", s):
            return True
        low = s.lower()
        if any(
            x in low
            for x in (
                " because ",
                " therefore ",
                " causes ",
                " leads ",
                " increases ",
                " decreases ",
                " reduces ",
                " improves ",
                " fails ",
                " must ",
                " should ",
            )
        ):
            return True
        if len(_content_words(s)) >= 5 and len(_words(s)) >= 8:
            return True
    return False


def assess_claim_quality(claims: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Returns ``score`` in [0, 1], ``warning`` if substrate is weak, and ``signals`` detail.
    """
    texts = [str(c.get("text") or "").strip() for c in claims if isinstance(c, dict)]
    texts = [t for t in texts if t]
    n = len(texts)

    if n == 0:
        return {
            "score": 0.0,
            "warning": True,
            "signals": {
                "fragment_ratio": 1.0,
                "redundant_pair": False,
                "specificity_ok": False,
                "claim_count": 0,
            },
        }

    frag_ct = sum(1 for t in texts if _is_fragment(t))
    fragment_ratio = frag_ct / n
    redundant = _has_redundant_pair(texts)
    specificity_ok = _has_specificity(texts)

    # Score: penalize fragments heavily, redundancy moderately, missing specificity.
    score = 1.0
    score -= min(0.55, fragment_ratio * 0.9)
    if redundant:
        score -= 0.22
    if not specificity_ok:
        score -= 0.18
    score = max(0.0, min(1.0, round(score, 4)))

    warning = score < _WARN_SCORE_BELOW

    return {
        "score": score,
        "warning": warning,
        "signals": {
            "fragment_ratio": round(fragment_ratio, 4),
            "fragments_count": frag_ct,
            "redundant_pair": redundant,
            "specificity_ok": specificity_ok,
            "claim_count": n,
        },
    }


def apply_claim_quality_gate(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stamp ``_claim_quality`` on ``report``. No-op when disabled or no claims.
    """
    if not _sgv_enabled():
        report["_claim_quality"] = {"skipped": True, "reason": "SOAPBOXX_CLAIM_QUALITY_GATE=0"}
        return report

    claims = [c for c in (report.get("claims") or []) if isinstance(c, dict)]
    report["_claim_quality"] = assess_claim_quality(claims)
    return report
