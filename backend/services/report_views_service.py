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


def build_producer_report(
    episode: Episode,
    features: EpisodeFeatures,
    report: CoachingReport,
    template_id: str,
) -> dict[str, Any]:
    """Layer 4A — metrics + structure + patterns; no schema/cohort/percentile blocks."""
    playbook = report.template_playbook or {}
    patterns = list(report.listener_experience[:5])
    if not patterns and report.what_this_means:
        patterns = list(report.what_this_means[:4])

    leverage = list(report.leverage_points[:3])
    tradeoffs = list(report.editorial_tradeoffs[:2])

    return {
        "episode_id": int(episode.id),
        "title": episode.title,
        "disclaimer": _DISCLAIMER,
        "transcript_warning": detect_transcript_warning(episode),
        "structure_label": _structure_label(report, template_id),
        "template_id": template_id,
        "structural_identity": list(report.structural_identity[:4]),
        "measurements": _features_measurements(features),
        "patterns": patterns,
        "leverage_points": leverage,
        "editorial_tradeoffs": tradeoffs,
        "transcript_limitations": list(report.transcript_limitations[:3]),
    }


def build_actions_report(
    episode: Episode,
    report: CoachingReport,
) -> dict[str, Any]:
    """Layer 4B — next-episode actions (editorial coach)."""
    actions: List[dict[str, str]] = []
    seen: set[str] = set()

    def _add(category: str, priority: str, text: str, prefix: str) -> None:
        t = (text or "").strip()
        if not t or t.lower() in seen:
            return
        seen.add(t.lower())
        actions.append(
            {
                "id": f"{prefix}-{len(actions)}",
                "category": category,
                "priority": priority,
                "text": t,
            }
        )

    playbook = report.template_playbook or {}
    for item in playbook.get("review_these") or []:
        _add("replay", "high", str(item), "review")

    pn = report.producer_notes or {}
    for flag in pn.get("edit_flags") or []:
        _add("edit", "medium", str(flag), "edit")

    for item in report.editorial_tradeoffs or []:
        _add("awareness", "low", str(item), "tradeoff")

    if len(actions) < 3:
        for item in (playbook.get("how_its_built") or [])[:2]:
            _add("structure", "medium", f"On your next episode, notice: {item}", "built")

    keep: List[str] = []
    for item in (playbook.get("how_its_built") or [])[:3]:
        t = str(item).strip()
        if t:
            keep.append(t)
    if not keep:
        keep = list(report.structural_identity[:2])

    return {
        "episode_id": int(episode.id),
        "title": episode.title,
        "transcript_warning": detect_transcript_warning(episode),
        "actions": actions[:7],
        "keep_patterns": keep[:4],
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
