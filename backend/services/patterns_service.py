"""Weekly pattern snapshot (v1 — simple aggregates, no LLM)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import Episode, EpisodeFeatures


def get_weekly_patterns(db: Session) -> Dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=7)

    measured_q = (
        select(EpisodeFeatures)
        .join(Episode, Episode.id == EpisodeFeatures.episode_id)
        .where(Episode.created_at >= since)
    )
    features = db.execute(measured_q).scalars().all()

    episodes_measured = len(features)
    if not features:
        return {
            "period_days": 7,
            "episodes_measured": 0,
            "patterns": [],
            "summary": "No episodes measured in the last 7 days.",
        }

    avg_questions = sum(int(f.question_count or 0) for f in features) / len(features)
    avg_turns = sum(int(f.speaking_turns or 0) for f in features) / len(features)
    cta_rate = sum(1 for f in features if f.cta_present) / len(features)
    guest_led = sum(1 for f in features if (f.host_guest_ratio or 0.5) < 0.45) / len(
        features
    )

    patterns: List[Dict[str, Any]] = []

    if guest_led >= 0.5:
        patterns.append(
            {
                "id": "guest_dominance",
                "label": "Guest-led conversations rising",
                "detail": f"{guest_led:.0%} of measured episodes show guest-heavy talk share this week.",
            }
        )
    if avg_questions >= 8:
        patterns.append(
            {
                "id": "high_question_density",
                "label": "High question density",
                "detail": f"Average {avg_questions:.1f} questions per episode across the library week.",
            }
        )
    if cta_rate >= 0.4:
        patterns.append(
            {
                "id": "cta_common",
                "label": "CTAs frequently present",
                "detail": f"{cta_rate:.0%} of episodes include a detectable call-to-action.",
            }
        )

    if not patterns:
        patterns.append(
            {
                "id": "stable_structure",
                "label": "Stable structural mix",
                "detail": "No dominant shift in talk ratio or question density this week.",
            }
        )

    ingested_count = int(
        db.scalar(
            select(func.count())
            .select_from(Episode)
            .where(Episode.created_at >= since)
        )
        or 0
    )

    return {
        "period_days": 7,
        "episodes_ingested": ingested_count,
        "episodes_measured": episodes_measured,
        "patterns": patterns,
        "summary": (
            f"{episodes_measured} episodes measured; "
            f"{len(patterns)} structural pattern(s) surfaced."
        ),
    }
