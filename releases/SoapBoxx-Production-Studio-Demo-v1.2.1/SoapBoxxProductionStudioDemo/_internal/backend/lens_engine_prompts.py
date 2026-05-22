# backend/lens_engine_prompts.py
"""
Parallel lens prompts + v3 assembly hook.

v3 attaches ``report["dual_lens"]`` from :func:`assemble_dual_lens_package`: same structured
brief the rest of the pipeline uses, heuristic episode lens (NARRATIVE / ANALYTICAL / HYBRID),
weights, prompt-injection text, and narrative / analytical / synthesis objects shaped like the
LLM engine outputs (here filled deterministically from the brief + coach fields). Optional
LLM passes can reuse ``NARRATIVE_ENGINE_PROMPT``, ``ANALYTICAL_ENGINE_PROMPT``,
``SYNTHESIS_LAYER_PROMPT``.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional, Tuple

EpisodeLensType = Literal["NARRATIVE", "ANALYTICAL", "HYBRID"]

# Dominant vs secondary emphasis (narrative_weight + analytical_weight == 1.0)
LENS_WEIGHTS: Dict[EpisodeLensType, Tuple[float, float]] = {
    "NARRATIVE": (0.8, 0.2),
    "ANALYTICAL": (0.2, 0.8),
    "HYBRID": (0.5, 0.5),
}


def lens_weights(episode_type: str) -> Tuple[float, float]:
    """Return (narrative_weight, analytical_weight); unknown types default to HYBRID."""
    key = str(episode_type or "").strip().upper()
    if key in LENS_WEIGHTS:
        return LENS_WEIGHTS[key]  # type: ignore[index]
    return LENS_WEIGHTS["HYBRID"]


CLASSIFICATION_INJECTION_TEMPLATE = """
This episode has been classified as: {episode_type}

Optimization rules:

If ANALYTICAL:
- Prioritize claims, arguments, and structured reasoning
- Emphasize verification, counterarguments, and logic

If NARRATIVE:
- Prioritize storytelling, interpersonal dynamics, and emotional context
- Focus on memory, perception, and human tension
- Avoid over-emphasizing claim verification or formal argumentation

If HYBRID:
- Balance storytelling with analysis
- Extract both narrative meaning and actionable insights

