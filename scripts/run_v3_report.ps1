# Step 3: SoapBoxx Episode Report (v3) from a full transcript via Ollama.
# Prereqs: Ollama installed, model pulled (`ollama pull <Model>`).
#
# Default template (override any parameter as needed):
#
#   .\scripts\run_v3_report.ps1 `
#     -Transcript "C:\path\to\your_full_transcript.txt" `
#     -Title "Your episode title" `
#     -Creator "Mel Robbins" `
#     -Genre "Education" `
#     -Model "llama3.1:8b"
#
# Minimal run: edit -Transcript below or pass -Transcript only; other defaults apply.

param(
    [string] $Transcript = "",
    [string] $Title = "Sample episode (smoke)",
    [string] $Creator = "SoapBoxx",
    [string] $Genre = "Education",
    [string] $Model = "llama3.1:8b",
    [string] $OutMd = "runs\episode_report_v3.md",
    [string] $JsonBundle = "runs\episode_report_bundle.json",
    [string] $JsonV3 = "runs\episode_report_v3.json"
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

if (-not $Transcript) {
    $Transcript = Join-Path $root "sample_transcript.txt"
}

if (-not (Test-Path -LiteralPath $Transcript)) {
    Write-Error "Transcript not found: $Transcript`nPass -Transcript or add sample_transcript.txt at repo root."
}

$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$env:SOAPBOXX_OLLAMA_MODEL = $Model
if (-not $env:OLLAMA_HOST) { $env:OLLAMA_HOST = "http://127.0.0.1:11434" }
if (-not $env:SOAPBOXX_BRIEF_MAX_CHARS) { $env:SOAPBOXX_BRIEF_MAX_CHARS = "200000" }
if (-not $env:SOAPBOXX_BLUEPRINT_V1) { $env:SOAPBOXX_BLUEPRINT_V1 = "1" }
# This script targets Ollama-backed v3; do not inherit SOAPBOXX_OFFLINE=1 from the environment.
$env:SOAPBOXX_OFFLINE = "0"
$env:PYTHONUTF8 = "1"

& $py (Join-Path $root "scripts\episode_brief.py") `
    -t $Transcript `
    --title $Title `
    -c $Creator `
    -g $Genre `
    --v3 `
    -o $OutMd `
    --json-out $JsonBundle `
    --json-v3-out $JsonV3

Write-Host "Done. Markdown: $(Join-Path $root $OutMd)"
