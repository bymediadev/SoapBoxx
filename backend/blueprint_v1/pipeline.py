# backend/blueprint_v1/pipeline.py
"""Master Blueprint v1 pipeline — orchestration + validation retries."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from .llm_runner import run_json_prompt
from .prompts import (
    ANALYTICAL_ENGINE_PROMPT,
    CLASSIFICATION_PROMPT,
    CLIP_DETECTION_PROMPT,
    MASTER_STRATEGIST_PROMPT,
    NARRATIVE_ENGINE_PROMPT,
    SYNTHESIS_ENGINE_PROMPT,
    THESIS_GENERATOR_PROMPT,
    control_injection_block,
)
from .schemas import (
    AnalyticalBlock,
    ClassificationResult,
    ClipItem,
    ClipsBlock,
    EpisodicInput,
    FinalReport,
    NarrativeBlock,
    SynthesisBlock,
    ThesisBlock,
)

try:
    from ..episode_report_v3 import (
        _strategist_network_lines_from_insights,
        _strategist_punchline_from_signal,
        _strategist_tension_from_claims,
    )
except ImportError:  # pragma: no cover
    from episode_report_v3 import (  # type: ignore
        _strategist_network_lines_from_insights,
        _strategist_punchline_from_signal,
        _strategist_tension_from_claims,
    )


def _excerpt(transcript: str, cap: int = 14_000) -> str:
    t = (transcript or "").strip()
    return t if len(t) <= cap else t[:cap] + "\n…[truncated]"


def _meta_blob(inp: EpisodicInput) -> str:
    return json.dumps(
        {
            "title": inp.title,
            "description": (inp.description or "")[:800],
            "topics": inp.topics,
            "entities": inp.entities,
            "duration": inp.duration,
        },
        ensure_ascii=False,
    )


def _heuristic_classification(inp: EpisodicInput) -> ClassificationResult:
    t = (inp.transcript or "").lower()
    analytical_hits = sum(1 for k in ("because", "therefore", "study", "data", "percent", "evidence", "research") if k in t)
    narrative_hits = sum(1 for k in (" i ", " we ", " my ", " felt ", " remember ", " story ", " when i ") if k in t)
    if analytical_hits >= 4 and narrative_hits <= 2:
        typ = "ANALYTICAL"
    elif narrative_hits >= 3 and analytical_hits <= 2:
        typ = "NARRATIVE"
    else:
        typ = "HYBRID"
    conf = min(88, 55 + abs(analytical_hits - narrative_hits) * 6)
    return ClassificationResult(type=typ, confidence=conf, reasoning="Heuristic fallback (no LLM or parse failure).")


def _parse_classification(raw: Dict[str, Any]) -> Optional[ClassificationResult]:
    try:
        return ClassificationResult.model_validate(raw)
    except ValidationError:
        return None


def _run_stage(
    *,
    control: str,
    engine_prompt: str,
    excerpt: str,
    meta: str,
    label: str,
) -> Optional[Dict[str, Any]]:
    user = f"{control}\n\n{engine_prompt}\n\nMETADATA:\n{meta}\n\nTRANSCRIPT (excerpt):\n{excerpt}"
    data = run_json_prompt(user)
    if not isinstance(data, dict):
        return None
    return data


def _fallback_narrative(inp: EpisodicInput) -> NarrativeBlock:
    return NarrativeBlock(
        core_story=f"Episode “{inp.title or 'Untitled'}” centers on interpersonal stakes described in the transcript.",
        key_moments=["Opening framing", "Personal reflection", "Closing takeaway"],
        hidden_dynamics=["Power and vulnerability implied between speakers."],
        memory_vs_reality="Listeners only hear recalled versions of events — verify names and timelines externally.",
        tension="Competing interpretations of what really happened versus how it is remembered.",
    )


def _fallback_analytical(inp: EpisodicInput) -> AnalyticalBlock:
    wc = len((inp.transcript or "").split())
    return AnalyticalBlock(
        core_ideas=[f"Primary subject matter of “{inp.title or 'this episode'}”."],
        claims=["Hosts assert positions that deserve fact-checking when stated as universal."],
        reasoning_quality="mixed — conversational podcast without primary sources on mic",
        missing_pieces=["Independent documentation for strong factual assertions."],
        counterpoints=["A skeptic would demand harder evidence before changing behavior."],
    )


def _fallback_thesis(inp: EpisodicInput, n: NarrativeBlock, a: AnalyticalBlock) -> ThesisBlock:
    return ThesisBlock(
        thesis=(
            f"The episode uses “{inp.title or 'this story'}” to juxtapose public competition "
            f"with private memory of relationships — asking whether camaraderie and rivalry can coexist."
        )
    )


def _fallback_clips(inp: EpisodicInput) -> List[ClipItem]:
    ex = _excerpt(inp.transcript, 1200)
    sentences = re.split(r"(?<=[.!?])\s+", ex)
    out: List[ClipItem] = []
    for s in sentences[:5]:
        s = s.strip()
        if len(s) < 40 or len(s) > 320:
            continue
        out.append(ClipItem(text=s, reason="Candidate beat from early transcript (fallback)."))
        if len(out) >= 3:
            break
    while len(out) < 3:
        out.append(
            ClipItem(
                text=f"Anchor on the clearest self-contained line about: {inp.title or 'the episode'}.",
                reason="Placeholder clip — replace after LLM clip pass.",
            )
        )
    return out[:5]


def _fallback_synthesis(n: NarrativeBlock, a: AnalyticalBlock) -> SynthesisBlock:
    return SynthesisBlock(
        key_insight="Human stakes drive attention while analytical discipline keeps claims honest.",
        friction_point="Story comfort can outrun what the transcript can actually support.",
        strength="Relatable voice and concrete moments listeners can recognize.",
        gap="Under-specified evidence for the strongest assertions.",
    )


def _default_actions(thesis: str, syn: SynthesisBlock) -> List[str]:
    return [
        "Pick one defendable thesis line before packaging clips or titles.",
        "Add one primary-source or expert check for the hardest factual claim.",
        f"Stress-test the friction point on-mic: {syn.friction_point[:120]}…",
    ]


def _signal_strength_label(confidence: int) -> str:
    if confidence >= 78:
        return "Strong"
    if confidence >= 60:
        return "Moderate"
    return "Weak"


def _score_signal_label(score: int) -> str:
    if score >= 8:
        return "Strong"
    if score >= 5:
        return "Moderate"
    return "Weak"


def _is_actionable_takeaway(text: str) -> bool:
    t = str(text or "").strip().lower()
    if len(t) < 18:
        return False
    action_markers = ("should", "do ", "start", "stop", "test", "apply", "change", "commit", "pick")
    return any(m in t for m in action_markers)


def _derive_score_components(thesis: str, clip_ops: List[str], behavior_change: str) -> Dict[str, bool]:
    thesis_ok = len((thesis or "").split()) >= 8
    clip_ok = len([c for c in clip_ops if len(c.split()) >= 6]) >= 2
    takeaway_ok = _is_actionable_takeaway(behavior_change)
    return {
        "clear_thesis": thesis_ok,
        "strong_clips": clip_ok,
        "actionable_takeaway": takeaway_ok,
    }


def _score_from_components(components: Dict[str, bool]) -> int:
    clear_thesis = bool(components.get("clear_thesis"))
    strong_clips = bool(components.get("strong_clips"))
    actionable_takeaway = bool(components.get("actionable_takeaway"))
    if clear_thesis and strong_clips and actionable_takeaway:
        return 9
    if clear_thesis or strong_clips or actionable_takeaway:
        return 6
    return 3


def _mode_aware_score(
    *,
    mode: str,
    anchors: List[Dict[str, str]],
    key_claims: List[str],
    conviction_statement: str,
    tension_position: Dict[str, Any],
    behavior_change: str,
    transcript_word_count: int,
) -> int:
    """
    Score decompression layer.

    Evidence mode prioritizes grounding density.
    Interpretive mode prioritizes tension + conviction clarity without rewarding
    synthetic structural completeness.
    """
    def _is_grounded_anchor(anchor_text: str) -> bool:
        a = str(anchor_text or "").strip().lower()
        if not a:
            return False
        generic = (
            "opening framing",
            "personal reflection",
            "closing takeaway",
            "in a central exchange",
            "same point is repeated",
        )
        return not any(g in a for g in generic)

    def _scale_into_band(raw_0_10: float, lo: int, hi: int) -> int:
        r = max(0.0, min(10.0, raw_0_10)) / 10.0
        return int(round(lo + r * (hi - lo)))

    mode_n = (mode or "interpretive").strip().lower()
    grounded_anchor_count = sum(1 for a in anchors if isinstance(a, dict) and _is_grounded_anchor(str(a.get("anchor") or "")))

    # STEP 1: mode ceiling (hard limit)
    max_score = 10 if mode_n == "evidence" else 7

    # STEP 2: hard fail gates (override scoring)
    if mode_n == "evidence" and grounded_anchor_count < 2:
        # Evidence mode without enough grounded anchors cannot be strong.
        return 3
    if mode_n == "interpretive" and int(transcript_word_count or 0) < 80:
        # Interpretive mode with thin actionable signal is weak by definition.
        return 3

    # STEP 3: score inside allowed band only
    if mode_n == "evidence":
        grounded_score = 10 if grounded_anchor_count >= 3 else 8 if grounded_anchor_count >= 2 else 4
        anchor_density = 10 if grounded_anchor_count >= max(1, len(key_claims)) else 6
        arg_structure = 9 if (len(key_claims) >= 2 and _is_actionable_takeaway(behavior_change)) else 6 if key_claims else 3
        raw = (grounded_score * 0.5) + (anchor_density * 0.3) + (arg_structure * 0.2)
        return max(1, min(max_score, _scale_into_band(raw, 5, max_score)))

    conviction = 9 if len((conviction_statement or "").split()) >= 10 else 6 if conviction_statement else 3
    implicit_argument = str((tension_position or {}).get("implicit_argument") or "").strip()
    stronger_position = str((tension_position or {}).get("stronger_position") or "").strip()
    tension_strength = 9 if implicit_argument and stronger_position and implicit_argument != stronger_position else 6 if implicit_argument or stronger_position else 3
    clarity = 8 if len(key_claims) >= 1 and len((behavior_change or "").split()) >= 6 else 5 if key_claims else 3
    raw = (conviction * 0.4) + (tension_strength * 0.4) + (clarity * 0.2)
    return max(1, min(max_score, _scale_into_band(raw, 4, max_score)))


def _slice_non_empty(values: List[str], *, lo: int, hi: int, fallback: List[str]) -> List[str]:
    rows = [str(v).strip() for v in values if str(v).strip()]
    if len(rows) < lo:
        rows.extend([x for x in fallback if x not in rows])
    return rows[:hi]


def _compress_critique_language(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return s
    replacements = (
        ("lack of clarity", "the episode keeps resetting its point instead of defending one claim"),
        ("weak structure", "the episode moves between points without escalating the argument"),
        ("missed opportunity", "the episode leaves the strongest claim unchallenged on-mic"),
        ("shows that", "makes clear that"),
        ("indicates that", "makes clear that"),
    )
    low = s.lower()
    for src, dst in replacements:
        if src in low:
            s = re.sub(re.escape(src), dst, s, flags=re.IGNORECASE)
            low = s.lower()
    return s


def _compress_payload_language(value: Any) -> Any:
    if isinstance(value, str):
        return _compress_critique_language(value)
    if isinstance(value, list):
        return [_compress_payload_language(v) for v in value]
    if isinstance(value, dict):
        return {k: _compress_payload_language(v) for k, v in value.items()}
    return value


def _moment_anchors_from_transcript(transcript: str, *, max_items: int = 3) -> List[str]:
    t = (transcript or "").strip()
    if not t:
        return []
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", t) if p.strip()]
    out: List[str] = []
    for p in parts:
        if len(p.split()) < 7:
            continue
        out.append(p)
        if len(out) >= max_items:
            break
    return out


def _is_placeholder_claim(text: str) -> bool:
    s = str(text or "").strip().lower()
    return (not s) or ("hosts assert positions" in s)


def _is_placeholder_clip(c: ClipItem) -> bool:
    return "placeholder clip" in str(c.reason or "").lower()


def _select_strategist_mode(inp: EpisodicInput, analytical: AnalyticalBlock, clips: List[ClipItem]) -> str:
    forced = (os.getenv("SOAPBOXX_STRATEGIST_MODE") or "").strip().lower()
    if forced in ("evidence", "interpretive"):
        return forced
    words = len((inp.transcript or "").split())
    real_claims = sum(1 for c in (analytical.claims or []) if not _is_placeholder_claim(c) and len(str(c).split()) >= 5)
    real_clips = sum(1 for c in clips if not _is_placeholder_clip(c) and len(str(c.text or "").split()) >= 8)
    if words >= 120 and real_claims >= 1 and real_clips >= 2:
        return "evidence"
    return "interpretive"


def _apply_mode_profile(
    *,
    strategist_report: Dict[str, Any],
    mode: str,
    inp: EpisodicInput,
    analytical: AnalyticalBlock,
    clips: List[ClipItem],
) -> Dict[str, Any]:
    out = dict(strategist_report or {})
    core = dict(out.get("core_breakdown") or {})
    key_claims = [str(x).strip() for x in (core.get("key_claims") or []) if str(x).strip()][:3]
    if not key_claims:
        key_claims = [str(x).strip() for x in (analytical.claims or []) if str(x).strip() and not _is_placeholder_claim(str(x))][:3]
    if not key_claims:
        key_claims = [str(core.get("thesis") or "").strip() or "The episode needs one defendable claim with explicit stakes."]
    core["key_claims"] = key_claims[:3]

    anchors = [x for x in (core.get("evidence_anchors") or []) if isinstance(x, dict)]
    if not anchors:
        moments = _moment_anchors_from_transcript(inp.transcript, max_items=3)
        for i, claim in enumerate(key_claims[:3]):
            anchor = (
                moments[i]
                if i < len(moments)
                else (
                    "No verbatim clip was paired for this claim in the blueprint pass — "
                    "attach a transcript quote before sharing."
                )
            )
            anchors.append({"claim": claim, "anchor": anchor})
    core["evidence_anchors"] = anchors[:3]
    out["core_breakdown"] = core

    if mode == "interpretive":
        out["core_problem"] = str(out.get("core_problem") or "").strip() or "The episode moves across ideas without committing to one argument."
        out["what_missing"] = _slice_non_empty(
            [str(x).strip() for x in (out.get("what_missing") or []) if str(x).strip() and "no claims were extracted" not in str(x).lower()],
            lo=3,
            hi=3,
            fallback=[
                "The episode resets the conversation before defending one claim.",
                "No one pressure-tests the central claim after it appears.",
                "The close ends without one explicit listener action.",
            ],
        )
        out["conviction_statement"] = str(out.get("conviction_statement") or "").strip() or (
            "This episode underperforms because it avoids committing to one argument long enough to defend it."
        )
    else:
        out["core_problem"] = str(out.get("core_problem") or "").strip() or "The episode presents evidence but does not press the strongest implication hard enough."
    # Recalibrate score after mode routing so no path bypasses decompression.
    snap = dict(out.get("snapshot") or {})
    normalized_score = _mode_aware_score(
        mode=mode,
        anchors=[x for x in (core.get("evidence_anchors") or []) if isinstance(x, dict)],
        key_claims=[str(x).strip() for x in (core.get("key_claims") or []) if str(x).strip()],
        conviction_statement=str(out.get("conviction_statement") or "").strip(),
        tension_position=(core.get("tension_position") if isinstance(core.get("tension_position"), dict) else {}),
        behavior_change=str((out.get("audience_engagement_intelligence") or {}).get("behavior_change") or "").strip(),
        transcript_word_count=len((inp.transcript or "").split()),
    )
    snap["overall_score"] = normalized_score
    snap["signal_strength"] = _score_signal_label(normalized_score)
    snap["scoring_basis"] = "8-10 clear thesis + strong clips + actionable takeaway; 5-7 decent story but weak clarity/payoff; 1-4 unclear point and low engagement value"
    out["snapshot"] = snap
    out["report_mode"] = mode
    return _compress_payload_language(out)


def _fallback_strategist_report(
    *,
    inp: EpisodicInput,
    classification: ClassificationResult,
    thesis_obj: ThesisBlock,
    narrative: NarrativeBlock,
    analytical: AnalyticalBlock,
    synthesis: SynthesisBlock,
    clips: List[ClipItem],
) -> Dict[str, Any]:
    key_claims = _slice_non_empty(
        list(analytical.claims),
        lo=1,
        hi=3,
        fallback=[thesis_obj.thesis],
    )
    raw_anchors = [c.text for c in clips if str(c.text or "").strip()] + list(narrative.key_moments)
    evidence_anchors: List[Dict[str, str]] = []
    for i, cl in enumerate(key_claims[:3]):
        anchor = str(raw_anchors[i] if i < len(raw_anchors) else "").strip()
        if not anchor:
            anchor = (
                "No verbatim clip was paired for this claim in the blueprint pass — "
                "attach a transcript quote before sharing."
            )
        evidence_anchors.append({"claim": str(cl).strip(), "anchor": anchor})
    working = _slice_non_empty(
        [synthesis.strength] + list(narrative.key_moments),
        lo=3,
        hi=3,
        fallback=[
            "The episode has a clear host voice listeners can follow.",
            "There are recognizable moments that can be packaged as clips.",
            "The topic has enough tension to support a stronger narrative arc.",
        ],
    )
    missing = _slice_non_empty(
        list(analytical.missing_pieces) + [synthesis.gap, synthesis.friction_point],
        lo=3,
        hi=3,
        fallback=[
            "The core thesis is not framed tightly enough early in the episode.",
            "The strongest claims need sharper validation and clearer boundaries.",
            "The closing does not convert insight into a specific behavior change.",
        ],
    )
    clip_ops = _slice_non_empty(
        [c.text for c in clips],
        lo=2,
        hi=3,
        fallback=[
            "Open with the strongest contradiction in the first 60 seconds.",
            "Build one midpoint quote where the host challenges the main claim.",
        ],
    )
    questions = _slice_non_empty(
        list(analytical.counterpoints),
        lo=3,
        hi=3,
        fallback=[
            "What is the strongest counterargument to your main claim, and why does it fail?",
            "Which specific proof would make this thesis undeniable for a skeptic?",
            "What should a listener do differently this week if they buy your argument?",
        ],
    )
    guests = [
        {
            "who_type": "Domain practitioner with direct operating experience",
            "why_they_matter": "They convert abstract claims into concrete tradeoffs.",
            "what_they_unlock": "Execution reality and credible counterexamples.",
        },
        {
            "who_type": "Researcher or analyst tied to primary data",
            "why_they_matter": "They separate defensible evidence from narrative momentum.",
            "what_they_unlock": "Higher-confidence claims and stronger validation moments.",
        },
        {
            "who_type": "Contrarian expert with a steel-manned opposing view",
            "why_they_matter": "They force sharper framing and create productive tension.",
            "what_they_unlock": "Shareable conflict and deeper listener engagement.",
        },
    ]
    behavior_change = "Pick one weekly behavior tied directly to the episode thesis and measure it."
    components = _derive_score_components(thesis_obj.thesis, clip_ops, behavior_change)
    score = _score_from_components(components)
    strength = _score_signal_label(score)
    diagnosis = (
        synthesis.gap
        or "This episode underperforms due to weak positioning and lack of clear takeaway, but the upside is strong with sharper framing."
    )
    core_problem = diagnosis
    recommendations = [
        "Open with one explicit argument in the first 60 seconds.",
        "Force a midpoint challenge that tests the core claim under pressure.",
        "End with one concrete listener behavior change and metric.",
    ]
    snap_pb: Dict[str, Any] = {
        "title": inp.title or "",
        "primary_topic": (inp.topics[0] if inp.topics else "") or "",
    }
    kc_str = [str(x).strip() for x in key_claims if str(x).strip()]
    weaknesses_fb: List[str] = []
    for x in list(analytical.missing_pieces) + [str(synthesis.gap or ""), str(synthesis.friction_point or "")]:
        xs = str(x).strip()
        if xs and xs not in weaknesses_fb:
            weaknesses_fb.append(xs)
    fill_w = [
        "The episode resets topics before one claim is defended.",
        "No speaker pressure-tests the central claim once it appears.",
        "The close ends without one explicit listener action.",
    ]
    while len(weaknesses_fb) < 3:
        weaknesses_fb.append(fill_w[len(weaknesses_fb)])
    wfb = weaknesses_fb[:3]
    punchline = _strategist_punchline_from_signal(snap_pb, kc_str, wfb)
    tension_position = _strategist_tension_from_claims(str(thesis_obj.thesis or "").strip(), kc_str)
    highlights_fb = [str(synthesis.strength or "").strip()] + [
        str(m).strip() for m in narrative.key_moments if str(m).strip()
    ]
    highlights_fb = [h for h in highlights_fb if h][:8]
    network_level_insight = _strategist_network_lines_from_insights(
        highlights_fb, wfb, str(thesis_obj.thesis or "").strip()
    )
    et_short = str(snap_pb.get("title") or snap_pb.get("primary_topic") or "this episode")[:90]
    one_line_fix = (
        f"Rebuild the open so listeners hear the spine claim for \"{et_short}\" in 60 seconds, "
        f"then cut beats that do not test it."
    )
    conv_topic = str(snap_pb.get("primary_topic") or snap_pb.get("title") or "the stakes")[:90]
    conviction_statement = (
        f"The episode lands when listeners can repeat one sentence about {conv_topic}."
    )
    show_title = str(snap_pb.get("title") or "this show")[:80]
    network_rollout_line = (
        f"Apply the same spine discipline across \"{show_title}\": one defended claim per episode "
        f"before growth packaging."
    )
    where_under = wfb[1] if len(wfb) > 1 else wfb[0]
    return {
        "punchline_header": punchline,
        "core_problem": core_problem,
        "snapshot": {
            "overall_score": score,
            "signal_strength": strength,
            "diagnosis": diagnosis,
            "scoring_basis": "8-10 clear thesis + strong clips + actionable takeaway; 5-7 decent story but weak clarity/payoff; 1-4 unclear point and low engagement value",
        },
        "core_breakdown": {
            "thesis": thesis_obj.thesis,
            "key_claims": key_claims,
            "evidence_anchors": evidence_anchors,
            "tension_position": tension_position,
        },
        "what_working": working,
        "what_missing": missing,
        "upgrade_plan": {
            "reposition_episode": f"This episode should be about {thesis_obj.thesis}",
            "structure_fix": {
                "opening_hook": "State the central tension in one sentence and promise what the listener will learn.",
                "midpoint_tension": "Challenge the strongest claim with a direct counter-case before defending it.",
                "closing_takeaway": "End with one concrete behavior change the listener can apply this week.",
            },
            "clip_opportunities": clip_ops,
            "recommendations": recommendations,
        },
        "audience_engagement_intelligence": {
            "listener_takeaway_gap": "The listener needs a clearer single takeaway tied to a concrete decision.",
            "behavior_change": behavior_change,
            "weekly_improvement_insight": "Design each episode around one defensible thesis, one tension beat, and one specific takeaway.",
        },
        "question_upgrade": questions,
        "guest_content_opportunities": guests[:3],
        "strategic_value_for_network": {
            "what_improving_unlocks": "Stronger retention, cleaner clip packaging, and higher repeatability across episodes.",
            "where_it_underperforms": where_under,
        },
        "network_level_insight": network_level_insight,
        "network_rollout_line": network_rollout_line,
        "one_line_fix": one_line_fix,
        "conviction_statement": conviction_statement,
    }


def _build_strategist_report(
    *,
    data: Optional[Dict[str, Any]],
    inp: EpisodicInput,
    classification: ClassificationResult,
    thesis_obj: ThesisBlock,
    narrative: NarrativeBlock,
    analytical: AnalyticalBlock,
    synthesis: SynthesisBlock,
    clips: List[ClipItem],
) -> Dict[str, Any]:
    base = _fallback_strategist_report(
        inp=inp,
        classification=classification,
        thesis_obj=thesis_obj,
        narrative=narrative,
        analytical=analytical,
        synthesis=synthesis,
        clips=clips,
    )
    if not isinstance(data, dict):
        return base
    out = dict(base)
    for key in ("punchline_header", "network_rollout_line", "one_line_fix", "conviction_statement"):
        v = str(data.get(key) or "").strip()
        if v:
            out[key] = v
    cp = str(data.get("core_problem") or "").strip()
    if cp:
        out["core_problem"] = cp
    for key in (
        "snapshot",
        "core_breakdown",
        "upgrade_plan",
        "audience_engagement_intelligence",
        "strategic_value_for_network",
    ):
        if isinstance(data.get(key), dict):
            merged = dict(out.get(key) or {})
            merged.update({k: v for k, v in data[key].items() if v not in ("", None, [], {})})
            out[key] = merged
    cb = dict(out.get("core_breakdown") or {})
    anchors_out: List[Dict[str, str]] = []
    if isinstance((data.get("core_breakdown") or {}).get("evidence_anchors"), list):
        for row in (data.get("core_breakdown") or {}).get("evidence_anchors")[:3]:
            if not isinstance(row, dict):
                continue
            cl = str(row.get("claim") or "").strip()
            an = str(row.get("anchor") or "").strip()
            if cl and an:
                anchors_out.append({"claim": cl, "anchor": an})
    if not anchors_out:
        key_claims = [str(x).strip() for x in (cb.get("key_claims") or []) if str(x).strip()][:3]
        fallback_anchor = (
            "No verbatim clip was paired for this claim in the blueprint pass — "
            "attach a transcript quote before sharing."
        )
        for cl in key_claims:
            anchors_out.append({"claim": cl, "anchor": fallback_anchor})
    cb["evidence_anchors"] = anchors_out[:3]
    if isinstance((data.get("core_breakdown") or {}).get("tension_position"), dict):
        tp_in = (data.get("core_breakdown") or {}).get("tension_position") or {}
        implicit_argument = str(tp_in.get("implicit_argument") or "").strip()
        stronger_position = str(tp_in.get("stronger_position") or "").strip()
        if implicit_argument and stronger_position:
            cb["tension_position"] = {
                "implicit_argument": implicit_argument,
                "stronger_position": stronger_position,
            }
    tp = cb.get("tension_position") if isinstance(cb.get("tension_position"), dict) else {}
    if not str(tp.get("implicit_argument") or "").strip():
        tp["implicit_argument"] = f"This episode treats this as true: {str(cb.get('key_claims', ['the current framing'])[0])}"
    if not str(tp.get("stronger_position") or "").strip():
        tp["stronger_position"] = f"But the stronger position is this: {str(cb.get('thesis') or 'Force one argument with explicit stakes.')}"
    cb["tension_position"] = tp
    out["core_breakdown"] = cb
    for key, lo, hi in (
        ("what_working", 3, 3),
        ("what_missing", 3, 3),
        ("question_upgrade", 3, 3),
        ("network_level_insight", 4, 4),
    ):
        if isinstance(data.get(key), list):
            out[key] = _slice_non_empty(list(data[key]), lo=lo, hi=hi, fallback=list(out[key]))
    if isinstance(data.get("guest_content_opportunities"), list):
        guest_rows: List[Dict[str, str]] = []
        for g in data["guest_content_opportunities"][:3]:
            if not isinstance(g, dict):
                continue
            who = str(g.get("who_type") or "").strip()
            why = str(g.get("why_they_matter") or "").strip()
            unlock = str(g.get("what_they_unlock") or "").strip()
            if who and why and unlock:
                guest_rows.append({"who_type": who, "why_they_matter": why, "what_they_unlock": unlock})
        if guest_rows:
            out["guest_content_opportunities"] = guest_rows
    up = dict(out.get("upgrade_plan") or {})
    if isinstance((data.get("upgrade_plan") or {}).get("recommendations"), list):
        recs = _slice_non_empty(
            list((data.get("upgrade_plan") or {}).get("recommendations") or []),
            lo=3,
            hi=3,
            fallback=list(up.get("recommendations") or []),
        )
        up["recommendations"] = recs
    else:
        up["recommendations"] = _slice_non_empty(
            list(up.get("recommendations") or []),
            lo=3,
            hi=3,
            fallback=[
                "Open with one explicit argument in the first 60 seconds.",
                "Force a midpoint challenge that tests the core claim under pressure.",
                "End with one concrete listener behavior change and metric.",
            ],
        )
    up["clip_opportunities"] = _slice_non_empty(
        list(up.get("clip_opportunities") or []),
        lo=2,
        hi=3,
        fallback=list(up.get("clip_opportunities") or []),
    )
    out["upgrade_plan"] = up

    # Mode-aware score calibration (decompress weak/interpretive inflation).
    cb_now = dict(out.get("core_breakdown") or {})
    anchors_now = [x for x in (cb_now.get("evidence_anchors") or []) if isinstance(x, dict)]
    key_claims_now = [str(x).strip() for x in (cb_now.get("key_claims") or []) if str(x).strip()]
    behavior_change = str((out.get("audience_engagement_intelligence") or {}).get("behavior_change") or "").strip()
    tension_now = cb_now.get("tension_position") if isinstance(cb_now.get("tension_position"), dict) else {}
    mode_now = str(out.get("report_mode") or "interpretive").strip().lower()
    normalized_score = _mode_aware_score(
        mode=mode_now,
        anchors=anchors_now,
        key_claims=key_claims_now,
        conviction_statement=str(out.get("conviction_statement") or "").strip(),
        tension_position=tension_now,
        behavior_change=behavior_change,
        transcript_word_count=len((inp.transcript or "").split()),
    )
    snap = dict(out.get("snapshot") or {})
    snap["overall_score"] = normalized_score
    snap["signal_strength"] = _score_signal_label(normalized_score)
    snap["scoring_basis"] = "8-10 clear thesis + strong clips + actionable takeaway; 5-7 decent story but weak clarity/payoff; 1-4 unclear point and low engagement value"
    out["snapshot"] = snap
    return _compress_payload_language(out)


def _build_narrative(data: Optional[Dict[str, Any]], inp: EpisodicInput) -> NarrativeBlock:
    if not data:
        return _fallback_narrative(inp)
    try:
        return NarrativeBlock.model_validate(data)
    except ValidationError:
        return _fallback_narrative(inp)


def _build_analytical(data: Optional[Dict[str, Any]], inp: EpisodicInput) -> AnalyticalBlock:
    if not data:
        return _fallback_analytical(inp)
    try:
        return AnalyticalBlock.model_validate(data)
    except ValidationError:
        return _fallback_analytical(inp)


def _build_clips(data: Optional[Dict[str, Any]], inp: EpisodicInput) -> List[ClipItem]:
    if not data or "clips" not in data:
        return _fallback_clips(inp)
    try:
        block = ClipsBlock.model_validate(data)
        return block.clips if block.clips else _fallback_clips(inp)
    except ValidationError:
        return _fallback_clips(inp)


def _build_synthesis(data: Optional[Dict[str, Any]], n: NarrativeBlock, a: AnalyticalBlock) -> SynthesisBlock:
    if not data:
        return _fallback_synthesis(n, a)
    try:
        return SynthesisBlock.model_validate(data)
    except ValidationError:
        return _fallback_synthesis(n, a)


def _build_thesis(data: Optional[Dict[str, Any]], inp: EpisodicInput, n: NarrativeBlock, a: AnalyticalBlock) -> ThesisBlock:
    if not data or not str(data.get("thesis") or "").strip():
        return _fallback_thesis(inp, n, a)
    try:
        return ThesisBlock.model_validate(data)
    except ValidationError:
        return _fallback_thesis(inp, n, a)


def _ensure_thesis_non_trivial(inp: EpisodicInput, narrative: NarrativeBlock, analytical: AnalyticalBlock, thesis_obj: ThesisBlock) -> ThesisBlock:
    if len(thesis_obj.thesis.strip()) >= 24:
        return thesis_obj
    return _fallback_thesis(inp, narrative, analytical)


def _assemble_validated_report(
    *,
    classification: ClassificationResult,
    thesis_obj: ThesisBlock,
    narrative: NarrativeBlock,
    analytical: AnalyticalBlock,
    synthesis: SynthesisBlock,
    clips: List[ClipItem],
    actions: List[str],
    strategist_report: Dict[str, Any],
    max_retries: int,
    inp: EpisodicInput,
    control: str,
) -> FinalReport:
    thesis_obj = _ensure_thesis_non_trivial(inp, narrative, analytical, thesis_obj)
    last_err: Optional[Exception] = None
    for _ in range(max(1, max_retries)):
        try:
            return FinalReport.from_blocks(
                classification=classification,
                thesis=thesis_obj.thesis,
                narrative=narrative,
                analytical=analytical,
                synthesis=synthesis,
                clips=clips,
                actions=actions,
                strategist_report=strategist_report,
            )
        except ValidationError as e:
            last_err = e
            repair = (
                f"{control}\n\n{THESIS_GENERATOR_PROMPT}\n\n"
                "Return JSON only. thesis: one debatable sentence, >= 24 characters, not a quote.\n"
                f"NARRATIVE: {json.dumps(narrative.model_dump(), ensure_ascii=False)[:6000]}\n"
                f"ANALYTICAL: {json.dumps(analytical.model_dump(), ensure_ascii=False)[:6000]}\n"
            )
            fixed = run_json_prompt(
                repair,
                system='Output strictly: {"thesis":"..."}',
            )
            thesis_obj = _ensure_thesis_non_trivial(inp, narrative, analytical, _build_thesis(fixed, inp, narrative, analytical))
    raise RuntimeError(f"Blueprint FinalReport validation failed: {last_err}")


def run_blueprint_v1(
    inp: EpisodicInput,
    *,
    max_retries: int = 2,
) -> FinalReport:
    """
    Execute blueprint stages. Uses Ollama when ``SOAPBOXX_OLLAMA_MODEL`` is set; otherwise heuristics + fallbacks.
    """
    excerpt = _excerpt(inp.transcript)
    meta = _meta_blob(inp)

    raw_c = run_json_prompt(
        f"{CLASSIFICATION_PROMPT}\n\nMETADATA:\n{meta}\n\nTRANSCRIPT (excerpt):\n{excerpt}",
        system="You are a strict JSON emitter. Output JSON only.",
    )
    classification = _parse_classification(raw_c or {}) or _heuristic_classification(inp)
    ctrl = control_injection_block(classification.type)

    n_raw = _run_stage(control=ctrl, engine_prompt=NARRATIVE_ENGINE_PROMPT, excerpt=excerpt, meta=meta, label="narrative")
    a_raw = _run_stage(control=ctrl, engine_prompt=ANALYTICAL_ENGINE_PROMPT, excerpt=excerpt, meta=meta, label="analytical")

    narrative = _build_narrative(n_raw, inp)
    analytical = _build_analytical(a_raw, inp)

    thesis_raw = run_json_prompt(
        f"{ctrl}\n\n{THESIS_GENERATOR_PROMPT}\n\n"
        f"NARRATIVE_JSON:\n{json.dumps(narrative.model_dump(), ensure_ascii=False)[:8000]}\n\n"
        f"ANALYTICAL_JSON:\n{json.dumps(analytical.model_dump(), ensure_ascii=False)[:8000]}\n",
        system="JSON only. thesis must be one debatable sentence, not a quote.",
    )
    thesis_obj = _build_thesis(thesis_raw, inp, narrative, analytical)

    clips_raw = _run_stage(control=ctrl, engine_prompt=CLIP_DETECTION_PROMPT, excerpt=excerpt, meta=meta, label="clips")
    clips = _build_clips(clips_raw, inp)

    syn_raw = run_json_prompt(
        f"{ctrl}\n\n{SYNTHESIS_ENGINE_PROMPT}\n\n"
        f"NARRATIVE_JSON:\n{json.dumps(narrative.model_dump(), ensure_ascii=False)[:6000]}\n"
        f"ANALYTICAL_JSON:\n{json.dumps(analytical.model_dump(), ensure_ascii=False)[:6000]}\n",
        system="JSON only.",
    )
    synthesis = _build_synthesis(syn_raw, narrative, analytical)

    actions = _default_actions(thesis_obj.thesis, synthesis)
    mode = _select_strategist_mode(inp, analytical, clips)
    strategist_input = {
        "mode": mode,
        "title": inp.title,
        "show": (inp.entities[0] if inp.entities else ""),
        "transcript": excerpt,
        "claims": analytical.claims,
        "topics": inp.topics,
        "segments": [c.text for c in clips],
        "thesis": thesis_obj.thesis,
        "synthesis": synthesis.model_dump(),
    }
    strategist_raw = run_json_prompt(
        f"{MASTER_STRATEGIST_PROMPT}\n\nINPUT_JSON:\n{json.dumps(strategist_input, ensure_ascii=False)[:16000]}",
        system="You are a strict JSON emitter. Return valid JSON only.",
    )
    strategist_report = _build_strategist_report(
        data=strategist_raw,
        inp=inp,
        classification=classification,
        thesis_obj=thesis_obj,
        narrative=narrative,
        analytical=analytical,
        synthesis=synthesis,
        clips=clips,
    )
    strategist_report = _apply_mode_profile(
        strategist_report=strategist_report,
        mode=mode,
        inp=inp,
        analytical=analytical,
        clips=clips,
    )

    return _assemble_validated_report(
        classification=classification,
        thesis_obj=thesis_obj,
        narrative=narrative,
        analytical=analytical,
        synthesis=synthesis,
        clips=clips,
        actions=actions,
        strategist_report=strategist_report,
        max_retries=max_retries,
        inp=inp,
        control=ctrl,
    )
