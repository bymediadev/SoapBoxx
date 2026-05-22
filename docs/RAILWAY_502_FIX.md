# Railway 502 — "Application failed to respond"

The edge proxy got **no HTTP response** from your container. The app crashed, never bound to `PORT`, or is still starting.

## Read deploy logs (API service → latest deployment → Deploy logs)

Search for these lines **in order**:

| Log line | Meaning |
|----------|---------|
| `=== SoapBoxx boot ===` | `start.py` ran |
| `DATABASE_URL: (not set)` | Add Postgres **reference** on API service |
| `DATABASE_URL: set (host=...railway...)` | URL looks OK |
| `FATAL: DATABASE_URL points to localhost` | Remove `127.0.0.1` value; use Postgres reference |
| `Import OK: main:app` | App loads |
| `Starting uvicorn main:app on 0.0.0.0:XXXX` | Should listen — if missing, process died after this |
| `ModuleNotFoundError` / `ImportError` | Build/deploy missing files or wrong deps |
| `alembic exited` | DB/migrations issue (app may still run degraded) |

Copy the **last 30 lines** if still stuck.

## Checklist (do in order)

### 1. Variables on **API** service (not only Postgres)

- [ ] `DATABASE_URL` = **reference** from Postgres (or paste URL from Postgres → Connect; host **not** `127.0.0.1`)
- [ ] `SOAPBOXX_CORS_ORIGINS=https://soapboxx.lovable.app`
- [ ] No duplicate/wrong `PORT` override

### 2. Build / start settings

- [ ] Builder: **Railpack**
- [ ] **Build command:** empty
- [ ] **Start:** `python start.py` (or leave blank if `railway.toml` applies)
- [ ] Root directory: repo root (`main.py`, `start.py`, `requirements.txt` visible)

### 3. Redeploy

- [ ] **Redeploy** → **Clear build cache**
- [ ] Latest `production` branch pushed (API-only `requirements.txt`, `start.py` with boot logs)

### 4. Isolate start script (if still 502)

Temporarily set **Start command** to:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Redeploy once.

- If **this works** → issue is in `start.py` / DB wait / alembic (set `BOOT_SKIP_DB_WAIT=1` on API service to test).
- If **still 502** → build/import/deps or wrong service root.

## Emergency env vars (API service)

| Variable | Effect |
|----------|--------|
| `BOOT_SKIP_DB_WAIT=1` | Skip DB wait (faster boot; debug only) |
| `DB_WAIT_ATTEMPTS=5` | Shorter wait |

## Logs show 200 but browser still 502?

Your deploy log had:

```text
Uvicorn running on http://0.0.0.0:8080
GET /health HTTP/1.1" 200 OK
```

That is **internal** Railway health traffic (`100.64.x.x`). Public 502 means the **public hostname is not reaching that running container**.

Check on the **API service**:

| Check | Where |
|-------|--------|
| **Public networking** enabled | Settings → Networking → Public Networking **ON** |
| **Correct domain** | Settings → Networking — copy the exact `*.up.railway.app` host (do not guess) |
| **Domain on API service** | Not on Postgres-only or cron service |
| **Latest deploy Active** | Deployments — green, not Crashed |
| **HTTP Logs** | Do requests appear when you hit the URL? If empty → wrong host/service |

Try:

1. **Generate domain** again on the API service (fresh URL).
2. Open `https://YOUR-EXACT-DOMAIN/health/live` (always 200, no DB).
3. Then `/health` and `/ui/`.

If HTTP logs show requests but 502 → paste those lines. If **no** HTTP logs when you browse → domain points elsewhere.

## HTTP logs show 502 (~200ms) on every path

Requests **reach** Railway (`GET /health 502` in HTTP logs) but nothing is listening on `$PORT`.

| Cause | Fix |
|-------|-----|
| Alembic ran during **build** (DNS on `postgres.railway.internal`) | Empty build command; migrations in **preDeploy** (`migrate_db.sh`); start `start_api.sh` only |
| Start script exited before uvicorn | Start: `sh scripts/start_api.sh` (no alembic in start) |
| Wrong start command | Leave dashboard start empty; use `railway.toml` |
| Process crash loop | Deploy logs: look for exit / restart after `Uvicorn running` |
| Custom port mismatch | Networking → target port = **$PORT** (often **8080**) |

**Fast dashboard test** — set Start command to:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Redeploy. Run `alembic upgrade head` once in Railway shell if needed.

## Pass criteria

```bash
curl https://YOUR-EXACT-DOMAIN/health/live
curl https://YOUR-EXACT-DOMAIN/health
```

HTTP **200** with JSON.

Then open `/ui/` and `/docs`.
