"""
Spine-first episode brief: interpret → decide → construct → extract, then critic, then refiner.

Pass 1 builds a falsifiable thesis and rewritten claims with evidence.
Pass 2 pressure-tests pass 1. Pass 3 repairs the argument using only pass 1 + pass 2 JSON (no transcript).
Results merge into the legacy v2 brief dict with ``argument_spine``, ``argument_critic``, ``argument_refined``.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Dict, List, Optional, Tuple

_TOKEN_STOP = frozenset(
    {
        "the",
        "and",
        "that",
        "this",
        "with",
        "from",
        "for",
        "are",
        "was",
        "were",
        "has",
        "have",
        "but",
        "not",
        "you",
        "they",
        "their",
        "its",
        "out",
        "when",
        "how",
        "what",
        "who",
        "into",
        "than",
        "then",
        "them",
        "about",
    }
)

_SPINE_OUTPUT_SCHEMA_SNIPPET = """
{
  "data": {
    "thesis": "one causal sentence OR null",
    "claims": [
      {
        "id": "c1",
        "claim": "rewritten assertion",
        "evidence": "short quote or paraphrase",
        "timestamp": "approximate timestamp or empty string"
      }
    ]
  },
  "metadata": {
    "quality": {
      "thesis_valid": true,
      "claims_count": 0,
      "argument_coherence": "strong"
    },
    "warnings": []
  }
}
""".strip()

SPINE_FIRST_SYSTEM_PROMPT = f"""You are an episode intelligence analyst, not a summarizer.

Your job is to THINK first, then extract.

You MUST return ONLY valid JSON.

=====================================
STRICT OUTPUT CONTRACT
=====================================
- Output must be a single JSON object
- Top-level keys MUST be exactly:
  1. "data"
  2. "metadata"

If you cannot comply, return:
{{"data": {{}}, "metadata": {{"error": "failed_to_generate"}}}}

No markdown. No commentary. JSON only.

=====================================
CORE RULE: NO TRANSCRIPT RECYCLING
=====================================
Do NOT copy sentences just because they exist.

Only include material that contributes to a coherent argument.

=====================================
STEP 1 — BUILD THE SPINE (THINKING STEP)
=====================================

From the transcript, construct ONE central thesis.

STRICT REQUIREMENTS:
- Must be ONE sentence
- Must include a causal relationship (X leads to Y / X shapes Y / X creates Y)
- Must be falsifiable (someone could reasonably disagree)
- Must NOT be a list of topics
- Must NOT be vague or slogan-like

If you cannot form a strong thesis:
- Set "thesis" to null
- Append "weak_thesis" to metadata.warnings (metadata.warnings must be a JSON array of strings)

=====================================
STEP 2 — SELECT CLAIMS (FILTER HARD)
=====================================

Select 3–6 claims that:

- Directly SUPPORT or CHALLENGE the thesis
- Contain a clear assertion (not a question, intro, or filler)
- Are NOT ads, sponsorships, or promotions
- Are NOT host setup, greetings, or transitions
- Are NOT vague or generic statements

REJECT:
- Sponsor reads
- "Welcome back" type lines
- Questions
- Topic labels
- Repetition

Each claim must pass:
- "If removed, the argument becomes weaker"

=====================================
STEP 3 — REWRITE CLAIMS (DO NOT COPY)
=====================================

For each selected claim:

- Rewrite it into a clear, concise assertion
- Preserve meaning, improve clarity
- Remove filler language
- Keep it grounded in what was actually said

=====================================
STEP 4 — ATTACH EVIDENCE
=====================================

For each claim, attach:

- A short supporting quote OR paraphrased evidence
- A timestamp (approximate is fine)

Evidence must:
- Be relevant to the claim
- Not be random transcript filler

=====================================
STEP 5 — VALIDATE ARGUMENT QUALITY
=====================================

Evaluate:

- Does each claim connect back to the thesis?
- Is there a logical flow (not random points)?
- Is the argument understandable in isolation?

If weak:
- Append "low_argument_coherence" to metadata.warnings

=====================================
OUTPUT FORMAT
=====================================

Use this shape exactly (argument_coherence must be one of: strong, medium, weak):

{_SPINE_OUTPUT_SCHEMA_SNIPPET}

metadata.quality.argument_coherence must be the string "strong", "medium", or "weak" only.

=====================================
FINAL RULE
=====================================

