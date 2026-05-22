# V1 Day 3 — RSS ingestion

## Endpoint

`POST /ingest/rss`

```json
{
  "rss_url": "https://feeds.example.com/podcast.xml",
  "podcast_id": null
}
```

Response: `podcast_id`, `episodes_created`, `episodes_skipped`, `episode_ids`

- Fetches feed (HTTP)
- Creates podcast from channel title if new (matched by `rss_url`)
- Creates episodes with **metadata only** (title, description, audio_url, published_at, guid, `raw_rss_json`)
- Parser: **feedparser** — see [`V1_INGESTION_LAYER.md`](V1_INGESTION_LAYER.md)
- Re-ingest skips episodes with same `podcast_id` + `guid`

## Migration

```powershell
alembic upgrade head   # 002 guid, 004 description + raw_rss_json
```

## Tests

```powershell
pytest tests/test_day3_rss_ingestion.py -v
```

## Next

Day 4 — transcription + `transcript_segments`
