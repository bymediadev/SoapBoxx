# SoapBoxx — System Architecture

**Purpose:** See [`SOAPBOXX_MASTER_PLAN_FOUNDATION.md`](SOAPBOXX_MASTER_PLAN_FOUNDATION.md) — build a measurement/pattern library; sources (Spotify, YouTube, RSS) feed ingest, not the primary asset.

**V1 API (Day 1+):** FastAPI + Postgres + Redis — [`docs/V1_DAY01.md`](docs/V1_DAY01.md), entry `uvicorn main:app`. Desktop PyQt remains legacy until V1 API reaches parity.

## High-level structure

SoapBoxx is divided into three user-facing modules:

| Module | UI tab | Purpose |
|--------|--------|---------|
| **Studio** (optional) | SoapBoxx | Recording — hidden unless `SOAPBOXX_SHOW_STUDIO=1` |
| **Scoop** | Scoop | Guest/topic prep |
| **Coach** | Coach | Post-episode **Episode Coach Report** (sections A–F) |

## Current repo mapping (source of truth)

The pack describes logical `/studio`, `/scoop`, `/reverb`, and `/services/*` folders. **Today the repo uses a flat `backend/` + `frontend/` layout:**

| Pack / logical | Actual path |
|----------------|-------------|
| Studio | [`frontend/soapboxx_tab.py`](frontend/soapboxx_tab.py), [`backend/soapboxx_core.py`](backend/soapboxx_core.py), [`backend/audio_recorder.py`](backend/audio_recorder.py) |
| Scoop | [`frontend/scoop_tab.py`](frontend/scoop_tab.py), [`backend/guest_research.py`](backend/guest_research.py) |
| Coach | [`frontend/reverb_tab.py`](frontend/reverb_tab.py), [`backend/episode_coach_report.py`](backend/episode_coach_report.py), [`backend/feedback_engine.py`](backend/feedback_engine.py) |
| Audio service | [`backend/audio_recorder.py`](backend/audio_recorder.py) |
| Transcription | [`backend/transcriber.py`](backend/transcriber.py) |
| AI (facade) | [`backend/llm_service.py`](backend/llm_service.py) wraps workflow LLM; also `feedback_engine`, `episode_intelligence`, `guest_research`, `blueprint_v1/llm_runner` |
| Question extraction | [`backend/question_extraction.py`](backend/question_extraction.py) |
| Scoop news | [`backend/scoop_news.py`](backend/scoop_news.py) |

Structural `/services/*` directories are a **target**, not the current tree.

## Canonical pipelines

### Desktop app (v1 — default for UI work)

```text
Coach tab → episode_ingest (URL / file / paste)
         → transcriber (audio only)
         → FeedbackEngine.generate_episode_coach_report
         → intelligence_v1 (metrics, SQLite, tier)
```

Do not wire new UI features through batch-only pipelines unless explicitly requested.

### Batch / CI / export (non-default for UI)

- [`backend/soapboxx_v3_workflow.py`](backend/soapboxx_v3_workflow.py)
- [`backend/episode_report_v3.py`](backend/episode_report_v3.py)
- [`backend/blueprint_v1/`](backend/blueprint_v1/)
- [`backend/atomic_pipeline/`](backend/atomic_pipeline/)

Used for scripts, evaluation, and markdown/JSON exports — not the primary PyQt path.

### V0/V1 instrumentation (see [`docs/SYSTEM_DESIGN_V0_V1.md`](docs/SYSTEM_DESIGN_V0_V1.md))

```text
episode_ingest → transcriber → backend/features (rule-based metrics)
  → intelligence_v1/db.py (SQLite)
  → analyzer (category benchmarks)
  → report (comparison; tier optional via SOAPBOXX_ENABLE_TIER)
```

### Insights library (hosting platforms as source)

```text
Spotify / Apple / YouTube / RSS  (catalog — not owned by SoapBoxx)
  → episode_ingest + weekly batch (backend/library/)
  → SQLite shelf: category → author → show → episodes
  → Coach / intelligence on demand
```

See [`docs/LIBRARY_AND_BATCH.md`](docs/LIBRARY_AND_BATCH.md).

Default metrics: **`backend/features/rule_based.py`** (reproducible).  
LLM metrics: only if `SOAPBOXX_LLM_METRICS=1`.  
Coach (A–F): separate product layer — [`episode_coach_report.py`](backend/episode_coach_report.py).

CLI: [`scripts/run_intelligence_pipeline.py`](scripts/run_intelligence_pipeline.py).

## Data flow

```text
Import (YouTube / file / paste)
  → Extract + normalize transcript
  → Episode Coach Report (A–F)
  → Intelligence (metrics + category benchmarks + tier)
  → SQLite history for comparison

Optional: Studio record (`SOAPBOXX_SHOW_STUDIO=1`); Scoop (`SOAPBOXX_SHOW_SCOOP=1`)
```

## UI rule

UI must **never** contain business logic. UI only:

- triggers actions
- displays results

## State management

Each recording session should resolve to one episode/session object:

- audio file (path)
- transcript
- analysis
- metadata

Today: [`RecordingSession`](backend/soapboxx_core.py) plus separate v3/strict JSON shapes — converging to one model is planned.

## Constraints

- No duplication of AI logic across modules (migrate to `llm_service`)
- No direct product API calls from `frontend/`
- No cross-module circular dependencies
- Git: see [`BRANCHES.md`](BRANCHES.md)

## v1 freeze scope (active)

**In scope:** record, transcribe, Episode Coach Report, export. Scoop optional.

**Out of scope for desktop v1:** new tabs, extending blueprint/atomic pipelines in UI, physical folder moves to `/studio` without a planned migration.

**Pre-release checklist:** [`docs/V1_RELEASE_CHECKLIST.md`](docs/V1_RELEASE_CHECKLIST.md)

**LLM callers (facade):** `feedback_engine` and `blueprint_v1/llm_runner` use [`backend/llm_service.py`](backend/llm_service.py). Episode briefs remain on `episode_intelligence` (Ollama). Workflow internals still implement `call_llm` inside `soapboxx_v3_workflow`.

## Ignore paths (not source code)

- `releases/`
- `SoapBoxx-Distribution-v1.0.0/`
- `SoapBoxx-Demo-Distribution/`
- `reports/`