If the transcript is noisy, unclear, or low-signal:

- Reduce the number of claims
- Do NOT fabricate structure
- Prefer fewer high-quality claims over many weak ones

Your goal is NOT completeness.

Your goal is:
→ a clear, defensible argument a human could repeat.
"""

_CRITIC_OUTPUT_SCHEMA_SNIPPET = """
{
  "data": {
    "thesis_review": {
      "status": "strong",
      "issues": [],
      "rewrite": ""
    },
    "claims_review": [
      {
        "id": "c1",
        "status": "strong",
        "issue": "",
        "suggestion": ""
      }
    ],
    "logic_gaps": [],
    "counterarguments": [],
    "evidence_review": {
      "overall": "strong",
      "issues": []
    }
  },
  "metadata": {
    "critic_mode": "hostile",
    "confidence": "high"
  }
}
""".strip()

CRITIC_SYSTEM_PROMPT = f"""You are a hostile analyst reviewing an episode intelligence brief.

Your job is to find weaknesses, not to agree.

You MUST return ONLY valid JSON.

=====================================
STRICT OUTPUT CONTRACT
=====================================
- Output must be a single JSON object
- Top-level keys MUST be exactly:
  1. "data"
  2. "metadata"

If you cannot comply, return:
{{"data": {{}}, "metadata": {{"error": "failed_to_generate"}}}}

No markdown. No commentary. JSON only.

=====================================
INPUT
=====================================
You will receive:
- A thesis
- A list of claims with evidence

=====================================
CORE RULE
=====================================
Assume the argument is flawed until proven otherwise.

Do NOT praise.
Do NOT summarize.
Do NOT repeat content unless necessary to critique it.

=====================================
STEP 1 — ATTACK THE THESIS
=====================================

Evaluate the thesis on:

1. Specificity
   - Is it vague or generic?

2. Causality
   - Does it actually show X → Y, or just association?

3. Falsifiability
   - Could someone realistically prove this wrong?

4. Overreach
   - Does it claim more than the evidence supports?

If weak:
- Explain why
- Provide a tighter rewritten version

=====================================
STEP 2 — ATTACK EACH CLAIM
=====================================

For each claim:

Check:

- Does it directly support the thesis?
- Is it actually an assertion, or just a statement?
- Is it too vague or obvious?
- Is it dependent on missing context?
- Is it just a restatement of the transcript without insight?

Mark each claim as:
- "strong"
- "weak"
- "irrelevant"

For weak/irrelevant claims:
- Explain the flaw
- Suggest a stronger version OR recommend removal

=====================================
STEP 3 — FIND LOGIC GAPS
=====================================

Identify:

- Missing steps in reasoning (A → C with no B)
- Assumptions not stated
- Leaps from anecdote → general conclusion

List them clearly.

=====================================
STEP 4 — COUNTERARGUMENTS
=====================================

Generate 1–3 strong counterarguments that:

- Directly challenge the thesis
- Would be raised by a smart, skeptical listener

=====================================
STEP 5 — EVIDENCE STRESS TEST
=====================================

Evaluate:

- Is the evidence actually supporting the claims?
- Is it anecdotal vs. generalizable?
- Are there missing sources or verification gaps?

Flag in evidence_review.issues using phrases like:
- weak_evidence
- anecdotal_only
- unsupported_claim

=====================================
OUTPUT FORMAT
=====================================

Use this shape (thesis_review.status and evidence_review.overall: strong, weak, or mixed for overall):

{_CRITIC_OUTPUT_SCHEMA_SNIPPET}

metadata.confidence must be one of: high, medium, low.

=====================================
FINAL RULE
=====================================

If the argument is weak:

- Say it clearly
- Do NOT soften language
- Do NOT invent strength where none exists

Your role is to pressure-test, not to protect.
"""


_REFINER_OUTPUT_SCHEMA_SNIPPET = """
{
  "data": {
    "thesis": "one sentence OR null",
    "claims": [
      {
        "id": "c1",
        "claim": "repaired assertion",
        "evidence": "quote or paraphrase",
        "timestamp": ""
      }
    ],
    "counterpoints": [
      {
        "point": "skeptical challenge",
        "response": "rebuttal if transcript supports; else empty string"
      }
    ]
  },
  "metadata": {
    "refinement": {
      "thesis_changed": true,
      "claims_reduced": true,
      "issues_remaining": []
    },
    "warnings": []
  }
}
""".strip()

REFINER_SYSTEM_PROMPT = f"""You are an intelligence refiner.