CRITICAL:
- Do not force analytical structure onto narrative content.
- Do not ignore insights just because content is conversational.
""".strip()


def format_classification_injection(episode_type: str) -> str:
    return CLASSIFICATION_INJECTION_TEMPLATE.format(
        episode_type=str(episode_type or "HYBRID").strip().upper() or "HYBRID"
    )


def _brief_claims(brief: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [c for c in (brief.get("claims") or []) if isinstance(c, dict) and str(c.get("text") or "").strip()]


def classify_episode_lens(
    brief: Dict[str, Any],
    transcript: str,
    *,
    signal_mode: str,
) -> Tuple[EpisodeLensType, int]:
    """
    Heuristic lens from brief + transcript (no extra LLM). Returns (type, confidence 52–96).
    """
    claims = _brief_claims(brief)
    narrative_bullets = [str(x).strip() for x in (brief.get("narrative") or []) if str(x).strip()]
    tlow = (transcript or "").lower()

    analytical = 0.0
    narrative = 0.0

    for c in claims:
        ct = str(c.get("claim_type") or "").lower()
        if ct == "fact":
            analytical += 2.0
        elif ct == "interpretation":
            analytical += 1.2
            narrative += 0.4
        elif ct == "belief":
            narrative += 0.8
            analytical += 0.5
        else:
            analytical += 0.8
        if str(c.get("counter_angle") or "").strip():
            analytical += 0.9
        na = str(c.get("next_action") or "").lower()
        if na == "verify":
            analytical += 1.1
        elif na in ("follow_up_segment", "challenge"):
            analytical += 0.4
            narrative += 0.2

    narrative += float(min(len(narrative_bullets), 5)) * 1.4

    story_markers = (
        " i remember",
        " when i was",
        " story",
        " felt ",
        " we were",
        " my mom",
        " my dad",
        " growing up",
    )
    if any(m in tlow for m in story_markers):
        narrative += 2.0

    eg = brief.get("evidence_gaps") or {}
    if isinstance(eg, dict):
        weak = [str(x).strip() for x in (eg.get("weak_or_unsupported") or []) if str(x).strip()]
        analytical += float(min(len(weak), 3)) * 0.7

    if str(signal_mode or "").upper() == "LOW_SIGNAL" and len(claims) <= 1:
        narrative += 1.5

    ratio = analytical / max(narrative, 0.01)
    if ratio >= 1.35:
        lens: EpisodeLensType = "ANALYTICAL"
    elif ratio <= 0.75:
        lens = "NARRATIVE"
    else:
        lens = "HYBRID"

    confidence = int(round(55.0 + min(40.0, abs(ratio - 1.0) * 35.0)))
    confidence = max(52, min(96, confidence))
    return lens, confidence


def build_normalized_input(
    brief: Dict[str, Any],
    transcript: str,
    metadata: Optional[Dict[str, str]] = None,
    *,
    transcript_cap: int = 10_000,
) -> Dict[str, Any]:
    """Single JSON-shaped input for engines / future LLM calls (shared SSOT contract)."""
    meta = dict(metadata or {})
    snap = brief.get("episode_snapshot") or {}
    title = str(meta.get("title") or snap.get("title") or "").strip()
    primary = str(snap.get("primary_topic") or "").strip()
    why = str(snap.get("why_it_matters") or "").strip()
    summary = " ".join(x for x in (primary, why) if x).strip()
    t = (transcript or "").strip()
    if len(t) > transcript_cap:
        t = t[:transcript_cap] + "\n…[truncated]"

    topics: List[str] = []
    if primary:
        topics.append(primary)
    g = str(meta.get("genre") or snap.get("genre") or "").strip()
    if g:
        topics.append(g)

    wc = len(re.findall(r"\b\w+\b", transcript or ""))
    structure_signals = [
        f"claim_count:{len(_brief_claims(brief))}",
        f"narrative_bullet_count:{len([x for x in (brief.get('narrative') or []) if str(x).strip()])}",
        f"transcript_word_count:{wc}",
    ]

    return {
        "title": title,
        "summary": summary,
        "transcript": t,
        "entities": [],
        "topics": topics,
        "tone_signals": [],
        "structure_signals": structure_signals,
    }


def assemble_dual_lens_package(
    brief: Dict[str, Any],
    transcript: str,
    metadata: Optional[Dict[str, str]],
    *,
    signal_mode: str,
    narrative_reconstruction: Dict[str, Any],
    coach_report: Optional[Dict[str, Any]],
    claims: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build ``dual_lens`` for v3: classification, weights, injection text, lens-shaped dicts,
    and deterministic synthesis (no merge of free-text report bodies).
    """
    lens, confidence = classify_episode_lens(brief, transcript, signal_mode=signal_mode)
    wn, wa = lens_weights(lens)
    norm = build_normalized_input(brief, transcript, metadata)

    nr = dict(narrative_reconstruction or {})
    stakes = [str(x).strip() for x in (brief.get("narrative") or []) if str(x).strip()][:4]
    core_story = " ".join(
        p
        for p in (
            str(nr.get("core_thesis") or "").strip(),
            str(nr.get("supporting_mechanism") or "").strip(),
            str(nr.get("practical_translation") or "").strip(),
        )
        if p
    ).strip()
    if not core_story and stakes:
        core_story = stakes[0]
    if not core_story:
        core_story = "Thin narrative grounding in the brief; treat story reads as provisional."

    pm = brief.get("production_moves") if isinstance(brief.get("production_moves"), dict) else {}
    clip_cand = [str(x).strip() for x in (pm.get("clip_candidates") or []) if str(x).strip()][:3]

    dynamics: List[str] = []
    cr = coach_report if isinstance(coach_report, dict) else {}
    for th in (cr.get("themes") or [])[:3]:
        if not isinstance(th, dict):
            continue
        label = str(th.get("label") or "").strip()
        imp = str(th.get("implying") or "").strip()
        if label and imp:
            dynamics.append(f"{label}: {imp}")
        elif label:
            dynamics.append(label)

    narrative_lens: Dict[str, Any] = {
        "lens": "narrative",
        "core_story": core_story[:2000],
        "stakes": stakes,
        "dynamics": dynamics[:5],
        "memory_and_perception": [],
        "open_loops": [str(x) for x in (cr.get("follow_up_questions") or []) if str(x).strip()][:3],
        "clip_hooks_narrative": clip_cand or [],
    }

    claims_out: List[Dict[str, Any]] = []
    for c in claims[:8]:
        claims_out.append(
            {
                "text": str(c.get("text") or "").strip(),
                "kind": str(c.get("claim_type") or "interpretation"),
                "support": str(c.get("why_it_matters") or "").strip() or "Aligned to brief claim row.",
                "falsifier": str(c.get("counter_angle") or "").strip()
                or "Disconfirming evidence, expert pushback, or missing mechanism.",
            }
        )

    eg = brief.get("evidence_gaps") if isinstance(brief.get("evidence_gaps"), dict) else {}
    logic_gaps = [str(x).strip() for x in (eg.get("weak_or_unsupported") or []) if str(x).strip()][
        :4
    ]
    verification_moves = [str(x).strip() for x in (eg.get("proof_needed") or []) if str(x).strip()][
        :4
    ]
    incentives: List[str] = []
    risk_note = ""
    if isinstance(pm, dict):
        risk_note = str(pm.get("risk_note") or "").strip()
    if risk_note:
        incentives.append(risk_note)

    analytical_lens: Dict[str, Any] = {
        "lens": "analytical",
        "thesis_candidate": str(cr.get("episode_thesis") or "").strip()
        or str((brief.get("episode_snapshot") or {}).get("why_it_matters") or "").strip(),
        "claims": claims_out,
        "incentives_and_stakes": incentives[:4],
        "logic_gaps": logic_gaps,
        "verification_moves": verification_moves,
        "clip_hooks_analytical": clip_cand[:3] if clip_cand else [],
    }

    thesis_line = str(cr.get("episode_thesis") or "").strip()
    snap = brief.get("episode_snapshot") or {}
    if not thesis_line:
        thesis_line = str(snap.get("why_it_matters") or "").strip()

    collision_notes: List[str] = []
    if stakes and logic_gaps:
        collision_notes.append(
            "Narrative bullets foreground tension while the analytical read flags weak or unsupported lines — "
            f"example gap: {logic_gaps[0][:200]}"
        )
    elif logic_gaps:
        collision_notes.append(
            "Analytical lens stresses verification; narrative stakes are thin in the brief — avoid over-selling story."
        )
    elif stakes:
        collision_notes.append(
            "Narrative material present; analytical lens should still pin claims to checkable support."
        )
    else:
        collision_notes.append("Sparse brief hooks for both lenses — expand transcript grounding before packaging.")

    if thesis_line and logic_gaps:
        collision_notes.append(
            "Thesis line should be read alongside flagged gaps: do not treat as settled fact without sources."
        )
    collision_notes = collision_notes[:4]

    if lens == "ANALYTICAL":
        lead = (
            f"Lead with argument integrity and verification moves ({wa:.0%} analytical weight); "
            f"use narrative only as audience context ({wn:.0%})."
        )
    elif lens == "NARRATIVE":
        lead = (
            f"Lead with story, stakes, and human tension ({wn:.0%} narrative weight); "
            f"keep analytical pressure as guardrails ({wa:.0%})."
        )
    else:
        lead = "Balance story pull with claim discipline (50/50 hybrid weighting)."

    core_positioning = f"{lead} {thesis_line}".strip()[:1200]

    differentiation = str(snap.get("why_it_matters") or thesis_line or "").strip()[:400]
    risk_flags = [str(x).strip() for x in (eg.get("proof_needed") or []) if str(x).strip()][:3]
    if not risk_flags and risk_note:
        risk_flags = [risk_note[:240]]

    synthesis: Dict[str, Any] = {
        "lens": "synthesis",
        "episode_type_used": lens,
        "weights_used": {"narrative": round(wn, 2), "analytical": round(wa, 2)},
        "core_positioning": core_positioning,
        "collision_notes": collision_notes,
        "differentiation_line": differentiation
        or "Position on what is honestly demonstrated vs. what is still open.",
        "execution_bias": {
            "clips": (
                "Weight clips toward human beats and tension."
                if wn >= wa
                else "Weight clips toward claims, contradictions, and verification moments."
            ),
            "actions": (
                "Weight next actions toward deepening the story and follow-up interviews."
                if wn >= wa
                else "Weight next actions toward fact-checks, expert validation, and structured follow-ups."
            ),
        },
        "risk_flags": risk_flags,
    }

    return {
        "episode_lens_type": lens,
        "confidence": confidence,
        "weights": {"narrative": round(wn, 2), "analytical": round(wa, 2)},
        "prompt_injection": format_classification_injection(lens),
        "normalized_input": norm,
        "narrative_lens": narrative_lens,
        "analytical_lens": analytical_lens,
        "synthesis": synthesis,
        "engine_prompts": {
            "narrative": NARRATIVE_ENGINE_PROMPT,
            "analytical": ANALYTICAL_ENGINE_PROMPT,
            "synthesis": SYNTHESIS_LAYER_PROMPT,
        },
    }


