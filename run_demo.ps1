$ErrorActionPreference = "Stop"

# Demo launcher: isolated bucket (no expiry)
$env:SOAPBOXX_BUCKET = "demo"
Remove-Item Env:SOAPBOXX_DEMO_EXPIRES_ON -ErrorAction SilentlyContinue
Remove-Item Env:SOAPBOXX_DEMO_START_ON -ErrorAction SilentlyContinue
Remove-Item Env:SOAPBOXX_DEMO_DURATION_DAYS -ErrorAction SilentlyContinue

# Optional explicit isolation paths (uncomment if you want custom folders)
# $env:SOAPBOXX_CONFIG_FILE = "soapboxx_config.demo.json"
# $env:SOAPBOXX_RUNS_DIR = "runs/demo"

Write-Host "Launching SoapBoxx DEMO..."
Write-Host "  bucket: $env:SOAPBOXX_BUCKET"

python "frontend/main_window.py"
