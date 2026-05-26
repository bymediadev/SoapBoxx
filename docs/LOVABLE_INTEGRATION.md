# SoapBoxx — Lovable frontend + V1 API

**Frontend:** [https://soapboxx.lovable.app](https://soapboxx.lovable.app) (hosted on Lovable, independent deploy)  
**Backend:** [https://soapboxx-production.up.railway.app](https://soapboxx-production.up.railway.app) (FastAPI + Postgres + Redis)

**Status:** Lovable is wired to the live API via `soapboxxApi` only — **no mock data**. Copy [`lovable/api-client.ts`](lovable/api-client.ts) into the Lovable repo as `src/lib/soapboxx-api.ts`.

The Lovable app is the **UI shell**. The API is the **system of record**. They deploy separately; every screen fetches over HTTPS.

---

## Architecture

```text
soapboxx.lovable.app  ──HTTPS──►  soapboxx-production.up.railway.app
                                      │
                                      ▼
                                 Postgres (podcasts, episodes, reports)
                                      ▲
                                 POST /ingest/rss
```

- Lovable does **not** store the library database.
- Ingestion and episode reports live on the API host.
- Re-deploying Lovable only changes UI; data persists in Postgres.

---

## 1. Deploy the API (required)

Expose FastAPI publicly, e.g. Railway, Render, Fly.io, or a VPS:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Environment:

| Variable | Example |
|----------|---------|
| `DATABASE_URL` | `postgresql+psycopg2://...` |
| `REDIS_URL` | `redis://...` |
| `SOAPBOXX_CORS_ORIGINS` | `https://soapboxx.lovable.app` |

Run migrations on deploy: `alembic upgrade head`.

Verify: `GET https://YOUR_API/health` → `"status": "ok"`.

---

## 2. Lovable environment variable

Canonical client: [`lovable/api-client.ts`](lovable/api-client.ts) → `src/lib/soapboxx-api.ts`.

| Setting | Behavior |
|---------|----------|
| *(unset)* | Defaults to `https://soapboxx-production.up.railway.app` |
| `VITE_API_URL=http://127.0.0.1:8000` | Local FastAPI (`uvicorn main:app --reload --port 8000`) |

Example (Lovable **Settings → Environment** or `.env`):

```text
VITE_API_URL=http://127.0.0.1:8000
```

See [`lovable/.env.lovable.example`](lovable/.env.lovable.example).

All screens import `soapboxxApi` from that file — do not duplicate `fetch` URLs in components.

---

## 3. System state layer (motion, not just rows)

```text
RSS → Ingestion → Pipeline → Postgres
                      ↓
              system_events + pipeline_status
                      ↓
                 Lovable UI
```

UI must show **state**, not only clean CRUD:

| Concept | API |
|---------|-----|
| Lifecycle per episode | `GET /episodes/{id}/state` |
| Counts by state | `GET /pipeline/status` |
| Activity feed | `GET /system/activity` |
| Weekly patterns | `GET /insights/patterns/weekly` |

### Episode lifecycle (`pipeline_status`)

```text
new → ingested → queued → transcribing → measured → ready
                              ↓
                           failed
```

After RSS ingest, episodes start as **`queued`**. Ingest emits `ingest.started` / `ingest.completed` / `episode.ingested` events.

---

## 4. Endpoint map (UI → `soapboxxApi`)

| Lovable screen | `soapboxxApi` method | Notes |
|----------------|----------------------|--------|
| **Library home** | `libraryHome()` | One bundle: stats, pipeline, tree, episodes, activity, patterns |
| **Ingestion** | `ingestRss(url)` then `libraryHome()` | RSS form |
| **Episodes index** | `libraryEpisodes(limit)` or rows from `libraryHome()` | Filter by `podcast_id` when needed |
| **Shows** | `listPodcasts()` and/or `libraryTree()` | Tree embeds shows per taxonomy branch |
| **Insights / patterns** | `weeklyPatterns()` or `libraryHome().patterns` | Weekly structural snapshot |
| **Episode detail** | `getEpisode(id)`, `episodeState(id)`, `getTranslation(id)` | Report view |
| **Run pipeline** | `processEpisode(id, {})` | Empty body; reuses stored transcript when possible |
| **Metrics on detail** | `processEpisode(id, {})` → `steps.find(s => s.step === "features")?.metrics` | Not on `getTranslation`; call once when needed |
| Health check | `health()` | Optional dev banner |

**Episode detail rules**

- `getTranslation` → 404 means “not processed yet”; show **Run pipeline**.
- Default pipeline: `processEpisode(id, {})` — never `force_retranscribe` in the main UI.
- Seven metrics only from the **features** step of `processEpisode` (or session cache after one call).

---

## 4. Auto-update (RSS)

The UI does not need to “download a database.”

1. **On demand:** Ingestion page calls `POST /ingest/rss` when the user adds a feed. New episodes are auto-dispatched into the processing queue.
2. **Scheduled (recommended):** On the API host, cron or Celery beat every N hours:
   - For each `podcasts.rss_url`, call `ingest_rss_feed(db, url)` and auto-dispatch only newly created episode IDs.
3. Lovable **refetches** `GET /library/stats` and `GET /library/episodes` on interval or on focus.

Auto-dispatch only finishes end to end if a queue worker is running (`python scripts/run_celery_worker.py` locally, or the `soapboxx-worker` Railway service).

That gives you an independently updating system without redeploying the frontend.

---

## 5. CORS

The API allows:

- Origins in `SOAPBOXX_CORS_ORIGINS`
- Any `https://*.lovable.app` preview URL (regex)

If the browser blocks requests, add your exact Lovable preview URL to `SOAPBOXX_CORS_ORIGINS`.

---

## 6. Re-wire or fix Lovable

If a preview regresses to mock data, use the one-shot prompt: [`lovable/LOVABLE_FREE_CHAT_PROMPT.md`](lovable/LOVABLE_FREE_CHAT_PROMPT.md) (paste prompt + full `api-client.ts` in one message).

---

## 7. Local dev loop

```powershell
# Terminal 1 — API
docker compose -f docker-compose.v1.yml up -d
alembic upgrade head
uvicorn main:app --reload --port 8000

# Terminal 2 — point Lovable preview or local Vite at API
# VITE_API_URL=http://127.0.0.1:8000
```

---

## 8. Security (before public launch)

- Add API key or JWT when moving off single-user demo.
- Do not expose Postgres publicly; only the API port.
- Rate-limit `POST /ingest/rss`.

---

## Quick checklist

- [x] API deployed (`soapboxx-production.up.railway.app`)
- [ ] `alembic upgrade head` on production DB after schema changes
- [ ] `SOAPBOXX_CORS_ORIGINS` includes `https://soapboxx.lovable.app`
- [x] Lovable uses `soapboxxApi` only (no mock library data)
- [ ] Optional: `VITE_API_URL` for local backend dev
- [ ] RSS re-ingest scheduled on server (optional but recommended)
