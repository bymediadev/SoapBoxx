# Railway — Postgres + cron sync

## Postgres + `DATABASE_URL`

1. Railway project → **New** → **Database** → **PostgreSQL** (or Add Postgres plugin to project).
2. On the **API service** → **Variables** → **Add reference** → `DATABASE_URL` from Postgres service.
3. Redeploy API service. `start.py` runs `alembic upgrade head` then uvicorn.
4. Verify: `GET https://YOUR-APP.up.railway.app/health` → `"status": "ok"` (Redis optional).

Required variables on **API** service:

| Variable | Source |
|----------|--------|
| `DATABASE_URL` | Postgres plugin (auto) |
| `SOAPBOXX_CORS_ORIGINS` | `https://soapboxx.lovable.app` |
| `PORT` | Railway (auto) |

## Daily RSS sync (second service)

Cron must be a **separate Railway service** (not the long-running web service).

### Create `soapboxx-sync` service

1. Same repo, same branch (`production`).
2. **Settings → Deploy** → Start command:

   ```bash
   python scripts/sync_all_feeds.py
   ```

3. **Settings → Cron Schedule** (UTC):

   ```text
   0 6 * * *
   ```

   (06:00 UTC daily — adjust for your timezone.)

4. **Variables** — same as API:

   - Reference `DATABASE_URL` from Postgres

5. Service must **exit** when done (`sync_all_feeds.py` already exits 0).

### Do not

- Put cron schedule on the **web** service (conflicts with uvicorn).
- Run sync inside the API process without a job queue.

## Seed feeds (one-time)

Locally or Railway shell:

```bash
python scripts/seed_feeds_from_file.py
```

Uses [`data/seed_feeds.txt`](../data/seed_feeds.txt).
