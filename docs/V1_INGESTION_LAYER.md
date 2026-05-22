# V1 — Podcast ingestion layer (source only)

**Scope:** Collect podcast + episode metadata from RSS. No transcription, analysis, or UI.

## Endpoint

`POST /ingest/rss`

```json
{ "rss_url": "https://feeds.example.com/show.xml" }
```

Response:

```json
{
  "podcast_id": 1,
  "episodes_created": 12,
  "episodes_skipped": 3,
  "episode_ids": [1, 2, 3]
}
```

## Service

`backend/services/rss_service.py` — uses **feedparser** for RSS/Atom.

Extracts and stores:

| Entity | Fields |
|--------|--------|
| Podcast | `name`, `description`, `rss_url` |
| Episode | `title`, `description`, `audio_url`, `published_at`, `guid`, `raw_rss_json` |

## Idempotency

1. Match by `(podcast_id, guid)` when GUID present.
2. Else match by `(podcast_id, title, published_at)`.
3. Re-ingest skips existing rows (increments `episodes_skipped`).

## Migration

```powershell
pip install -r requirements-v1-api.txt
alembic upgrade head   # 004: description + raw_rss_json
```

## Tests

```powershell
pytest tests/test_day3_rss_ingestion.py -v
```

## Downstream pipeline (not this layer)

Transcribe → features → translate are separate endpoints on `/episodes/{id}/…`.