SHARED_INPUT_CONTEXT = """
You receive a single normalized input object (shared across all engines). Treat it as
the only source of truth; do not invent entities or topics not grounded there.

Shape (fields may be empty arrays when unknown):
{{
  "title": "...",
  "summary": "...",
  "transcript": "...",
  "entities": [],
  "topics": [],
  "tone_signals": [],
  "structure_signals": []
}}
""".strip()


NARRATIVE_ENGINE_PROMPT = f"""
You are the Narrative Lens for a podcast intelligence system.

{SHARED_INPUT_CONTEXT}

Your job:
- Surface story, dynamics, memory, stakes, and human tension.
- Name who is involved and how relationships or roles shift (when inferable from input).
- Call out beats: setup, turn, resolution or open loop — even if implicit.
- Prefer concrete scene language over abstract labels.

Hard rules:
- Do not fabricate events absent from transcript/summary; you may infer *dynamics* only
  when strongly supported by repeated themes or explicit speaker intent.
- Do not optimize for "sounding smart"; optimize for clarity of what happened emotionally
  and interpersonally.
- If the input is thin, say what is thin and what is still fair to infer (one short line).

Output (JSON only, no markdown fences):
{{
  "lens": "narrative",
  "core_story": "2–4 sentences",
  "stakes": ["max 4 bullets"],
  "dynamics": ["max 5 bullets: relationships, power, vulnerability, conflict, alliance"],
  "memory_and_perception": ["max 4 bullets: how speakers frame past, identity, blame, hope"],
  "open_loops": ["max 3 unresolved tensions or unanswered questions grounded in input"],
  "clip_hooks_narrative": ["max 3: moment types worth cutting for story — not raw timestamps unless given"]
}}
""".strip()


