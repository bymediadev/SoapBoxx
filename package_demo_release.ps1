param(
    [string]$Version = "1.1.0-demo",
    [string]$ExpiresOn = "2026-05-20"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==============================================="
Write-Host " SoapBoxx Production Studio Demo Packager"
Write-Host "==============================================="
Write-Host "Version: $Version"
Write-Host "Expires: $ExpiresOn"
Write-Host ""

if (-not (Test-Path "frontend\main_window.py")) {
    throw "Run this script from the repository root."
}

$distRoot = "dist\demo"
$buildRoot = "build\demo"
$releaseRoot = "releases"
$releaseName = "SoapBoxx-Production-Studio-Demo-v$Version"
$releaseDir = Join-Path $releaseRoot $releaseName
$zipPath = "$releaseDir.zip"
$exeName = "SoapBoxxProductionStudioDemo"
$repoRoot = (Get-Location).Path
$backendData = "$repoRoot\backend;backend"
$frontendData = "$repoRoot\frontend;frontend"
$entryScript = "$repoRoot\frontend\main_window.py"

function Remove-PathForce($path) {
    if (-not (Test-Path $path)) { return }
    try {
        Remove-Item $path -Recurse -Force -ErrorAction Stop
        return
    } catch {
        # Fallback for stubborn locked trees on Windows.
        cmd /c "rmdir /s /q `"$path`"" | Out-Null
    }
}

Remove-PathForce $distRoot
Remove-PathForce $buildRoot
Remove-PathForce $releaseDir
Remove-PathForce $zipPath

New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null

$runtimeHookPath = Join-Path $buildRoot "demo_runtime_env.py"
@"
import os

os.environ.setdefault("SOAPBOXX_BUCKET", "demo")
os.environ.setdefault("SOAPBOXX_DEMO_EXPIRES_ON", "$ExpiresOn")
"@ | Out-File -FilePath $runtimeHookPath -Encoding utf8

Write-Host "Installing packaging dependency (PyInstaller)..."
python -m pip install --upgrade pyinstaller

Write-Host "Building demo executable..."
python -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name $exeName `
  --distpath $distRoot `
  --workpath $buildRoot `
  --specpath $buildRoot `
  --runtime-hook $runtimeHookPath `
  --collect-submodules backend `
  --collect-submodules frontend `
  --exclude-module torch `
  --exclude-module onnxruntime `
  --exclude-module pandas `
  --exclude-module pyarrow `
  --exclude-module av `
  --exclude-module numba `
  --exclude-module llvmlite `
  --exclude-module pytest `
  --exclude-module openpyxl `
  --exclude-module lxml `
  --exclude-module sqlalchemy `
  --exclude-module jinja2 `
  --add-data $backendData `
  --add-data $frontendData `
  $entryScript

$builtAppDir = Join-Path $distRoot $exeName
if (-not (Test-Path $builtAppDir)) {
    throw "Build output not found: $builtAppDir"
}

Write-Host "Preparing release folder..."
Copy-Item $builtAppDir -Destination $releaseDir -Recurse -Force
Copy-Item "README_DEMO.md" -Destination (Join-Path $releaseDir "README_DEMO.md") -Force
Copy-Item "DEMO_INSTRUCTIONS.md" -Destination (Join-Path $releaseDir "DEMO_INSTRUCTIONS.md") -Force

$launcherBat = Join-Path $releaseDir "Launch SoapBoxx Production Studio Demo.bat"
@"
@echo off
setlocal
set "SOAPBOXX_BUCKET=demo"
set "SOAPBOXX_DEMO_EXPIRES_ON=$ExpiresOn"
start "" "%~dp0$exeName\$exeName.exe"
endlocal
"@ | Out-File -FilePath $launcherBat -Encoding ascii

$launcherPs1 = Join-Path $releaseDir "Launch SoapBoxx Production Studio Demo.ps1"
@"
\$ErrorActionPreference = "Stop"
\$env:SOAPBOXX_BUCKET = "demo"
\$env:SOAPBOXX_DEMO_EXPIRES_ON = "$ExpiresOn"
Start-Process -FilePath (Join-Path \$PSScriptRoot "$exeName\$exeName.exe")
"@ | Out-File -FilePath $launcherPs1 -Encoding utf8

$metaPath = Join-Path $releaseDir "demo_release.json"
@"
{
  "name": "SoapBoxx Production Studio Demo",
  "version": "$Version",
  "expires_on": "$ExpiresOn",
  "bucket": "demo"
}
"@ | Out-File -FilePath $metaPath -Encoding utf8

Write-Host "Creating zip archive..."
for ($i = 1; $i -le 6; $i++) {
    try {
        if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
        Compress-Archive -Path "$releaseDir\*" -DestinationPath $zipPath -Force
        break
    } catch {
        if ($i -eq 6) { throw }
        Start-Sleep -Seconds 2
    }
}

if (-not (Test-Path $zipPath)) {
    throw "Zip creation failed: $zipPath"
}

Write-Host ""
Write-Host "Demo package ready:"
Write-Host "  Folder: $releaseDir"
Write-Host "  Zip:    $zipPath"
Write-Host ""
Write-Host "Tester run command:"
Write-Host "  Launch SoapBoxx Production Studio Demo.bat"