You are given:
1) An initial episode brief (thesis + claims)
2) A hostile critique identifying weaknesses

Your job is to REPAIR the argument using the critique.

You MUST return ONLY valid JSON.

=====================================
STRICT OUTPUT CONTRACT
=====================================
- Output must be a single JSON object
- Top-level keys MUST be exactly:
  1. "data"
  2. "metadata"

If you cannot comply, return:
{{"data": {{}}, "metadata": {{"error": "failed_to_generate"}}}}

No markdown. No commentary. JSON only.

=====================================
CORE RULES
=====================================

- Do NOT ignore the critic
- Do NOT keep weak structure for completeness
- Do NOT invent facts not grounded in the original transcript
- Prefer removing weak elements over preserving them

Goal:
→ A tighter, defensible argument

=====================================
STEP 1 — FIX THE THESIS
=====================================

If thesis_review.status = "weak":

- Rewrite the thesis to:
  - include a clear causal relationship
  - be specific and falsifiable
  - align with available claims and evidence

If no strong thesis can be formed:
- Set thesis = null
- Append "no_defensible_thesis" to metadata.warnings (array of strings)

=====================================
STEP 2 — REBUILD CLAIM SET
=====================================

Using claims_review:

- REMOVE claims marked "irrelevant"
- FIX claims marked "weak" using suggestions where possible
- KEEP only claims that clearly support the revised thesis

Rules:
- Final claim count: 2–5 (strict)
- Each claim must directly support the thesis
- Rewrite for clarity (no transcript noise)

=====================================
STEP 3 — CLOSE LOGIC GAPS
=====================================

Using logic_gaps:

- Add or refine claims so that reasoning becomes:
  A → B → C (not A → C)

If gaps cannot be resolved:
- Append "incomplete_reasoning" to metadata.warnings

=====================================
STEP 4 — INTEGRATE COUNTERARGUMENTS
=====================================

From counterarguments:

- Select 1–2 strongest
- Fill data.counterpoints:
  - clearly stated
  - optionally rebutted if supported by transcript

=====================================
STEP 5 — STRENGTHEN EVIDENCE
=====================================

From evidence_review:

- Remove claims with unsupported or irrelevant evidence
- Prefer fewer claims with stronger grounding
- Ensure each claim includes:
  - a clean supporting quote or paraphrase
  - a timestamp

If evidence is weak overall:
- Append "weak_evidence_base" to metadata.warnings

=====================================
OUTPUT FORMAT
=====================================

Use this shape (ids may be c1, c2, … or a1, a2 — stay consistent):

{_REFINER_OUTPUT_SCHEMA_SNIPPET}

metadata.refinement must be an object with thesis_changed and claims_reduced booleans and issues_remaining string array.

=====================================
FINAL RULE
=====================================

If the argument cannot be made strong:

- Output a minimal structure
- Clearly signal failure in metadata.warnings
- Do NOT fabricate coherence

