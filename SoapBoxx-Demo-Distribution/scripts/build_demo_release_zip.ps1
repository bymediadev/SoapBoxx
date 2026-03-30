# Build SoapBoxx-Demo-vVERSION.zip for GitHub Releases (from demo/soapboxx-barebones tree).
# Run from a clean checkout on demo/soapboxx-barebones. Output is a zip whose root folder is SoapBoxx-Demo/.

param(
    [string]$Version = "1.0.0",
    [string]$OutDir = "",
    [switch]$AlsoStableName,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    Write-Host @"
Build SoapBoxx-Demo-vVERSION.zip for attaching to a GitHub Release.

Usage:
  .\build_demo_release_zip.ps1 [-Version "1.0.0"] [-OutDir "path"] [-Help]

  -Version   Version tag for the filename (default 1.0.0). Match your Git tag, e.g. demo-v1.0.0
  -OutDir    Folder for the zip (default: SoapBoxx-Demo-Distribution\release next to this script)
  -AlsoStableName  Also write SoapBoxx-Demo.zip (same contents) for a stable GitHub asset name:
                    .../releases/latest/download/SoapBoxx-Demo.zip

Steps after build:
  1. Create a release on https://github.com/bymediadev/SoapBoxx/releases
  2. Upload SoapBoxx-Demo-vVERSION.zip
  3. Point testers at: Releases -> latest, or paste the asset URL into your email

Excludes: .env, .venv, __pycache__, .git, local beta state files (see script).
"@
    exit 0
}

$ScriptDir = $PSScriptRoot
$DemoSrc = Join-Path $ScriptDir "..\SoapBoxx-Demo" | Resolve-Path
if (-not (Test-Path (Join-Path $DemoSrc "frontend\main_window.py"))) {
    Write-Host "ERROR: SoapBoxx-Demo not found or incomplete at: $DemoSrc" -ForegroundColor Red
    exit 1
}

if (-not $OutDir) {
    $OutDir = Join-Path $ScriptDir "..\release"
}
$OutDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutDir)
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$zipName = "SoapBoxx-Demo-v$Version.zip"
$zipPath = Join-Path $OutDir $zipName

$stagingRoot = Join-Path $env:TEMP ("soapboxx-demo-zip-" + [guid]::NewGuid().ToString("n"))
$stagingDemo = Join-Path $stagingRoot "SoapBoxx-Demo"
try {
    New-Item -ItemType Directory -Path $stagingDemo -Force | Out-Null

    # /E copy subdirs; robocopy exit 0-7 = success
    & robocopy $DemoSrc $stagingDemo /E `
        /XD __pycache__ .git .venv .pytest_cache .mypy_cache `
        /XF .env .soapboxx_beta_state.json beta_events.jsonl *.pyc `
        /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) {
        Write-Host "ERROR: robocopy failed with exit $LASTEXITCODE" -ForegroundColor Red
        exit 1
    }

    if (Test-Path $zipPath) {
        Remove-Item -Force $zipPath
    }
    Compress-Archive -Path $stagingDemo -DestinationPath $zipPath -CompressionLevel Optimal

    $len = (Get-Item $zipPath).Length
    Write-Host ""
    Write-Host "OK: $zipPath" -ForegroundColor Green
    Write-Host "     Size: $len bytes"
    Write-Host ""
    Write-Host "Next: upload to GitHub Releases, then share:" -ForegroundColor Cyan
    Write-Host "  https://github.com/bymediadev/SoapBoxx/releases"
    Write-Host "  Direct asset URL pattern (replace TAG):" -ForegroundColor DarkGray
    Write-Host "  https://github.com/bymediadev/SoapBoxx/releases/download/TAG/$zipName"
    if ($AlsoStableName) {
        $stable = Join-Path $OutDir "SoapBoxx-Demo.zip"
        Copy-Item -Path $zipPath -Destination $stable -Force
        Write-Host ""
        Write-Host "Also wrote (stable name for latest/download):" -ForegroundColor Cyan
        Write-Host "  $stable"
        Write-Host "  https://github.com/bymediadev/SoapBoxx/releases/latest/download/SoapBoxx-Demo.zip"
    }
}
finally {
    if (Test-Path $stagingRoot) {
        Remove-Item -Recurse -Force $stagingRoot -ErrorAction SilentlyContinue
    }
}
