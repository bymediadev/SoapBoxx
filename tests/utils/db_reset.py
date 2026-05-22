"""Reset V1 tables between tests (Postgres only)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

# Order respects FK dependencies
_TRUNCATE_ORDER = (
    "system_events",
    "episode_translations",
    "podcast_taxonomy_map",
    "episode_features",
    "transcript_segments",
    "episodes",
    "taxonomy_nodes",
    "podcasts",
)


def reset_v1_tables(engine: Engine) -> None:
    with engine.connect() as conn:
        for table in _TRUNCATE_ORDER:
            conn.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
        conn.commit()
