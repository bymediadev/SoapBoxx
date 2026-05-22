# Lovable = presentation layer (not the system)

[soapboxx.lovable.app](https://soapboxx.lovable.app) is the **museum building**.  
Railway FastAPI + Postgres is the **archive and acquisition pipeline**.

## Layer map

| Layer | Owns | Does not own |
|-------|------|----------------|
| **Lovable** | Navigation, layout, library *feeling*, fetch + display | RSS logic, DB, pipeline, patterns math |
| **FastAPI** | Ingest, episodes, pipeline status, activity, patterns API | UI polish, routing UX |
| **Postgres** | Podcasts, episodes, metrics, events | — |
| **RSS / cron** | New episodes into DB | — |

Intelligence lives in **API + pipeline + DB** only.

## Keep Lovable when

- UI direction is already validated (tree, episodes, ingestion, taxonomy).
- You want fast iteration on *perception*, not on measurement code.
- You treat Lovable as **replaceable skin** wired to one public API URL.

## Drop or defer Lovable when

- You need one repo for API + UI + workers with no second deploy.
- You refuse a second platform — use **`/ui/`** on the same Railway service instead.

Both are valid; they are not mutually exclusive (`/ui/` = engineer console, Lovable = product shell).

## Priority order (avoid empty museum)

```text
1. Postgres + DATABASE_URL on Railway (reference from plugin)
2. /health 200 — API listening
3. RSS ingest → real rows in DB (POST /ingest/rss or seed + cron)
4. pipeline_status + system_events updating
5. Wire Lovable (or /ui/) to live endpoints — no mock counts
6. Polish / wow
```

UI without data = illusion. Data without UI = invisible. **Wire after data.**

## Minimum real system (Lovable becomes real)

**Done when a stranger can:**

1. Open [soapboxx.lovable.app](https://soapboxx.lovable.app) (or `/ui/`).
2. See **their** episode counts from `GET /library/stats` (not 1,492 unless true).
3. Submit an RSS URL → `POST /ingest/rss` → tree and activity update.
4. See episode rows with statuses from `GET /library/episodes` (`queued` → `measured` → `ready`).
5. See activity from `GET /system/activity` and patterns from `GET /insights/patterns/weekly`.

### API endpoints Lovable must call

| Screen | Endpoint |
|--------|----------|
| Header stats | `GET /library/stats`, `GET /pipeline/status` |
| Domain tree | `GET /library/tree` |
| Episode list | `GET /library/episodes` |
| Activity | `GET /system/activity` |
| Patterns | `GET /insights/patterns/weekly` |
| Ingest | `POST /ingest/rss` `{ "rss_url": "..." }` |

Base URL: `https://soapboxx-production.up.railway.app` (hardcode in Lovable if Secrets unavailable).

### Railway

- `DATABASE_URL` = **reference** from Postgres (never `127.0.0.1`).
- `SOAPBOXX_CORS_ORIGINS=https://soapboxx.lovable.app`

### Wire Lovable (free tier)

Paste [`lovable/LOVABLE_FREE_CHAT_PROMPT.md`](lovable/LOVABLE_FREE_CHAT_PROMPT.md) into project chat.

## Related docs

- [`LOVABLE_INTEGRATION.md`](LOVABLE_INTEGRATION.md)
- [`FREE_FRONTEND_OPTIONS.md`](FREE_FRONTEND_OPTIONS.md)
- [`RAILWAY_POSTGRES_CRON.md`](RAILWAY_POSTGRES_CRON.md)
- [`DATABASE_URL_LOCAL_VS_RAILWAY.md`](DATABASE_URL_LOCAL_VS_RAILWAY.md)
