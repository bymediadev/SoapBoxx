#!/bin/sh
# Web process only — no migrations (see migrate_db.sh / preDeployCommand).
cd "$(dirname "$0")/.."
echo "=== start_api.sh ==="
echo "PORT=${PORT:-8000}"
exec python -m uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
