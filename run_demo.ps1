$ErrorActionPreference = "Stop"

# Demo launcher: isolated bucket + 2-week runtime window
$env:SOAPBOXX_BUCKET = "demo"

# Preferred fixed cutoff date for this demo build
$env:SOAPBOXX_DEMO_EXPIRES_ON = "2026-05-20"

# Optional explicit isolation paths (uncomment if you want custom folders)
# $env:SOAPBOXX_CONFIG_FILE = "soapboxx_config.demo.json"
# $env:SOAPBOXX_RUNS_DIR = "runs/demo"

Write-Host "Launching SoapBoxx DEMO..."
Write-Host "  bucket: $env:SOAPBOXX_BUCKET"
Write-Host "  expires_on: $env:SOAPBOXX_DEMO_EXPIRES_ON"

python "frontend/main_window.py"
