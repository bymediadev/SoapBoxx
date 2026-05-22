from __future__ import annotations

import math
import re
from typing import Any, Callable, Dict, List, Tuple

import numpy as np

SUPPORT_SCORE_THRESHOLD = 0.65
# Episode debug: count claims with per-claim semantic score below this (weak / non-supporting).
LOW_SUPPORT_CLAIM_THRESHOLD = 0.4
_TOP_K_WTOP = 0.7
_SUPPORT_RATIO_W = 0.3
_DISPERSION_PENALTY_COEFF = 0.25


def _normalize_token(tok: str) -> str:
    out = tok.lower().strip()
    for suffix in ("ing", "ed", "es", "s"):
        if len(out) > 4 and out.endswith(suffix):
            out = out[: -len(suffix)]
            break
    return out


def _tokenize(text: str) -> List[str]:
    return [_normalize_token(t) for t in re.split(r"[^a-z0-9]+", (text or "").lower()) if t]


def _chargram_overlap(a: str, b: str, n: int = 4) -> float:
    aa = re.sub(r"[^a-z0-9]+", " ", (a or "").lower()).strip()
    bb = re.sub(r"[^a-z0-9]+", " ", (b or "").lower()).strip()
    if len(aa) < n or len(bb) < n:
        return 0.0
    ag = {aa[i : i + n] for i in range(0, len(aa) - n + 1)}
    bg = {bb[i : i + n] for i in range(0, len(bb) - n + 1)}
    if not ag or not bg:
        return 0.0
    return len(ag & bg) / max(1, min(len(ag), len(bg)))


def _fallback_embed(text: str, dim: int = 128) -> List[float]:
    vec = [0.0] * dim
    toks = _tokenize(text)
    if not toks:
        return vec
    for tok in toks:
        idx = hash(tok) % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 0:
        return vec
    return [v / norm for v in vec]


# ---- Embedding (plug your existing function here) ----
def embed(text: str) -> List[float]:
    """
    Default safe embedding for deterministic local scoring.

    Replace with your local embedding call (Ollama or sentence-transformers)
    if/when available.
    """
    return _fallback_embed(text)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    a2 = a[:n]
    b2 = b[:n]
    dot = sum(x * y for x, y in zip(a2, b2))
    norm_a = math.sqrt(sum(x * x for x in a2))
    norm_b = math.sqrt(sum(x * x for x in b2))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def embedding_score(thesis: str, claim: str) -> float:
    try:
        t_vec = embed(thesis)
        c_vec = embed(claim)
    except Exception:
        t_vec, c_vec = [], []

    cos = cosine_similarity(t_vec, c_vec)
    t_toks = set(_tokenize(thesis))
    c_toks = set(_tokenize(claim))
    if not t_toks or not c_toks:
        return cos
    overlap = len(t_toks & c_toks) / max(1, min(len(t_toks), len(c_toks)))
    chargram = _chargram_overlap(thesis, claim)
    return max(cos, overlap, chargram)


# ---- NLI (stub – replace with local model or lightweight classifier) ----
def nli_score(thesis: str, claim: str) -> float:
    """
    Replace with real NLI model.
    Temporary heuristic fallback.
    """
    overlap = len(set(_tokenize(thesis)) & set(_tokenize(claim)))
    if overlap > 5:
        return 0.7
    if overlap > 2:
        return 0.4
    return 0.2


# ---- LLM judgment (uses your existing Ollama invoke) ----
def llm_alignment_score(thesis: str, claim: str, llm_call: Callable[[str], Dict[str, Any]]) -> float:
    prompt = f"""
You are scoring whether a claim supports a thesis.

Return JSON only.

{{
  "relation": "supports" | "weakly_supports" | "unrelated" | "contradicts"
}}

Thesis:
{thesis}

Claim:
{claim}
"""

    relation = "unrelated"
    try:
        res = llm_call(prompt)
        if isinstance(res, dict):
            relation = str(res.get("relation", "unrelated")).strip().lower()
    except Exception:
        relation = "unrelated"

    mapping = {
        "supports": 1.0,
        "weakly_supports": 0.6,
        "unrelated": 0.2,
        "contradicts": 0.0,
    }
    return mapping.get(relation, 0.2)


