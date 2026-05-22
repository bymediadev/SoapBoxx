"""
SoapBoxx Phase 1 — measurement engine (local SQLite + metrics + benchmarks + rule-based tier).

Not Spotify/YouTube ingestion. Reuses ``transcriber`` and ``llm_service`` / OpenAI coach path.
"""

from .pipeline import process_episode

__all__ = ["process_episode"]
