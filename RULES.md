# SoapBoxx — Development Rules

## 1. Core principle

**V1 daily build** ([`SOAPBOXX_V1_7DAY_EXECUTION.md`](SOAPBOXX_V1_7DAY_EXECUTION.md)) — execute **current day only**; no feature creep.

**V1 pipeline** ([`SOAPBOXX_EXECUTION_PLAN_V1.md`](SOAPBOXX_EXECUTION_PLAN_V1.md)):

**Ingest → Transcribe → Segment → Measure → Store → Pattern → Translate**

No coaching, scoring, or ranking in V1. If something feels missing: **V1 or V2?** — not redesign.

## 2. Architecture discipline

- Never create new top-level modules without updating [`ARCHITECTURE.md`](ARCHITECTURE.md)
- All features must belong to Studio (SoapBoxx tab), Scoop, or Reverb
- No "misc" or utils dumping grounds
- Active git lines: see [`BRANCHES.md`](BRANCHES.md) — develop on `production` only

## 3. AI integration rules

- All AI calls MUST go through a single backend facade (target: `backend/llm_service.py`; interim: no new duplicate LLM clients)
- No direct API calls in UI or modules for product features
- No duplicate prompt logic across files

## 4. UI rules

- UI is presentation only
- UI cannot contain business logic
- UI cannot modify transcripts directly

## 5. Feature expansion rule

Before adding a feature, ask ([`SOAPBOXX_MASTER_PLAN_FOUNDATION.md`](SOAPBOXX_MASTER_PLAN_FOUNDATION.md) Rule #5):

> Does this help us collect, organize, compare, or learn from podcast **patterns**?

Legacy loop check: does it improve recording, transcription, or improvement?

If not → reject it

## 6. Refactor rule

- Prefer modifying existing flows over creating new ones
- Do not rename modules unless structure changes globally
- No unplanned refactors; align with [`ARCHITECTURE.md`](ARCHITECTURE.md) when changing structure

## 7. Data rule

Every recording must resolve into an episode/session object containing:

- audio
- transcript
- analysis
- metadata

No exceptions.

## 8. Stability rule

If uncertain:

- preserve working behavior
- do not optimize prematurely

## 9. Source-of-truth paths

Do not edit as product code:

- `releases/`
- `SoapBoxx-Distribution-v1.0.0/`
- `SoapBoxx-Demo-Distribution/`
- `reports/`
