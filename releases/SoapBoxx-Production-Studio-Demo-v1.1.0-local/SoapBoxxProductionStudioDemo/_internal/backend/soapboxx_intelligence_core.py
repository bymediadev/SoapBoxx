"""
Single-file intelligence core: **judgment** (transcript → passes → ship) plus **brief** ship gate.

**Judgment path** (transcript, no module sprawl; calibrate only thresholds)::

    empty_brief, run_spine_first, run_critic, run_refiner, semantic_alignment, ship_decision, run, EVAL_SET, run_eval

**Episode-brief path** (production; unchanged API)::

    assess_brief_intelligence_ship, load_ship_gate_config, claim_alignment_detail (from ``semantic_alignment``)

Tweak ``JUDGMENT_*`` and ``SHIP_GATE_DEFAULT`` / ``load_ship_gate_config`` for fast iteration.
For a quick check: ``python backend/soapboxx_intelligence_core.py --smoke`` (briefs) or ``--judgment`` (EVAL_SET).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.error
import urllib.request

# ===== JUDGMENT ENGINE (transcript; structural repair, not paraphrase) — calibrate: JUDGMENT_* only =====

JUDGMENT_ALIGNMENT_FAIL = 0.45
JUDGMENT_SCORE_REVIEW = 0.6

_VAGUE_TOKENS = ("maybe", "perhaps", "sort of", "kind of", "sortof", "hmm", "umm", "uh", "things")


def empty_brief() -> Dict[str, Any]:
    return {
        "pass1": {},
        "pass2": {},
        "pass3": {},
        "score": 0.0,
        "alignment": 0.0,
        "decision": None,
    }


def run_spine_first(transcript: str) -> Dict[str, Any]:
    """
    Pass 1: thesis + atomic claims (heuristic extraction from raw transcript; replace with LLM in pipeline).
    """
    t = (transcript or "").strip()
    if not t:
        return {"thesis": "", "claims": []}
    parts = re.split(r"(?<=[.!?])\s+|\n+", t)
    sents = [p.strip() for p in parts if p and p.strip()]
    if not sents:
        sents = [t]

    def _wc(s: str) -> int:
        return len(s.split())

    thesis_s = sents[0]
    if _wc(thesis_s) < 6 and len(sents) > 1:
        thesis_s = (sents[0] + " " + sents[1]).strip()

    claim_texts: List[str] = []
    for s in sents:
        if not s or s == thesis_s:
            continue
        if _wc(s) >= 8:
            claim_texts.append(s)
    if not claim_texts:
        for s in sents[1:4]:
            if s and s not in (thesis_s,):
                claim_texts.append(s)
    if not claim_texts and thesis_s:
        claim_texts = [thesis_s if len(thesis_s) <= 200 else thesis_s[:197] + "..."]

    claims = [{"id": f"c{j+1}", "text": tx} for j, tx in enumerate(claim_texts[:12])]
    return {"thesis": thesis_s, "claims": claims}


def run_critic(pass1: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pass 2: attack vagueness, unsupported (short) claims, and weak structure (heuristic).
    """
    issues: List[Dict[str, Any]] = []
    for c in pass1.get("claims") or []:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id", "") or "")
        text = (c.get("text") or "").strip()
        low = text.lower()
        if len(text) < 12:
            issues.append({"claim_id": cid, "problem": "unverifiable"})
        elif any(v in low for v in _VAGUE_TOKENS):
            issues.append({"claim_id": cid, "problem": "vague"})
    thesis = (pass1.get("thesis") or "").strip()
    if len(thesis.split()) < 6:
        issues.append({"claim_id": "", "problem": "vague_thesis"})
    if ";" in thesis and thesis.count(";") >= 1 and len(thesis.split()) < 8:
        issues.append({"claim_id": "", "problem": "unstructured_thesis"})

    severity = min(1.0, 0.12 * len(issues) + (0.15 if not thesis else 0.0))
    return {"issues": issues, "severity": round(float(severity), 4)}


