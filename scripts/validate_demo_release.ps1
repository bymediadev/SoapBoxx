# Validates a packaged SoapBoxx demo release folder or zip.
param(
    [string]$Version = "1.2.3",
    [string]$RepoRoot = (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path (Join-Path $RepoRoot "frontend\main_window.py"))) {
    $RepoRoot = Split-Path $PSScriptRoot -Parent
}

$releaseDir = Join-Path (Join-Path $RepoRoot "releases") "SoapBoxx-Production-Studio-Demo-v$Version"
$zipPath = "$releaseDir.zip"
$exeRel = "SoapBoxxProductionStudioDemo\SoapBoxxProductionStudioDemo.exe"
$failures = @()

function Fail([string]$msg) {
    $script:failures += $msg
    Write-Host "FAIL: $msg" -ForegroundColor Red
}

function Pass([string]$msg) {
    Write-Host "OK:   $msg" -ForegroundColor Green
}

Write-Host ""
Write-Host "SoapBoxx demo release validation (v$Version)"
Write-Host "============================================"
Write-Host ""

if (-not (Test-Path $releaseDir)) {
    Fail "Release folder missing: $releaseDir"
} else {
    Pass "Release folder exists"
}

if (-not (Test-Path $zipPath)) {
    Fail "Zip missing: $zipPath"
} else {
    $zipMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
    if ($zipMb -lt 50) {
        Fail "Zip suspiciously small (${zipMb} MB)"
    } else {
        Pass "Zip exists (${zipMb} MB)"
    }
}

$required = @(
    "00_EXTRACT_THIS_ZIP_FIRST.txt",
    "TESTER_QUICKSTART.md",
    "Launch SoapBoxx Production Studio Demo.bat",
    "DEMO_INSTRUCTIONS.md",
    "demo_release.json",
    "soapboxx_config.demo.json",
    ".env.example",
    $exeRel,
    "SoapBoxxProductionStudioDemo\SoapBoxx Production Studio Demo.bat",
    "SoapBoxxProductionStudioDemo\_internal\frontend\soapboxx_tab.py",
    "SoapBoxxProductionStudioDemo\_internal\frontend\main_window.py",
    "SoapBoxxProductionStudioDemo\_internal\backend\runtime_paths.py"
)

foreach ($rel in $required) {
    $p = Join-Path $releaseDir $rel
    if (-not (Test-Path $p)) {
        Fail "Missing: $rel"
    } else {
        Pass "Present: $rel"
    }
}

$bat = Get-Content (Join-Path $releaseDir "Launch SoapBoxx Production Studio Demo.bat") -Raw
if ($bat -notmatch 'SOAPBOXX_BUCKET=demo') { Fail "Launcher missing SOAPBOXX_BUCKET=demo" }
else { Pass "Launcher sets demo bucket" }
if ($bat -notmatch 'SOAPBOXX_CONFIG_FILE') { Fail "Launcher missing SOAPBOXX_CONFIG_FILE" }
else { Pass "Launcher sets demo config path" }
if ($bat -notmatch 'if not exist') { Fail "Launcher missing exe existence check" }
else { Pass "Launcher checks exe exists before start" }

$meta = Get-Content (Join-Path $releaseDir "demo_release.json") -Raw | ConvertFrom-Json
if ($meta.expires_on) { Fail "demo_release.json still has expires_on" }
else { Pass "No expiry in demo_release.json" }

# Zip should contain one top-level folder
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
$roots = $zip.Entries | ForEach-Object {
    $n = $_.FullName.TrimEnd('/', '\')
    if ($n -match '[\\/]') { ($n -split '[\\/]')[0] } else { $n }
} | Where-Object { $_ } | Select-Object -Unique
$zip.Dispose()
if ($roots.Count -ne 1) {
    Fail "Zip should have one root folder; found: $($roots -join ', ')"
} else {
    Pass "Zip has single root folder: $($roots[0])"
}

# Import smoke test (same as frozen bundle layout)
$env:SOAPBOXX_BUCKET = "demo"
$env:SOAPBOXX_CONFIG_FILE = Join-Path $releaseDir "soapboxx_config.demo.json"
Push-Location (Join-Path $releaseDir "SoapBoxxProductionStudioDemo")
try {
    $internal = Join-Path (Get-Location) "_internal"
    $py = "python"
    $code = @"
import sys, os
sys.path.insert(0, r'$internal')
sys.path.insert(0, os.path.join(r'$internal', 'frontend'))
sys.path.insert(0, os.path.join(r'$internal', 'backend'))
os.chdir(r'$(Join-Path $releaseDir 'SoapBoxxProductionStudioDemo')')
os.environ['SOAPBOXX_BUCKET'] = 'demo'
os.environ['SOAPBOXX_CONFIG_FILE'] = r'$(Join-Path $releaseDir 'soapboxx_config.demo.json')'
from backend.runtime_paths import configure_frozen_runtime
configure_frozen_runtime()
from frontend.soapboxx_tab import SoapBoxxTab
assert hasattr(SoapBoxxTab, 'setup_ui'), 'SoapBoxxTab is stub'
from frontend.main_window import _soapboxx_tab_is_real
assert _soapboxx_tab_is_real(), 'main_window thinks tab is stub'
print('IMPORT_OK')
"@
    $out = & $py -c $code 2>&1
    if ($LASTEXITCODE -ne 0 -or ($out -join '') -notmatch 'IMPORT_OK') {
        Fail "Bundled import smoke test failed: $out"
    } else {
        Pass "Bundled import smoke test (SoapBoxxTab + runtime_paths)"
    }
} finally {
    Pop-Location
    Remove-Item Env:SOAPBOXX_BUCKET -ErrorAction SilentlyContinue
    Remove-Item Env:SOAPBOXX_CONFIG_FILE -ErrorAction SilentlyContinue
}

Write-Host ""
if ($failures.Count -eq 0) {
    Write-Host "All checks passed. Demo v$Version looks ready to ship." -ForegroundColor Cyan
    exit 0
}
Write-Host "$($failures.Count) check(s) failed." -ForegroundColor Red
exit 1
