"""
Deterministic caption → sentence → claim/evidence scaffolding (no LLM).

Used when workflow AI returns too little structure to pass the export truth gate.
All rows are tagged ``confidence: low`` and ``source: rule_based_inference``.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

# Sentences containing these substrings (case-insensitive) are treated as candidate claims.
_CLAIM_HINT_PATTERNS = (
    r"we have seen",
    r"we've seen",
    r"the reason is",
    r"this happened because",
    r"what'?s happening is",
    r"what is happening is",
    r"the problem is",
    r"this leads to",
    r"it follows that",
    r"the point is",
    r"the idea is",
    r"i think that",
    r"it seems (?:clear|obvious) that",
    r"what that means is",
    r"the (?:fact|truth) is",
)

# Causal / directional language — required for "longest sentence" fallback picks (not for hint-matched lines).
_CAUSAL_DIRECTIONAL = re.compile(
    r"\b(because|due to|therefore|thus|hence|so that|as a result|for that reason)\b|"
    r"\b(causes?|caused|causing|leading to|leads to|led to|result(?:s|ed|ing)? in)\b|"
    r"\b(increase[sd]?|decrease[sd]?|reduces?|raised|lowered|fell|rose|grew|dropped|shifted)\b|"
    r"\b(means that|shows that|implies?|suggests?|indicates?|proves?|demonstrates?)\b|"
    r"\b(drives?|forced?|forcing|pushes?)\b",
    re.IGNORECASE,
)

_IS_ARE_CONCRETE = re.compile(
    r"\b(is|are)\s+(not\s+)?(a|an|the)\s+[a-z][a-z\-]{3,}",
    re.IGNORECASE,
)

# Pure transition / hedging without an argument hook (drop before gate rows).
_TRANSITION_FUZZ = re.compile(
    r"^\s*(so|yeah|well|okay|um|uh|like)[,!.\s]*"
    r"(that'?s|this is|it'?s|what'?s)\s+(kind of\s+|sort of\s+)?"
    r"(been\s+)?(happening|going on)",
    re.IGNORECASE,
)

# Mid-sentence contrast often marks real tension (rule-based).
_CONTRAST_MARKERS = re.compile(
    r"\b(but|however|instead|although|though|nevertheless|yet|while)\b",
    re.IGNORECASE,
)

_STOPWORDS = frozenset(
    """
    a an the and or but if as at to of in on for with from by is are was were been be
    have has had do does did will would could should may might must this that these those
    it its we you they he she i my our your their not no so than then there their
    """.split()
)


def caption_structure_bootstrap_enabled() -> bool:
    v = (os.getenv("SOAPBOXX_CAPTION_STRUCTURE_BOOTSTRAP") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _collapse_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


_RE_YT_CAPTION_KIND = re.compile(
    r"Kind:\s*captions\s+Language:\s*\S+\s*",
    re.IGNORECASE,
)


def strip_youtube_caption_metadata(text: str) -> str:
    """
    Remove YouTube ``Kind: captions Language: …`` tokens wherever they appear.

    Captions sometimes repeat this header on every chunk; stripping keeps claims and
    evidence from inheriting metadata as if it were spoken content.
    """
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not t.strip():
        return t.strip()
    out: List[str] = []
    for ln in t.split("\n"):
        s = ln.rstrip()
        if not s.strip():
            out.append("")
            continue
        s2 = _RE_YT_CAPTION_KIND.sub(" ", s)
        s2 = re.sub(r"[ \t]{2,}", " ", s2).rstrip()
        out.append(s2)
    return "\n".join(out).rstrip()


def clean_caption_transcript(raw: str) -> str:
    """
    Strip caption preambles / VTT-ish junk, merge lines, normalize spaces.
    Does not call the LLM.
    """
    t = strip_youtube_caption_metadata(raw or "")
    # Speaker / VTT direction markers
    t = re.sub(r"&gt;&gt;|>>|‹‹|››", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace("&nbsp;", " ").replace("&gt;", "").replace("&lt;", "")
    lines = []
    for ln in t.split("\n"):
        s = ln.strip()
        if not s:
            continue
        s = _RE_YT_CAPTION_KIND.sub(" ", s).strip()
        s = re.sub(r"[ \t]{2,}", " ", s).strip()
        if not s:
            continue
        if len(s.split()) < 2 and lines:
            lines[-1] = f"{lines[-1]} {s}".strip()
            continue
        lines.append(s)
    merged = " ".join(lines)
    return _collapse_ws(merged)


def split_sentences(text: str) -> List[str]:
    """Split on . ? ! while keeping short fragments attached."""
    t = _collapse_ws(text)
    if not t:
        return []
    parts = re.split(r"(?<=[.!?])\s+", t)
    out: List[str] = []
    buf = ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p.split()) < 5 and out:
            out[-1] = f"{out[-1]} {p}".strip()
        elif len(p.split()) < 5 and not out:
            buf = f"{buf} {p}".strip() if buf else p
        else:
            if buf:
                p = f"{buf} {p}".strip()
                buf = ""
            out.append(p)
    if buf:
        if out:
            out[-1] = f"{out[-1]} {buf}".strip()
        else:
            out.append(buf)
    return [s for s in out if len(s.split()) >= 5]


def _sentence_claim_and_evidence(sentences: Sequence[str], idx: int) -> Tuple[str, str]:
    """Derive a short claim + full evidence quote from sentence [idx] and maybe [idx+1]."""
    s0 = sentences[idx].strip()
    ev = s0
    if idx + 1 < len(sentences) and len(ev) < 120:
        ev = f"{s0} {sentences[idx + 1].strip()}".strip()
    words = s0.split()
    if len(words) <= 18:
        claim = s0
    else:
        claim = " ".join(words[:18]).strip().rstrip(",;:") + "."
    if len(claim) < 24 and len(ev) > len(claim):
        claim = ev[:160].strip()
        if claim[-1] not in ".!?":
            claim += "."
    return claim, ev


def _hint_match(sentence: str) -> bool:
    low = sentence.lower()
    return any(re.search(p, low) for p in _CLAIM_HINT_PATTERNS)


def contains_causal_or_directional_language(sentence: str) -> bool:
    """True when the line has an arguable causal / directional hook (rule-based, no LLM)."""
    s = (sentence or "").strip()
    if len(s) < 12:
        return False
    return bool(_CAUSAL_DIRECTIONAL.search(s)) or bool(_IS_ARE_CONCRETE.search(s))


def _is_transition_fluff(sentence: str) -> bool:
    """Reject obvious filler that used to pass as a 'long sentence' anchor."""
    s = (sentence or "").strip()
    if len(s) < 10:
        return True
    if _TRANSITION_FUZZ.search(s):
        return True
    low = s.lower()
    if "kind of" in low or "sort of" in low:
        if "happening" in low or "going on" in low:
            if not contains_causal_or_directional_language(s) and not _hint_match(s):
                return True
    if re.search(
        r"\b(that'?s|it'?s)\s+(kind of\s+)?(what'?s\s+been\s+happening|how things are)\b",
        low,
    ):
        if not contains_causal_or_directional_language(s) and not _hint_match(s):
            return True
    if re.search(r"^\s*(so|yeah)\b", low) and re.search(r"\b(happening recently|going on lately)\b", low):
        if not contains_causal_or_directional_language(s) and not _hint_match(s):
            return True
    return False


def acceptable_bootstrap_sentence(sentence: str) -> bool:
    """
    Sentence is allowed to become a rule-based evidence row.

    Hint-matched lines get a pass as *moderate* structure; fallback rows must also satisfy
    causal/directional (or concrete is/are) so we do not anchor on pure description.
    """
    s = (sentence or "").strip()
    if _is_transition_fluff(s):
        return False
    if _hint_match(s):
        return True
    return contains_causal_or_directional_language(s)


def claim_dedupe_jaccard_threshold() -> float:
    raw = (os.getenv("SOAPBOXX_CLAIM_DEDUPE_JACCARD") or "0.7").strip()
    try:
        v = float(raw)
    except ValueError:
        v = 0.7
    return min(max(v, 0.35), 0.95)


def norm_claim_tokens(claim: str) -> Set[str]:
    """Lowercase, strip punctuation, drop short tokens and stopwords — for overlap only."""
    low = re.sub(r"[^a-z0-9\s]", " ", (claim or "").lower())
    out: Set[str] = set()
    for w in low.split():
        if len(w) < 3 or w in _STOPWORDS:
            continue
        out.add(w)
    return out


def jaccard_similarity(tokens_a: Set[str], tokens_b: Set[str]) -> float:
    if not tokens_a or not tokens_b:
        return 0.0
    inter = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    return inter / union if union else 0.0


def has_contrast_structure(sentence: str) -> bool:
    """True when the line signals tension / turn (contrast markers)."""
    s = (sentence or "").strip()
    if len(s) < 14:
        return False
    return bool(_CONTRAST_MARKERS.search(s))


def _row_quality_tuple(r: Dict[str, Any]) -> Tuple[int, int, int, int]:
    """Higher = keep when deduping (strength, moderate tier, claim words, -sentence_idx for earlier)."""
    st = int(r.get("strength") or 0)
    mod = 1 if r.get("claim_strength") == "moderate" else 0
    wn = len(str(r.get("claim") or "").split())
    idx = int(r.get("_sentence_idx", 10**6))
    return (st, mod, wn, -idx)


def _dedupe_evidence_rows_by_claim_overlap(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop near-duplicate claims (Jaccard on token sets); keep higher-quality row."""
    if len(rows) < 2:
        return rows
    thr = claim_dedupe_jaccard_threshold()
    ranked = sorted(rows, key=_row_quality_tuple, reverse=True)
    kept: List[Dict[str, Any]] = []
    token_sets: List[Set[str]] = []
    for r in ranked:
        tok = norm_claim_tokens(str(r.get("claim") or ""))
        if len(tok) < 3:
            continue
        dup = False
        for prev in token_sets:
            if jaccard_similarity(tok, prev) > thr:
                dup = True
                break
        if dup:
            continue
        kept.append(r)
        token_sets.append(tok)
    return sorted(kept, key=lambda x: int(x.get("_sentence_idx", 10**6)))