def run_refiner(pass1: Dict[str, Any], pass2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pass 3: repair support structure: drop or tighten, not paraphrase for its own sake.
    """
    issues = pass2.get("issues") or []
    claims: List[Dict[str, Any]] = []
    for c in pass1.get("claims") or []:
        if not isinstance(c, dict):
            continue
        cid = c.get("id", "")
        issue = next((i for i in issues if i.get("claim_id") == cid), None)
        if issue and issue.get("problem") == "unverifiable":
            continue
        if issue and issue.get("problem") == "vague" and len((c.get("text") or "").split()) < 8:
            continue
        claims.append(dict(c))
    if any(x.get("problem") == "unstructured_thesis" for x in issues if isinstance(x, dict)):
        return {"refined_thesis": "", "claims": []}
    return {"refined_thesis": pass1.get("thesis") or "", "claims": claims}


def semantic_alignment(thesis: str, claims: List[Dict[str, Any]]) -> float:
    """
    Simple agreement signal thesis↔claims; swap for embeddings/NLI later — keep signature stable.
    """
    if not claims:
        return 0.0
    scores: List[float] = []
    toks = (thesis or "").split()
    head = toks[0] if toks else ""
    for c in claims:
        text = (c.get("text", "") or "") if isinstance(c, dict) else str(c)
        score = 1.0 if (head and head.lower() in text.lower()) else 0.4
        scores.append(score)
    return float(sum(scores) / max(1, len(scores)))


def ship_decision(pass1: Dict[str, Any], pass2: Dict[str, Any], pass3: Dict[str, Any]) -> Dict[str, Any]:
    th = (pass1.get("thesis") or "") or (pass3.get("refined_thesis") or "")
    claims = pass3.get("claims") or []
    align = semantic_alignment(str(th), claims if isinstance(claims, list) else [])
    sev = float(pass2.get("severity") or 0.0)
    score = align * 0.5 + (1.0 - sev) * 0.5
    if align < JUDGMENT_ALIGNMENT_FAIL:
        return {
            "decision": "FAIL",
            "reason": "low_alignment",
            "score": round(float(score), 4),
            "alignment": round(float(align), 4),
        }
    if score < JUDGMENT_SCORE_REVIEW:
        return {
            "decision": "REVIEW",
            "reason": "borderline",
            "score": round(float(score), 4),
            "alignment": round(float(align), 4),
        }
    return {
        "decision": "PASS",
        "reason": "ok",
        "score": round(float(score), 4),
        "alignment": round(float(align), 4),
    }


EVAL_SET: List[Dict[str, Any]] = [
    {
        "id": "case_1",
        "transcript": (
            "Revenue growth often reflects pricing power in durable competitive moats. "
            "Revenue increases when customers accept higher prices for the same value proposition. "
            "Revenue deceleration sometimes signals market saturation or new competition in the same segment."
        ),
        "label": "PASS",
    },
    {
        "id": "case_2",
        "transcript": "One; two; three; four",
        "label": "FAIL",
    },
    {
        "id": "case_3",
        "transcript": "",
        "label": "FAIL",
    },
]


def run(transcript: str) -> Dict[str, Any]:
    p1 = run_spine_first(transcript)
    p2 = run_critic(p1)
    p3 = run_refiner(p1, p2)
    dec = ship_decision(p1, p2, p3)
    return {
        "pass1": p1,
        "pass2": p2,
        "pass3": p3,
        "decision": dec,
    }


def run_eval() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for case in EVAL_SET:
        r = run(str(case.get("transcript") or ""))
        d = r.get("decision") or {}
        out.append(
            {
                "id": case.get("id"),
                "pred": d.get("decision"),
                "label": case.get("label"),
                "score": d.get("score"),
                "alignment": d.get("alignment"),
            }
        )
    return out


# Scoring formulas live in ``semantic_alignment`` (patchable in tests). This module owns ship math + Ollama.
try:
    from .semantic_alignment import claim_alignment_detail
except ImportError:
    from semantic_alignment import claim_alignment_detail

# --- Ollama alignment (standalone HTTP; same env as episode_intelligence) ---

# Same contract as ``LLM_ENVELOPE_SYSTEM_SUFFIX`` in episode_intelligence (brief envelope).
_LLM_ENVELOPE_SUFFIX = """
----
Response contract (mandatory): reply with ONE JSON object and exactly two top-level keys: "text" and "data" only.
- "text": always a string (one-line summary or "").
- "data": always a JSON object (never null, never an array — put the brief object directly here).
- Put the task-specific structured payload inside "data" (see the task schema below).
- Prefer snake_case keys inside "data" (episode_snapshot, claims, …). The server accepts common camelCase
- aliases, but snake_case reduces parse failures on small local models.
- No markdown. No code fences. No top-level keys other than "text" and "data".
""".strip()


def _envelope_data_from_ollama_content(content: Any) -> Dict[str, Any]:
    if content is None:
        return {}
    if isinstance(content, str):
        s = (content or "").strip()
        if not s:
            return {}
        try:
            parsed: Any = json.loads(s)
        except json.JSONDecodeError:
            return {}
    elif isinstance(content, dict):
        parsed = content
    else:
        return {}
    if not isinstance(parsed, dict):
        return {}
    d = parsed.get("data")
    if isinstance(d, dict):
        return d
    if "relation" in parsed and isinstance(parsed.get("relation"), str):
        return {"relation": parsed.get("relation")}
    return {}


def _ollama_http_chat(*, system: str, user: str, _stage: str = "", temperature: float) -> str:
    host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model = os.environ.get("SOAPBOXX_OLLAMA_MODEL", "").strip()
    if not model:
        raise RuntimeError("SOAPBOXX_OLLAMA_MODEL is not set")
    o_opts: Dict[str, Any] = {
        "num_predict": 4096,
        "temperature": temperature,
    }
    _ctx = os.environ.get("SOAPBOXX_OLLAMA_NUM_CTX", os.environ.get("OLLAMA_NUM_CTX", "")).strip()
    if _ctx:
        try:
            o_opts["num_ctx"] = int(_ctx)
        except ValueError:
            pass
    _tp = os.environ.get("SOAPBOXX_OLLAMA_TOP_P", "").strip()
    if _tp:
        try:
            o_opts["top_p"] = float(_tp)
        except ValueError:
            pass
    _seed = os.environ.get("SOAPBOXX_OLLAMA_SEED", "").strip()
    if _seed:
        try:
            o_opts["seed"] = int(_seed)
        except ValueError:
            pass
    system_full = system.rstrip() + "\n\n" + _LLM_ENVELOPE_SUFFIX
    payload_obj: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_full},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "format": "json",
        "options": o_opts,
    }
    data = json.dumps(payload_obj).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return str((body.get("message") or {}).get("content") or "")


def _ollama_alignment_call(prompt: str) -> Dict[str, Any]:
    system = (
        "You score whether a claim semantically supports a thesis. "
        "Return JSON only with key 'relation' in data (supports / weakly_supports / unrelated / contradicts)."
    )
    raw = _ollama_http_chat(
        system=system,
        user=prompt,
        _stage="alignment_scoring",
        temperature=0.0,
    )
    d = _envelope_data_from_ollama_content(raw)
    return d if isinstance(d, dict) else {}


# --- ship gate (inlined) -----------------------------------------------------

THESIS_MIN_WORDS = 6
# At least this fraction of claims must clear SUPPORT_SCORE_THRESHOLD in semantic_alignment.
SUPPORT_RATIO_GATE_MIN = 0.4
# Below this share of supporting claims, clamp PASS to REVIEW (consistency is borderline).
SUPPORT_RATIO_REVIEW_MAX = 0.65

SHIP_GATE_DEFAULT: Dict[str, Any] = {
    "version": 4,
    "weights": {
        "thesis_strength": 0.35,
        "claim_quality": 0.20,
        "claim_alignment": 0.25,
        "evidence_quality": 0.10,
        "critic_composure": 0.05,
        "refinement_delta": 0.05,
    },
    "thresholds": {"pass_min": 0.72, "review_min": 0.52},
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_ship_gate_config() -> Dict[str, Any]:
    cfg = json.loads(json.dumps(SHIP_GATE_DEFAULT))
    raw_path = os.getenv("SOAPBOXX_SHIP_GATE_CONFIG", "").strip()
    path = Path(raw_path) if raw_path else _repo_root() / "config" / "ship_gate.json"
    if path.is_file():
        try:
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                if isinstance(loaded.get("weights"), dict):
                    cfg["weights"].update({k: float(v) for k, v in loaded["weights"].items() if isinstance(v, (int, float))})
                if isinstance(loaded.get("thresholds"), dict):
                    cfg["thresholds"].update(
                        {k: float(v) for k, v in loaded["thresholds"].items() if isinstance(v, (int, float))}
                    )
                if loaded.get("version") is not None:
                    cfg["version"] = loaded.get("version")
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    # Fill missing weight keys from defaults (e.g. older ship_gate.json without alignment).
    base_w = SHIP_GATE_DEFAULT.get("weights") or {}
    w = cfg.get("weights") or {}
    if isinstance(w, dict) and isinstance(base_w, dict):
        # Backward compatibility for old config keys.
        if "claim_quality" not in w and "claim_relevance" in w:
            w["claim_quality"] = float(w.get("claim_relevance", 0.0))
        if "claim_alignment" not in w and "alignment" in w:
            w["claim_alignment"] = float(w.get("alignment", 0.0))
        w.pop("claim_relevance", None)
        w.pop("alignment", None)
        for k, v in base_w.items():
            if k not in w:
                w[k] = float(v)
        cfg["weights"] = w
    # Renormalize weights to sum to 1 if user edited file
    w = cfg.get("weights") or {}
    if isinstance(w, dict):
        s = sum(float(x) for x in w.values() if isinstance(x, (int, float)))
        if s > 0 and abs(s - 1.0) > 0.05:
            cfg["weights"] = {k: float(v) / s for k, v in w.items() if isinstance(v, (int, float))}
    return cfg


def _as_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def _thesis_too_vague_to_evaluate(thesis: str) -> bool:
    t = (thesis or "").strip()
    if not t:
        return True
    return len(t.split()) < THESIS_MIN_WORDS


def _thesis_unstructured_list(thesis: str) -> bool:
    """Tag-cloud / list-style theses (e.g. "A; B; C") are not a single testable claim."""
    t = (thesis or "").strip()
    if t.count(";") >= 2:
        return True
    if ";" in t and len(t.split()) < 8:
        return True
    return False


def _thesis_line(brief: Dict[str, Any]) -> str:
    asp = brief.get("argument_spine") if isinstance(brief.get("argument_spine"), dict) else {}
    th = asp.get("thesis")
    if th is None:
        return ""
    return _as_str(th)


def _score_thesis_strength(brief: Dict[str, Any]) -> float:
    thesis_s = _thesis_line(brief)
    if not thesis_s:
        return 0.28
    n = len(thesis_s)
    if n < 24:
        return 0.42
    if n < 60:
        return 0.62
    return min(0.95, 0.62 + (n - 60) / 400.0)


def _score_claim_quality(brief: Dict[str, Any]) -> float:
    claims = [c for c in (brief.get("claims") or []) if isinstance(c, dict)]
    if not claims:
        return 0.15
    good = 0
    for c in claims[:6]:
        t = _as_str(c.get("text"))
        conf = _as_str(c.get("confidence")).lower()
        if len(t) >= 18 and conf != "low":
            good += 1
    return min(1.0, 0.25 + 0.75 * (good / max(1, len(claims))))


def _score_evidence_quality(brief: Dict[str, Any]) -> float:
    ac = brief.get("argument_critic") if isinstance(brief.get("argument_critic"), dict) else {}
    d = ac.get("data") if isinstance(ac.get("data"), dict) else {}
    evr = d.get("evidence_review") if isinstance(d.get("evidence_review"), dict) else {}
    overall = _as_str(evr.get("overall")).lower()
    if overall == "strong":
        base = 0.88
    elif overall == "mixed":
        base = 0.58
    elif overall == "weak":
        base = 0.35
    else:
        base = 0.52
    issues = evr.get("issues") or []
    n_bad = 0
    if isinstance(issues, list):
        for it in issues:
            s = _as_str(it).lower()
            if "weak_evidence" in s or "unsupported" in s or "anecdotal" in s:
                n_bad += 1
    return max(0.12, base - 0.12 * min(3, n_bad))


def _score_critic_composure(brief: Dict[str, Any]) -> float:
    ac = brief.get("argument_critic") if isinstance(brief.get("argument_critic"), dict) else {}
    d = ac.get("data") if isinstance(ac.get("data"), dict) else {}
    meta = ac.get("metadata") if isinstance(ac.get("metadata"), dict) else {}
    conf = _as_str(meta.get("confidence")).lower()
    bonus = 0.0 if conf == "high" else 0.06 if conf == "medium" else 0.12

    tr = d.get("thesis_review") if isinstance(d.get("thesis_review"), dict) else {}
    tstat = _as_str(tr.get("status")).lower()
    thesis_pen = 0.18 if tstat == "weak" else 0.08 if tstat else 0.0

    weak_n = 0
    irr = 0
    for row in d.get("claims_review") or []:
        if not isinstance(row, dict):
            continue
        st = _as_str(row.get("status")).lower()
        if st == "weak":
            weak_n += 1
        elif st == "irrelevant":
            irr += 1
    claim_pen = min(0.35, 0.07 * weak_n + 0.14 * irr)

    gaps = d.get("logic_gaps") or []
    gap_pen = min(0.2, 0.04 * len(gaps)) if isinstance(gaps, list) else 0.0

    return max(0.08, 0.92 - thesis_pen - claim_pen - gap_pen - bonus)


def _score_refinement_delta(brief: Dict[str, Any]) -> float:
    ar = brief.get("argument_refined") if isinstance(brief.get("argument_refined"), dict) else {}
    md = ar.get("metadata") if isinstance(ar.get("metadata"), dict) else {}
    refn = md.get("refinement") if isinstance(md.get("refinement"), dict) else {}
    status = _as_str(refn.get("status")).lower()
    if status == "failed":
        return 0.22
    claims = [c for c in (brief.get("claims") or []) if isinstance(c, dict)]
    any_refined = any(_as_str(c.get("refined_text")) for c in claims)
    if any_refined:
        return 0.78
    supported = brief.get("evidence_gaps") or {}
    sup = supported.get("supported") if isinstance(supported, dict) else []
    adv = False
    if isinstance(sup, list):
        adv = any("advisory" in _as_str(x).lower() for x in sup)
    if adv or isinstance(brief.get("argument_refined"), dict):
        return 0.5
    return 0.55


def _brief_without_refiner_marks(brief: Dict[str, Any]) -> Dict[str, Any]:
    """Strip pass-3 artifacts so refinement_delta matches pre–pass-3 state."""
    out = {k: v for k, v in brief.items() if k != "argument_refined"}
    claims = []
    for c in (brief.get("claims") or []):
        if not isinstance(c, dict):
            continue
        cc = dict(c)
        cc.pop("refined_text", None)
        cc.pop("refinement_changed", None)
        claims.append(cc)
    out["claims"] = claims
    return out


def _extract_thesis_and_claims(brief: Dict[str, Any]) -> tuple[str, List[str]]:
    spine = (brief or {}).get("argument_spine", {}) or {}
    data = spine.get("data") or {}
    thesis = _as_str(data.get("thesis") or spine.get("thesis") or "")

    claims: List[str] = []
    rows = data.get("claims")
    if not isinstance(rows, list):
        rows = spine.get("claims")
    for c in rows or []:
        if not isinstance(c, dict):
            continue
        text = _as_str(c.get("claim") or c.get("text"))
        if text:
            claims.append(text)

    # Fallback for older brief shape that stores claims at top-level.
    if not claims:
        for c in (brief.get("claims") or []):
            if not isinstance(c, dict):
                continue
            text = _as_str(c.get("text") or c.get("claim"))
            if text:
                claims.append(text)

    return thesis, claims


def _weighted_score(
    brief: Dict[str, Any],
    w: Dict[str, Any],
    *,
    alignment: float,
    ref_brief: Optional[Dict[str, Any]] = None,
) -> float:
    ref_src = ref_brief if ref_brief is not None else brief
    parts = {
        "thesis_strength": _score_thesis_strength(brief),
        "claim_quality": _score_claim_quality(brief),
        "claim_alignment": alignment,
        "evidence_quality": _score_evidence_quality(brief),
        "critic_composure": _score_critic_composure(brief),
        "refinement_delta": _score_refinement_delta(ref_src),
    }
    total = 0.0
    for key, val in parts.items():
        wt = float(w.get(key, 0) or 0)
        total += wt * val
    return total, parts


def _critic_thesis_is_weak(brief: Dict[str, Any]) -> bool:
    ac = brief.get("argument_critic") if isinstance(brief.get("argument_critic"), dict) else {}
    d = ac.get("data") if isinstance(ac.get("data"), dict) else {}
    tr = d.get("thesis_review") if isinstance(d.get("thesis_review"), dict) else {}
    return _as_str(tr.get("status")).lower() == "weak"


def _gate_label(score: float, thresholds: Dict[str, float]) -> str:
    p = float(thresholds.get("pass_min", 0.72))
    r = float(thresholds.get("review_min", 0.52))
    if score >= p:
        return "PASS"
    if score >= r:
        return "REVIEW"
    return "FAIL"


def _clamp_gate_to_review(label: str) -> str:
    if label == "PASS":
        return "REVIEW"
    return label


def _alignment_debug_payload(thesis: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    n = int(detail.get("n", detail.get("num_claims", 0)))
    return {
        "score": round(float(detail.get("score", 0.0)), 4),
        "top_k_mean": round(float(detail.get("top_k_mean", 0.0)), 4),
        "support_ratio": round(float(detail.get("support_ratio", 0.0)), 4),
        "std_dev": round(float(detail.get("std_dev", 0.0)), 4),
        "low_support_count": int(detail.get("low_support_count", 0)),
        "num_claims": n,
        "k": int(detail.get("k", 0)),
        "n": n,
        "thesis": thesis,
    }


def _early_fail_ship(
    brief: Dict[str, Any],
    cfg: Dict[str, Any],
    w: Dict[str, Any],
    *,
    thesis: str,
    alignment: float,
    notes: List[str],
    detail: Dict[str, Any],
) -> Dict[str, Any]:
    """Shared shape for pre-weighted early FAIL (alignment / thesis / support ratio)."""
    notes = list(notes)
    claims_count = len([c for c in (brief.get("claims") or []) if isinstance(c, dict)])
    damp = 0.9 if claims_count < 3 else 1.0
    return {
        "config_version": cfg.get("version", 4),
        "components": {"claim_alignment": round(float(alignment), 4)},
        "components_pre_refine": {"claim_alignment": round(float(alignment), 4)},
        "weights_used": {k: round(float(v), 4) for k, v in (w or {}).items() if isinstance(v, (int, float))},
        "ship_score_weighted": round(float(alignment), 4),
        "ship_score": round(float(alignment), 4),
        "claim_count": claims_count,
        "claim_count_dampening": damp,
        "score_before_refine": round(float(alignment), 4),
        "score_after_refine": round(float(alignment), 4),
        "refinement_score_delta": 0.0,
        "refinement_helped": False,
        "ship_gate": "FAIL",
        "notes": notes,
        "alignment_debug": _alignment_debug_payload(thesis, detail),
    }


def assess_brief_intelligence_ship(
    brief: Dict[str, Any],
    *,
    alignment_detail_fn: Optional[Callable[..., Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Return a scorecard dict, or None when the brief has no spine pipeline artifacts.

    ``alignment_detail_fn`` defaults to ``semantic_alignment.claim_alignment_detail``. The
    ``intelligence_ship_gate`` wrapper passes ``sys.modules[__name__].claim_alignment_detail`` so
    tests can ``patch`` the aligner on that module.
    """
    if not isinstance(brief, dict) or not isinstance(brief.get("argument_spine"), dict):
        return None

    _align = alignment_detail_fn or claim_alignment_detail

    cfg = load_ship_gate_config()
    w = cfg.get("weights") or {}
    th = cfg.get("thresholds") if isinstance(cfg.get("thresholds"), dict) else {}

    thesis, claims = _extract_thesis_and_claims(brief)
    notes: List[str] = []
    claims_count = len([c for c in (brief.get("claims") or []) if isinstance(c, dict)])
    damp = 0.9 if claims_count < 3 else 1.0

    if _thesis_too_vague_to_evaluate(thesis):
        empty_detail = {
            "score": 0.0,
            "top_k_mean": 0.0,
            "support_ratio": 0.0,
            "std_dev": 0.0,
            "num_claims": 0,
            "k": 0,
            "n": 0,
        }
        return _early_fail_ship(
            brief,
            cfg,
            w,
            thesis=thesis,
            alignment=0.0,
            notes=["Thesis too vague to evaluate"],
            detail=empty_detail,
        )

    if _thesis_unstructured_list(thesis):
        empty_detail = {
            "score": 0.0,
            "top_k_mean": 0.0,
            "support_ratio": 0.0,
            "std_dev": 0.0,
            "num_claims": 0,
            "k": 0,
            "n": 0,
        }
        return _early_fail_ship(
            brief,
            cfg,
            w,
            thesis=thesis,
            alignment=0.0,
            notes=["Thesis is not a structured, testable claim"],
            detail=empty_detail,
        )

    align_detail = _align(thesis, claims, llm_call=_ollama_alignment_call)
    alignment = float(align_detail["score"])
    support_ratio = float(align_detail["support_ratio"])

    if alignment < 0.45:
        return _early_fail_ship(
            brief,
            cfg,
            w,
            thesis=thesis,
            alignment=alignment,
            notes=["Low semantic alignment between thesis and claims"],
            detail=align_detail,
        )

    if support_ratio < SUPPORT_RATIO_GATE_MIN:
        return _early_fail_ship(
            brief,
            cfg,
            w,
            thesis=thesis,
            alignment=alignment,
            notes=["Most claims do not support thesis"],
            detail=align_detail,
        )

    brief_pre = _brief_without_refiner_marks(brief)
    score_w_before, comps_before = _weighted_score(brief, w, alignment=alignment, ref_brief=brief_pre)
    score_w_after, comps_after = _weighted_score(brief, w, alignment=alignment, ref_brief=brief)

    score_before = round(score_w_before * damp, 4)
    score_after = round(score_w_after * damp, 4)

    label = _gate_label(score_w_after * damp, th)
    if _critic_thesis_is_weak(brief):
        label = "FAIL"
        notes.append("Critic flagged weak thesis — ship_gate forced to FAIL (overrides score band).")
    else:
        if alignment < 0.65:
            label = _clamp_gate_to_review(label)
            notes.append("Semantic alignment below PASS confidence band — escalated to REVIEW.")
        # Borderline support share (0.40–0.64): not a hard fail (≥0.4 cleared the gate) but not strong enough
        # for confident PASS—clamp toward REVIEW. Same for support_ratio < 0.65 in general.
        if support_ratio < SUPPORT_RATIO_REVIEW_MAX:
            label = _clamp_gate_to_review(label)
            notes.append("Support coverage below PASS confidence band — escalated to REVIEW.")
        if label == "FAIL":
            notes.append("Weighted intelligence score fell below review threshold — external send is risky.")
        elif label == "REVIEW" and "escalated to REVIEW" not in " ".join(notes):
            notes.append("Intelligence score is borderline — human review recommended before distribution.")

    refinement_helped = (score_w_after - score_w_before) > 0.01

    w_used = w if isinstance(w, dict) else {}
    return {
        "config_version": cfg.get("version", 4),
        "components": {k: round(float(v), 4) for k, v in comps_after.items()},
        "components_pre_refine": {k: round(float(v), 4) for k, v in comps_before.items()},
        "weights_used": {k: round(float(v), 4) for k, v in w_used.items() if isinstance(v, (int, float))},
        "ship_score_weighted": round(score_w_after, 4),
        "ship_score": score_after,
        "claim_count": claims_count,
        "claim_count_dampening": damp,
        "score_before_refine": score_before,
        "score_after_refine": score_after,
        "refinement_score_delta": round(score_after - score_before, 4),
        "refinement_helped": refinement_helped,
        "ship_gate": label,
        "notes": notes,
        "alignment_debug": _alignment_debug_payload(thesis, align_detail),
    }


def run_episode(transcript: str, _eval_mode: bool = False) -> Dict[str, Any]:
    """Backward-compatible alias for ``run``; ``_eval_mode`` reserved."""
    return run(transcript)


# === Public re-exports (subset of this module) ================================
__all__ = [
    "claim_alignment_detail",
    "assess_brief_intelligence_ship",
    "load_ship_gate_config",
    "SHIP_GATE_DEFAULT",
    "THESIS_MIN_WORDS",
    "SUPPORT_RATIO_GATE_MIN",
    "SUPPORT_RATIO_REVIEW_MAX",
    "JUDGMENT_ALIGNMENT_FAIL",
    "JUDGMENT_SCORE_REVIEW",
    "empty_brief",
    "run",
    "run_spine_first",
    "run_critic",
    "run_refiner",
    "semantic_alignment",
    "ship_decision",
    "run_episode",
    "run_eval",
    "EVAL_SET",
    "EVAL_SMOKE",
    "run_brief_smoke_eval",
    "main",
]


# --- built-in eval (optional); same smoke briefs as eval_ship_gate_batch ----

EVAL_SMOKE: list[dict[str, Any]] = [
    {
        "id": "smoke_ok",
        "label": None,
        "brief": {
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
        },
    },
    {
        "id": "smoke_tag",
        "label": None,
        "brief": {
            "argument_spine": {
                "data": {
                    "thesis": "A; B; C; D; E; F; G; H",
                    "claims": [{"claim": "Some filler claim text with enough length for alignment scoring only."}],
                }
            },
            "claims": [],
        },
    },
]


def run_brief_smoke_eval() -> list[dict[str, Any]]:
    """Synthetic **brief** briefs (EVAL_SMOKE) through ``assess_brief_intelligence_ship`` (Ollama alignment)."""
    out: list[dict[str, Any]] = []
    for row in EVAL_SMOKE:
        r = assess_brief_intelligence_ship(row["brief"])
        out.append(
            {
                "id": row["id"],
                "label": row.get("label"),
                "ship_gate": (r or {}).get("ship_gate") if r else None,
                "ship_score": (r or {}).get("ship_score") if r else None,
            }
        )
    return out


def _cli() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="SoapBoxx single-file intelligence core (eval / smoke).")
    ap.add_argument("--smoke", action="store_true", help="Run EVAL_SMOKE briefs through assess_brief_intelligence_ship")
    ap.add_argument("--eval", dest="do_eval", action="store_true", help="Same as --smoke (alias)")
    ap.add_argument(
        "--judgment",
        action="store_true",
        help="Run EVAL_SET transcripts through the embedded judgment pipeline (run_eval)",
    )
    args = ap.parse_args()
    if not args.smoke and not args.do_eval and not args.judgment:
        ap.print_help()
        return 0
    rows: list[dict[str, Any]] = []
    if args.judgment:
        rows.extend(run_eval())
    if args.smoke or args.do_eval:
        rows.extend(run_brief_smoke_eval())
    for row in rows:
        print(json.dumps(row, ensure_ascii=True))
    return 0


def main() -> int:
    return _cli()


if __name__ == "__main__":
    raise SystemExit(main())
