#!/bin/sh
# Pre-deploy only — runs when private network can reach Postgres (not during Railpack build).
set -e
cd "$(dirname "$0")/.."
echo "=== migrate_db.sh (preDeploy) ==="
if [ -z "$DATABASE_URL" ]; then
  echo "FATAL: DATABASE_URL not set" >&2
  exit 1
fi
python -m alembic upgrade head
