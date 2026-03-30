# SoapBoxx Demo — one-step setup and launch (Windows, PowerShell)
# Use after unzipping the GitHub Release: double-click setup_and_run.bat or run:
#   powershell -ExecutionPolicy Bypass -File .\setup_and_run.ps1

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

Set-Location -LiteralPath $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  SoapBoxx Demo — setup and run" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

if (-not (Test-Path "frontend\main_window.py")) {
    Write-Host ""
    Write-Host "ERROR: Run this from inside the SoapBoxx-Demo folder (where frontend\main_window.py lives)." -ForegroundColor Red
    Write-Host "Current folder: $PWD" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path "requirements_demo.txt")) {
    Write-Host "ERROR: requirements_demo.txt not found in this folder." -ForegroundColor Red
    exit 1
}

# Pick a Python launcher (Windows: py launcher preferred when both exist)
$pythonExe = $null
$pythonArgs = @()

if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonExe = "py"
    $pythonArgs = @("-3")
    Write-Step "Using Python launcher: py -3"
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonExe = "python"
    Write-Step "Using: python"
}
else {
    Write-Host ""
    Write-Host "ERROR: Python 3.8+ not found in PATH." -ForegroundColor Red
    Write-Host "Install from https://www.python.org/downloads/ and check 'Add Python to PATH' on Windows." -ForegroundColor Yellow
    exit 1
}

Write-Step "Python version"
if ($pythonExe -eq "py") {
    & py -3 --version
} else {
    & python --version
}

Write-Step "Installing dependencies (pip install -r requirements_demo.txt)"
if ($pythonExe -eq "py") {
    & py -3 -m pip install -r requirements_demo.txt
} else {
    & python -m pip install -r requirements_demo.txt
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: pip install failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Step "Starting SoapBoxx Demo"
if ($pythonExe -eq "py") {
    & py -3 frontend/main_window.py
} else {
    & python frontend/main_window.py
}

$code = $LASTEXITCODE
if ($code -ne 0) {
    Write-Host ""
    Write-Host ("The app exited with an error (code " + $code + "). See messages above.") -ForegroundColor Yellow
}
exit $code
