param(
    [string]$Version = "1.1.0-demo"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "==============================================="
Write-Host " SoapBoxx Production Studio Demo Packager"
Write-Host "==============================================="
Write-Host "Version: $Version"
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

$extractFirstPath = Join-Path $releaseDir "00_EXTRACT_THIS_ZIP_FIRST.txt"
@"
SoapBoxx Production Studio Demo
==============================

IMPORTANT (Windows / WinRAR / 7-Zip):
  Extract the ENTIRE zip to a folder on your PC before launching.
  Do NOT double-click the .bat file from inside the archive viewer.
  If you do, Windows will only extract the .bat to a temp folder and the app will not start.

Steps:
  1. Right-click the zip -> Extract All... (or drag the folder out of WinRAR).
  2. Open the extracted folder.
  3. Double-click: Launch SoapBoxx Production Studio Demo.bat
     OR open SoapBoxxProductionStudioDemo and run SoapBoxx Production Studio Demo.bat
"@ | Out-File -FilePath $extractFirstPath -Encoding utf8

$exeRel = "$exeName\$exeName.exe"
$launcherBat = Join-Path $releaseDir "Launch SoapBoxx Production Studio Demo.bat"
@"
@echo off
setlocal
set "EXE=%~dp0$exeRel"
if not exist "%EXE%" (
    echo.
    echo  SoapBoxx Demo could not start.
    echo  Extract the ENTIRE zip to a folder first — do not run this file from inside WinRAR.
    echo.
    echo  Missing: %EXE%
    echo.
    pause
    exit /b 1
)
set "SOAPBOXX_BUCKET=demo"
start "" "%EXE%"
endlocal
"@ | Out-File -FilePath $launcherBat -Encoding ascii

$innerLauncherBat = Join-Path $releaseDir "$exeName\SoapBoxx Production Studio Demo.bat"
@"
@echo off
setlocal
cd /d "%~dp0"
set "EXE=%~dp0$exeName.exe"
if not exist "%EXE%" (
    echo Missing demo executable: %EXE%
    pause
    exit /b 1
)
set "SOAPBOXX_BUCKET=demo"
start "" "%EXE%"
endlocal
"@ | Out-File -FilePath $innerLauncherBat -Encoding ascii

$launcherPs1 = Join-Path $releaseDir "Launch SoapBoxx Production Studio Demo.ps1"
@"
\$ErrorActionPreference = "Stop"
\$exe = Join-Path \$PSScriptRoot "$exeRel"
if (-not (Test-Path \$exe)) {
    Write-Host ""
    Write-Host "Extract the ENTIRE zip to a folder first — do not run from inside WinRAR."
    Write-Host "Missing: \$exe"
    exit 1
}
\$env:SOAPBOXX_BUCKET = "demo"
Start-Process -FilePath \$exe
"@ | Out-File -FilePath $launcherPs1 -Encoding utf8

$metaPath = Join-Path $releaseDir "demo_release.json"
@"
{
  "name": "SoapBoxx Production Studio Demo",
  "version": "$Version",
  "bucket": "demo"
}
"@ | Out-File -FilePath $metaPath -Encoding utf8

Write-Host "Creating zip archive..."
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
$releaseParent = (Resolve-Path $releaseRoot).Path
$releaseLeaf = Split-Path $releaseDir -Leaf
$zipFull = Join-Path $releaseParent "$releaseLeaf.zip"
Push-Location $releaseParent
try {
    # tar -a creates a zip with one top-level folder (more reliable than Compress-Archive on locked files).
    tar.exe -a -c -f $zipFull $releaseLeaf
} finally {
    Pop-Location
}
if (-not (Test-Path $zipFull)) {
    Write-Host "tar zip failed; falling back to Compress-Archive..."
    Start-Sleep -Seconds 3
    Compress-Archive -Path "$releaseDir\*" -DestinationPath $zipFull -Force
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
