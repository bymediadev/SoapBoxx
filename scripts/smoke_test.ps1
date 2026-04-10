<#
.SYNOPSIS
  Imports, v3 unit tests, optional workflow JSON + doctor_validate_report.

.EXAMPLE
  .\scripts\smoke_test.ps1
.EXAMPLE
  .\scripts\smoke_test.ps1 -RestartUI
#>
param(
    [string]$TranscriptPath = "",
    [switch]$SkipWorkflow,
    [switch]$RestartUI
)

$ErrorActionPreference = "Stop"

function Step($msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$runsDir = Join-Path $repoRoot "runs"
$reportPath = Join-Path $runsDir "smoke_workflow_report.json"
$validateScript = Join-Path $repoRoot "scripts\doctor_validate_report.py"

if (-not (Test-Path $venvPython)) {
    throw ".venv is missing. Run .\scripts\setup_local.ps1 first."
}

Set-Location $repoRoot
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

function Invoke-VenvPythonRedirected {
    param([string[]]$ArgList)
    $stdoutPath = Join-Path $env:TEMP "soapboxx_smoke_stdout.txt"
    $stderrPath = Join-Path $env:TEMP "soapboxx_smoke_stderr.txt"
    Remove-Item $stdoutPath, $stderrPath -ErrorAction SilentlyContinue
    $p = Start-Process -FilePath $venvPython -WorkingDirectory $repoRoot -ArgumentList $ArgList -Wait -PassThru -NoNewWindow `
        -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $code = if ($null -ne $p.ExitCode) { $p.ExitCode } else { -1 }
    $combined = ""
    if (Test-Path $stdoutPath) { $combined += [System.IO.File]::ReadAllText($stdoutPath) }
    if (Test-Path $stderrPath) { $combined += [System.IO.File]::ReadAllText($stderrPath) }
    return @{ ExitCode = $code; Text = $combined }
}

Step "Python version"
& $venvPython --version

Step "Module import smoke check"
& $venvPython -c "import backend.episode_report_v3, backend.soapboxx_v3_workflow, backend.episode_intelligence; print('Core module imports OK')"

Step "Run targeted v3 tests"
& $venvPython -m unittest tests.test_episode_report_v3 tests.test_soapboxx_v3_workflow tests.test_episode_intelligence tests.test_doctor_validate_report

if (-not $SkipWorkflow) {
    $tp = $TranscriptPath
    if (-not $tp) {
        $tp = Join-Path $repoRoot "sample_transcript.txt"
    }
    if (-not (Test-Path $tp)) {
        throw "Transcript file not found: $tp"
    }
    if (-not (Test-Path $runsDir)) { New-Item -ItemType Directory -Force -Path $runsDir | Out-Null }

    Step "Workflow CLI + report validation"
    $rWf = Invoke-VenvPythonRedirected -ArgList @(
        "backend\soapboxx_v3_workflow.py",
        "--transcript", $tp,
        "--output", $reportPath
    )
    if ($rWf.ExitCode -ne 0) {
        throw "workflow failed (exit $($rWf.ExitCode)): $($rWf.Text)"
    }

    $rVal = Invoke-VenvPythonRedirected -ArgList @($validateScript, $reportPath)
    if ($rVal.ExitCode -ne 0) {
        throw "doctor_validate_report.py failed: $($rVal.Text)"
    }

    Write-Host "Report written and validated: $reportPath" -ForegroundColor Green
} else {
    Step "Skipped workflow (-SkipWorkflow)"
}

if ($RestartUI) {
    Step "Restart SoapBoxx UI (pick up backend module changes)"
    & (Join-Path $PSScriptRoot "restart_ui.ps1")
}

Step "Smoke test complete"
