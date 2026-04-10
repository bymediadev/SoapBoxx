<#
.SYNOPSIS
  Restart the SoapBoxx PyQt desktop app so it reloads Python modules from disk.

.DESCRIPTION
  Stops python.exe processes whose command line indicates frontend.main_window / main_window,
  then starts a new instance via the repo .venv. Use after backend changes; CI should not call this.

.EXAMPLE
  .\scripts\restart_ui.ps1
.EXAMPLE
  .\scripts\restart_ui.ps1 -NoKill
#>
param(
    [switch]$NoKill
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    throw ".venv not found at $venvPython. Run .\scripts\setup_local.ps1"
}

if (-not $NoKill) {
    $toKill = @(
        Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -match 'main_window|frontend\.main_window' }
    )
    foreach ($proc in $toKill) {
        Write-Host "Stopping SoapBoxx UI (PID $($proc.ProcessId))" -ForegroundColor Yellow
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    if ($toKill.Count -gt 0) {
        Start-Sleep -Milliseconds 500
    } else {
        Write-Host "No running SoapBoxx main_window process found." -ForegroundColor Gray
    }
}

Write-Host "Starting SoapBoxx UI..." -ForegroundColor Cyan
Start-Process -FilePath $venvPython -ArgumentList "-m", "frontend.main_window" -WorkingDirectory $repoRoot