A weak but honest output is better than a polished but false one.
"""


def build_spine_first_user_block(
    transcript_excerpt: str,
    metadata: Dict[str, str],
    *,
    correction_feedback: str = "",
) -> str:
    meta = dict(metadata or {})
    parts = [
        "GROUNDING: Episode identity is in METADATA. The thesis and claims must be consistent with "
        "title, creator, and genre. Do not impose religious framing unless the show is clearly faith-oriented.\n",
        "METADATA:\n",
        json.dumps(meta, ensure_ascii=False, indent=2),
        "\n\nTRANSCRIPT:\n",
        transcript_excerpt,
    ]
    if correction_feedback.strip():
        parts.extend(
            [
                "\n\nVALIDATION / CORRECTION (address every item; then output valid JSON only):\n",
                correction_feedback.strip(),
            ]
        )
    return "".join(parts)


def build_critic_user_payload(pass1_root: Dict[str, Any]) -> str:
    """Serialize pass-1 JSON for the critic model (input context)."""
    return (
        "INPUT (episode intelligence pass 1 — critique this, do not replace it wholesale):\n\n"
        + json.dumps(pass1_root, ensure_ascii=False, indent=2)[:100_000]
    )


def build_refiner_user_payload(pass1_root: Dict[str, Any], pass2_root: Optional[Dict[str, Any]]) -> str:
    """
    Refiner input: pass 1 + pass 2 only (no transcript) so the model repairs from reasoning, not re-summarization.
    """
    p2 = pass2_root if isinstance(pass2_root, dict) else {"data": {}, "metadata": {"skipped": True}}
    block = {
        "pass_1_initial_brief": pass1_root,
        "pass_2_hostile_critique": p2,
    }
    return (
        "INPUT (repair using ONLY the JSON below — no transcript is provided; do not invent new facts):\n\n"
        + json.dumps(block, ensure_ascii=False, indent=2)[:120_000]
    )


def _as_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


def _norm_claim_id(raw: Any, index_one_based: int) -> str:
    s = _as_str(raw).lower()
    m = re.match(r"^c(\d+)$", s)
    if m:
        return f"c{int(m.group(1))}"
    m = re.match(r"^a(\d+)$", s)
    if m:
        return f"c{int(m.group(1))}"
    return f"c{index_one_based}"


def _content_tokens(s: str) -> set[str]:
    toks = re.findall(r"[a-z0-9']{3,}", (s or "").lower())
    return {t for t in toks if t not in _TOKEN_STOP}


def shares_keywords(original: str, refined: str, *, min_overlap: int = 2, min_jaccard: float = 0.08) -> bool:
    a = _content_tokens(original)
    b = _content_tokens(refined)
    if not a or not b:
        return False
    inter = len(a & b)
    if inter >= min_overlap:
        return True
    union = len(a | b)
    return (inter / max(1, union)) >= min_jaccard


def is_semantic_drift(original: str, refined: str) -> bool:
    """Heuristic: refiner likely invented a new idea vs. tightened the same one."""
    o = (original or "").strip()
    r = (refined or "").strip()
    if not o or not r:
        return True
    if len(r) > 2 * max(len(o), 12):
        return True
    if not shares_keywords(o, r):
        return True
    return False


def should_promote_refined(pass2: Optional[Dict[str, Any]], pass3: Dict[str, Any]) -> bool:
    """
    Only allow refiner to change top-level brief fields when the critic flagged a weak thesis,
    the refiner reports no open issues_remaining, and it kept at least two claims.
    """
    d2 = dict((pass2 or {}).get("data") or {})
    tr = d2.get("thesis_review") if isinstance(d2.get("thesis_review"), dict) else {}
    if _as_str(tr.get("status")).lower() != "weak":
        return False
    d3 = dict(pass3.get("data") or {})
    m3 = dict(pass3.get("metadata") or {})
    refn = m3.get("refinement") if isinstance(m3.get("refinement"), dict) else {}
    issues = refn.get("issues_remaining")
    if isinstance(issues, list) and any(_as_str(x) for x in issues):
        return False
    claims = d3.get("claims")
    if not isinstance(claims, list) or len(claims) < 2:
        return False
    return True


def _apply_refiner_to_base_claims(
    base_claims: List[Dict[str, Any]],
    pass3: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Keep pass-1 canonical ``text``; attach ``refined_text`` only when aligned with pass-3 and not drifting.
    Returns (claims, drift_warning_tokens).
    """
    drift_notes: List[str] = []
    d3 = dict(pass3.get("data") or {})
    p3_by_id: Dict[str, Dict[str, Any]] = {}
    for j, rc in enumerate(d3.get("claims") or []):
        if not isinstance(rc, dict):
            continue
        cid = _norm_claim_id(rc.get("id"), j + 1)
        p3_by_id[cid] = rc

    out: List[Dict[str, Any]] = []
    for i, bc in enumerate(base_claims):
        if not isinstance(bc, dict):
            continue
        merged = dict(bc)
        merged.pop("refined_text", None)
        merged.pop("refinement_changed", None)
        cid = _norm_claim_id(bc.get("id"), i + 1)
        merged["id"] = cid
        p3c = p3_by_id.get(cid)
        if p3c:
            orig = _as_str(merged.get("text"))
            refined = _as_str(p3c.get("claim") or p3c.get("text"))
            if refined and len(refined) >= 8:
                if is_semantic_drift(orig, refined):
                    drift_notes.append(f"refinement_drift:{cid}")
                else:
                    merged["refined_text"] = refined[:520]
                    merged["refinement_changed"] = orig.strip().lower() != refined.strip().lower()
                    ev = _as_str(p3c.get("evidence"))
                    ts = _as_str(p3c.get("timestamp"))
                    if ev:
                        tail = " — ".join(x for x in (ev, f"@{ts}" if ts else "") if x)
                        cur = _as_str(merged.get("why_it_matters"))
                        merged["why_it_matters"] = (tail + (" — " + cur if cur else ""))[:500]
        out.append(merged)
    return out, drift_notes


