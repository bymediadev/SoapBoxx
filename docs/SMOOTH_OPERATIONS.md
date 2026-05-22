# SoapBoxx — smooth operations runbook

One-page checklist: local dev, deploy, Lovable, staying up to date.

## Architecture (locked)

```text
Lovable UI  →  FastAPI (truth)  →  Postgres (memory)
                  ↑
            RSS re-ingest (cron)
```

---

## 1. Local (every dev session)

```powershell
cd c:\Users\yasuk\SoapBoxx
.\.venv\Scripts\Activate.ps1
docker compose -f docker-compose.v1.yml up -d
alembic upgrade head
uvicorn main:app --reload --port 8000
```

| Check | URL / command |
|-------|----------------|
| Health | http://127.0.0.1:8000/health → `"status": "ok"` |
| API docs | http://127.0.0.1:8000/docs |
| Full V1 tests | `pytest tests/test_day1_foundation.py tests/test_day2_core_entities.py tests/test_day3_rss_ingestion.py tests/test_day4_transcription.py tests/test_day5_feature_extraction.py tests/test_day6_taxonomy.py tests/test_day7_translation.py tests/test_system_state.py tests/test_lovable_library_api.py tests/test_system_health.py -q` |

---

## 2. Railway deploy

| Step | Action |
|------|--------|
| 1 | Postgres plugin on API service |
| 2 | Variables: `DATABASE_URL` (auto), `SOAPBOXX_CORS_ORIGINS=https://soapboxx.lovable.app` |
| 3 | Optional: `RAILPACK_START_CMD=python start.py` |
| 4 | Builder: **Railpack**; push `production`; redeploy **without cache** |
| 5 | Verify: `curl https://YOUR-APP.up.railway.app/health` |

Config files: `railpack.json`, `start.py`, `Procfile`, `railway.toml`  
Troubleshooting: [`RAILWAY_DEPLOY.md`](RAILWAY_DEPLOY.md)

---

## 3. Lovable frontend

| Step | Action |
|------|--------|
| 1 | `VITE_API_URL=https://YOUR-APP.up.railway.app` |
| 2 | Remove all mock library numbers |
| 3 | Wire endpoints per [`LOVABLE_INTEGRATION.md`](LOVABLE_INTEGRATION.md) |

---

## 4. Stay up to date (RSS)

| Task | Command |
|------|---------|
| Add feeds from file | Edit `data/seed_feeds.txt` → `python scripts/seed_feeds_from_file.py` |
| Re-sync all known feeds | `python scripts/sync_all_feeds.py` |
| Single feed (API) | `POST /ingest/rss` `{ "rss_url": "..." }` |

Schedule on Railway: **separate cron service** — see [`RAILWAY_POSTGRES_CRON.md`](RAILWAY_POSTGRES_CRON.md).

---

## 5. Episode pipeline (per episode)

```text
ingested/queued → POST /episodes/{id}/transcribe → POST .../features → POST .../translate
```

Status: `GET /episodes/{id}/state`  
Activity: `GET /system/activity`  
Patterns: `GET /insights/patterns/weekly`

---

## 6. What we skip (V1)

- Spotify API  
- Supabase (unless you need auth later)  
- Desktop PyQt on Railway  

---

## 7. Quick fixes

| Symptom | Fix |
|---------|-----|
| Railpack no start command | Push `start.py` + `railpack.json`; set `RAILPACK_START_CMD` |
| PortAudio crash | `libportaudio2` in `railpack.json`; lazy `backend/__init__.py` |
| requirements-v1-api missing | Use inlined deps in `requirements.txt`; no custom install step |
| Health degraded | Add Postgres; Redis optional |