ANALYTICAL_ENGINE_PROMPT = f"""
You are the Analytical Lens for a podcast intelligence system.

{SHARED_INPUT_CONTEXT}

Your job:
- Extract defensible claims, incentives, mechanisms, and what would falsify them.
- Separate evidence-supported assertions from belief or interpretation (tag each).
- Surface counterarguments, missing proof, and logical leaps.

Hard rules:
- Every non-trivial claim must tie to something in transcript/summary (paraphrase is fine).
- Prefer "what we can say" over "nice sounding thesis".
- If evidence is anecdotal only, say so explicitly.

Output (JSON only, no markdown fences):
{{
  "lens": "analytical",
  "thesis_candidate": "one sentence: the strongest arguable through-line (may be qualified)",
  "claims": [
    {{
      "text": "one sentence",
      "kind": "fact|interpretation|belief",
      "support": "brief: what in the input backs this (or 'thin / anecdotal only')",
      "falsifier": "what would prove this wrong or incomplete"
    }}
  ],
  "incentives_and_stakes": ["max 4 bullets: who benefits, what is being sold, reputational risk"],
  "logic_gaps": ["max 4: leaps, missing premises, correlation vs causation, etc."],
  "verification_moves": ["max 4 concrete checks: data, expert, document, counter-interview"],
  "clip_hooks_analytical": ["max 3: contradiction, strong claim, or methodological tension worth cutting"]
}}
""".strip()


SYNTHESIS_LAYER_PROMPT = f"""
You are the Synthesis Layer. You receive:
1) The same normalized input object (source of truth)
2) JSON output from the Narrative Lens
3) JSON output from the Analytical Lens
4) Episode classification: NARRATIVE | ANALYTICAL | HYBRID
5) Weights: narrative_weight and analytical_weight (0–1, sum to 1)

{SHARED_INPUT_CONTEXT}

Your job:
- Do NOT duplicate long lists from the two lenses; reference them by theme.
- Produce collisions: where story framing and evidence/logic agree or disagree.
- State one clear "so what" for a creator or editor (what to do with this episode).

Weighting:
- Core positioning and execution guidance should reflect the dominant lens without
  silencing the secondary lens.
- If classification is NARRATIVE: lead with human/story implications; analytical as guardrails.
- If ANALYTICAL: lead with argument integrity; narrative as context for why audiences care.
- If HYBRID: explicit 50/50 balance in the synthesis paragraphs.

Hard rules:
- If the analytical lens says evidence is thin, the synthesis must not pretend certainty.
- If the narrative lens flags open loops, the synthesis should not "close" them without support.
- No generic praise; every sentence should earn its place.

Output (JSON only, no markdown fences):
{{
  "lens": "synthesis",
  "episode_type_used": "NARRATIVE|ANALYTICAL|HYBRID",
  "weights_used": {{ "narrative": 0.0, "analytical": 0.0 }},
  "core_positioning": "2–3 sentences; dominant-lens voice",
  "collision_notes": [
    "max 4: each states agreement or tension between narrative and analytical reads"
  ],
  "differentiation_line": "one sentence: the sharpest honest positioning line for marketing or packaging",
  "execution_bias": {{
    "clips": "one line: lean narrative-heavy vs analytical-heavy and why",
    "actions": "one line: lean narrative-heavy vs analytical-heavy and why"
  }},
  "risk_flags": ["max 3: misframing risks if grounding is weak"]
}}
""".strip()