def validate_spine_pass1(obj: Any) -> Tuple[bool, str]:
    """Structural checks before mapping to v2 (strict enough to retry)."""
    if not isinstance(obj, dict):
        return False, "root is not an object"
    if set(obj.keys()) != {"data", "metadata"}:
        return False, 'top-level keys must be exactly {"data","metadata"}'
    d = obj.get("data")
    if not isinstance(d, dict):
        return False, '"data" must be an object'
    claims = d.get("claims")
    if not isinstance(claims, list) or len(claims) < 1:
        return False, "data.claims must be a non-empty array"
    good = 0
    for i, c in enumerate(claims[:8]):
        if not isinstance(c, dict):
            return False, f"claims[{i}] must be an object"
        text = _as_str(c.get("claim") or c.get("text"))
        if len(text) >= 18:
            good += 1
    if good < 1:
        return False, "at least one claim must have claim/text >= 18 characters"
    md = obj.get("metadata")
    if not isinstance(md, dict):
        return False, '"metadata" must be an object'
    return True, ""


def validate_refiner_pass3(obj: Any) -> Tuple[bool, str]:
    """Refiner must be a valid envelope; empty data with hard error is unusable."""
    if not isinstance(obj, dict):
        return False, "root is not an object"
    if set(obj.keys()) != {"data", "metadata"}:
        return False, 'top-level keys must be exactly {"data","metadata"}'
    d = obj.get("data")
    if not isinstance(d, dict):
        return False, '"data" must be an object'
    md = obj.get("metadata")
    if not isinstance(md, dict):
        return False, '"metadata" must be an object'
    err = _as_str(md.get("error")).lower()
    if err == "failed_to_generate" and not d:
        return False, "refiner returned failed_to_generate with empty data"
    claims = d.get("claims")
    if claims is not None and not isinstance(claims, list):
        return False, "data.claims must be an array when present"
    cps = d.get("counterpoints")
    if cps is not None and not isinstance(cps, list):
        return False, "data.counterpoints must be an array when present"
    return True, ""


def _critic_claim_row(
    critic_data: Dict[str, Any], claim_id: str
) -> Optional[Dict[str, Any]]:
    for row in critic_data.get("claims_review") or []:
        if not isinstance(row, dict):
            continue
        rid = _as_str(row.get("id")).lower() or None
        if rid == claim_id.lower():
            return row
    return None


