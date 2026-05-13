$ErrorActionPreference = "Stop"

# Production launcher: clean env (no demo restrictions)
$env:SOAPBOXX_BUCKET = "production"
Remove-Item Env:SOAPBOXX_DEMO_EXPIRES_ON -ErrorAction SilentlyContinue
Remove-Item Env:SOAPBOXX_DEMO_START_ON -ErrorAction SilentlyContinue
Remove-Item Env:SOAPBOXX_DEMO_DURATION_DAYS -ErrorAction SilentlyContinue

Write-Host "Launching SoapBoxx PRODUCTION..."
Write-Host "  bucket: $env:SOAPBOXX_BUCKET"

python "frontend/main_window.py"
