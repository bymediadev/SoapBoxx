# V1 Day 4 — Transcription pipeline

## Endpoint

`POST /episodes/{id}/transcribe`

Optional body (paste transcript for tests / offline):

```json
{ "transcript": "Host: Welcome...\nGuest: Thanks for having me." }
```

Without body: downloads `audio_url` and runs STT when configured.

Response: `episode_id`, `segment_count`, `transcript_length`

- Stores `full_transcript` on `episodes`
- Stores rows in `transcript_segments` (speaker, start/end, text)

## Worker

`backend/workers/tasks.py` — Celery task `transcribe_episode` (async path).

## Tests

```powershell
pytest tests/test_day4_transcription.py -v
```

## Next

Day 5 — seven metrics in `episode_features`