def map_spine_critic_to_v2_brief(
    pass1: Dict[str, Any],
    pass2: Optional[Dict[str, Any]],
    metadata: Dict[str, str],
) -> Dict[str, Any]:
    """
    Merge pass-1 spine + optional pass-2 critic into the v2 brief dict.

    Preserves generation (pass 1) in ``argument_spine`` and critique (pass 2) in ``argument_critic``.
    """
    meta = dict(metadata or {})
    d1 = dict(pass1.get("data") or {})
    thesis = d1.get("thesis")
    thesis_s = _as_str(thesis) if thesis is not None else ""
    raw_claims = [c for c in (d1.get("claims") or []) if isinstance(c, dict)]

    d2: Dict[str, Any] = {}
    if isinstance(pass2, dict):
        d2 = dict(pass2.get("data") or {})

    claims_v2: List[Dict[str, Any]] = []
    for i, rc in enumerate(raw_claims[:6], start=1):
        cid = _norm_claim_id(rc.get("id"), i)
        text = _as_str(rc.get("claim") or rc.get("text"))
        if len(text) < 12:
            continue
        ev = _as_str(rc.get("evidence"))
        ts = _as_str(rc.get("timestamp"))
        why_parts = [x for x in (ev, f"@{ts}" if ts else "") if x]
        why = " — ".join(why_parts) if why_parts else "Grounded in episode spine extraction."
        why = why[:500]

        crow = _critic_claim_row(d2, cid) if d2 else None
        status = _as_str(crow.get("status")).lower() if crow else ""
        counter = _as_str(crow.get("issue")) if crow else ""
        if len(counter) > 400:
            counter = counter[:400]
        suggestion = _as_str(crow.get("suggestion")) if crow else ""
        if suggestion and len(suggestion) < 500:
            counter = (counter + " — Suggestion: " + suggestion)[:500] if counter else suggestion[:500]

        conf = "medium"
        if status == "strong":
            conf = "high"
        elif status in ("weak", "irrelevant"):
            conf = "low"

        low = text.lower()
        claim_type = "interpretation"
        next_action = "challenge"
        if re.search(r"\b(\d+|percent|data|study|evidence|record|document)\b", low):
            claim_type = "fact"
            next_action = "verify"

        claims_v2.append(
            {
                "id": cid,
                "text": text[:520],
                "claim_type": claim_type,
                "confidence": conf,
                "why_it_matters": why[:500],
                "counter_angle": counter,
                "next_action": next_action,
            }
        )

    if not claims_v2 and thesis_s:
        claims_v2.append(
            {
                "id": "c1",
                "text": thesis_s[:520],
                "claim_type": "interpretation",
                "confidence": "medium",
                "why_it_matters": (thesis_s[:240] + "…") if len(thesis_s) > 240 else thesis_s,
                "counter_angle": "",
                "next_action": "verify",
            }
        )

    primary = thesis_s[:500] if thesis_s else ""
    if not primary and claims_v2:
        primary = claims_v2[0]["text"][:500]

    tr = d2.get("thesis_review") if isinstance(d2.get("thesis_review"), dict) else {}
    why_core = thesis_s if thesis_s else (claims_v2[0]["text"] if claims_v2 else "")
    why = why_core[:900] if why_core else "Episode argument spine from transcript."
    if len(why.strip()) < 20:
        why = (why + " Distilled from transcript spine.").strip()[:900]
    rewrite = _as_str(tr.get("rewrite"))
    if rewrite and len(why) < 40:
        why = rewrite[:900]

    narrative: List[str] = []
    if thesis_s:
        line = thesis_s[:500]
        if len(line.strip()) < 18:
            line = f"Central thesis (spine): {thesis_s}".strip()[:500]
        narrative.append(line)
    for c in claims_v2[:3]:
        narrative.append(c["text"][:400])
    while len(narrative) < 1 and claims_v2:
        narrative.append(claims_v2[0]["text"][:500])
    if len(narrative) < 1:
        narrative.append("Episode did not yield a compact spine; treat downstream output as low confidence.")

    supported: List[str] = []
    weak_ev: List[str] = []
    proof_need: List[str] = []

    evr = d2.get("evidence_review") if isinstance(d2.get("evidence_review"), dict) else {}
    for x in evr.get("issues") or []:
        sx = _as_str(x)
        if sx:
            weak_ev.append(sx)
    for x in d2.get("logic_gaps") or []:
        sx = _as_str(x)
        if sx:
            weak_ev.append(f"Logic gap: {sx}")
    for x in d2.get("counterarguments") or []:
        sx = _as_str(x)
        if sx:
            proof_need.append(sx)
    if claims_v2:
        supported.append(f"Spine claims recorded: {', '.join(c['id'] for c in claims_v2)}")

    title = _as_str(meta.get("title")) or "Untitled episode"
    arg_topic = (thesis_s or primary or title)[:500]
    snap = {
        "title": title[:300],
        "creator": _as_str(meta.get("creator"))[:200],
        "genre": _as_str(meta.get("genre"))[:200],
        "primary_topic": primary or title[:500],
        "argument_topic": arg_topic,
        "why_it_matters": why[:900],
    }

    host_qs: List[str] = [
        "What is the strongest counterargument to the thesis?",
        "Which claim would break first under fact-checking?",
        "What proof would convert this from interpretation to verified claim?",
    ]
    caps = d2.get("counterarguments") or []
    if isinstance(caps, list):
        for ca in caps[:3]:
            s = _as_str(ca)
            if s and len(host_qs) < 5:
                host_qs.insert(0, f"Skeptical listener asks: {s[:220]}")

    clips: List[str] = []
    for c in claims_v2[:4]:
        raw_ts = ""
        for j, raw in enumerate(raw_claims):
            if _norm_claim_id(raw.get("id"), j + 1) == c["id"]:
                raw_ts = _as_str(raw.get("timestamp"))
                break
        ts_bit = f"{raw_ts} — " if raw_ts else ""
        clips.append(ts_bit + c["text"][:320])

    risk_note = ""
    if _as_str(tr.get("status")).lower() == "weak":
        risk_note = "Thesis flagged weak by critic review."

    pm = {
        "segment_to_run": {
            "name": "Argument spine",
            "goal": (thesis_s[:200] if thesis_s else (claims_v2[0]["text"][:200] if claims_v2 else "")),
        },
        "host_questions": host_qs[:3],
        "clip_candidates": clips[:6] or ([narrative[0][:280]] if narrative else []),
        "risk_note": risk_note,
    }

    guests: List[Dict[str, Any]] = []
    if claims_v2:
        guests = [
            {
                "name": "Subject-matter skeptic",
                "title": "Analyst / researcher",
                "angle": "Pressure-tests the spine claims against evidence and missing context.",
                "maps_to_claim_id": claims_v2[0]["id"],
            }
        ]

    plan = [
        {"day": "Day 1", "task": "Compare thesis to critic rewrite; decide which framing to ship."},
        {"day": "Day 2", "task": "Cut or repair claims marked weak/irrelevant in critic pass."},
        {"day": "Day 3-7", "task": "Collect proof for the top counterargument; update brief if evidence shifts."},
    ]

    m1 = dict(pass1.get("metadata") or {})
    m2 = dict((pass2 or {}).get("metadata") or {})

    out: Dict[str, Any] = {
        "episode_snapshot": snap,
        "narrative": narrative[:3],
        "claims": claims_v2[:5],
        "evidence_gaps": {
            "supported": supported[:12],
            "weak_or_unsupported": weak_ev[:16],
            "proof_needed": proof_need[:12],
        },
        "production_moves": pm,
        "guests": guests,
        "action_plan_7d": plan,
        "argument_spine": {
            "thesis": thesis if thesis is not None else None,
            "claims": raw_claims[:8],
            "metadata": m1,
        },
        "argument_critic": {"data": d2, "metadata": m2} if d2 or m2 else {},
    }
    return out


