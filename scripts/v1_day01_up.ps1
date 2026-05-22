# Day 1 - start Postgres + Redis, install deps, run migrations
param(
    [switch]$SkipDocker,
    [switch]$SkipMigrate
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Invoke-External {
    param([scriptblock]$Command, [string]$Label = "command")
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $Command 2>&1
        $output | ForEach-Object { Write-Host $_ }
    } finally {
        $ErrorActionPreference = $prev
    }
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "$Label failed (exit $LASTEXITCODE)"
    }
}

if (-not $SkipDocker) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker not found. Install Docker Desktop or run with -SkipDocker."
    }
    Write-Host "Starting Postgres + Redis (docker-compose.v1.yml)..."
    # Docker prints progress to stderr; do not treat that as a PowerShell error.
    Invoke-External { docker compose -f docker-compose.v1.yml up -d } "docker compose"
}

$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host 'No .venv found - run .\scripts\setup_local.ps1 -ApiOnly first.' -ForegroundColor Yellow
    $venvPython = "python"
}

Write-Host "Installing V1 API requirements (requirements.txt)..."
Invoke-External { & $venvPython -m pip install -q -r requirements.txt } "pip install"

if (-not $SkipMigrate) {
    Write-Host "Running Alembic migrations..."
    $env:DATABASE_URL = "postgresql+psycopg2://soapboxx:soapboxx@127.0.0.1:5432/soapboxx_v1"
    if (-not $SkipDocker) {
        Write-Host "Waiting for Postgres on 127.0.0.1:5432..."
        Invoke-External { & $venvPython scripts/wait_for_db.py } "wait_for_db"
    }
    Invoke-External { & $venvPython -m alembic upgrade head } "alembic upgrade"
}

Write-Host ""
Write-Host "Day 1 ready. Run API:" -ForegroundColor Green
Write-Host "  uvicorn main:app --reload --host 127.0.0.1 --port 8000"
Write-Host "  http://127.0.0.1:8000/health"
Write-Host '  http://127.0.0.1:8000/ui/'
