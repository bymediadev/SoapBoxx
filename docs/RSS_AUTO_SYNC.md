# RSS auto-sync (backend — not Lovable)

Scheduled re-ingest lives in the **SoapBoxx API repo**. The Lovable app only calls `POST /ingest/rss` on demand; it cannot run Celery or cron.

## Already implemented

| Piece | Location |
|-------|----------|
| Re-ingest all feeds | `sync_saved_rss_feeds()` in `backend/services/rss_service.py` |
| Celery task | `soapboxx.sync_rss_feeds` in `backend/workers/tasks.py` |
| Beat schedule | `backend/workers/celery_app.py` when `RSS_SYNC_MINUTES > 0` (default **180**) |
| Worker + embedded beat | `python scripts/run_celery_worker.py` (`-B` unless `SOAPBOXX_ENABLE_BEAT=0`) |
| Daily cron (no Celery) | `soapboxx-sync` service → `railway.cron.toml` → `scripts/sync_all_feeds.py` |
| HTTP cron (optional) | `POST /pipeline/sync-feeds` + `X-Cron-Secret` (see below) |

Behavior matches what Lovable described: for each `podcasts.rss_url`, `ingest_rss_feed()` (idempotent), then `process_episode_task.delay()` only for **new** episode IDs.

---

## Option A — Celery beat on worker (recommended)

1. Railway services: **API** + **Redis** + **Postgres** + **`soapboxx-worker`** ([`railway.worker.toml`](../railway.worker.toml)).
2. Worker variables: `DATABASE_URL`, `REDIS_URL`, `GROQ_API_KEY` (for STT).
3. Keep `SOAPBOXX_ENABLE_BEAT` unset (beat enabled by default).
4. Optional: `RSS_SYNC_MINUTES=120` for every 2 hours (min schedule interval in beat config is 5 minutes).

Worker logs should show beat firing `soapboxx.sync_rss_feeds` and `soapboxx.process_pending_queue`.

---

## Option B — Railway cron service

**Without Celery:** use [`railway.cron.toml`](../railway.cron.toml) on service `soapboxx-sync`:

- `python scripts/sync_all_feeds.py`
- Default schedule: daily `0 6 * * *`

Same `DATABASE_URL` as API. For processing new episodes you still need a worker or run backlog via `POST /pipeline/dispatch-backlog`.

**HTTP cron on API:** set `SOAPBOXX_CRON_SECRET` on the API service, then schedule:

```http
POST https://soapboxx-production.up.railway.app/pipeline/sync-feeds
X-Cron-Secret: <your-secret>
```

Returns `episodes_created`, `episodes_dispatched`, per-podcast `results`. Disabled when secret is unset (503).

---

## Local dev

```powershell
# One-shot (same as beat task body)
python scripts/sync_all_feeds.py

# Worker + beat
python scripts/run_celery_worker.py
```

---

## Env reference

| Variable | Default | Role |
|----------|---------|------|
| `RSS_SYNC_MINUTES` | `180` | Beat interval for `soapboxx.sync_rss_feeds` (`0` = off) |
| `PIPELINE_DRAIN_MINUTES` | `5` | Beat interval for backlog drain |
| `PIPELINE_SYNC_BATCH_SIZE` | `5` | Extra backlog drain after each RSS sync |
| `SOAPBOXX_ENABLE_BEAT` | on | `0` = worker without `-B` |
| `SOAPBOXX_CRON_SECRET` | — | Enables `POST /pipeline/sync-feeds` |

See also [`RAILWAY_POSTGRES_CRON.md`](RAILWAY_POSTGRES_CRON.md).
