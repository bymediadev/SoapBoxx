# SoapBoxx — System Architecture

## High-level structure

SoapBoxx is divided into three user-facing modules:

| Module | UI tab | Purpose |
|--------|--------|---------|
| **Studio** | SoapBoxx | Recording, transcription |
| **Scoop** | Scoop | Guest/topic prep |
| **Reverb** | Reverb | Analysis and improvement feedback |

## Current repo mapping (source of truth)

The pack describes logical `/studio`, `/scoop`, `/reverb`, and `/services/*` folders. **Today the repo uses a flat `backend/` + `frontend/` layout:**

| Pack / logical | Actual path |
|----------------|-------------|
| Studio | [`frontend/soapboxx_tab.py`](frontend/soapboxx_tab.py), [`backend/soapboxx_core.py`](backend/soapboxx_core.py), [`backend/audio_recorder.py`](backend/audio_recorder.py) |
| Scoop | [`frontend/scoop_tab.py`](frontend/scoop_tab.py), [`backend/guest_research.py`](backend/guest_research.py) |
| Reverb | [`frontend/reverb_tab.py`](frontend/reverb_tab.py), [`backend/feedback_engine.py`](backend/feedback_engine.py) |
| Audio service | [`backend/audio_recorder.py`](backend/audio_recorder.py) |
| Transcription | [`backend/transcriber.py`](backend/transcriber.py) |
| AI (target facade) | `backend/llm_service.py` (planned); today: `feedback_engine`, `episode_intelligence`, `guest_research`, `soapboxx_v3_workflow`, `blueprint_v1/llm_runner`, `ollama_chat_http` |

Structural `/services/*` directories are a **target**, not the current tree.

## Canonical pipelines

### Desktop app (v1 — default for UI work)

```text
SoapBoxx tab → SoapBoxxCore → audio_recorder
                          → transcriber
                          → Reverb tab → FeedbackEngine
```

Do not wire new UI features through batch-only pipelines unless explicitly requested.

### Batch / CI / export (non-default for UI)

- [`backend/soapboxx_v3_workflow.py`](backend/soapboxx_v3_workflow.py)
- [`backend/episode_report_v3.py`](backend/episode_report_v3.py)
- [`backend/blueprint_v1/`](backend/blueprint_v1/)
- [`backend/atomic_pipeline/`](backend/atomic_pipeline/)

Used for scripts, evaluation, and markdown/JSON exports — not the primary PyQt path.

## Data flow

```text
Audio Input
  → Studio (recording)
  → Transcription (Whisper / OpenAI / local)
  → Structured transcript
  → Reverb analysis
  → Feedback + insights

Optional: Scoop → prep context for Studio
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

## v1 freeze scope

**In scope:** record, transcribe, Scoop prep, Reverb feedback, export.

**Out of scope for desktop v1:** new tabs, extending blueprint/atomic pipelines in UI, physical folder moves to `/studio` without a planned migration.

## Ignore paths (not source code)

- `releases/`
- `SoapBoxx-Distribution-v1.0.0/`
- `SoapBoxx-Demo-Distribution/`
- `reports/`
