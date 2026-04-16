# SoapBoxx codebase overview

This document describes the **main development tree** at the repo root (`SoapBoxx/`). Nested folders such as `SoapBoxx-Distribution-v1.0.0/` and `SoapBoxx-Demo-Distribution/` are **packaged or demo snapshots**—use root sources as the source of truth unless you are building a release.

## Top-level layout

| Path | Role |
|------|------|
| `backend/` | Core Python services: transcription, feedback, v3 workflow, episode reports, **Master Blueprint v1** (`blueprint_v1/`), config, APIs. |
| `frontend/` | PyQt6 UI: main window, tabs (SoapBoxx / Scoop / Reverb), batch processing, themes. |
| `scripts/` | CLIs (e.g. `episode_brief.py`, batch / strategist runners). |
| `tests/` | Pytest suite (unit + integration-style scripts). |
| `docs/` | Product and technical documentation. |
| `reports/` | Generated run outputs (often gitignored or large; not source). |

Entry points consumers care about:

- **Desktop app**: `frontend/main_window.py` (and related tabs) launched from project scripts or frozen `SoapBoxx.exe` in releases.
- **Episode analysis from transcript**: `scripts/episode_brief.py` (`--v3`, optional `--network-snapshot`).
- **Blueprint v1 (structured JSON strategist)**: `backend/blueprint_v1/pipeline.py` → `run_blueprint_v1`; integrated via `backend/feedback_engine.py` when enabled.

## Backend (concise)

- **`feedback_engine.py`** — Orchestrates brief generation; can attach Blueprint v1 output (`public_payload()` for external-facing JSON).
- **`episode_intelligence.py`** — Episode brief / LLM path for v2-style output.
- **`episode_report_v3.py`** — Unified markdown export for the app; strategist sections; legacy diagnostic blocks removed from user-facing export where configured.
- **`soapboxx_v3_workflow.py`** — Local v3 workflow glue, reality checks, metadata.
- **`transcriber.py`** / **`transcriber_barebones.py`** — Audio → text (OpenAI, local, etc., per config).
- **`blueprint_v1/`** — Classification → narrative/analytical → thesis → clips → synthesis → **MASTER_STRATEGIST** JSON; Ollama via `llm_runner.py` (`run_json_prompt`, `run_text_prompt`).
- **`youtube_subtitles.py`** — Rate-limit-friendly English VTT download (two-phase: manual `en`, then auto `en`).
- **`config.py`**, **`logger.py`**, **`error_tracker.py`** — Cross-cutting concerns.

## Frontend (concise)

- Tab-based UI: recording, research (“Scoop”), analysis (“Reverb”), batch jobs.
- Theme and keyboard handling under `frontend/`; distribution copies may lag—edit root `frontend/` first.

## Scripts (concise)

- **`episode_brief.py`** — Transcript/audio → markdown (v2, `--v3` full report, `--network-snapshot` editorial memo via Ollama text).
- **`run_strategist_real_batch.py`** — Dev/batch validation using captions + Blueprint strategist path.

## Configuration

- **`.env`** at repo root (see **`.env.example`**): Ollama, brief limits, Blueprint flags, optional YouTube/yt-dlp tuning, JSON integrity logging.

## Tests

- Run: `python -m pytest tests -q`
- Some tests **skip** if optional deps or API keys are missing (YouTube, snscrape, local Whisper, etc.).

## Known architectural notes

- **Duplicate trees**: `SoapBoxx-Distribution-*` duplicates are for packaging; avoid diverging logic there without syncing back to root.
- **Integration tests that hit the network** are intentionally soft (skip/fail gracefully) so CI stays green without secrets.

## Dependency overview

See **`requirements.txt`** (runtime) and **`requirements-dev.txt`** / **`requirements-dev-qt.txt`** for development and Qt tooling.
