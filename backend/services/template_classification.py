"""Template classification + transcript reliability (single source of truth)."""

from __future__ import annotations

from typing import List

from backend.models import EpisodeFeatures

# Minimum labeled handoffs to treat question density as interview structure.
_MIN_INTERVIEW_TURNS = 4


def has_speaker_diarization(f: EpisodeFeatures) -> bool:
    return int(f.speaking_turns or 0) >= _MIN_INTERVIEW_TURNS


def template_id_from_features(f: EpisodeFeatures) -> str:
    """
    A: extended opening
    B: question-led interview (requires detected handoffs)
    C: narrative / diary / produced story
    """
    hook = float(f.hook_length_seconds or 0)
    intro = float(f.intro_length_seconds or 0)
    questions = int(f.question_count or 0)
    turns = int(f.speaking_turns or 0)

    if intro >= 120 or hook >= 90:
        return "A"
    if questions >= 12 and turns >= _MIN_INTERVIEW_TURNS:
        return "B"
    return "C"


def is_rhetorical_question_heavy(f: EpisodeFeatures) -> bool:
    """Many ? marks but no diarization — typical of diary/explainer narration."""
    return int(f.question_count or 0) >= 12 and not has_speaker_diarization(f)


def transcript_limitation_notes(f: EpisodeFeatures) -> List[str]:
    notes: List[str] = []
    if int(f.speaking_turns or 0) == 0:
        notes.append(
            "Speaker labels not detected in transcript — question marks may be "
            "rhetorical (narration), not interview pivots; talk-share is unavailable."
        )
    elif is_rhetorical_question_heavy(f):
        notes.append(
            "Few speaker handoffs despite many question marks — structure may read "
            "as diary or explainer narration rather than Q&A interview."
        )
    return notes


def effective_form_label(template_id: str, f: EpisodeFeatures) -> str:
    if is_rhetorical_question_heavy(f):
        return "Diary / explainer narration (structural pattern)"
    if template_id == "A":
        return "Extended-opening structure"
    if template_id == "B":
        return "Question-led interview (structural pattern)"
    return "Narrative documentary (structural pattern)"
