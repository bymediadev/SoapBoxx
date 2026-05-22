# Railway — Postgres + cron sync

Production host: `https://soapboxx-production.up.railway.app`

## Pending checklist (order)

| # | Task | Done when |
|---|------|-----------|
| 1 | **Postgres** on project → reference `DATABASE_URL` on API service | Variable visible in API → Variables |
| 2 | **Redeploy API** (Railpack, empty build command, start via `railway.toml`, clear cache) | `GET /health` → HTTP 200, `"status":"ok"` (Redis optional) |
| 3 | **Cron service** `soapboxx-sync` → `python scripts/sync_all_feeds.py`, schedule `0 6 * * *`, same `DATABASE_URL` | ✅ Done — cron run logs show feed sync |
| 4 | **UI** — open `/ui/` on Railway (free; no Lovable) or Lovable chat prompt | Library stats/ingest work |
| 5 | **Lovable wireup** — copy `docs/lovable/api-client.ts`, follow [`WIREUP.md`](lovable/WIREUP.md) | Library/stats/activity from API |

**502 "Application failed to respond"** — see **[`RAILWAY_502_FIX.md`](RAILWAY_502_FIX.md)** (deploy log lines + isolate `uvicorn` start).

## Dashboard: build vs start (API service)

| Setting | Value |
|---------|--------|
| **Build command** | **Empty** — clear any `python start.py` here; Railpack installs from `requirements.txt` automatically |
| **Pre-deploy command** | Leave unset in dashboard; **`railway.toml`** runs `sh scripts/migrate_db.sh` (`alembic upgrade head`) |
| **Start command** | Leave unset in dashboard; **`railway.toml`** runs uvicorn on `$PORT` |
| **Domain port** | Edit icon next to `*.up.railway.app` in Public Networking → **8080** (not local dev 8000) |

Railway rejects using the same command for build and start. **Do not** name start scripts `railway_start.sh` — Railpack may auto-run them during **build**, where `postgres.railway.internal` is unreachable.

## Postgres + `DATABASE_URL`

**Do not** set `DATABASE_URL` to `127.0.0.1` on Railway. Inside the API container, localhost is the container — not Postgres. Use the plugin reference only.

### DATABASE_URL disappeared? (restore in 2 minutes)

1. Open Railway project → confirm a **PostgreSQL** service exists (if not: **+ New** → **Database** → **PostgreSQL**).
2. Click your **API / web service** (soapboxx-production) → **Variables**.
3. **+ New variable** → **Add variable reference** (or **Reference variable**).
4. Select the **Postgres** service → choose **`DATABASE_URL`** (or `POSTGRES_URL` / `DATABASE_PRIVATE_URL` if that is what the plugin exposes — Railway maps it to `DATABASE_URL` on the API service).
5. **Do not** type a value by hand from `.env.v1.example`.
6. **Redeploy** the API service.

You should see a linked/reference icon on the variable, not a plain text `127.0.0.1` string.

Repeat on **soapboxx-sync** cron service when you add it (same reference).

### First-time setup

1. Railway project → **New** → **Database** → **PostgreSQL** (or Add Postgres plugin to project).
2. On the **API service** → **Variables** → **Add reference** → `DATABASE_URL` from Postgres service (host will look like `${{Postgres.*}}` / `*.railway.internal`, not `127.0.0.1`).
3. Redeploy API service. Pre-deploy runs `alembic upgrade head`; start runs uvicorn only.
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

**Do not use root `railway.toml` on the cron service** — that file is for the API (uvicorn + `migrate_db.sh`). If sync uses it, you get `migrate_db.sh: No such file` or wrong start command.

Use repo file **[`railway.cron.toml`](../railway.cron.toml)** on the sync service only:

1. Same repo, same branch (`production`).
2. Click service **soapboxx-sync** (not soapboxx-production).
3. **Settings** → **Config-as-code** (or **Build**) → set **Config file path** to:

   ```text
   railway.cron.toml
   ```

4. Leave dashboard **Build / Start / Pre-deploy** empty (the cron toml controls deploy).
5. **Variables:** reference `DATABASE_URL` from Postgres.
6. **Networking:** no public domain.

That file sets:

```toml
startCommand = "python scripts/sync_all_feeds.py"
cronSchedule = "0 6 * * *"
```

(No `preDeployCommand` — migrations run on the API service only.)

**If you cannot set a separate config path:** remove deploy overrides from dashboard on sync; set only **Cron schedule** + **Start** = `python scripts/sync_all_feeds.py` and **Pre-deploy** = empty (see error note below).

1. Same repo, same branch (`production`).
2. **Build command:** empty (Railpack install only).
3. **Settings → Deploy** → **Pre-deploy:** empty · Start command (only if not using `railway.cron.toml`):

   ```bash
   python scripts/sync_all_feeds.py
   ```

4. **Settings → Cron Schedule** (UTC):

   ```text
   0 6 * * *
   ```

   (06:00 UTC daily — adjust for your timezone.)

5. **Variables** — same as API:

   - Reference `DATABASE_URL` from Postgres

6. Service must **exit** when done (`sync_all_feeds.py` already exits 0).

### Do not

- Put cron schedule on the **web** service (conflicts with uvicorn).
- Run sync inside the API process without a job queue.
- Leave **preDeploy** on the cron service (inherits `migrate_db.sh` from repo `railway.toml`).

## Seed feeds (one-time)

Locally or Railway shell:

```bash
python scripts/seed_feeds_from_file.py
```

Uses [`data/seed_feeds.txt`](../data/seed_feeds.txt).
