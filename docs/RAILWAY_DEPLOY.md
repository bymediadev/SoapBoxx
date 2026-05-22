# Deploy SoapBoxx V1 API (Railway / Railpack)

## Your entry point

| File | Role |
|------|------|
| **`main.py`** | Exports FastAPI `app` (`from backend.api.app import app`) |
| **Start command** | `sh scripts/railway_start.sh` (migrations + uvicorn) |

This is **not** the PyQt desktop app. Do not deploy `requirements.txt` (PyQt/Whisper desktop stack) for the API service.

---

## Why Railpack said “No start command”

Your build log showed `pydub` / `ffmpeg` and **no start command** — Railpack used desktop deps, not the API stack. Usually:

1. **`railpack.json` / `start.py` were not pushed** to GitHub yet, or  
2. Builder is **Nixpacks** (ignores `railpack.json`), or  
3. **`deploy.startCommand` was not read**.

**Fixes in repo:** V1 deps **inlined in `requirements.txt`**; `railpack.json` only sets `startCommand` (do not override `install` — that runs before files are copied). Root **`start.py`**.

If you see `No such file: requirements-v1-api.txt` — remove custom `steps.install` from `railpack.json`.

---

## Railway checklist

### Builder

In Railway → Service → Settings → Build:

- Builder: **Railpack** (not Nixpacks, if you migrated)
- Root directory: repo root (where `main.py` and `railpack.json` live)

### Environment variables

| Variable | Example |
|----------|---------|
| `DATABASE_URL` | Postgres plugin URL (`postgresql+psycopg2://...`) |
| `REDIS_URL` | `redis://...` (optional for health) |
| `SOAPBOXX_CORS_ORIGINS` | `https://soapboxx.lovable.app` |
| `PORT` | Set by Railway automatically |

Optional override (if deploy still fails):

```text
RAILPACK_START_CMD=sh scripts/railway_start.sh
```

### Migrations

**Release phase** (Procfile `release:` line):

```bash
alembic upgrade head
```

Or run once from Railway shell after first deploy.

### Verify

```bash
curl https://YOUR_SERVICE.up.railway.app/health
curl https://YOUR_SERVICE.up.railway.app/docs
```

---

## Config files (priority)

1. `RAILPACK_START_CMD` env (highest)
2. `railpack.json` → `deploy.startCommand`
3. `Procfile` → `web:` process
4. Auto-detect FastAPI (only if `fastapi` is in the **installed** requirements file)

See [Railpack Procfile docs](https://railpack.com/config/procfile.md).

---

## Lovable frontend

Set in Lovable:

```text
VITE_API_URL=https://YOUR_SERVICE.up.railway.app
```

See [`LOVABLE_INTEGRATION.md`](LOVABLE_INTEGRATION.md).

---

## Common mistakes

| Mistake | Result |
|---------|--------|
| Deploying desktop `requirements.txt` only | No FastAPI, wrong start detection |
| PyQt `main` as start | No HTTP server |
| Missing `DATABASE_URL` | API up, `/health` degraded |
| Nixpacks builder with only `railpack.json` | Config ignored — switch builder to Railpack |

---

## Troubleshooting (Railway keeps failing)

### “No start command detected”

1. Confirm **Railpack** builder (Settings → Build).
2. Push `railpack.json`, `Procfile`, `railway.toml`, `scripts/railway_start.sh`.
3. Set variable: `RAILPACK_START_CMD=sh scripts/railway_start.sh`
4. **Redeploy without cache.**

### Build OK, crash on start

| Log hint | Fix |
|----------|-----|
| `could not connect to server` / DB errors | Add **Postgres** plugin; wait for `DATABASE_URL` to appear on the service |
| `postgres://` driver errors | Fixed in code — pulls latest `backend/api/config.py` (normalizes to `postgresql+psycopg2://`) |
| `alembic` / migration errors | Open Railway **Shell**: `alembic upgrade head` |
| `ModuleNotFoundError: backend` | Root directory must be repo root (where `main.py` lives) |
| Health `degraded` | OK for demo — add **Redis** plugin or ignore; API still serves `/docs` |

### Health check failing

Railway health path: **`/health`** (set in `railway.toml`).  
Needs Postgres connected for `status: ok`. Redis optional.

### Still stuck

1. Railway → Deployments → latest → **View logs** (build + deploy).
2. Copy the **last 20 lines** of the deploy log.
3. Compare with local: `sh scripts/railway_start.sh` (with Docker Postgres up).

### One-service layout

Deploy **only the API** on Railway. Do not deploy PyQt desktop on the same service. Lovable is separate hosting.
