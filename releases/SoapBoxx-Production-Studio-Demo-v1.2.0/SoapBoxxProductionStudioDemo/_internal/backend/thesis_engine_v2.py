# backend/thesis_engine_v2.py
"""
Thesis Construction Engine v2 (SOAPBOXX core): a thesis is *extracted* from repetition under
constraint — not “what does the episode feel like?”. No interpretive model; only structural
overlap (lexical, mechanism regex, simple entity patterns).

**Contract:** :func:`construct_thesis_v2` requires non-empty ``accepted_claims``,
``evaluation_map`` (claim_id → source_segment_id), and ``source_segments`` (each with ``id``).
Optional ``episode_metadata`` supports title/guest *leakage checks only* — never used to invent text.

**Fail closed** when inputs are missing or constraints fail (see ``reason`` in the return dict).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

# --- Repetition / coverage constraints ---
MIN_CLAIMS_IN_CLUSTER = 3
MIN_DISTINCT_SOURCE_SEGMENTS = 2
GRAPH_EDGE_TH = 0.1

# --- Confidence bands (tune on real shows) ---
CONF_SHIPPABLE = 0.8
CONF_WEAK = 0.6

_BANNED_THESIS_PATTERNS = re.compile(
    r"(?i)\b("
    r"this episode is about|we discuss|today we\W*(talk|explore)|in this (episode|show)|"
    r"critical discussion of|important conversation|deep dive into( the)?\s*(larger )?meaning|"
    r"exploring themes|thematic(ally)?\s,|sentiment|overall tone|vibe|feels like"
    r")\b",
)
_VAGUE_ABSTRACTIONS = re.compile(
    r"(?i)\b("
    r"global politics|the world order|geopolitics in general|international relations broadly|"
    r"society as a whole|in today's world(?!,)"
    r")\b",
)
_STOP = frozenset(
    "the a an and or but if in on at to for of is are was were be been being it this that these those "
    "with as by from into through over under again then once here there when where why how all any "
    "each every both few more most other some such no nor not only own same so than too very can "
    "will just should now that what which who also about than into your our their they them his her "
    "its we you i me my ve re ll d ont doesn didn wasn weren".split()
)
_MECH_LEX = re.compile(
    r"(?i)\b("
    r"influenc\w*|threat\w*|surveill\w*|intelligen\w*|policy|narrative\w*|perception|"
    r"operat\w*|agenc\w*|align\w*|shap\w*|driv\w*|disclos\w*|monitor\w*"
    r")\b",
)
_ENTITY_HINT = re.compile(
    r"(?i)\b("
    r"u\.?s\.?a?\.?|united states|u\.?k\.?|e\.?u\.?|u\.?n\.?|nato|"
    r"cia|fbi|nsa|israel|china|russia|iran|gaza|ukraine|"
    r"congress|senate|white house|pentagon"
    r")\b"
)


def _norm(s: str) -> str:
    t = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"\s+", " ", t).strip()


def _tokens(s: str) -> List[str]:
    return [w for w in re.findall(r"[a-z0-9']+", (s or "").lower()) if len(w) >= 3 and w not in _STOP]


def _content_token_set(s: str) -> Set[str]:
    return set(_tokens(s))


def _mechems(s: str) -> Set[str]:
    return {m.group(0).lower() for m in _MECH_LEX.finditer(s)}


def _structural_pair_score(a: str, b: str) -> float:
    ta, tb = _content_token_set(a), _content_token_set(b)
    if not ta or not tb:
        return 0.0
    j = len(ta & tb) / max(1, len(ta | tb))
    m_a, m_b = _mechems(a), _mechems(b)
    m_bon = 0.15 * (1.0 if m_a & m_b else 0.0)
    e_a = {x.lower() for x in _ENTITY_HINT.findall(a)}
    e_b = {x.lower() for x in _ENTITY_HINT.findall(b)}
    e_bon = 0.1 * (1.0 if e_a & e_b else 0.0)
    return min(1.0, j + m_bon + e_bon)


def _coerce_eval_map(raw: Any) -> Tuple[Dict[str, str], str]:
    if raw is None:
        return {}, "missing evaluation_map"
    if isinstance(raw, dict):
        out = {str(k).strip(): str(v).strip() for k, v in raw.items() if k is not None and v is not None}
        return (out, "" if out else "empty evaluation_map")
    if isinstance(raw, list):
        out: Dict[str, str] = {}
        for i, row in enumerate(raw):
            if not isinstance(row, Mapping):
                return {}, f"evaluation_map[{i}] is not an object"
            cid = str(row.get("claim_id") or row.get("id") or row.get("claimId") or "").strip()
            sid = str(
                row.get("source_segment_id")
                or row.get("segment_id")
                or row.get("segmentId")
                or row.get("source_segment")
                or ""
            ).strip()
            if not cid or not sid:
                return {}, f"evaluation_map[{i}] needs claim_id and source_segment_id"
            out[cid] = sid
        return (out, "" if out else "empty evaluation_map")
    return {}, "evaluation_map must be a list or dict"


def _strict_inputs(
    accepted_claims: Any,
    evaluation_map: Any,
    source_segments: Any,
) -> Tuple[List[Dict[str, Any]], Dict[str, str], List[Dict[str, Any]], str]:
    if not isinstance(accepted_claims, (list, tuple)) or not accepted_claims:
        return [], {}, [], "NO_THESIS: accepted_claims must be a non-empty list"
    claims = [c for c in accepted_claims if isinstance(c, dict)]
    if len(claims) < MIN_CLAIMS_IN_CLUSTER:
        return [], {}, [], "NO_THESIS: need at least 3 claim dicts"
    em, emsg = _coerce_eval_map(evaluation_map)
    if emsg:
        return [], {}, [], f"NO_THESIS: {emsg}"
    if not isinstance(source_segments, (list, tuple)) or not source_segments:
        return [], {}, [], "NO_THESIS: source_segments must be a non-empty list"
    segs = [s for s in source_segments if isinstance(s, dict) and s.get("id") is not None]
    if not segs:
        return [], {}, [], "NO_THESIS: each source_segment must be a dict with id"
    return claims, em, segs, ""


def _claim_id(c: Dict[str, Any], idx: int) -> str:
    return str(c.get("id") or f"c{idx+1}").strip()


def _claim_text(c: Dict[str, Any]) -> str:
    return _norm(str(c.get("text") or c.get("claim") or ""))


def _largest_component_indices(n: int, texts: List[str]) -> List[int]:
    adj: List[Set[int]] = [set() for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if _structural_pair_score(texts[i], texts[j]) >= GRAPH_EDGE_TH:
                adj[i].add(j)
                adj[j].add(i)
    best: List[int] = []
    seen = [False] * n

    def dfs(i: int, acc: List[int]) -> None:
        acc.append(i)
        seen[i] = True
        for j in adj[i]:
            if not seen[j]:
                dfs(j, acc)

    for s in range(n):
        if seen[s]:
            continue
        comp: List[int] = []
        dfs(s, comp)
        if len(comp) > len(best):
            best = comp
    return best


def _build_cluster(claim_texts: List[str], claim_ids: List[str], em: Dict[str, str]) -> Tuple[List[str], Set[str], str]:
    n = len(claim_texts)
    if n < MIN_CLAIMS_IN_CLUSTER:
        return [], set(), "INSUFFICIENT_SIGNAL_FOR_THESIS"
    comp = _largest_component_indices(n, claim_texts)
    if len(comp) < MIN_CLAIMS_IN_CLUSTER:
        return [], set(), "INSUFFICIENT_SIGNAL_FOR_THESIS"
    cids = [claim_ids[i] for i in comp]
    segs: Set[str] = set()
    for cid in cids:
        if cid in em:
            segs.add(em[cid])
    if len(segs) < MIN_DISTINCT_SOURCE_SEGMENTS:
        return [], set(), "INSUFFICIENT_SIGNAL_FOR_THESIS: need at least 2 source segments in cluster"
    return cids, segs, ""


def _thesis_banned_narrative(thesis: str) -> bool:
    return bool(_BANNED_THESIS_PATTERNS.search(thesis) or _VAGUE_ABSTRACTIONS.search(thesis))


def _thesis_too_like_title(thesis: str, title: str) -> bool:
    if not (thesis and title and len(title) > 8):
        return False
    t, ti = _norm(thesis).lower(), _norm(title).lower()
    if SequenceMatcher(a=t, b=ti).ratio() > 0.55:
        return True
    a, b = set(_tokens(t)), set(_tokens(ti))
    if not a or not b:
        return False
    return len(a & b) / max(1, len(a | b)) > 0.45


def _thesis_too_like_guest_bubble(thesis: str, guest_blob: str) -> bool:
    if not (thesis and guest_blob and len(guest_blob) > 20):
        return False
    a, b = set(_tokens(thesis)), set(_tokens(guest_blob))
    if not a or not b:
        return False
    return len(a & b) / max(1, len(a)) > 0.5


def _thesis_vocabulary_in_claims(thesis: str, combined_claims: str) -> Tuple[bool, List[str]]:
    glue = frozenset(
        "this episode suggests that based on repeated claims across independent segments connects "
        "and the a an of to in for with by from that related key cited material elements stated "
        "content claims".split()
    )
    tks = re.findall(r"[a-z0-9']+", thesis.lower())
    big = {w for w in tks if len(w) >= 4 and w not in glue}
    blob = (combined_claims or "").lower()
    bad = [w for w in big if w not in blob]
    return (len(bad) == 0, bad)


def _collapse_thesis(claim_texts: List[str]) -> str:
    m_all: List[str] = []
    e_all: List[str] = []
    c_all: List[str] = []
    for t in claim_texts:
        m_all.extend(_mechems(t))
        e_all.extend(_ENTITY_HINT.findall(t))
        c_all.extend(_tokens(t))
    if m_all:
        mech, _ = Counter(m_all).most_common(1)[0]
    else:
        mech = Counter(c_all).most_common(1)[0][0] if c_all else "repeatedly stated elements"
    mech_l = (mech or "").lower()
    ec_full = [x for x, _ in Counter(e.lower() for e in e_all).most_common(6)]
    ent_excl = set(ec_full) | {mech_l}
    toks = [x for x, _ in Counter(c_all).most_common(10) if x not in ent_excl and x != mech_l]
    if len(ec_full) >= 2:
        enta, entb = ec_full[0], ec_full[1]
    elif len(ec_full) == 1 and len(toks) >= 1:
        enta, entb = ec_full[0], toks[0]
    elif len(toks) >= 2:
        enta, entb = toks[0], toks[1]
    elif len(toks) == 1:
        enta = entb = toks[0]
    else:
        enta = entb = "claims"
    return (
        f"This episode suggests that {mech} connects {enta} and {entb}, "
        f"based on repeated claims across independent segments."
    )


def _confidence(
    n_claims: int,
    n_segs: int,
    n_tok_thesis: int,
    oob_toks: int,
    cluster_tight: float,
) -> float:
    csc = min(0.5, 0.12 * n_claims)
    cd = min(0.35, 0.1 * n_segs + cluster_tight * 0.25)
    cross = min(0.3, 0.12 * max(0, n_segs - 1))
    abstr = 0.12 * (1.0 if n_tok_thesis > 28 else 0.0) + 0.25 * float(oob_toks)
    novel = 0.08 * float(oob_toks)
    return max(0.0, min(1.0, csc + cd + cross - abstr - novel))


def _cluster_tightness(texts: List[str]) -> float:
    n = len(texts)
    if n < 2:
        return 0.0
    acc = 0.0
    pair = 0
    for i in range(n):
        for j in range(i + 1, n):
            acc += _structural_pair_score(texts[i], texts[j])
            pair += 1
    return acc / max(1, pair)


def construct_thesis_v2(
    *,
    accepted_claims: Sequence[Mapping[str, Any]],
    evaluation_map: Any,
    source_segments: Sequence[Mapping[str, Any]],
    episode_metadata: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    def _empty(
        reason: str,
        *,
        conf: float = 0.0,
        status: str = "INSUFFICIENT_SIGNAL",
        cids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        cl = (
            [
                {
                    "cluster_name": "structural_repetition",
                    "claim_ids": cids,
                }
            ]
            if cids
            else []
        )
        return {
            "thesis": None,
            "supporting_clusters": cl,
            "confidence_score": round(conf, 4),
            "generation_status": status,
            "reason": reason,
        }

    claims, em, segs, err = _strict_inputs(accepted_claims, evaluation_map, source_segments)
    if err:
        return _empty(err)

    valid_seg = {str(s.get("id")) for s in segs}
    claim_ids = [_claim_id(claims[i], i) for i in range(len(claims))]
    claim_texts = [_claim_text(claims[i]) for i in range(len(claims))]
    id_to_text = {claim_ids[i]: claim_texts[i] for i in range(len(claim_ids))}
    for cid in claim_ids:
        if cid not in em:
            return _empty(f"NO_THESIS: claim {cid!r} missing in evaluation_map")
        if em[cid] not in valid_seg:
            return _empty(f"NO_THESIS: segment {em[cid]!r} for {cid!r} not in source_segments")

    cids, seg_set, cerr = _build_cluster(claim_texts, claim_ids, em)
    if not cids or cerr:
        return _empty(cerr or "INSUFFICIENT_SIGNAL_FOR_THESIS")
    cl_texts = [id_to_text[c] for c in cids if c in id_to_text]
    if len(cl_texts) < MIN_CLAIMS_IN_CLUSTER:
        return _empty("INSUFFICIENT_SIGNAL_FOR_THESIS")
    combined = " \n".join(cl_texts)
    thesis = _collapse_thesis(cl_texts)
    meta = dict(episode_metadata) if isinstance(episode_metadata, Mapping) else {}
    title = str(meta.get("title") or meta.get("episode_title") or "")
    gbio = " ".join(str(meta.get(x) or "") for x in ("guest_bio", "description", "guest_description", "creator_note"))

    if _thesis_banned_narrative(thesis):
        return _empty("BANNED_NARRATIVE_PATTERN", status="UNSHIPPABLE", cids=cids)
    if _thesis_too_like_title(thesis, title):
        return _empty("THESIS_DERIVED_FROM_OR_TOO_CLOSE_TO_TITLE", status="UNSHIPPABLE", cids=cids)
    if _thesis_too_like_guest_bubble(thesis, gbio):
        return _empty("THESIS_OVERLAPS_GUEST_BIO_ONLY", status="UNSHIPPABLE", cids=cids)

    ok_vocab, oob = _thesis_vocabulary_in_claims(thesis, combined)
    if not ok_vocab:
        return {
            "thesis": None,
            "supporting_clusters": [{"cluster_name": "structural_repetition", "claim_ids": cids}],
            "confidence_score": 0.0,
            "generation_status": "UNSHIPPABLE",
            "reason": f"THESIS_INTRODUCED_TOKENS_NOT_IN_CLAIMS: {oob[:8]}",
        }

    ct = _cluster_tightness(cl_texts)
    conf = _confidence(
        n_claims=len(cids),
        n_segs=len(seg_set),
        n_tok_thesis=len(_tokens(thesis)),
        oob_toks=len(oob),
        cluster_tight=ct,
    )
    out_base = {
        "thesis": thesis,
        "supporting_clusters": [{"cluster_name": "structural_repetition", "claim_ids": cids}],
        "confidence_score": round(conf, 4),
    }
    if conf < CONF_WEAK:
        return {
            "thesis": None,
            "supporting_clusters": out_base["supporting_clusters"],
            "confidence_score": out_base["confidence_score"],
            "generation_status": "INSUFFICIENT_SIGNAL" if conf < 0.35 else "UNSHIPPABLE",
            "reason": f"THESIS_CONFIDENCE_BELOW_{CONF_WEAK}",
        }
    if conf < CONF_SHIPPABLE:
        return {
            **out_base,
            "generation_status": "UNSHIPPABLE",
            "reason": "WEAK_THESIS_BELOW_SHIPPABLE_THRESHOLD",
        }
    return {
        **out_base,
        "generation_status": "SHIPPABLE",
        "reason": None,
    }


__all__ = [
    "construct_thesis_v2",
    "CONF_SHIPPABLE",
    "CONF_WEAK",
    "MIN_CLAIMS_IN_CLUSTER",
    "MIN_DISTINCT_SOURCE_SEGMENTS",
]
