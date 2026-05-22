#!/usr/sh
# SoapBoxx V1 API — migrate then serve (Railway / Railpack)
set -e
cd "$(dirname "$0")/.."
echo "Running alembic upgrade head..."
alembic upgrade head
echo "Starting uvicorn on port ${PORT:-8000}"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
