<#
.SYNOPSIS
  Bootstrap local Python env for SoapBoxx.

.PARAMETER RebuildVenv
  Delete and recreate .venv.

.PARAMETER ApiOnly
  Install V1 API deps only (requirements.txt) - same stack as Railway. Skips PyQt/Whisper.

.PARAMETER V1Infra
  After install: start Docker Postgres/Redis and run migrations (calls v1_day01_up.ps1).

.EXAMPLE
  .\scripts\setup_local.ps1 -ApiOnly -V1Infra
#>
param(
    [switch]$RebuildVenv,
    [switch]$ApiOnly,
    [switch]$V1Infra
)

$ErrorActionPreference = "Stop"

function Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Ensure-Command($name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $name"
    }
}

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

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvDir = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

Step "Validating prerequisites"
Ensure-Command "python"

Step "Moving to repo root"
Set-Location $repoRoot
Write-Host "Repo: $repoRoot"
if ($ApiOnly) {
    Write-Host "Mode: ApiOnly (Railway-parity deps)" -ForegroundColor Yellow
}

$envExample = Join-Path $repoRoot ".env.example"
$envFile = Join-Path $repoRoot ".env"
$envV1Example = Join-Path $repoRoot ".env.v1.example"

if ($ApiOnly -or $V1Infra) {
    if (-not (Test-Path $envFile) -and (Test-Path $envV1Example)) {
        Step "Creating .env from .env.v1.example (V1 API)"
        Copy-Item -LiteralPath $envV1Example -Destination $envFile
    }
}
elseif (-not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Step "Creating .env from .env.example (desktop)"
    Copy-Item -LiteralPath $envExample -Destination $envFile
}
elseif (-not (Test-Path $envFile)) {
    Write-Host "Note: create .env manually (see .env.v1.example for V1 API)." -ForegroundColor Yellow
}

if ($RebuildVenv -and (Test-Path $venvDir)) {
    Step "Removing existing .venv (requested)"
    Remove-Item -Recurse -Force $venvDir
}

if (-not (Test-Path $venvPython)) {
    Step "Creating virtual environment"
    Invoke-External { python -m venv .venv } "python -m venv"
}

if (-not (Test-Path $venvPython)) {
    throw "Virtual environment python was not created at $venvPython"
}

Step "Upgrading pip/setuptools/wheel"
Invoke-External { & $venvPython -m pip install --upgrade pip setuptools wheel } "pip upgrade"

Step "Installing V1 API dependencies (requirements.txt)"
Invoke-External { & $venvPython -m pip install -r "requirements.txt" } "pip install requirements.txt"

if (-not $ApiOnly) {
    if (Test-Path "requirements-desktop.txt") {
        Step "Installing desktop dependencies"
        Invoke-External { & $venvPython -m pip install -r "requirements-desktop.txt" } "pip install desktop"
    }
    if (Test-Path "requirements-dev.txt") {
        Step "Installing dev dependencies"
        Invoke-External { & $venvPython -m pip install -r "requirements-dev.txt" } "pip install dev"
    }
    if (Test-Path "requirements-episode-intelligence.txt") {
        Step "Installing episode intelligence dependencies"
        Invoke-External {
            & $venvPython -m pip install -r "requirements-episode-intelligence.txt"
        } "pip install episode-intelligence"
    }
}

Step "Setting stable environment flags for this shell"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
if (-not $env:SOAPBOXX_BRIEF_MAX_CHARS) {
    $env:SOAPBOXX_BRIEF_MAX_CHARS = "200000"
}

Step "V1 API import check"
Invoke-External {
    & $venvPython -c "from main import app; print('V1 API OK:', app.title)"
} "V1 API import"

if ($V1Infra) {
    Step "Starting V1 Postgres/Redis + migrations"
    & (Join-Path $repoRoot "scripts\v1_day01_up.ps1")
}

Step "Setup complete"
Write-Host ""
if ($ApiOnly -or $V1Infra) {
    Write-Host "V1 API:   uvicorn main:app --reload --host 127.0.0.1 --port 8000" -ForegroundColor Green
    Write-Host "          http://127.0.0.1:8000/health" -ForegroundColor Green
    Write-Host "          http://127.0.0.1:8000/ui/  (free UI, no Lovable)" -ForegroundColor Green
}
if (-not $ApiOnly) {
    Write-Host "Desktop:  .\scripts\smoke_test.ps1" -ForegroundColor Green
}
if (-not $V1Infra) {
    Write-Host "V1 DB:    .\scripts\setup_local.ps1 -ApiOnly -V1Infra" -ForegroundColor Green
}