def _apply_contrast_boost(rows: List[Dict[str, Any]], sentences: Sequence[str]) -> None:
    """Contrast-heavy lines become moderate with strength 7 (per product spec)."""
    for r in rows:
        idx = r.get("_sentence_idx")
        if idx is None:
            continue
        try:
            i = int(idx)
        except (TypeError, ValueError):
            continue
        if i < 0 or i >= len(sentences):
            continue
        if not has_contrast_structure(sentences[i]):
            continue
        r["claim_strength"] = "moderate"
        r["strength"] = 7


def _assign_primary_claim(rows: List[Dict[str, Any]]) -> None:
    """Exactly one ``primary: true`` — best strength/moderate, then earliest, then longest claim."""
    for r in rows:
        r["primary"] = False
    if not rows:
        return

    def sort_key(r: Dict[str, Any]) -> Tuple[int, int, int, int]:
        st = int(r.get("strength") or 0)
        mod = 1 if r.get("claim_strength") == "moderate" else 0
        early = -int(r.get("_sentence_idx", 10**6))
        ln = len(str(r.get("claim") or "").split())
        return (st, mod, early, ln)

    best = max(rows, key=sort_key)
    bid = id(best)
    for r in rows:
        r["primary"] = id(r) == bid


def build_rule_based_evidence_rows(transcript_raw: str) -> List[Dict[str, Any]]:
    """
    Produce ≥2 evidence_map-shaped dicts with verbatim quotes from the cleaned transcript.

    Rows use ``claim_strength`` (``weak`` | ``moderate``), numeric ``strength`` (4–7),
    ``primary`` on one anchor, and Jaccard dedup so two paraphrases of the same idea do not
    both survive. Contrast-heavy sentences (``but`` / ``however`` / …) bump to moderate @ 7.
    """
    cleaned = clean_caption_transcript(transcript_raw)
    sentences = split_sentences(cleaned)
    if len(sentences) < 2:
        blob = cleaned
        if len(blob.split()) >= 20:
            half = len(blob) // 2
            sentences = [blob[:half].strip(), blob[half:].strip()]
        else:
            return []

    acceptable_idx = [i for i, s in enumerate(sentences) if acceptable_bootstrap_sentence(s)]
    if len(acceptable_idx) < 2:
        return []

    picked: List[int] = []
    for i in acceptable_idx:
        if _hint_match(sentences[i]) and i not in picked:
            picked.append(i)
        if len(picked) >= 4:
            break

    if len(picked) < 2:
        order = sorted(
            [j for j in acceptable_idx if j not in picked],
            key=lambda j: len(sentences[j].split()),
            reverse=True,
        )
        for j in order:
            picked.append(j)
            if len(picked) >= 3:
                break

    rows: List[Dict[str, Any]] = []
    used_evidence: set[str] = set()
    for n, idx in enumerate(picked[:6], start=1):
        claim, ev = _sentence_claim_and_evidence(sentences, idx)
        ev_key = ev[:200]
        if ev_key in used_evidence:
            continue
        used_evidence.add(ev_key)
        hint = _hint_match(sentences[idx])
        tier = "moderate" if hint else "weak"
        strength_n = 6 if hint else 4
        rows.append(
            {
                "id": f"c{n}",
                "claim": claim,
                "evidence": ev,
                "timestamp": None,
                "type": "rule_anchor",
                "strength": strength_n,
                "claim_strength": tier,
                "confidence": "low",
                "source": "rule_based_inference",
                "_sentence_idx": idx,
            }
        )
        if len(rows) >= 5:
            break

    _apply_contrast_boost(rows, sentences)
    rows = _dedupe_evidence_rows_by_claim_overlap(rows)
    if len(rows) < 2:
        return []

    _assign_primary_claim(rows)
    for r in rows:
        r.pop("_sentence_idx", None)

    for i, r in enumerate(rows):
        r["id"] = f"c{i + 1}"

    return rows[:5]


