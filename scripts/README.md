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