def map_spine_critic_refined_to_v2_brief(
    pass1: Dict[str, Any],
    pass2: Optional[Dict[str, Any]],
    pass3: Dict[str, Any],
    metadata: Dict[str, str],
) -> Dict[str, Any]:
    """
    Attach pass-3 refiner JSON and optionally **promote** refinements into the v2 brief.

    By default (promotion gate false), pass-1 text remains the claim source of truth; refiner is advisory
    only (see ``argument_refined``). When promoted, ``refined_text`` is added per claim only if drift
    checks pass; ``primary_topic`` stays title-aligned from pass 1+2; ``argument_topic`` tracks the
    refined thesis line for intelligence consumers.
    """
    base = map_spine_critic_to_v2_brief(pass1, pass2, metadata)
    d1 = dict(pass1.get("data") or {})
    d3 = dict(pass3.get("data") or {})
    m3 = copy.deepcopy(dict(pass3.get("metadata") or {}))
    d2: Dict[str, Any] = {}
    if isinstance(pass2, dict):
        d2 = dict(pass2.get("data") or {})

    raw_refined = [c for c in (d3.get("claims") or []) if isinstance(c, dict)]
    if not raw_refined:
        rf = m3.setdefault("refinement", {})
        if not isinstance(rf, dict):
            m3["refinement"] = {"status": "failed", "reason": "no_defensible_claims"}
        else:
            rf["status"] = "failed"
            rf["reason"] = "no_defensible_claims"

    thesis_p1 = _as_str(d1.get("thesis")) if d1.get("thesis") is not None else ""
    thesis_r3 = _as_str(d3.get("thesis")) if d3.get("thesis") is not None else ""

    promote = should_promote_refined(pass2, {"data": d3, "metadata": m3})

    snap = dict(base.get("episode_snapshot") or {})
    if promote and thesis_r3:
        snap["argument_topic"] = thesis_r3[:500]
    else:
        snap["argument_topic"] = (thesis_p1 or _as_str(snap.get("argument_topic")))[:500]

    supported = list((base.get("evidence_gaps") or {}).get("supported") or [])
    weak_ev = list((base.get("evidence_gaps") or {}).get("weak_or_unsupported") or [])
    proof_need = list((base.get("evidence_gaps") or {}).get("proof_needed") or [])

    if promote:
        merged_claims, drift_notes = _apply_refiner_to_base_claims(list(base.get("claims") or []), pass3)
        for dn in drift_notes:
            weak_ev.append(f"Refiner drift rejected ({dn}).")
        if merged_claims:
            base["claims"] = merged_claims[:5]

        narrative: List[str] = []
        head = thesis_r3 or thesis_p1
        if head:
            line = head[:500]
            if len(line.strip()) < 18:
                line = f"Argument topic (refined): {head}".strip()[:500]
            narrative.append(line)
        for c in (base.get("claims") or [])[:2]:
            narrative.append(_as_str(c.get("text"))[:400])
        if len(narrative) < 1 and base.get("claims"):
            narrative.append(_as_str(base["claims"][0].get("text"))[:500])
        if len(narrative) < 1:
            narrative.append(
                "Episode argument retained from spine; refiner did not add headline bullets."
            )
        base["narrative"] = narrative[:3]

        if thesis_r3 and len(thesis_r3.strip()) >= 20:
            snap["why_it_matters"] = thesis_r3[:900]
        elif len(_as_str(snap.get("why_it_matters")).strip()) < 20:
            snap["why_it_matters"] = (thesis_p1 or _as_str(snap.get("why_it_matters")))[:900]

        refn = m3.get("refinement") if isinstance(m3.get("refinement"), dict) else {}
        for x in refn.get("issues_remaining") or []:
            sx = _as_str(x)
            if sx:
                weak_ev.append(f"Refiner: {sx}")

        for cp in d3.get("counterpoints") or []:
            if not isinstance(cp, dict):
                continue
            pt = _as_str(cp.get("point"))
            rsp = _as_str(cp.get("response"))
            if not pt:
                continue
            if rsp:
                supported.append(f"Counterpoint: {pt[:300]} — Response: {rsp[:300]}")
            else:
                proof_need.append(pt[:400])

        pm = dict(base.get("production_moves") or {})
        seg = dict(pm.get("segment_to_run") or {})
        seg["name"] = "Refined argument (promoted)"
        if thesis_r3:
            seg["goal"] = thesis_r3[:200]
        elif base.get("claims"):
            seg["goal"] = _as_str(base["claims"][0].get("text"))[:200]
        else:
            seg["goal"] = _as_str(seg.get("goal"))[:200]
        pm["segment_to_run"] = seg
        hq = list(pm.get("host_questions") or [])
        for cp in (d3.get("counterpoints") or [])[:2]:
            if isinstance(cp, dict) and _as_str(cp.get("point")):
                hq.insert(0, f"Stress-test: {_as_str(cp.get('point'))[:200]}")
        pm["host_questions"] = hq[:3]

        raw_p3_list = [c for c in (d3.get("claims") or []) if isinstance(c, dict)]
        clips: List[str] = []
        for c in base["claims"][:4]:
            cid = _as_str(c.get("id")).lower()
            raw_ts = ""
            for j, raw in enumerate(raw_p3_list):
                if _norm_claim_id(raw.get("id"), j + 1) == cid:
                    raw_ts = _as_str(raw.get("timestamp"))
                    break
            ts_bit = f"{raw_ts} — " if raw_ts else ""
            clips.append(ts_bit + _as_str(c.get("text"))[:320])
        pm["clip_candidates"] = clips[:6] or pm.get("clip_candidates") or []
        base["production_moves"] = pm

        ids = [str(c.get("id")) for c in (base.get("claims") or []) if c.get("id")]
        supported.append("Refiner promotion applied: refined_text merged where drift-safe. IDs: " + ", ".join(ids[:5]))

        base["action_plan_7d"] = [
            {"day": "Day 1", "task": "Lock promoted refined thesis vs. tape; verify refined_text vs. audio."},
            {"day": "Day 2", "task": "Clear issues_remaining from refiner metadata or demote promotion."},
            {"day": "Day 3-7", "task": "Ship one clip tied to strongest canonical (pass-1) claim text."},
        ]
    else:
        supported.append(
            "Pass-3 refiner output is advisory only (promotion gate not met). "
            "Top-level claims remain pass-1 grounded; see argument_refined."
        )

    base["episode_snapshot"] = snap
    base["evidence_gaps"] = {
        "supported": supported[:16],
        "weak_or_unsupported": weak_ev[:20],
        "proof_needed": proof_need[:14],
    }
    base["argument_refined"] = {"data": d3, "metadata": m3}
    return base
