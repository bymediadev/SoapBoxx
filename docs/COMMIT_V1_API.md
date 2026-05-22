# Commit guide — V1 API + Railway + Lovable bridge

Use this when committing the online stack to `production`. **Do not** add `releases/`, `Exports/`, or `data/` unless intentional.

## Suggested commit message

```text
Add SoapBoxx V1 API: FastAPI, Postgres schema, RSS ingest, pipeline, system state, Railway deploy

- FastAPI app (main.py) with ingest, library, episodes, taxonomy, system activity, patterns
- Alembic migrations 001–005; feedparser RSS ingestion with idempotent dedupe
- Episode pipeline_status + system_events for Lovable UI motion
- CORS, library endpoints, Railpack/Railway start scripts and docs
```

## Stage (API + deploy — copy/paste)

```powershell
git add main.py start.py app.py Procfile railpack.json railway.toml runtime.txt alembic.ini alembic/ requirements.txt requirements-v1-api.txt .env.v1.example docker-compose.v1.yml
git add backend/api/ backend/models/ backend/services/ backend/workers/ backend/batch/
git add backend/features/ backend/services/rss_service.py
git add .github/workflows/v1-tests.yml
git add tests/conftest.py tests/fixtures/ tests/utils/ tests/test_day*.py tests/test_system_health.py tests/test_system_state.py tests/test_lovable_library_api.py
git add scripts/railway_start.sh scripts/v1_day01_up.ps1 scripts/sync_all_feeds.py scripts/seed_feeds_from_file.py data/seed_feeds.txt
git add docs/SMOOTH_OPERATIONS.md
git add docs/V1_*.md docs/V1_INGESTION_LAYER.md docs/SYSTEM_STATE_LAYER.md docs/LOVABLE_INTEGRATION.md docs/RAILWAY_DEPLOY.md docs/COMMIT_V1_API.md
git add SOAPBOXX_V1_7DAY_EXECUTION.md SOAPBOXX_EXECUTION_PLAN_V1.md SOAPBOXX_MASTER_PLAN_FOUNDATION.md
git add pytest.ini
```

## Do not stage (unless you mean to)

- `releases/**`
- `Exports/**`
- `data/soapboxx.db`
- Desktop-only churn unless part of same PR

## After push

1. Railway: Postgres plugin → redeploy → `curl .../health`
2. Lovable: `VITE_API_URL=https://<railway-host>`
