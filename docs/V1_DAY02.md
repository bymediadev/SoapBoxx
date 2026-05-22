# V1 Day 2 — Podcast + episode core

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/podcasts` | Create show (source container) |
| GET | `/podcasts` | List shows |
| POST | `/episodes` | Create episode (metadata only) |
| GET | `/episodes/{id}` | Get one episode |

No transcription, metrics, or RSS on Day 2.

## Try it

```powershell
# API running: uvicorn main:app --port 8000

curl -X POST http://127.0.0.1:8000/podcasts -H "Content-Type: application/json" -d "{\"name\":\"My Show\"}"
curl http://127.0.0.1:8000/podcasts

curl -X POST http://127.0.0.1:8000/episodes -H "Content-Type: application/json" -d "{\"podcast_id\":1,\"title\":\"Episode 1\"}"
curl http://127.0.0.1:8000/episodes/1
```

## Tests

```powershell
pytest tests/test_day2_core_entities.py -v
```

## Next

Day 3 — `POST /ingest/rss`