# ---- Combined scorer ----
def semantic_alignment(thesis: str, claim: str, llm_call: Callable[[str], Dict[str, Any]] | None = None) -> float:
    e = embedding_score(thesis, claim)

    # Early exit (performance + hard penalty).
    if e < 0.3:
        return 0.0

    n = nli_score(thesis, claim)

    components: List[tuple[float, float]] = [
        (e, 0.5),
        (n, 0.3),
    ]
    if llm_call is not None:
        l = llm_alignment_score(thesis, claim, llm_call)
        components.append((l, 0.2))

    total_weight = sum(w for _, w in components)
    if total_weight <= 0:
        return 0.0
    return sum(score * w for score, w in components) / total_weight


# ---- Episode-level score ----
def aggregate_alignment(
    scores: List[float],
    *,
    support_score_threshold: float = SUPPORT_SCORE_THRESHOLD,
) -> Tuple[float, Dict[str, Any]]:
    """
    Combine top-k mean (stricter k), support_ratio, and dispersion in one [0, 1] score.
    """
    if not scores:
        return 0.0, {
            "top_k_mean": 0.0,
            "support_ratio": 0.0,
            "std_dev": 0.0,
            "k": 0,
            "n": 0,
        }

    s = sorted(scores, reverse=True)
    n = len(s)

    k_cap = min(5, max(3, n // 3))
    k = min(n, k_cap)
    top_k = s[:k]
    top_k_mean = float(sum(top_k) / len(top_k))

    support_ratio = sum(1 for x in s if x >= support_score_threshold) / float(n)
    std_dev = float(np.std(np.asarray(s, dtype=np.float64)))
    dispersion_penalty = _DISPERSION_PENALTY_COEFF * std_dev

    raw = _TOP_K_WTOP * top_k_mean + _SUPPORT_RATIO_W * support_ratio - dispersion_penalty
    alignment = max(0.0, min(1.0, float(raw)))

    debug = {
        "top_k_mean": top_k_mean,
        "support_ratio": support_ratio,
        "std_dev": std_dev,
        "k": k,
        "n": n,
    }
    return alignment, debug


def claim_alignment_detail(
    thesis: str,
    claims: List[str],
    llm_call: Callable[[str], Dict[str, Any]] | None = None,
    *,
    support_score_threshold: float = SUPPORT_SCORE_THRESHOLD,
) -> Dict[str, Any]:
    """
    Per-claim alignment plus episode-level mix: best-case (top-k mean) + majority support
    (support_ratio) minus a dispersion (incoherence) penalty.
    """
    if not thesis or not claims:
        return {
            "score": 0.0,
            "top_k_mean": 0.0,
            "support_ratio": 0.0,
            "std_dev": 0.0,
            "num_claims": 0,
            "k": 0,
            "n": 0,
            "low_support_count": 0,
            "support_score_threshold": float(support_score_threshold),
        }

    scores = [semantic_alignment(thesis, c, llm_call) for c in claims if c and len(c) > 10]
    if not scores:
        return {
            "score": 0.0,
            "top_k_mean": 0.0,
            "support_ratio": 0.0,
            "std_dev": 0.0,
            "num_claims": 0,
            "k": 0,
            "n": 0,
            "low_support_count": 0,
            "support_score_threshold": float(support_score_threshold),
        }

    score, agg_debug = aggregate_alignment(scores, support_score_threshold=support_score_threshold)
    n = int(agg_debug["n"])
    low_support_count = sum(1 for s in scores if s < LOW_SUPPORT_CLAIM_THRESHOLD)
    return {
        "score": float(score),
        "top_k_mean": float(agg_debug["top_k_mean"]),
        "support_ratio": float(agg_debug["support_ratio"]),
        "std_dev": float(agg_debug["std_dev"]),
        "num_claims": n,
        "k": int(agg_debug["k"]),
        "n": n,
        "low_support_count": int(low_support_count),
        "support_score_threshold": float(support_score_threshold),
    }


def claim_alignment_score(
    thesis: str, claims: List[str], llm_call: Callable[[str], Dict[str, Any]] | None = None
) -> float:
    return float(claim_alignment_detail(thesis, claims, llm_call)["score"])


__all__ = [
    "SUPPORT_SCORE_THRESHOLD",
    "LOW_SUPPORT_CLAIM_THRESHOLD",
    "aggregate_alignment",
    "claim_alignment_detail",
    "claim_alignment_score",
    "cosine_similarity",
    "embed",
    "embedding_score",
    "llm_alignment_score",
    "nli_score",
    "semantic_alignment",
]