def _evidence_anchor_frac(cleaned: str, evidence: str) -> float:
    """Approximate where the quote sits in the cleaned transcript (0..1)."""
    ev = (evidence or "").strip()
    if not ev or not cleaned:
        return 0.0
    for n in (min(96, len(ev)), 72, 48, 32):
        needle = ev[:n].strip()
        if len(needle) < 20:
            continue
        pos = cleaned.find(needle)
        if pos >= 0:
            return pos / max(1, len(cleaned))
    return 0.0


def _segments_by_thirds(rows: List[Dict[str, Any]], cleaned: str) -> List[Dict[str, Any]]:
    """
    One segment per occupied third of the transcript, titled from the first claim in that third.
    Adds ``span_start_frac`` / ``span_end_frac`` for cheap downstream grouping (0–1).
    """
    default_run = [
        "Play clip",
        "Host reacts",
        "Guest responds",
        "Challenge assumptions",
        "Summarize takeaway",
    ]
    if not rows:
        return _minimal_segments_for_claims([])

    buckets: Dict[int, List[Dict[str, Any]]] = {0: [], 1: [], 2: []}
    for r in rows:
        if not isinstance(r, dict):
            continue
        frac = _evidence_anchor_frac(cleaned, str(r.get("evidence") or ""))
        t = min(2, int(frac * 3))
        buckets[t].append(r)

    segs: List[Dict[str, Any]] = []
    n = 0
    for t in (0, 1, 2):
        b = buckets[t]
        if not b:
            continue
        ct = str(b[0].get("claim") or "Segment").strip()
        title = (ct[:72] + "…") if len(ct) > 72 else ct
        segs.append(
            {
                "segment_id": f"s{n + 1}",
                "title": title,
                "clip_id": None,
                "host_position": "",
                "guest_position": "",
                "goal": "Develop this thread with explicit listener takeaway.",
                "run_of_show": default_run,
                "span_start_frac": t / 3.0,
                "span_end_frac": (t + 1) / 3.0,
            }
        )
        n += 1

    if not segs:
        return _minimal_segments_for_claims(
            [str(x.get("claim") or "") for x in rows[:2] if isinstance(x, dict)]
        )
    return segs


