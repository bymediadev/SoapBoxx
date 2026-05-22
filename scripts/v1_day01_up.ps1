# Day 1 — start Postgres + Redis, install deps, run migrations
param(
    [switch]$SkipDocker,
    [switch]$SkipMigrate
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if (-not $SkipDocker) {
    Write-Host "Starting Postgres + Redis (docker-compose.v1.yml)..."
    docker compose -f docker-compose.v1.yml up -d
    Start-Sleep -Seconds 5
}

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    $venvPython = "python"
}

Write-Host "Installing V1 API requirements..."
& $venvPython -m pip install -q -r requirements-v1-api.txt

if (-not $SkipMigrate) {
    Write-Host "Running Alembic migrations..."
    $env:DATABASE_URL = "postgresql+psycopg2://soapboxx:soapboxx@127.0.0.1:5432/soapboxx_v1"
    & $venvPython -m alembic upgrade head
}

Write-Host ""
Write-Host "Day 1 ready. Run API:"
Write-Host "  uvicorn main:app --reload --host 127.0.0.1 --port 8000"
Write-Host "  curl http://127.0.0.1:8000/health"
