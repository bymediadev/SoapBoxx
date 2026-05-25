# DATABASE_URL — local vs Railway

## The error

```text
psycopg2.OperationalError: connection to server at "127.0.0.1", port 5432 failed: Connection refused
```

## What it means

| Where the API runs | `127.0.0.1:5432` means |
|--------------------|-------------------------|
| **Your PC** (uvicorn local) | Your machine — OK if Postgres is in Docker with `ports: 5432:5432` |
| **Railway / any container** | The same container — **wrong**; Postgres is a different service |

---

## Local (correct)

```text
API: uvicorn on Windows/Mac (host)
DB:  docker compose -f docker-compose.v1.yml up -d
URL: postgresql+psycopg2://soapboxx:soapboxx@127.0.0.1:5432/soapboxx_v1
```

```powershell
.\scripts\setup_local.ps1 -ApiOnly -V1Infra
.\.venv\Scripts\python.exe scripts\wait_for_db.py   # optional check
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

If connection refused **locally** → Postgres container is not running:

```powershell
docker compose -f docker-compose.v1.yml up -d
docker compose -f docker-compose.v1.yml ps
```

---

## Railway (correct)

### Variable missing entirely

Railway does not auto-fill `DATABASE_URL` on the API service until you **reference** it:

1. API service → **Variables** → **+ New variable** → **Reference** from Postgres service → `DATABASE_URL`.
2. Redeploy.

If Postgres was deleted, create a new Postgres service first (data from old DB is gone unless you have backups).

### Normal setup

1. Add **PostgreSQL** to the project.
2. On the **API service** → Variables → **Reference** `DATABASE_URL` from Postgres.
3. **Delete** any manual `DATABASE_URL` you pasted from `.env.v1.example`.

The value should **not** contain `127.0.0.1` or `localhost`.

`start.py` will **exit with a clear error** if Railway detects localhost in `DATABASE_URL`.

---

## Mental model

```text
Local:    [uvicorn on host] ----5432----> [postgres container]
Railway:  [API container] ----network--> [Postgres plugin host]
```

---

## Startup order

`start.py` now:

1. Guards against localhost URL on Railway  
2. Runs `scripts/wait_for_db.py` (retries ~60s; script prepends repo root to `sys.path` so `backend` imports work)  
3. Runs `alembic upgrade head`  
4. Starts uvicorn  
