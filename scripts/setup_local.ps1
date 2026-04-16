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

$envExample = Join-Path $repoRoot ".env.example"
$envFile = Join-Path $repoRoot ".env"
if (-not (Test-Path $envFile) -and (Test-Path $envExample)) {
    Step "Creating .env from .env.example (edit .env for your machine)"
    Copy-Item -LiteralPath $envExample -Destination $envFile
}
elseif (-not (Test-Path $envFile)) {
    Write-Host "Note: no .env.example found; create .env manually if you use Ollama." -ForegroundColor Yellow
}

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
if (-not $env:SOAPBOXX_BRIEF_MAX_CHARS) {
    $env:SOAPBOXX_BRIEF_MAX_CHARS = "200000"
}

Step "Quick import sanity check"
& $venvPython -c "import sys, os; sys.path.insert(0, os.path.join(os.getcwd(), 'backend')); import pydantic, tenacity, jsonschema, structlog; import blueprint_v1.pipeline; print('Imports OK')"

Step "Setup complete"
Write-Host "Run next: .\scripts\smoke_test.ps1" -ForegroundColor Green
