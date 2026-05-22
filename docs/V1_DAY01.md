# V1 Day 1 — Foundation

## Quick start

```powershell
# 1) Postgres + Redis
docker compose -f docker-compose.v1.yml up -d

# 2) Env (merge into .env)
# DATABASE_URL=postgresql+psycopg2://soapboxx:soapboxx@127.0.0.1:5432/soapboxx_v1
# REDIS_URL=redis://127.0.0.1:6379/0

# 3) One-shot setup
.\scripts\v1_day01_up.ps1

# 4) API
uvicorn main:app --reload --port 8000

# 5) Verify
curl http://127.0.0.1:8000/health
pytest tests/v1/day01/ -q
```

## Layout

```text
backend/api/          FastAPI app + health
backend/models/       SQLAlchemy V1 tables
backend/services/     (Day 3+)
backend/workers/      Celery stub
backend/batch/        (Day 3+)
alembic/versions/     Migrations
main.py               uvicorn main:app
```

## Tables (Day 1)

- `podcasts`, `episodes`, `transcript_segments`, `episode_features`
- `taxonomy_nodes`, `podcast_taxonomy_map`

Next: **Day 2** — `POST/GET /podcasts`, `POST/GET /episodes/{id}`
