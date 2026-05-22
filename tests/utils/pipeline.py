"""V1 pipeline helpers for tests."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from backend.services.feature_service import run_feature_extraction
from backend.services.rss_service import ingest_rss_xml
from backend.services.transcription_service import transcribe_episode
from backend.services.translation_service import run_translation

FIXTURE_TRANSCRIPT = (
    Path(__file__).resolve().parents[1] / "fixtures" / "sample_transcript.txt"
)
FIXTURE_RSS = Path(__file__).resolve().parents[1] / "fixtures" / "sample_rss.xml"


def seed_episode_with_transcript(db: Session) -> int:
    xml = FIXTURE_RSS.read_text(encoding="utf-8")
    ing = ingest_rss_xml(db, xml, rss_url="https://example.com/pipe-feed")
    episode_id = ing.episode_ids[0]
    text = FIXTURE_TRANSCRIPT.read_text(encoding="utf-8")
    transcribe_episode(db, episode_id, transcript=text)
    return episode_id


def run_all_steps(db: Session, episode_id: int) -> None:
    run_feature_extraction(db, episode_id)
    run_translation(db, episode_id)
