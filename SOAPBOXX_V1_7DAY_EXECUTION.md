# SoapBoxx V1 — 7 Day Execution Plan (Cursor Ready)

**Status:** V1 pipeline **complete** (Days 1–7 verified) — scope still locked for V2+  
**Goal:** Working podcast library + measurement pipeline + basic meaning layer  
**Constraint:** No scoring, no coaching expansion, no new modules  

**Authority:** This doc is the **daily build order**. [`SOAPBOXX_EXECUTION_PLAN_V1.md`](SOAPBOXX_EXECUTION_PLAN_V1.md) is the layer/spec reference. If they conflict on scope, this doc wins for **what to build each day**.

**Cursor rule when something feels missing:**

> Does this belong in V1 or V2?  
> If not in this checklist → **not V1**. Do not redesign.

---

## Status block

```text
Locked Scope: V1 (NO NEW FEATURES UNTIL COMPLETE)
Goal: Working podcast library + measurement pipeline + basic meaning layer
Constraint: No scoring, no coaching expansion, no new modules
```

---

## Core product identity (locked)

> SoapBoxx is a podcast library system that converts episodes into structured measurements and translates them into human-readable insights.

---

# Day 1 — Foundation + clean architecture

## Goal

Get system structure stable and runnable.

## Tasks

### Backend setup

- [x] FastAPI app running (`main:app`, `GET /health`)
- [x] Postgres connected (`docker-compose.v1.yml`, Alembic)
- [x] Redis running (health check + Celery broker stub)

### Folder structure (must match spec)

```text
backend/api/
backend/services/
backend/workers/
backend/models/
backend/batch/
```

### Database migration init

Create tables:

- [x] `podcasts`
- [x] `episodes`
- [x] `transcript_segments`
- [x] `episode_features`
- [x] `taxonomy_nodes`
- [x] `podcast_taxonomy_map`

## Done when

- [x] `uvicorn main:app` runs successfully — see [`docs/V1_DAY01.md`](docs/V1_DAY01.md)
- [x] DB migrations apply cleanly — `alembic upgrade head`

---

# Day 2 — Podcast + episode core

## Goal

Create source layer (no intelligence yet).

## API endpoints

- [x] `POST /podcasts`
- [x] `GET /podcasts`
- [x] `POST /episodes`
- [x] `GET /episodes/{id}`

## Core behavior

- Podcast = container
- Episode = atomic unit
- No processing yet

## Done when

- [x] You can manually create podcast + episode via API — see [`docs/V1_DAY02.md`](docs/V1_DAY02.md)

---

# Day 3 — RSS ingestion (critical)

## Goal

Automate content ingestion.

## Build

| Piece | Path |
|-------|------|
| Service | `backend/services/rss_service.py` |
| Endpoint | `POST /ingest/rss` |

- [x] `backend/services/rss_service.py`
- [x] `POST /ingest/rss`

### Behavior

- Fetch RSS feed
- Create episodes
- Store metadata only (no transcription yet)

## Done when

- [x] One podcast RSS feed populates multiple episodes automatically — [`docs/V1_DAY03.md`](docs/V1_DAY03.md)

---

# Day 4 — Transcription pipeline

## Goal

Convert episodes → structured text.

## Build

- [x] `backend/services/transcription_service.py`
- [x] Celery task: `transcribe_episode`

## Output

```text
episode_id
full_transcript
segments[]  → transcript_segments
```

## Done when

- [x] Episode can be fully transcribed and stored — [`docs/V1_DAY04.md`](docs/V1_DAY04.md)

---

# Day 5 — Feature extraction (structure only)

## Goal

Measure episodes (NO AI opinions).

## Implement exactly 7 metrics

```text
1. hook_length_seconds
2. intro_length_seconds
3. question_count
4. speaking_turns
5. host_guest_ratio
6. topic_shift_count
7. cta_present
```

## Rules

- Deterministic or simple NLP only
- No scoring
- No ranking

## Done when

- [x] Every transcribed episode has one row in `episode_features` — [`docs/V1_DAY05.md`](docs/V1_DAY05.md)

---

# Day 6 — Taxonomy + library structure

## Goal

Turn system into a browsable library.

## Build

- [x] `taxonomy_nodes`
- [x] `podcast_taxonomy_map`

### Structure

```text
Domain → Category → Subcategory
```

Example: Business → Entrepreneurship → Startups

## Behavior

- Podcasts assigned to taxonomy (many-to-many)
- Episodes inherit podcast taxonomy

