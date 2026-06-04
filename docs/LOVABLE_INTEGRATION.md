# SoapBoxx — Lovable frontend + V1 API

**Frontend:** [https://soapboxx.lovable.app](https://soapboxx.lovable.app) (hosted on Lovable, independent deploy)  
**Backend:** [https://soapboxx-production.up.railway.app](https://soapboxx-production.up.railway.app) (FastAPI + Postgres + Redis)

**Status:** [soapboxx.lovable.app](https://soapboxx.lovable.app) matches bundled `/ui/` (3-column home, paginated episodes, coaching report v2). API via `soapboxxApi` only — **no mock data**. Canonical client: [`lovable/api-client.ts`](lovable/api-client.ts).

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
| **Ingestion** | `searchPodcasts(q)` → `ingestRss(rss_url)` or paste URL | Name search resolves RSS via iTunes directory |
| **Episodes index** | `libraryEpisodes(limit)` or rows from `libraryHome()` | Filter by `podcast_id` when needed |
| **Shows** | `listPodcasts()` and/or `libraryTree()` | Tree embeds shows per taxonomy branch |
| **Insights / patterns** | `weeklyPatterns()` or `libraryHome().patterns` | Weekly structural snapshot |
| **Episode detail (default)** | `getProducerReport`, `getActionsReport`, `getEpisodeFeatures` | Tabs: Measurements / Structure / Next episode |
| **Episode detail (advanced)** | `getTranslation` → `report` | Collapsed “full coaching report” only |
| **Run pipeline** | `processEpisode(id, {})` | Empty body; poll state if `queued` |
| **Metrics on detail** | `getEpisodeFeatures(id)` | 404 until measured; do not run pipeline on open for metrics |
| **Batch** | `processNextBatch(10)` | Topbar “Process next 10” |
| **Episode table** | `libraryEpisodes({ limit, offset, podcast_id, status })` | Paginated; filters — not only `home.episodes` |
| Health check | `health()` | Poll ~30s; live/offline pill |

**Episode detail rules** (same as bundled `/ui/`)

- Parallel load: episode, state, features (404 OK), translation (404 OK).
- Render full `translation.report` when present (coaching report v2); legacy `insight_text` only if report empty.
- `getTranslation` → 404 means “not processed yet”; show **Run pipeline**.
- Default pipeline: `processEpisode(id, {})` — never `force_retranscribe` in the main UI.
- Layer contracts: [`LAYER_ARCHITECTURE.md`](LAYER_ARCHITECTURE.md)
- Visual reference: `static/v1-library/index.html` — Layer 4 tabs + Advanced details

---

## 4. Auto-update (RSS)

The UI does not need to “download a database.” **Scheduled re-ingest is backend-only** — implement in this SoapBoxx API repo, not in Lovable.

1. **On demand:** Lovable `POST /ingest/rss` when the user adds a feed (new episodes auto-dispatch when `AUTO_PROCESS_ON_INGEST=true`).
2. **Scheduled (already in API repo):** Celery beat task `soapboxx.sync_rss_feeds` → `sync_saved_rss_feeds()` re-ingests every stored `rss_url` and dispatches **new** episodes only. Default every **3h** (`RSS_SYNC_MINUTES=180`) on `soapboxx-worker` with embedded beat.
3. **Alternatives:** daily `soapboxx-sync` cron (`scripts/sync_all_feeds.py`) or `POST /pipeline/sync-feeds` with `X-Cron-Secret` — see [`RSS_AUTO_SYNC.md`](RSS_AUTO_SYNC.md).
4. Lovable may **refetch** library endpoints on focus/refresh; that is not a substitute for server-side RSS sync.

Processing requires **Redis + `soapboxx-worker`** (or manual `POST /pipeline/dispatch-backlog` / `POST /episodes/{id}/process`).

---

## 5. CORS

The API allows:

- Origins in `SOAPBOXX_CORS_ORIGINS`
- Any `https://*.lovable.app` preview URL (regex)

If the browser blocks requests, add your exact Lovable preview URL to `SOAPBOXX_CORS_ORIGINS`.

---

## 6. Re-wire or fix Lovable

If the UI drifts from `/ui/` or mock data returns, use [`lovable/LOVABLE_FREE_CHAT_PROMPT.md`](lovable/LOVABLE_FREE_CHAT_PROMPT.md) (paste prompt + full `api-client.ts` in one message). Audit pass: [`lovable/FRONTEND_AUDIT_PROMPT.md`](lovable/FRONTEND_AUDIT_PROMPT.md).

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
