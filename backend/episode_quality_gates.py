# backend/episode_quality_gates.py
"""
Deterministic quality gates: title/topic coherence, domain mismatch repair, claim shape filtering,
and v3 readiness hints. Complements the LLM; does not replace it.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

# Narrative bullets must share vocabulary with episode identity (title/topic/genre).
# Catches obvious cross-domain drift (e.g. agriculture vs Nez Perce) without ML.
NARRATIVE_IDENTITY_MIN_JACCARD = 0.07
# Separate check vs title alone (lightweight “no invented domain” guard).
NARRATIVE_TITLE_MIN_JACCARD = 0.05

# Cheap keyword buckets for DOMAIN_SHIFT_REJECTED (bullet vs anchor disjoint strong domains).
_DOMAIN_MARKERS = {
    "agri": frozenset(
        "farm farming crop crops livestock agriculture agricultural soil harvest rural tractor pasture "
        "irrigation pesticide wheat grain vineyard disease cattle dairy silo".split()
    ),
    "war": frozenset(
        "war warfare battle army military soldier weapon invasion treaty combat siege navy raid "
        "chief resistance campaign fort".split()
    ),
    "philosophy": frozenset(
        "epistemology metaphysics ontology syllogism plato socrates aristotle kant hume existentialism "
        "phenomenology dialectic".split()
    ),
    "tech": frozenset(
        "software algorithm api server codebase deploy kubernetes docker python javascript cloud database "
        "saas firmware".split()
    ),
    "finance": frozenset(
        "stock equity bond dividend portfolio merger acquisition revenue earnings quarterly nasdaq "
        "derivative option".split()
    ),
}

_STOP = frozenset(
    "the a an and or but if in on at to for of is are was were be been being it this that these those "
    "with as by from into through over under again further then once here there when where why how "
    "all each every both few more most other some such no nor not only own same so than too very can "
    "will just don should now".split()
)


def _tokens(s: str) -> List[str]:
    return re.findall(r"[a-z0-9]{3,}", (s or "").lower())


def _content_tokens(s: str) -> List[str]:
    return [t for t in _tokens(s) if t not in _STOP and len(t) >= 4]


def jaccard_tokens(a: str, b: str) -> float:
    A = set(_content_tokens(a))
    B = set(_content_tokens(b))
    if not A or not B:
        return 0.0
    inter = len(A & B)
    union = len(A | B)
    return inter / union if union else 0.0


def build_identity_anchor(
    meta: Optional[Dict[str, Any]],
    snapshot: Optional[Dict[str, Any]],
) -> str:
    """
    Single-string identity anchor for cross-layer consistency (title + topic + genre).
    ``primary_topic`` is read from ``snapshot`` first, then ``meta``.
    """
    m = meta if isinstance(meta, dict) else {}
    s = snapshot if isinstance(snapshot, dict) else {}
    parts: List[str] = []
    for x in (
        s.get("title") or m.get("title") or m.get("episode_title"),
        s.get("primary_topic") or m.get("primary_topic"),
        s.get("genre") or m.get("genre"),
    ):
        t = str(x or "").strip()
        if t:
            parts.append(t)
    return " ".join(parts).strip()


def narrative_matches_title(narrative_line: str, title: str) -> bool:
    """True when the line shares enough token mass with the episode title (anti–new-domain drift)."""
    a = str(narrative_line or "").strip()
    b = str(title or "").strip()
    if not a or not b or len(b) < 6:
        return True
    return jaccard_tokens(a, b) >= NARRATIVE_TITLE_MIN_JACCARD


def _top_terms_text(snap: Dict[str, Any]) -> str:
    raw = snap.get("top_terms")
    if isinstance(raw, list):
        parts = [str(x).strip() for x in raw if str(x).strip()]
        return " ".join(parts[:24])
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return ""


def _domain_marker_hits(text: str) -> Set[str]:
    """Label coarse domains present in ``text`` (token substring match)."""
    low = " ".join(_tokens(text))
    hits: Set[str] = set()
    for name, markers in _DOMAIN_MARKERS.items():
        if any(m in low for m in markers):
            hits.add(name)
    return hits


def _domain_shift_vs_anchor(bullet: str, anchor: str) -> bool:
    """
    Heuristic: bullet and anchor activate disjoint domain buckets (e.g. agriculture vs military history).
    Used only when Jaccard vs anchor is already below threshold.
    """
    bh = _domain_marker_hits(bullet)
    ah = _domain_marker_hits(anchor)
    if not bh:
        return False
    if not ah:
        return True
    return len(bh & ah) == 0


def _dedupe_preserve_order(lines: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for s in lines:
        k = s.strip()
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(s.strip())
    return out


def align_narrative_lines_to_title(
    lines: List[str],
    *,
    title: str,
    primary_topic: str,
) -> Tuple[List[str], List[str]]:
    """
    If a line is too far from the title token-wise, replace with a primary_topic-safe sentence
    (no new domain vs title/topic).
    """
    warnings: List[str] = []
    t = str(title or "").strip()
    pt = str(primary_topic or "").strip()
    if len(t) < 6:
        return lines, warnings

    out: List[str] = []
    mismatch = 0
    for line in lines:
        s = str(line).strip()
        if not s:
            continue
        if narrative_matches_title(s, t):
            out.append(s)
            continue
        mismatch += 1
        if pt:
            rep = f"The core theme of this episode is {pt}."
        else:
            short = t[:200] + ("…" if len(t) > 200 else "")
            rep = f"The core theme of this episode is {short}"
        if not out or out[-1] != rep:
            out.append(rep)
    if mismatch:
        warnings.append(
            f"NARRATIVE_TITLE_MISMATCH: replaced {mismatch} line(s); weak title overlap "
            f"(threshold {NARRATIVE_TITLE_MIN_JACCARD:.2f})."
        )
    return _dedupe_preserve_order(out), warnings


RELIGIOUS_TOPIC_MARKERS = (
    "spiritual",
    "theological",
    "theology",
    "scripture",
    "bible",
    "sermon",
    "ministry",
    "gospel",
    "faith tradition",
    "doctrine",
    "ecclesial",
    "liturgy",
    "prayer",
    "divine",
)

RELIGIOUS_TITLE_MARKERS = RELIGIOUS_TOPIC_MARKERS + (
    "church",
    "pastor",
    "rabbi",
    "imam",
    "mosque",
    "synagogue",
    "christian",
    "catholic",
    "protestant",
    "jewish",
    "muslim",
    "hindu",
    "buddhist",
)


def _text_implies_religion(s: str) -> bool:
    low = (s or "").lower()
    return any(m in low for m in RELIGIOUS_TOPIC_MARKERS)


def _title_genre_implies_religion(title: str, genre: str) -> bool:
    blob = f"{title} {genre}".lower()
    return any(m in blob for m in RELIGIOUS_TITLE_MARKERS)


def religious_framing_mismatch(primary_topic: str, title: str, genre: str) -> bool:
    """True when primary_topic reads religious but title/genre do not."""
    pt = (primary_topic or "").strip()
    if not pt or not _text_implies_religion(pt):
        return False
    return not _title_genre_implies_religion(title, genre)


def coherence_anchor(title: str, creator: str, genre: str, primary_topic: str) -> float:
    """Token overlap between episode identity (title, creator, genre) and primary_topic."""
    anchor = f"{title} {creator} {genre}"
    return jaccard_tokens(anchor, primary_topic)


def fallback_primary_topic(snap: Dict[str, Any], claims: Sequence[Dict[str, Any]]) -> str:
    title = str(snap.get("title") or "").strip()
    if title and len(title) > 6:
        return title[:200]
    if claims:
        t = str(claims[0].get("text") or "").strip()
        if len(t) > 24:
            return (t[:140] + "…") if len(t) > 140 else t
    return "Episode themes (from transcript)"


def clamp_narrative_bullets_to_identity(
    snap: Dict[str, Any],
    bullets: List[str],
    *,
    min_jaccard: float = NARRATIVE_IDENTITY_MIN_JACCARD,
) -> Tuple[List[str], List[str]]:
    """
    Drop narrative lines whose tokens barely overlap episode identity text.

    Anchor = title + primary_topic + genre + creator + why_it_matters + episode_snapshot.top_terms
    (when present). Expanding the anchor slightly improves recall on thin titles without ML.

    When overlap is below ``min_jaccard`` and a coarse domain heuristic disagrees with the anchor,
    the drop is tagged ``DOMAIN_SHIFT_REJECTED``; otherwise ``LOW_IDENTITY_OVERLAP``.

    Lines are then aligned to the title via :func:`narrative_matches_title` (separate threshold).

    If all lines are dropped, replace with a single identity-safe line from
    ``primary_topic`` or ``title`` so the brief never presents an unrelated thesis.
    """
    warnings: List[str] = []
    title = str(snap.get("title") or "").strip()
    pt = str(snap.get("primary_topic") or "").strip()
    genre = str(snap.get("genre") or "").strip()
    creator = str(snap.get("creator") or "").strip()
    why = str(snap.get("why_it_matters") or "").strip()
    tt = _top_terms_text(snap)
    anchor = f"{title} {pt} {genre} {creator} {why} {tt}".strip()
    if not bullets:
        return [], warnings
    if len(anchor) < 8:
        loose = [str(b).strip() for b in bullets if str(b).strip()]
        aligned, aw = align_narrative_lines_to_title(loose, title=title, primary_topic=pt)
        warnings.extend(aw)
        return aligned, warnings

    kept: List[str] = []
    dropped_plain = 0
    dropped_domain = 0
    for b in bullets:
        s = str(b).strip()
        if not s:
            continue
        if jaccard_tokens(s, anchor) >= min_jaccard:
            kept.append(s)
            continue
        if _domain_shift_vs_anchor(s, anchor):
            dropped_domain += 1
        else:
            dropped_plain += 1

    if dropped_domain:
        warnings.append(
            f"DOMAIN_SHIFT_REJECTED: dropped {dropped_domain} narrative line(s) "
            f"(low identity overlap + domain mismatch heuristics; threshold {min_jaccard:.2f})."
        )
    if dropped_plain:
        warnings.append(
            f"LOW_IDENTITY_OVERLAP: dropped {dropped_plain} narrative line(s) "
            f"(threshold {min_jaccard:.2f})."
        )

    if not kept:
        if pt:
            kept = [f"The through-line for listeners: {pt}."]
            warnings.append("Narrative replaced with primary_topic fallback (identity alignment).")
        elif title:
            short = title[:200] + ("…" if len(title) > 200 else "")
            kept = [f"This episode follows the arc suggested by the title: {short}"]
            warnings.append("Narrative replaced with title-led fallback (identity alignment).")

    aligned, aw = align_narrative_lines_to_title(kept, title=title, primary_topic=pt)
    warnings.extend(aw)
    return aligned, warnings


def repair_primary_topic_if_needed(
    snap: Dict[str, Any],
    claims: List[Dict[str, Any]],
    *,
    coherence_min: float = 0.06,
) -> List[str]:
    """
    Mutate ``episode_snapshot.primary_topic`` when incoherent or wrong-domain.
    Returns human-readable repair notes for warnings / readiness.
    """
    notes: List[str] = []
    title = str(snap.get("title") or "").strip()
    genre = str(snap.get("genre") or "").strip()
    creator = str(snap.get("creator") or "").strip()
    pt = str(snap.get("primary_topic") or "").strip()
    if not pt:
        snap["primary_topic"] = fallback_primary_topic(snap, claims)
        notes.append("primary_topic was empty — defaulted to title or first claim.")
        return notes

    if religious_framing_mismatch(pt, title, genre):
        old = pt
        snap["primary_topic"] = fallback_primary_topic(snap, claims)
        notes.append(
            f"primary_topic looked misaligned with title/genre ({old[:80]}…) — reset to title-led framing."
        )
        return notes

    if len(title) >= 10:
        coh = coherence_anchor(title, creator, genre, pt)
        if coh < coherence_min:
            old = pt
            snap["primary_topic"] = fallback_primary_topic(snap, claims)
            notes.append(
                f"primary_topic had low overlap with title/show ({coh:.2f}) — replaced “{old[:70]}…” with title-led topic."
            )
    return notes


def claim_structure_score(text: str) -> float:
    """Heuristic 0..1: standalone sentence vs ASR splice / filler."""
    t = (text or "").strip()
    if len(t) < 28:
        return 0.15
    score = 0.2
    if t[0].isupper():
        score += 0.15
    if t[-1] in ".!?":
        score += 0.2
    words = t.split()
    if len(words) >= 10:
        score += 0.15
    if len(words) >= 14:
        score += 0.1
    fillers = sum(1 for w in words if w.lower() in {"like", "um", "uh", "yeah", "you", "know"})
    if words and fillers / len(words) > 0.22:
        score -= 0.35
    if t.count('"') >= 4 or t.count("“") + t.count("”") >= 4:
        score -= 0.25
    low = t.lower()
    if re.search(r"\b(didn't think|if you guys|that day but|none of\.|hands and knees)\b", low):
        score -= 0.3
    return max(0.0, min(1.0, score))


def filter_claims_by_sentence_quality(
    claims: List[Dict[str, Any]],
    *,
    min_score: float = 0.38,
) -> List[Dict[str, Any]]:
    """
    Drop obvious ASR-splice “claims” when we still have enough signal; renumber c1..cn.
    If filtering would leave fewer than 2 claims, return the original list (unchanged ids).
    """
    clean = [c for c in claims if isinstance(c, dict) and str(c.get("text") or "").strip()]
    if len(clean) <= 2:
        return clean
    scored = [(claim_structure_score(str(c.get("text") or "")), c) for c in clean]
    scored.sort(key=lambda x: -x[0])
    kept = [c for s, c in scored if s >= min_score]
    if len(kept) >= 2:
        chosen = kept[:5]
    else:
        return clean[:5]
    out: List[Dict[str, Any]] = []
    for i, c in enumerate(chosen, start=1):
        c2 = dict(c)
        c2["id"] = f"c{i}"
        out.append(c2)
    return out


def apply_brief_quality_pass(data: Dict[str, Any], metadata: Dict[str, str]) -> List[str]:
    """
    Run after claims are deduped and assigned ids; may renumber ids again after structure filter.
    Mutates ``data`` (claims, episode_snapshot). Returns warnings to surface to the caller.
    """
    warnings: List[str] = []
    snap = data.get("episode_snapshot") or {}
    if not isinstance(snap, dict):
        return warnings
    for k in ("title", "creator", "genre"):
        if not str(snap.get(k) or "").strip():
            v = str(metadata.get(k) or "").strip()
            if v:
                snap[k] = v
    claims = [c for c in (data.get("claims") or []) if isinstance(c, dict)]
    filtered = filter_claims_by_sentence_quality(claims, min_score=0.38)
    if filtered != claims:
        data["claims"] = filtered
        claims = filtered
        warnings.append("Filtered low-structure claim rows (ASR splices / filler) before packaging.")
    notes = repair_primary_topic_if_needed(snap, claims, coherence_min=0.06)
    warnings.extend(notes)
    data["episode_snapshot"] = snap
    return warnings


def evaluate_v3_quality_gates(
    brief: Dict[str, Any],
    transcript: str,
) -> Dict[str, Any]:
    """
    Read-only signals for v3 ``report_readiness`` and optional diagnostic downgrade.
    """
    snap = brief.get("episode_snapshot") or {}
    title = str(snap.get("title") or "").strip()
    genre = str(snap.get("genre") or "").strip()
    creator = str(snap.get("creator") or "").strip()
    pt = str(snap.get("primary_topic") or "").strip()
    claims = [c for c in (brief.get("claims") or []) if isinstance(c, dict)]

    notes: List[str] = []
    force_diagnostic = False

    coh_val: float | None = None
    if pt:
        coh_val = round(coherence_anchor(title, creator, genre, pt), 4)

    if pt and religious_framing_mismatch(pt, title, genre):
        notes.append("Quality gate: religious/spiritual framing on a non-religious title/genre — review-first recommended.")
        force_diagnostic = True

    if len(title) >= 10 and pt and coh_val is not None and coh_val < 0.05:
        notes.append(
            f"Quality gate: primary topic weakly overlaps title/show (score {coh_val:.2f}) — verify framing before clips."
        )
        force_diagnostic = True

    low_structure = 0
    for c in claims:
        if claim_structure_score(str(c.get("text") or "")) < 0.35:
            low_structure += 1
    if len(claims) >= 3 and low_structure >= max(2, len(claims) - 1):
        notes.append("Quality gate: most claims look like transcript fragments, not standalone arguments.")
        force_diagnostic = True

    wc = len((transcript or "").split())
    if wc > 8000 and len(claims) <= 2:
        notes.append("Quality gate: long transcript but very few claims — extraction may be under-firing.")

    return {
        "force_diagnostic": force_diagnostic,
        "notes": notes,
        "title_topic_coherence": coh_val,
    }