def _minimal_segments_for_claims(claim_texts: List[str]) -> List[Dict[str, Any]]:
    default_run = [
        "Play clip",
        "Host reacts",
        "Guest responds",
        "Challenge assumptions",
        "Summarize takeaway",
    ]
    if not claim_texts:
        return [
            {
                "segment_id": "s1",
                "title": "Episode spine (rule-based anchor)",
                "clip_id": None,
                "host_position": "",
                "guest_position": "",
                "goal": "Anchor one clear through-line from transcript for packaging.",
                "run_of_show": default_run,
            }
        ]
    segs: List[Dict[str, Any]] = []
    for i, ct in enumerate(claim_texts[:2]):
        title = (ct[:72] + "…") if len(ct) > 72 else ct
        segs.append(
            {
                "segment_id": f"s{i + 1}",
                "title": title,
                "clip_id": None,
                "host_position": "",
                "guest_position": "",
                "goal": "Develop this thread with explicit listener takeaway.",
                "run_of_show": default_run,
            }
        )
    return segs


def _ensure_followups_for_claim_ids(
    report: Dict[str, Any], claim_ids: List[str]
) -> None:
    valid_set = {str(x).strip() for x in claim_ids if str(x).strip()}
    existing = [
        q
        for q in (report.get("follow_up_questions") or [])
        if isinstance(q, dict) and str(q.get("claim_id") or "").strip() in valid_set
    ]
    have = set()
    for q in existing:
        cid = str(q.get("claim_id") or "")
        qt = str(q.get("question_type") or "").lower().strip()
        if cid and qt in ("counter", "validation", "application"):
            have.add((cid, qt))

    out = list(existing)
    for cid in claim_ids:
        tpl = {
            "counter": (
                "What is the strongest counterargument a skeptical listener would raise about "
                f"the on-mic tension summarized for {cid}?"
            ),
            "validation": (
                "Which lines in the transcript best support the sharpest claim you would defend "
                f"in public for {cid}?"
            ),
            "application": (
                "What concrete behavior should listeners change this week based on the thread "
                f"anchored at {cid}?"
            ),
        }
        for qt in ("counter", "validation", "application"):
            if (cid, qt) not in have:
                out.append({"question": tpl[qt], "question_type": qt, "claim_id": cid})
    report["follow_up_questions"] = out


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _quote_plausible_in_transcript(transcript: str, evidence: str) -> bool:
    """Match ``soapboxx_v3_workflow._evidence_quote_grounded`` without importing that module."""
    ev = (evidence or "").strip()
    if len(ev) < 12:
        return True
    t = _norm_ws(transcript)
    e = _norm_ws(ev)
    if e in t:
        return True
    t_alnum = re.sub(r"[^\w\s]", "", t)
    e_alnum = re.sub(r"[^\w\s]", "", e)
    if len(e_alnum) >= 12 and e_alnum in t_alnum:
        return True
    words = e_alnum.split()
    if len(words) < 5:
        return False
    need = max(4, int(len(words) * 0.72))
    chunk = " ".join(words[:need])
    return chunk in t_alnum


