<#
.SYNOPSIS
  One-command environment check: setup (optional), imports, tests, workflow, report validation.

.EXAMPLE
  .\scripts\doctor.ps1
.EXAMPLE
  .\scripts\doctor.ps1 -Fast
.EXAMPLE
  .\scripts\doctor.ps1 -CI
.EXAMPLE
  .\scripts\doctor.ps1 -TranscriptPath .\sample_transcript.txt -SkipWorkflow:$false
.EXAMPLE
  .\scripts\doctor.ps1 -RestartUI
#>
param(
    [switch]$Fast,
    [switch]$CI,
    [switch]$SkipWorkflow,
    [string]$TranscriptPath = "",
    [switch]$RebuildVenv,
    [switch]$UsePytest,
    [switch]$CheckRequirementsFingerprint,
    [switch]$RestartUI
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$runsDir = Join-Path $repoRoot "runs"
$reportPath = Join-Path $runsDir "smoke_workflow_report.json"
$setupScript = Join-Path $repoRoot "scripts\setup_local.ps1"
$validateScript = Join-Path $repoRoot "scripts\doctor_validate_report.py"

$useCi = $CI -or ($env:CI -eq "true") -or ($env:CI -eq "1")

function Write-DoctorLine {
    param([string]$Message, [string]$Color = "White")
    if ($useCi) {
        Write-Output $Message
    } else {
        Write-Host $Message -ForegroundColor $Color
    }
}

function Write-Ok { param([string]$m) Write-DoctorLine "  [OK] $m" "Green" }
function Write-Fail { param([string]$m) Write-DoctorLine "  [FAIL] $m" "Red" }
function Write-WarnLine { param([string]$m) Write-DoctorLine "  [WARN] $m" "Yellow" }

function Fail-Stage {
    param(
        [string]$Stage,
        [string]$Message,
        [string]$NextSteps
    )
    Write-Fail "[$Stage] $Message"
    if ($NextSteps) {
        Write-DoctorLine "  Next: $NextSteps" "Yellow"
    }
    if ($useCi) {
        Write-Output "DOCTOR_FAIL $Stage"
    } else {
        Write-Host ""
        Write-Host "STATUS: broken" -ForegroundColor Red
    }
    exit 1
}

function Invoke-PythonRedirected {
    param(
        [string[]]$Arguments
    )
    $stdoutPath = Join-Path $env:TEMP "soapboxx_doctor_stdout.txt"
    $stderrPath = Join-Path $env:TEMP "soapboxx_doctor_stderr.txt"
    Remove-Item $stdoutPath, $stderrPath -ErrorAction SilentlyContinue
    $p = Start-Process -FilePath $venvPython -WorkingDirectory $repoRoot -ArgumentList $Arguments -Wait -PassThru -NoNewWindow `
        -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $code = if ($null -ne $p.ExitCode) { $p.ExitCode } else { -1 }
    $combined = ""
    if (Test-Path $stdoutPath) { $combined += [System.IO.File]::ReadAllText($stdoutPath) }
    if (Test-Path $stderrPath) { $combined += [System.IO.File]::ReadAllText($stderrPath) }
    return @{ ExitCode = $code; Text = $combined }
}

Set-Location $repoRoot
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
# So `import backend` works when the helper script lives under $env:TEMP (not under the repo).
$env:PYTHONPATH = $repoRoot

if (-not $useCi) {
    Write-Host ""
    Write-Host "SoapBoxx doctor" -ForegroundColor Cyan
    Write-Host "---------------" -ForegroundColor Cyan
}

# --- Optional requirements fingerprint ---
if ($CheckRequirementsFingerprint) {
    $reqBits = @()
    foreach ($name in @("requirements.txt", "requirements-dev.txt", "requirements-episode-intelligence.txt")) {
        $p = Join-Path $repoRoot $name
        if (Test-Path $p) { $reqBits += (Get-Content $p -Raw) }
    }
    $bytes = [System.Text.Encoding]::UTF8.GetBytes(($reqBits -join "`n"))
    $sha = [System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
    $hex = ([BitConverter]::ToString($sha) -replace '-', '').ToLowerInvariant()
    $fpFile = Join-Path $runsDir "doctor_requirements.sha256"
    if (-not (Test-Path $runsDir)) { New-Item -ItemType Directory -Force -Path $runsDir | Out-Null }
    if (Test-Path $fpFile) {
        $prev = (Get-Content $fpFile -Raw).Trim()
        if ($prev -and $prev -ne $hex) {
            Write-WarnLine "requirements fingerprint changed (previous doctor run). Re-run setup if installs drift."
        }
    }
    Set-Content -Path $fpFile -Value $hex -Encoding utf8
    if (-not $useCi) { Write-Ok "requirements fingerprint: $hex" }
}

# --- ENV: venv + setup ---
if (-not $Fast) {
    if (-not (Test-Path $setupScript)) {
        Fail-Stage "ENV" "setup script missing: $setupScript" "Restore scripts/setup_local.ps1 from the repo."
    }
    try {
        if ($RebuildVenv) {
            & $setupScript -RebuildVenv
        } else {
            & $setupScript
        }
    } catch {
        Fail-Stage "ENV" $_.Exception.Message "Close apps using .venv, run: .\scripts\setup_local.ps1 -RebuildVenv"
    }
} else {
    if (-not (Test-Path $venvPython)) {
        Fail-Stage "ENV" ".venv missing (Fast mode skips install)" "Run without -Fast, or: .\scripts\setup_local.ps1"
    }
    if (-not $useCi) { Write-Ok "Fast mode: skipped dependency install" }
}

if (-not (Test-Path $venvPython)) {
    Fail-Stage "ENV" "Python not found at $venvPython" "Run .\scripts\setup_local.ps1"
}

# --- IMPORTS ---
# Use a temp script (not -c) so semicolons are not mangled by Start-Process argument parsing on Windows.
$importTmp = Join-Path $env:TEMP "soapboxx_doctor_import_check.py"
@'
import pydantic, tenacity
import backend.episode_report_v3, backend.soapboxx_v3_workflow, backend.episode_intelligence
print("ok")
'@ | Set-Content -Path $importTmp -Encoding UTF8
$rImport = Invoke-PythonRedirected -Arguments @($importTmp)
Remove-Item $importTmp -ErrorAction SilentlyContinue
if ($rImport.ExitCode -ne 0) {
    Fail-Stage "IMPORTS" $rImport.Text "Activate .venv and run: pip install -r requirements.txt"
}
if (-not $useCi) { Write-Ok "Core Python imports" }

# --- TESTS ---
$testModulesFull = @(
    "tests.test_episode_report_v3",
    "tests.test_soapboxx_v3_workflow",
    "tests.test_episode_intelligence",
    "tests.test_doctor_validate_report"
)
$testModulesFast = @("tests.test_episode_report_v3")
$mods = if ($Fast) { $testModulesFast } else { $testModulesFull }

$testFilesFull = @(
    "tests/test_episode_report_v3.py",
    "tests/test_soapboxx_v3_workflow.py",
    "tests/test_episode_intelligence.py",
    "tests/test_doctor_validate_report.py"
)
$testFilesFast = @("tests/test_episode_report_v3.py")
$tfiles = if ($Fast) { $testFilesFast } else { $testFilesFull }

$hasPytest = $false
& $venvPython -c "import pytest" 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { $hasPytest = $true }

$testFailed = $false
$testTail = ""
if ($hasPytest -and $UsePytest) {
    $pyArgs = @("-m", "pytest") + $tfiles + @("-q", "--tb=short", "--no-header")
    if ($useCi) { $pyArgs += "--disable-warnings" }
    $r = Invoke-PythonRedirected -Arguments $pyArgs
    if ($r.ExitCode -ne 0) {
        $testFailed = $true
        $lines = $r.Text -split "`r?`n"
        $take = [Math]::Min(30, $lines.Count)
        if ($take -gt 0) {
            $testTail = ($lines[($lines.Count - $take)..($lines.Count - 1)] -join "`n")
        }
    }
} else {
    $pyArgs = @("-m", "unittest") + $mods
    $r = Invoke-PythonRedirected -Arguments $pyArgs
    if ($r.ExitCode -ne 0) {
        $testFailed = $true
        $lines = $r.Text -split "`r?`n"
        $take = [Math]::Min(30, $lines.Count)
        if ($take -gt 0) {
            $testTail = ($lines[($lines.Count - $take)..($lines.Count - 1)] -join "`n")
        }
    }
}

if ($testFailed) {
    $msg = "Tests failed.`n--- last 30 lines ---`n$testTail"
    Fail-Stage "TESTS" $msg "Fix failing tests; re-run doctor. If using pytest, try without -UsePytest."
}
if (-not $useCi) { Write-Ok "Tests ($($mods -join ', '))" }

# --- WORKFLOW + OUTPUT ---
if ($SkipWorkflow) {
    if (-not $useCi) { Write-WarnLine "Skipped workflow (-SkipWorkflow)" }
} else {
    $tp = $TranscriptPath
    if (-not $tp) {
        $tp = Join-Path $repoRoot "sample_transcript.txt"
    }
    if (-not (Test-Path $tp)) {
        Fail-Stage "WORKFLOW/OUTPUT" "Transcript not found: $tp" "Pass -TranscriptPath or add sample_transcript.txt"
    }
    if (-not (Test-Path $runsDir)) { New-Item -ItemType Directory -Force -Path $runsDir | Out-Null }
    $rWf = Invoke-PythonRedirected -Arguments @(
        "backend\soapboxx_v3_workflow.py",
        "--transcript", $tp,
        "--output", $reportPath
    )
    if ($rWf.ExitCode -ne 0) {
        Fail-Stage "WORKFLOW/OUTPUT" $rWf.Text "Run: .\.venv\Scripts\python.exe backend\soapboxx_v3_workflow.py --transcript `"$tp`" --output `"$reportPath`""
    }
    if (-not (Test-Path $reportPath)) {
        Fail-Stage "WORKFLOW/OUTPUT" "Report not written: $reportPath" "Check workflow stderr for errors"
    }
    $rVal = Invoke-PythonRedirected -Arguments @($validateScript, $reportPath)
    if ($rVal.ExitCode -ne 0) {
        foreach ($line in ($rVal.Text -split "`r?`n")) {
            if ("$line") { Write-DoctorLine "$line" "Red" }
        }
        Fail-Stage "WORKFLOW/OUTPUT" "Report validation failed: $reportPath" "Inspect JSON; ensure summary/score and sections are populated."
    }
    if (-not $useCi) { Write-Ok "Workflow report + validation: $reportPath" }
}

# --- Summary ---
if ($useCi) {
    Write-Output "DOCTOR_OK"
} else {
    Write-Host ""
    Write-Host "STATUS: healthy" -ForegroundColor Green
    $parts = @("venv", "imports", "tests")
    if (-not $SkipWorkflow) { $parts += "workflow report" }
    else { $parts += "workflow skipped" }
    Write-Host ("  ({0})" -f ($parts -join ", ")) -ForegroundColor Gray
}

if ($RestartUI -and -not $useCi) {
    Write-Host ""
    Write-Host "==> Restart SoapBoxx UI (pick up backend module changes)" -ForegroundColor Cyan
    & (Join-Path $PSScriptRoot "restart_ui.ps1")
}

exit 0
