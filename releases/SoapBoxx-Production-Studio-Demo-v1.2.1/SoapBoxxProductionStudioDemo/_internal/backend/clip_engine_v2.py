# backend/clip_engine_v2.py
"""
Clip Engine v2 — evidence-bound extraction.

Clips are derived only from **supported** (accepted) claims and traceable **source_segments**.
We do *not* hunt for “viral” moments; we score **structural** strength and reject low-signal
outputs (``clip_score < MIN_CLIP_SCORE``).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.thesis_engine_v2 import (
    _ENTITY_HINT,
    _coerce_eval_map,
    _mechems,
    _norm,
    _structural_pair_score,
    _tokens,
)

# --- Gating (spec: reject if < 4) ---
MIN_CLIP_SCORE = 4.0
GRAPH_TH = 0.11
CLSentence_OVERLAP = 0.32
# Adjacent sentences need not self-overlap; they may cohere only through shared *claim* vocabulary.
_CONSEC_CLAIM_BRIDGES = 2
_CONSEC_STRUCT_OR_JACC = 0.08

_FENCE = re.compile(
    r"(?i)(maybe|perhaps|i think|i feel|i guess|sort of|kind of|you know|like,|i mean)\b"
)
_FILLER = re.compile(
    r"(?i)\b(um|uh|er|ah|hmm|you know|like|basically|literally|actually|just sort of|right\?|okay\?)\b"
)
_VAGUE = re.compile(
    r"(?i)\b(thing|stuff|matters|reality|always|everyone|never|everything|something)\b"
)
_EXPL = re.compile(
    r"(?i)\b(because|since|as a result|therefore|due to|driven by|leads? to|explains? why)\b"
)
_ASSERT = re.compile(
    r"(?i)\b(is|are|was|were|proves?|demonstrates?|shows? that|means? that|establishes?)\b"
)


def _coerce_time(seg: Mapping[str, Any]) -> Tuple[float, float]:
    s = seg.get("start_time", seg.get("start", seg.get("t")))
    e = seg.get("end_time", seg.get("end"))
    try:
        st = float(s) if s is not None else 0.0
    except (TypeError, ValueError):
        st = 0.0
    try:
        en = float(e) if e is not None else st
    except (TypeError, ValueError):
        en = st
    if en < st:
        en = st
    return st, en


def _segment_index(segs: Sequence[Mapping[str, Any]]) -> Tuple[Dict[str, Mapping[str, Any]], str]:
    by_id: Dict[str, Mapping[str, Any]] = {}
    for s in segs:
        if not isinstance(s, Mapping) or s.get("id") is None:
            return {}, "each source_segment must be a dict with id"
        by_id[str(s["id"]).strip()] = s
    return by_id, ""


def _strict_inputs(
    accepted_claims: Any,
    evaluation_map: Any,
    source_segments: Any,
) -> Tuple[List[Dict[str, Any]], Dict[str, str], Dict[str, Mapping[str, Any]], str]:
    if not isinstance(accepted_claims, (list, tuple)) or not accepted_claims:
        return [], {}, {}, "NO_CLIPS: accepted_claims must be a non-empty list"
    claims = [c for c in accepted_claims if isinstance(c, dict)]
    if not claims:
        return [], {}, {}, "NO_CLIPS: no valid claim dicts"
    em, emsg = _coerce_eval_map(evaluation_map)
    if emsg:
        return [], {}, {}, f"NO_CLIPS: {emsg}"
    if not isinstance(source_segments, (list, tuple)) or not source_segments:
        return [], {}, {}, "NO_CLIPS: source_segments must be a non-empty list"
    by_id, serr = _segment_index([s for s in source_segments if isinstance(s, Mapping)])
    if serr or not by_id:
        return [], {}, {}, serr or "NO_CLIPS: bad source_segments"
    return claims, em, by_id, ""


def _claim_id(c: Dict[str, Any], idx: int) -> str:
    return str(c.get("id") or f"c{idx+1}").strip()


def _claim_text(c: Dict[str, Any]) -> str:
    return _norm(str(c.get("text") or c.get("claim") or ""))


def _claim_strength_value(c: Dict[str, Any]) -> float:
    for k in ("claim_score", "score", "strength"):
        v = c.get(k)
        if v is not None:
            try:
                return max(0.0, min(6.0, float(v)))
            except (TypeError, ValueError):
                pass
    return 0.0


def _split_sentences(t: str) -> List[str]:
    s = _norm(t)
    if not s:
        return []
    parts = re.split(r"(?<=[.!?])\s+", s)
    return [p.strip() for p in parts if p.strip()]


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def _narrative_drift(clip_sents: List[str], claim_union: Set[str]) -> bool:
    """
    Reject *topic switching* (multi-thread), not two sentences with low token overlap
    (common in well-written analytical speech).
    Drift: adjacent lines share no surface overlap *and* no structural link *and* too few
    bridge terms from supported claims.
    """
    sents = [s for s in clip_sents if s.strip()]
    if len(sents) <= 1:
        return True
    for i in range(len(sents) - 1):
        a, b = sents[i], sents[i + 1]
        ta, tb = set(_tokens(a)), set(_tokens(b))
        if not ta or not tb:
            continue
        if _jaccard(ta, tb) >= 0.04:
            continue
        if _structural_pair_score(a, b) >= _CONSEC_STRUCT_OR_JACC:
            continue
        bridge = (ta | tb) & claim_union
        if len(bridge) < _CONSEC_CLAIM_BRIDGES:
            return False
    return True


def _sentences_anchored(clip: str, claim_union: Set[str]) -> bool:
    sents = _split_sentences(clip)
    if not sents:
        return False
    for sent in sents:
        ts = set(_tokens(sent))
        if not ts:
            continue
        r = len(ts & claim_union) / max(1, len(ts))
        if r < CLSentence_OVERLAP:
            return False
    return True


def _claim_clusters(texts: List[str]) -> List[List[int]]:
    n = len(texts)
    if n == 0:
        return []
    adj: List[Set[int]] = [set() for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if _structural_pair_score(texts[i], texts[j]) >= GRAPH_TH:
                adj[i].add(j)
                adj[j].add(i)
    seen = [False] * n
    out: List[List[int]] = []

    def dfs(i: int, acc: List[int]) -> None:
        seen[i] = True
        acc.append(i)
        for j in adj[i]:
            if not seen[j]:
                dfs(j, acc)

    for s in range(n):
        if seen[s]:
            continue
        comp: List[int] = []
        dfs(s, comp)
        out.append(comp)
    return out


def _clip_type_for(text: str) -> str:
    t = (text or "").lower()
    if _EXPL.search(t):
        return "EXPLANATION"
    if _ASSERT.search(t):
        return "ASSERTION"
    return "NARRATIVE"


def _score_clip(
    clip_text: str,
    claim_rows: List[Dict[str, Any]],
) -> float:
    """
    clip_score = sum(0-2 for four positives) - sum(0-2 for two penalties).
    """
    if not (clip_text or "").strip():
        return 0.0
    cs = [_claim_strength_value(c) for c in claim_rows]
    # claim_strength: map claim_score 0-6+ to 0-2; missing → mid
    if cs and max(cs) > 0:
        claim_strength = min(2.0, 2.0 * (max(cs) / 6.0))
    else:
        claim_strength = min(2.0, 0.8 + 0.2 * min(3, len(claim_rows)))
    toks = _tokens(clip_text)
    ents = len(_ENTITY_HINT.findall(clip_text))
    mec = len(_mechems(clip_text))
    specificity = min(2.0, 0.3 * min(3, ents) + 0.25 * min(3, mec) + 0.4 * min(1.0, len(toks) / 55.0))
    hed = len(_FENCE.findall(clip_text))
    emo_clear = min(2.0, 2.0 - 0.22 * min(4, hed))
    sents = _split_sentences(clip_text)
    stoks = [set(_tokens(s)) for s in sents if s.strip()]
    if len(stoks) >= 2:
        pairs = [_jaccard(stoks[i], stoks[i + 1]) for i in range(len(stoks) - 1)]
        mean_j = sum(pairs) / max(1, len(pairs))
        narr = min(2.0, 2.0 * mean_j + 0.2)
    else:
        narr = 1.2
    abstr = min(2.0, 0.45 * min(4, len(_VAGUE.findall(clip_text))))
    fill = min(2.0, 0.18 * min(8, len(_FILLER.findall(clip_text))))
    return claim_strength + specificity + emo_clear + narr - abstr - fill


def _suggested_title(claim_rows: List[Dict[str, Any]], claim_texts: List[str], clip_text: str) -> str:
    if claim_rows and len(claim_rows) == len(claim_texts) and claim_texts:
        bi = max(range(len(claim_rows)), key=lambda k: _claim_strength_value(claim_rows[k]))
        best = claim_texts[bi]
    else:
        best = max(claim_texts, key=len, default=clip_text) if claim_texts else clip_text
    words = (best or "").split()
    if not words:
        return ""
    title = " ".join(words[:14])
    if len(title) > 110:
        title = title[:107] + "…"
    return title


def extract_clips_v2(
    *,
    accepted_claims: Sequence[Mapping[str, Any]],
    evaluation_map: Any,
    source_segments: Sequence[Mapping[str, Any]],
    thesis: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return ``{ "clips": [ ... ] }`` only. Every clip lists ``claim_ids``, ``segment_ids``,
    ``start_time`` / ``end_time``, and ``clip_type``. ``suggested_title`` is **compressed
    from the strongest supported claim** (or clip text) — no external invention.

    Fail closed: on invalid input, returns ``{"clips": [], "reason": "..."}`` (and no orphan clips).
    """
    out_empty = {"clips": []}
    claims, em, by_id, err = _strict_inputs(accepted_claims, evaluation_map, source_segments)
    if err:
        return {**out_empty, "reason": err}

    rows: List[Tuple[str, str, str, int]] = []
    claim_objs: List[Dict[str, Any]] = []
    for i, c in enumerate(claims):
        cid = _claim_id(c, i)
        txt = _claim_text(c)
        if cid not in em:
            return {**out_empty, "reason": f"NO_CLIPS: claim {cid!r} not in evaluation_map"}
        sid = em[cid]
        if sid not in by_id:
            return {**out_empty, "reason": f"NO_CLIPS: segment {sid!r} for claim {cid!r} missing"}
        if not txt:
            return {**out_empty, "reason": f"NO_CLIPS: empty text for claim {cid!r}"}
        rows.append((cid, txt, sid, i))
        claim_objs.append(dict(c))
    th_tokens: Set[str] = set()
    if thesis and str(thesis).strip():
        th_tokens = set(_tokens(str(thesis)))

    texts = [t[1] for t in rows]
    clusters = _claim_clusters(texts)
    clips_out: List[Dict[str, Any]] = []

    for comp in clusters:
        comp = sorted(set(comp), key=lambda x: (_coerce_time(by_id[rows[x][2]])[0], x))
        cids = [rows[i][0] for i in comp]
        ctexts = [rows[i][1] for i in comp]
        seg_u: List[str] = []
        for i in comp:
            s = rows[i][2]
            if s not in seg_u:
                seg_u.append(s)
        # Time order: sort unique segments by start
        seg_u.sort(key=lambda sid: _coerce_time(by_id[sid])[0])
        st_min = min((_coerce_time(by_id[s])[0] for s in seg_u), default=0.0)
        en_max = max((_coerce_time(by_id[s])[1] for s in seg_u), default=st_min)
        # Build text: prefer full segment text when one segment; else join claim text (claim-bounded)
        if len(seg_u) == 1:
            s0 = by_id[seg_u[0]]
            seg_txt = _norm(str(s0.get("text") or ""))
            if seg_txt and all(ct in seg_txt for ct in ctexts if len(ct) > 6):
                clip_text = seg_txt
            else:
                clip_text = " ".join(ctexts) if ctexts else seg_txt
        else:
            parts: List[str] = []
            for sid in seg_u:
                p = _norm(str(by_id[sid].get("text") or ""))
                if p:
                    parts.append(p)
            clip_text = " ".join(parts) if parts else " ".join(ctexts)
        if not _norm(clip_text):
            continue
        claim_union: Set[str] = set()
        for i in comp:
            claim_union |= set(_tokens(rows[i][1]))
        if th_tokens and claim_union:
            if len(th_tokens & claim_union) / max(1, len(th_tokens | claim_union)) > 0.12:
                pass
        sents = _split_sentences(clip_text)
        if not sents:
            continue
        if not _narrative_drift(sents, claim_union):
            continue
        if not _sentences_anchored(clip_text, claim_union):
            continue
        c_rows = [claim_objs[rows[i][3]] for i in comp]
        base = _score_clip(clip_text, c_rows)
        if th_tokens and sents:
            boost = 0.12 * min(1.0, len(set(_tokens(clip_text)) & th_tokens) / max(1, len(th_tokens)))
            base = min(8.0, base + boost)
        if base < MIN_CLIP_SCORE:
            continue
        ctype = _clip_type_for(clip_text)
        title = _suggested_title(c_rows, ctexts, clip_text)
        clips_out.append(
            {
                "clip_id": f"clip_{len(clips_out) + 1}",
                "text": _norm(clip_text),
                "suggested_title": title,
                "start_time": float(st_min),
                "end_time": float(en_max),
                "claim_ids": cids,
                "segment_ids": seg_u,
                "clip_type": ctype,
                "clip_score": round(base, 2),
            }
        )
    # Stable order by time
    clips_out.sort(key=lambda c: (c["start_time"], c.get("clip_id", "")))
    for i, c in enumerate(clips_out):
        c["clip_id"] = f"clip_{i+1}"
    return {"clips": clips_out}


def structural_connected_components(claim_texts: List[str]) -> List[List[int]]:
    """
    Structural graph over claim indices: edges from :func:`_structural_pair_score` ≥ ``GRAPH_TH``.
    Returns all connected components (for integration and regression tests, not for narrative “themes”).
    """
    return _claim_clusters(claim_texts)


__all__ = [
    "extract_clips_v2",
    "structural_connected_components",
    "MIN_CLIP_SCORE",
    "GRAPH_TH",
]
