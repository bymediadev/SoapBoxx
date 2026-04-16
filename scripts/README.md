# SoapBoxx scripts

| Script | Purpose |
|--------|---------|
| `setup_local.ps1` | Create/update `.venv` and install `requirements*.txt` |
| `smoke_test.ps1` | Imports, unit tests, workflow JSON + validation (defaults to `sample_transcript.txt`) |
| `doctor.ps1` | Full health check: setup (unless `-Fast`), imports, tests, workflow, report validation |
| `doctor_validate_report.py` | Validates `summary`, `score`, and non-empty sections in a workflow JSON file |

Typical flow (Windows PowerShell, repo root):

```powershell
.\scripts\setup_local.ps1
.\scripts\doctor.ps1 -Fast
```

CI-friendly:

```powershell
.\scripts\doctor.ps1 -CI -Fast -SkipWorkflow
```

Linux/macOS can run the same Python steps as in `.github/workflows/doctor.yml`.

## Episode report (v3) — transcript cleanup (default on)

`generate_episode_report_v3` / Reverb v3 **normalize** ASR-heavy text by default (dedupe consecutive
lines, collapse long blank runs). Disable if you need the raw string:

```powershell
$env:SOAPBOXX_TRANSCRIPT_NORMALIZE = "0"
```

## Ollama model and editorial pass

For local LLM (brief + workflow), set a model and keep Ollama running:

```powershell
$env:SOAPBOXX_OLLAMA_MODEL = "llama3.1:8b"   # or your pulled tag (`ollama pull llama3.1:8b`)
$env:OLLAMA_HOST = "http://127.0.0.1:11434"
```

Long episodes: raise context if your hardware allows (example 8192):

```powershell
$env:SOAPBOXX_OLLAMA_NUM_CTX = "8192"
```

**Editorial pass** (one light polish on unified markdown: wording, obvious ASR glitches) runs automatically
when `SOAPBOXX_OLLAMA_MODEL` is set. Turn off with:

```powershell
$env:SOAPBOXX_EDITORIAL_PASS = "0"
```
