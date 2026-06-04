"""Layer 4 — curated report views (producer, actions) from stored measurements + coaching."""

from __future__ import annotations

from typing import Any, List, Optional

from backend.models import Episode, EpisodeFeatures
from backend.services.coaching_report_service import (
    CoachingReport,
    build_coaching_report,
    _DISCLAIMER,
)

# Markers from tests/fixtures/demo pipeline — not valid production transcripts.
_DEMO_TRANSCRIPT_MARKERS = (
    "welcome to the soapboxx test episode",
    "soapboxx test episode",
    "soapboxx demo podcast",
)


def detect_transcript_warning(
    episode: Episode,
    *,
    transcript: Optional[str] = None,
) -> Optional[dict[str, str]]:
    """
    Return a user-visible warning when stored transcript is likely demo/fixture text.
    """
    text = (transcript or episode.full_transcript or "").strip().lower()
    if not text:
        return {
            "code": "missing_transcript",
            "message": "No transcript stored — run the pipeline on episode audio before trusting this report.",
        }
    for marker in _DEMO_TRANSCRIPT_MARKERS:
        if marker in text:
            title = (episode.title or "").strip()
            return {
                "code": "demo_transcript",
                "message": (
                    "This report was built from demo/sample transcript text, not this episode's audio. "
                    f"Re-run the pipeline with real STT to measure «{title}»."
                ),
            }
    return None


def _features_measurements(features: EpisodeFeatures) -> dict[str, Any]:
    return {
        "hook_length_seconds": features.hook_length_seconds,
        "intro_length_seconds": features.intro_length_seconds,
        "question_count": features.question_count,
        "speaking_turns": features.speaking_turns,
        "host_guest_ratio": features.host_guest_ratio,
        "topic_shift_count": features.topic_shift_count,
        "cta_present": features.cta_present,
    }


def _structure_label(report: CoachingReport, template_id: str) -> str:
    playbook = report.template_playbook or {}
    form = (playbook.get("form") or "").strip()
    if form:
        return form
    labels = {
        "A": "Guest-led interview",
        "B": "Question-driven interview",
        "C": "Narrative documentary",
    }
    return labels.get(template_id, f"Template {template_id}")


def _dedupe_lines(lines: List[str], limit: int) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for line in lines:
        t = (line or "").strip()
        if not t:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
        if len(out) >= limit:
            break
    return out


def build_editorial_readout(report: CoachingReport) -> dict[str, List[str]]:
    """
    Single interpretation block: what happened, why it matters, what to try next.
    Merges listener experience, trade-offs, and playbook without repeating structure labels.
    """
    playbook = report.template_playbook or {}
    what_happening = _dedupe_lines(
        list(report.structural_identity[:1])
        + list(report.listener_experience[:3]),
        4,
    )
    why_it_matters = _dedupe_lines(
        list(report.editorial_tradeoffs[:2])
        + ([playbook.get("feels_like")] if playbook.get("feels_like") else [])
        + list(report.what_this_means[:1]),
        3,
    )
    what_to_try: List[str] = []
    for item in playbook.get("review_these") or []:
        what_to_try.append(str(item).strip())
    pn = report.producer_notes or {}
    for flag in pn.get("edit_flags") or []:
        what_to_try.append(str(flag).strip())
    what_to_try = _dedupe_lines(what_to_try, 5)

    if not what_happening and report.listener_experience:
        what_happening = _dedupe_lines(report.listener_experience, 3)
    if not why_it_matters and report.editorial_tradeoffs:
        why_it_matters = _dedupe_lines(report.editorial_tradeoffs, 2)

    return {
        "what_happening": what_happening,
        "why_it_matters": why_it_matters,
        "what_to_try_next": what_to_try,
    }


def build_producer_report(
    episode: Episode,
    features: EpisodeFeatures,
    report: CoachingReport,
    template_id: str,
) -> dict[str, Any]:
    """Layer 4 — signals, structure class, one editorial readout (no schema/%/duplicate sections)."""
    return {
        "episode_id": int(episode.id),
        "title": episode.title,
        "disclaimer": _DISCLAIMER,
        "transcript_warning": detect_transcript_warning(episode),
        "structure_label": _structure_label(report, template_id),
        "template_id": template_id,
        "measurements": _features_measurements(features),
        "editorial_readout": build_editorial_readout(report),
        "transcript_limitations": list(report.transcript_limitations[:2]),
    }


def build_actions_report(
    episode: Episode,
    report: CoachingReport,
) -> dict[str, Any]:
    """Layer 4B — next-episode actions (editorial coach)."""
    readout = build_editorial_readout(report)
    actions: List[dict[str, str]] = []
    for i, text in enumerate(readout["what_to_try_next"]):
        actions.append(
            {
                "id": f"action-{i}",
                "category": "next_episode",
                "priority": "high" if i < 2 else "medium",
                "text": text,
            }
        )

    keep = _dedupe_lines(
        (report.template_playbook or {}).get("how_its_built") or [],
        3,
    )
    if not keep:
        keep = _dedupe_lines(readout["what_happening"], 2)

    return {
        "episode_id": int(episode.id),
        "title": episode.title,
        "transcript_warning": detect_transcript_warning(episode),
        "actions": actions[:7],
        "keep_patterns": keep,
    }


def producer_report_for_episode(
    db,
    episode_id: int,
) -> Optional[dict[str, Any]]:
    episode = db.get(Episode, episode_id)
    features = db.get(EpisodeFeatures, episode_id)
    if not episode or not features:
        return None
    from backend.models import EpisodeTranslation

    row = db.get(EpisodeTranslation, episode_id)
    template_id = row.template_id if row else "?"
    report = build_coaching_report(db, features)
    return build_producer_report(episode, features, report, template_id)


def actions_report_for_episode(db, episode_id: int) -> Optional[dict[str, Any]]:
    episode = db.get(Episode, episode_id)
    features = db.get(EpisodeFeatures, episode_id)
    if not episode or not features:
        return None
    report = build_coaching_report(db, features)
    return build_actions_report(episode, report)
