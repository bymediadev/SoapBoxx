# Deploy SoapBoxx V1 API (Railway / Railpack)

## Your entry point

| File | Role |
|------|------|
| **`main.py`** | Exports FastAPI `app` (`from backend.api.app import app`) |
| **Start command** | `python start.py` via `railway.toml` / `railpack.json` (migrations + uvicorn) |
| **ASGI app** | Root `main.py` → `app` (same as `backend.api.app:app`). Override: `ASGI_APP=backend.api.app:app` |
| **Root directory** | Repo root (must contain `main.py`, `start.py`, `requirements.txt`) |
| **Build command (dashboard)** | **Empty** — Railpack auto-detects; never set `python start.py` here |

This is **not** the PyQt desktop app. `requirements.txt` is API-only; install desktop deps locally with `requirements-desktop.txt`.

### Dashboard settings (API service)

In Railway → Service → **Settings**:

| Field | Set to |
|-------|--------|
| Builder | **Railpack** |
| **Build command** | **Clear / empty** |
| **Start command** | **Clear / empty** (use `railway.toml` `[deploy] startCommand`) |
| Custom start in Variables | Only if needed: `RAILPACK_START_CMD=python start.py` — not as build command |

If both dashboard **Build command** and `railway.toml` **start** are `python start.py`, Railway blocks deploy or mis-runs the build phase.

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
- **Build command:** leave **empty** (do not duplicate `python start.py`)
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
RAILPACK_START_CMD=sh scripts/start_api.sh
```

### Migrations

**Pre-deploy** (`railway.toml` / `railpack.json` → `preDeployCommand`):

```bash
sh scripts/migrate_db.sh
```

Also in Procfile `release:` for Heroku-style platforms. Or run once from Railway shell after first deploy.

**Do not** run migrations in a script named `railway_start.sh` — Railpack may execute it during **build**, where the private network is unavailable (`postgres.railway.internal` DNS failure).

### Verify

```bash
curl https://YOUR_SERVICE.up.railway.app/health
curl https://YOUR_SERVICE.up.railway.app/docs
```

---

## Config files (priority)

1. `RAILPACK_START_CMD` env (highest)
2. `railway.toml` → `preDeployCommand` / `startCommand`
3. `railpack.json` → `deploy.preDeployCommand` / `deploy.startCommand`
4. `Procfile` → `web:` / `release:` processes
5. Auto-detect scripts (avoid `railway_*` names at build time)

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
| Missing `DATABASE_URL` | API up, `/health` degraded (no Postgres) |
| `requirements.txt` includes PyQt/Whisper | Build OOM or crash — API file must be V1-only; desktop: `requirements-desktop.txt` |
| `PortAudio` / `sounddevice` crash at startup | `railpack.json` → `deploy.aptPackages: ["libportaudio2"]`; `backend/__init__.py` lazy-loads desktop modules |
| Nixpacks builder with only `railpack.json` | Config ignored — switch builder to Railpack |
| `python start.py` as **Build command** in dashboard | Conflicts with `railway.toml` start — clear build command; Railpack installs deps only |

---

## Troubleshooting (Railway keeps failing)

### “No start command detected”

1. Confirm **Railpack** builder (Settings → Build).
2. Push `railpack.json`, `Procfile`, `railway.toml`, `scripts/start_api.sh`, `scripts/migrate_db.sh`.
3. Set variable: `RAILPACK_START_CMD=sh scripts/start_api.sh` (optional)
4. **Redeploy without cache.**

### Build OK, crash on start

| Log hint | Fix |
|----------|-----|
| `could not connect to server` / DB errors | Add **Postgres** plugin; wait for `DATABASE_URL` to appear on the service |
| `postgres://` driver errors | Fixed in code — pulls latest `backend/api/config.py` (normalizes to `postgresql+psycopg2://`) |
| `alembic` / migration errors at **build** | Clear build command; migrations belong in **preDeploy** only (`migrate_db.sh`) |
| `alembic` / migration errors at **preDeploy** | Check `DATABASE_URL` reference; redeploy |
| `ModuleNotFoundError: backend` | Root directory must be repo root (where `main.py` lives) |
| Health `degraded` | OK for demo — add **Redis** plugin or ignore; API still serves `/docs` |

### Health check failing

Railway health path: **`/health`** (set in `railway.toml`).  
Needs Postgres connected for `status: ok`. Redis optional.

### Still stuck

1. Railway → Deployments → latest → **View logs** (build + deploy).
2. Copy the **last 20 lines** of the deploy log.
3. Compare with local: `sh scripts/migrate_db.sh` then `sh scripts/start_api.sh` (Docker Postgres up).

### One-service layout

Deploy **only the API** on Railway. Do not deploy PyQt desktop on the same service. Lovable is separate hosting.
