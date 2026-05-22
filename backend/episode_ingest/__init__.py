"""
Episode ingestion — pull published or local episodes into one transcript + metadata shape.

Desktop Coach tab and CLI use this instead of the Studio recording path.
"""

from .ingest import (
    IngestResult,
    ingest_from_audio_file,
    ingest_from_text,
    ingest_from_transcript_file,
    ingest_from_youtube_url,
)

__all__ = [
    "IngestResult",
    "ingest_from_youtube_url",
    "ingest_from_transcript_file",
    "ingest_from_audio_file",
    "ingest_from_text",
]