def _filter_rows_quote_grounded(transcript: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not rows:
        return rows
    kept = [
        r
        for r in rows
        if isinstance(r, dict)
        and _quote_plausible_in_transcript(transcript, str(r.get("evidence") or ""))
    ]
    if len(kept) >= max(1, len(rows) // 4):
        return kept
    return rows


def _sanitize_evidence_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    try:
        from .episode_report_v3 import _dedupe_repeated_sentences, _is_broken_evidence_claim_line
    except ImportError:
        from episode_report_v3 import _dedupe_repeated_sentences, _is_broken_evidence_claim_line

    seen = set()
    out: List[Dict[str, Any]] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        cl = str(r.get("claim") or "").strip()
        if not cl or _is_broken_evidence_claim_line(cl):
            continue
        key = re.sub(r"[^a-z0-9]+", " ", cl.lower()).strip()[:140]
        if key in seen:
            continue
        seen.add(key)
        rr = dict(r)
        ev = str(rr.get("evidence") or "").strip()
        if ev:
            rr["evidence"] = _dedupe_repeated_sentences(ev)
        out.append(rr)
    return out


def _assign_evidence_ids(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    n = 0
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        n += 1
        rr = dict(r)
        if not str(rr.get("id") or "").strip():
            rr["id"] = f"c{n}"
        out.append(rr)
    return out


def _count_export_grounded(rows: List[Dict[str, Any]]) -> int:
    try:
        from .episode_report_v3 import evidence_row_is_export_grounded
    except ImportError:
        from episode_report_v3 import evidence_row_is_export_grounded

    return sum(1 for r in rows if isinstance(r, dict) and evidence_row_is_export_grounded(r))


def _r3_evidence_row(r: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "id": str(r.get("id")),
        "claim": r.get("claim"),
        "evidence": r.get("evidence"),
        "type": r.get("type", "other"),
        "strength": r.get("strength", 5),
    }
    cs = r.get("claim_strength")
    if cs in ("weak", "moderate"):
        out["claim_strength"] = cs
    if r.get("primary") is True:
        out["primary"] = True
    return out


def apply_rule_based_structure_bootstrap(
    report: Dict[str, Any],
    r3: Dict[str, Any],
    transcript: str,
) -> None:
    """
    If workflow evidence/segments are too thin for the export gate, append rule-based rows
    (verbatim transcript quotes). Mutates ``report`` and mirrors into ``r3`` when needed.
    """
    if not caption_structure_bootstrap_enabled():
        return
    tx = transcript or ""
    if len(tx.split()) < 80:
        return

    cleaned = clean_caption_transcript(tx)

    em = [dict(x) for x in (report.get("evidence_map") or []) if isinstance(x, dict)]
    em = _sanitize_evidence_rows(em)
    em = _filter_rows_quote_grounded(tx, em)
    n_g = _count_export_grounded(em)
    segs = [x for x in (report.get("segments") or []) if isinstance(x, dict)]

    if n_g >= 2 and len(segs) >= 1:
        return

    applied = False
    if n_g >= 2 and len(segs) < 1:
        report["segments"] = _segments_by_thirds(em, cleaned)
        valid_ids = [str(x.get("id")) for x in em if isinstance(x, dict) and x.get("id")]
        _ensure_followups_for_claim_ids(report, valid_ids)
        md = report.get("metadata")
        if isinstance(md, dict):
            md["structure_bootstrap_applied"] = True
        r3["evidence_mapping"] = [
            _r3_evidence_row(r)
            for r in em
            if isinstance(r, dict)
        ]
        r3["segments"] = [
            {
                "segment_title": s.get("title") or "Segment",
                "trigger_clip": s.get("clip_id"),
                "host_angle": s.get("host_position") or "",
                "guest_angle": s.get("guest_position") or "",
                "goal": s.get("goal") or "",
            }
            for s in (report.get("segments") or [])[:3]
            if isinstance(s, dict)
        ]
        return

    bootstrap = build_rule_based_evidence_rows(tx)
    bootstrap = _sanitize_evidence_rows(bootstrap)
    bootstrap = _filter_rows_quote_grounded(tx, bootstrap)
    bootstrap = _assign_evidence_ids(bootstrap)

    seen_claim = {re.sub(r"[^a-z0-9]+", " ", str(r.get("claim") or "").lower())[:120] for r in em}
    for row in bootstrap:
        key = re.sub(r"[^a-z0-9]+", " ", str(row.get("claim") or "").lower())[:120]
        if key in seen_claim:
            continue
        seen_claim.add(key)
        em.append(row)

    em = _assign_evidence_ids(em)
    em = _sanitize_evidence_rows(em)
    em = _filter_rows_quote_grounded(tx, em)

    # Renumber ids c1..cn
    for i, row in enumerate(em):
        if isinstance(row, dict):
            row["id"] = f"c{i + 1}"

    if _count_export_grounded(em) < 2:
        return

    report["evidence_map"] = em
    applied = True

    if len(segs) < 1:
        report["segments"] = _segments_by_thirds(em, cleaned)

    valid_ids = [str(x.get("id")) for x in em if isinstance(x, dict) and x.get("id")]
    _ensure_followups_for_claim_ids(report, valid_ids)

    if applied:
        md = report.get("metadata")
        if isinstance(md, dict):
            md["structure_bootstrap_applied"] = True

    # Mirror into report_v3 for consumers that read evidence_mapping / segments only
    r3["evidence_mapping"] = [
        _r3_evidence_row(r)
        for r in em
        if isinstance(r, dict)
    ]
    if not (r3.get("segments") or []):
        r3["segments"] = [
            {
                "segment_title": s.get("title") or "Segment",
                "trigger_clip": s.get("clip_id"),
                "host_angle": s.get("host_position") or "",
                "guest_angle": s.get("guest_position") or "",
                "goal": s.get("goal") or "",
            }
            for s in (report.get("segments") or [])[:3]
            if isinstance(s, dict)
        ]


__all__ = [
    "acceptable_bootstrap_sentence",
    "apply_rule_based_structure_bootstrap",
    "build_rule_based_evidence_rows",
    "caption_structure_bootstrap_enabled",
    "claim_dedupe_jaccard_threshold",
    "clean_caption_transcript",
    "strip_youtube_caption_metadata",
    "contains_causal_or_directional_language",
    "has_contrast_structure",
    "jaccard_similarity",
    "norm_claim_tokens",
    "split_sentences",
]
