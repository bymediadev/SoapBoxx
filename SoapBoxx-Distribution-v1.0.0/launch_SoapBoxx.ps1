# SoapBoxx v1.0.0 PowerShell Launcher
# Run with: PowerShell -ExecutionPolicy Bypass -File launch_SoapBoxx.ps1

param(
    [switch]$Help,
    [switch]$SkipCheck
)

if ($Help) {
    Write-Host @"
SoapBoxx v1.0.0 PowerShell Launcher

Usage:
    .\launch_SoapBoxx.ps1 [-SkipCheck] [-Help]

Parameters:
    -SkipCheck    Skip environment checks
    -Help         Show this help message

Examples:
    .\launch_SoapBoxx.ps1
    .\launch_SoapBoxx.ps1 -SkipCheck
"@
    exit 0
}

# Set console title and colors
$Host.UI.RawUI.WindowTitle = "SoapBoxx v1.0.0 Launcher"
$Host.UI.RawUI.ForegroundColor = "Cyan"

Write-Host @"

========================================
        SoapBoxx v1.0.0 Launcher
========================================

"@ -ForegroundColor Green

if (-not $SkipCheck) {
    # Check if virtual environment exists
    if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
        Write-Host "❌ Virtual environment not found!" -ForegroundColor Red
        Write-Host ""
        Write-Host "Please run the setup first:" -ForegroundColor White
        Write-Host "python -m venv .venv" -ForegroundColor White
        Write-Host ".\.venv\Scripts\Activate.ps1" -ForegroundColor White
        Write-Host "pip install -r requirements.txt" -ForegroundColor White
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit 1
    }

    # Check if main window file exists
    if (-not (Test-Path "frontend\main_window.py")) {
        Write-Host "❌ Main window file not found!" -ForegroundColor Red
        Write-Host "   Make sure you're running this from the SoapBoxx directory" -ForegroundColor Red
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit 1
    }

    Write-Host "✅ Environment check passed" -ForegroundColor Green
}

# Activate virtual environment
Write-Host ""
Write-Host "🔧 Activating virtual environment..." -ForegroundColor Cyan
try {
    & .\.venv\Scripts\Activate.ps1
    Write-Host "✅ Virtual environment activated" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to activate virtual environment: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Launch SoapBoxx
Write-Host ""
Write-Host "🚀 Launching SoapBoxx..." -ForegroundColor Green
Write-Host ""

try {
    python frontend/main_window.py
} catch {
    Write-Host "❌ Failed to launch SoapBoxx: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "SoapBoxx has closed." -ForegroundColor Yellow
Read-Host "Press Enter to exit"
