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

Second terminal for queued episode processing after RSS ingest:

```powershell
cd c:\Users\yasuk\SoapBoxx
.\.venv\Scripts\Activate.ps1
python scripts/run_celery_worker.py
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
| 3 | Dashboard **Build command**: empty; start from `railway.toml` (`python start.py`) |
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
| Re-sync all known feeds | `python scripts/sync_all_feeds.py` (new episodes auto-dispatch into processing) |
| Single feed (API) | `POST /ingest/rss` `{ "rss_url": "..." }` |

Schedule on Railway: **separate cron service** — see [`RAILWAY_POSTGRES_CRON.md`](RAILWAY_POSTGRES_CRON.md).

---

## 5. Episode pipeline (per episode)

Single call (recommended):

```text
POST /episodes/{id}/process
```

Or step-by-step: `transcribe` → `features` → `translate`.

Pre-flight: `GET /episodes/{id}/state` (`steps.transcribed`, `next_action`).

### `POST /process` body (Railway)

| Body | Use when | Railway safe? |
|------|----------|----------------|
| `{}` | Transcript already in Postgres; refresh 7 metrics + template insight | Yes (seconds) |
| `{ "transcript": "..." }` | Paste transcript; skip audio download/STT | Yes |
| `{ "force_retranscribe": true }` | Re-STT from `audio_url` | Often **no** on full episodes (proxy timeout); short clips/dev only |

Default: `force_retranscribe=false` **skips** STT when `full_transcript` exists — intentional, not a bug. Response `steps[0].reason` is `existing_transcript` when skipped; top-level `transcript_source` is `existing | stt | pasted`.

Deploy logs show step timing: `pipeline episode_id=N step=transcribe skipped duration_ms=...`

Env: `SOAPBOXX_STT_HTTP_TIMEOUT` (default 300s) bounds Groq/OpenAI STT HTTP reads.

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
| Railpack no start command | Push `start.py` + `railway.toml`; clear dashboard build command; optional `RAILPACK_START_CMD=python start.py` |
| Build + start both `python start.py` | Clear **Build command** in dashboard; keep start in `railway.toml` only |
| `can't open file '/app/start.py'` | Remove `steps.build` override from `railpack.json`; clear build cache — [`RAILWAY_502_FIX.md`](RAILWAY_502_FIX.md) |
| `ModuleNotFoundError: backend` in `wait_for_db.py` | Pull latest `production`; script prepends repo root to `sys.path` |
| PortAudio crash | `libportaudio2` in `railpack.json`; lazy `backend/__init__.py` |
| requirements-v1-api missing | Use inlined deps in `requirements.txt`; no custom install step |
| Health degraded | Add Postgres; Redis optional |
