# build_and_run.ps1
# Sets up environment, formats code, then runs the app

Write-Host "`nActivating virtual environment..."
if (!(Test-Path .\.venv\Scripts\Activate.ps1)) {
    Write-Host "No virtual environment found. Run: python -m venv .venv"
    exit 1
}
. .\.venv\Scripts\Activate.ps1

# Optional: load .env if available
if (Test-Path .env) {
    Write-Host "Loading .env file..."
    Get-Content .env | ForEach-Object {
        if ($_ -match '^\s*([^#].*?)\s*=\s*(.*)\s*$') {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2])
        }
    }
}

# Format code
Write-Host "`nRunning code formatter (black) and import sorter (isort)..."
try {
    black .
    isort .
} catch {
    Write-Host "Formatter tools not found. Installing..."
    pip install black isort
    black .
    isort .
}

# Launch app
Write-Host "`nLaunching SoapBoxx UI..."
try {
    python frontend\main_window.py
} catch {
    Write-Host "Error launching frontend. Ensure the file exists at frontend\main_window.py"
}

# Optional: open logs
$logPath = "log.txt"
if (Test-Path $logPath) {
    Write-Host "`nOpening log file..."
    Start-Process notepad.exe $logPath
} else {
    Write-Host "No log.txt found, skipping log open."
}
