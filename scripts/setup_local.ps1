param(
    [switch]$RebuildVenv
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

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvDir = Join-Path $repoRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"

Step "Validating prerequisites"
Ensure-Command "python"
Ensure-Command "pip"

Step "Moving to repo root"
Set-Location $repoRoot
Write-Host "Repo: $repoRoot"

if ($RebuildVenv -and (Test-Path $venvDir)) {
    Step "Removing existing .venv (requested)"
    Remove-Item -Recurse -Force $venvDir
}

if (-not (Test-Path $venvPython)) {
    Step "Creating virtual environment"
    python -m venv .venv
}

if (-not (Test-Path $venvPython)) {
    throw "Virtual environment python was not created at $venvPython"
}

Step "Upgrading pip/setuptools/wheel"
& $venvPython -m pip install --upgrade pip setuptools wheel

Step "Installing runtime dependencies"
& $venvPython -m pip install -r "requirements.txt"

if (Test-Path "requirements-dev.txt") {
    Step "Installing dev dependencies"
    & $venvPython -m pip install -r "requirements-dev.txt"
}

if (Test-Path "requirements-episode-intelligence.txt") {
    Step "Installing episode intelligence dependencies"
    & $venvPython -m pip install -r "requirements-episode-intelligence.txt"
}

Step "Setting stable environment flags for this shell"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

Step "Quick import sanity check"
& $venvPython -c "import pydantic, tenacity, jsonschema, structlog; print('Imports OK')"

Step "Setup complete"
Write-Host "Run next: .\scripts\smoke_test.ps1" -ForegroundColor Green
