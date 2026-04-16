"""
Semantic Grounding Validator (SGV): one post-assembly pass — text must be explainable from ``claims``.

Runs after :func:`episode_report_v3.apply_identity_consistency_to_report_v3`, before guest trace /
downstream render. Intentionally lexical and deterministic (no embeddings).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Minimum overlapping content-word hits vs union of claim word bags.
_MIN_OVERLAP_WORDS = 3
_MIN_OVERLAP_SHORT = 2  # for single-line hooks / short lines


def _sgv_enabled() -> bool:
    v = os.environ.get("SOAPBOXX_SGV", "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    return True


def _claim_texts(claims: Sequence[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        t = str(c.get("text") or "").strip()
        if t:
            out.append(t)
    return out


def _word_bag(text: str) -> set:
    return {w for w in text.lower().split() if len(w) > 2}


def _union_bag(claim_texts: List[str]) -> set:
    bag: set = set()
    for t in claim_texts:
        bag |= _word_bag(t)
    return bag


def _overlap_count(text: str, bag: set) -> int:
    if not text or not bag:
        return 0
    return sum(1 for w in _word_bag(text) if w in bag)


def _is_grounded(
    text: str,
    bag: set,
    *,
    short: bool = False,
    min_main: int = _MIN_OVERLAP_WORDS,
    min_short: int = _MIN_OVERLAP_SHORT,
) -> bool:
    n = _overlap_count(text, bag)
    need = min_short if short else min_main
    return n >= need


def _closest_claim(text: str, claim_texts: List[str]) -> str:
    if not claim_texts:
        return ""
    if not text.strip():
        return claim_texts[0]
    tb = _word_bag(text)
    best = claim_texts[0]
    best_score = -1
    for c in claim_texts:
        inter = len(tb & _word_bag(c))
        if inter > best_score:
            best_score = inter
            best = c
    return best


def _trim(s: str, max_chars: int = 360) -> str:
    s = str(s).strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1].rstrip() + "…"


def apply_semantic_grounding_validator(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure narrative + coach execution strings + follow-ups tie lexically to ``claims``.

    Sets ``_sgv_applied``, ``_sgv_status``, ``_sgv_rewrite_count`` (and optional section flags).
    """
    if not _sgv_enabled():
        report["_sgv_status"] = "DISABLED"
        report["_sgv_applied"] = False
        return report

    claims = [c for c in (report.get("claims") or []) if isinstance(c, dict)]
    claim_texts = _claim_texts(claims)
    if not claim_texts:
        report["_sgv_status"] = "NO_CLAIMS_SKIP"
        report["_sgv_applied"] = False
        return report

    cq = report.get("_claim_quality") if isinstance(report.get("_claim_quality"), dict) else {}
    relax = bool(cq.get("warning")) and not cq.get("skipped")
    min_main = 2 if relax else _MIN_OVERLAP_WORDS
    min_short = 1 if relax else _MIN_OVERLAP_SHORT
    if relax:
        report["_sgv_relaxed_for_claim_quality"] = True

    bag = _union_bag(claim_texts)
    rewrites = 0
    followups_touched = 0

    def _maybe_rewrite(val: str, *, short: bool = False) -> Tuple[str, bool]:
        s = str(val or "").strip()
        if not s:
            return s, False
        if _is_grounded(s, bag, short=short, min_main=min_main, min_short=min_short):
            return s, False
        return _trim(_closest_claim(s, claim_texts)), True

    # --- A. Core narrative (narrative_reconstruction) ---
    nr = report.get("narrative_reconstruction")
    if not isinstance(nr, dict):
        nr = {}
        report["narrative_reconstruction"] = nr
    for key in ("core_thesis", "supporting_mechanism", "practical_translation"):
        raw = str(nr.get(key) or "").strip()
        if not raw:
            continue
        fixed, ch = _maybe_rewrite(raw, short=False)
        if ch:
            nr[key] = fixed
            rewrites += 1
            report["_sgv_narrative_rewritten"] = True

    # --- B. Coach execution layer (hooks, clips, contrarian) ---
    cr = report.get("coach_report")
    if isinstance(cr, dict):
        ch = cr.get("contrarian_hook")
        if isinstance(ch, dict):
            body = str(ch.get("body") or "").strip()
            if body:
                nb, chg = _maybe_rewrite(body, short=True)
                if chg:
                    ch["body"] = nb
                    cr["contrarian_hook"] = ch
                    rewrites += 1
                    report["_sgv_contrarian_rewritten"] = True

        opp = cr.get("opportunities")
        if isinstance(opp, dict):
            for key in ("spinoff_title", "spinoff_structure", "segment_idea"):
                raw = str(opp.get(key) or "").strip()
                if not raw:
                    continue
                fixed, chg = _maybe_rewrite(raw, short=key != "spinoff_structure")
                if chg:
                    opp[key] = fixed
                    rewrites += 1
            cms = opp.get("clip_moments")
            if isinstance(cms, list) and cms:
                new_cms: List[str] = []
                for item in cms:
                    s = str(item).strip()
                    if not s:
                        continue
                    fixed, chg = _maybe_rewrite(s, short=True)
                    if chg:
                        rewrites += 1
                    new_cms.append(fixed)
                opp["clip_moments"] = new_cms
            cr["opportunities"] = opp

        fu = cr.get("follow_up_questions")
        if isinstance(fu, list) and fu:
            new_fu: List[str] = []
            for q in fu:
                s = str(q).strip()
                if not s:
                    continue
                if _is_grounded(s, bag, short=False, min_main=min_main, min_short=min_short):
                    new_fu.append(s)
                else:
                    anchor = _closest_claim(s, claim_texts)
                    new_fu.append(_trim(f"Grounded in your claim: {anchor[:200]}", 420))
                    rewrites += 1
                    followups_touched += 1
            cr["follow_up_questions"] = new_fu

        report["coach_report"] = cr

    # --- C. Engagement triads (per claim) — replace line with claim-derived template if empty of overlap ---
    eng = report.get("engagement_questions")
    if isinstance(eng, dict):
        for cid, tri in list(eng.items()):
            if not isinstance(tri, dict):
                continue
            ctext = ""
            for c in claims:
                if str(c.get("id")) == str(cid):
                    ctext = str(c.get("text") or "").strip()
                    break
            if not ctext:
                continue
            cbag = _word_bag(ctext)
            new_tri = dict(tri)
            for qk in (
                "failure_case",
                "constraint",
                "contrarian",
                "application",
                "counterpunch",
                "validation",
            ):
                if qk not in new_tri:
                    continue
                line = str(new_tri.get(qk) or "").strip()
                if not line:
                    continue
                # Must share vocabulary with *this* claim, not just global bag.
                if len(_word_bag(line) & cbag) >= 2 or _overlap_count(line, cbag) >= min_short:
                    continue
                focus = ctext[:120] + ("…" if len(ctext) > 120 else "")
                if qk in ("validation",):
                    new_tri[qk] = f"What evidence would confirm or refute this claim: {focus}"
                elif qk in ("application",):
                    new_tri[qk] = f"What should listeners change this week, given: {focus}"
                else:
                    new_tri[qk] = f"What breaks this argument in practice: {focus}"
                rewrites += 1
            eng[cid] = new_tri
        report["engagement_questions"] = eng

    report["_sgv_rewrite_count"] = rewrites
    report["_sgv_applied"] = True
    report["_sgv_status"] = "REWRITTEN" if rewrites else "OK"
    if followups_touched:
        report["_sgv_followups_rewritten"] = True
    return report