## Done when

- [x] You can browse podcasts by category tree (API or UI) — [`docs/V1_DAY06.md`](docs/V1_DAY06.md)

---

# Day 7 — Translation layer (wow layer)

## Goal

Turn metrics into meaning (not advice).

## Build

- [x] `backend/services/translation_service.py`

### Input

`episode_features`

### Output templates only (examples)

**Template A:** Guest-led conversation with minimal host structuring.

**Template B:** Highly structured interview with frequent guiding questions.

**Template C:** Narrative-driven episode with low question density.

## Rules

- NO scoring
- NO advice
- NO optimization
- ONLY interpretation of structure

## Done when

- [x] Every episode with features displays a translated insight (`episode_translations`) — [`docs/V1_DAY07.md`](docs/V1_DAY07.md)

---

# System rules (do not break)

| # | Rule |
|---|------|
| 1 | **No feature creep** — not on this list → not V1 |
| 2 | **No scoring** — no good/bad, no ratings |
| 3 | **Measurement before meaning** — features before translation |
| 4 | **RSS is mandatory** — without RSS, V1 is incomplete |
| 5 | **Library structure > dashboards** — taxonomy navigation is primary |

---

# Final output state (V1 feel)

When complete, you can:

1. Add a podcast via RSS
2. Automatically ingest episodes
3. View episodes in a library tree
4. Open an episode and see: transcript, structure metrics, translated meaning

---

# What you are NOT building

- AI coach
- Scoring system
- Rankings
- Recommendations engine
- “Best podcast” detection

Existing desktop Coach UI is **legacy / out of V1 scope** — do not expand during this 7-day build.

---

# Daily verification (test suite plan)

**Spec:** [`docs/V1_TEST_SUITE.md`](docs/V1_TEST_SUITE.md) — PASS/FAIL per day; no intuition.

Run after each day’s checklist before starting the next day.

| Day | Command | PASS when |
|-----|---------|-----------|
| 1 | `pytest tests/test_day1_foundation.py -v` | API, DB, 6 tables |
| 2 | `pytest tests/test_day2_core_entities.py -v` | CRUD podcasts + episodes |
| 3 | `pytest tests/test_day3_rss_ingestion.py -v` | RSS → episodes, no dupes |
| 4 | `pytest tests/test_day4_transcription.py -v` | transcript + segments |
| 5 | `pytest tests/test_day5_feature_extraction.py -v` | 7 metrics, numeric |
| 6 | `pytest tests/test_day6_taxonomy.py -v` | taxonomy + map |
| 7 | `pytest tests/test_day7_translation.py -v` | translation, no scoring words |

Full pipeline (Day 7+):

```bash
set SOAPBOXX_V1_E2E=1
pytest tests/test_system_health.py -v
```

CI: `.github/workflows/v1-tests.yml` runs Days 1–7 + E2E on push.

---

# Repo today vs this plan (start line)

| Area | Current repo | 7-day target |
|------|--------------|--------------|
| API | PyQt desktop, no FastAPI V1 app | FastAPI + Postgres |
| Queue | In-process weekly batch | Redis + Celery workers |
| Schema | SQLite `metrics`, simplified shelf | § Day 1 tables |
| RSS | Not built | Day 3 |
| Segments | Not built | Day 4 |
| Features | 9+ rule metrics in SQLite | Exactly 7 in `episode_features` |
| Translation | Not built | Day 7 templates |
| Coach | Optional UI | **Frozen out** |

Reuse where aligned: `backend/features/rule_based.py` logic → Day 5; ingest patterns → Day 3–4. **Do not** duplicate into parallel SQLite product paths during V1 API build.

---

# Cursor execution contract

1. Read **this file** for the current day only.
2. Complete **all** checkboxes for that day.
3. Run that day’s tests.
4. Do **not** add tables, endpoints, or UI not listed for that day.
5. If blocked, fix within the day’s scope — do not skip ahead to “nice to have” features.

**Prompt to paste in Cursor:**

```text
Execute SOAPBOXX_V1_7DAY_EXECUTION.md Day N only.
Follow checkboxes and Done when criteria.
No new architecture. No coach/scoring/ranking.
If missing scope: ask V1 vs V2, do not redesign.
```

---

## Changelog

| Date | Change |
|------|--------|
| 2026-05 | 7-day Cursor-ready execution plan + test matrix |
| 2026-05-20 | Days 4–7 + E2E complete; 27 tests + `docs/V1_DAY04`–`07` |
