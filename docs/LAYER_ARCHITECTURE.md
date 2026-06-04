# SoapBoxx — Layer architecture (capture → analyze → interpret → present)

**Status:** Locked direction for V1+ presentation split  
**Product bias:** **Editorial producer** (Product B) on top of a **trustworthy measurement** base (Layer 2 only)

This doc maps the four-layer “newsroom” model to repo modules and API contracts. It does not replace [`SOAPBOXX_V1_TRUTH_CONTRACT.md`](SOAPBOXX_V1_TRUTH_CONTRACT.md) for Layer 1 invariants.

---

## Four layers

```text
[1] INGESTION     — raw truth (segments, metadata)
[2] SIGNALS       — what happened (7 metrics, reproducible)
[3] INTELLIGENCE  — what it means + what to do (structure, patterns, actions)
[4] EXPERIENCE    — curated views (UI, exports)
```

Each layer is **replaceable** without rewriting the others.

---

## Layer 1 — Ingestion (raw truth only)

| Responsibility | Repo |
|----------------|------|
| RSS / metadata | `backend/services/rss_service.py` |
| STT | `backend/services/transcription_service.py`, `backend/transcriber.py` |
| Segment storage | `transcript_segments`, `episodes.full_transcript` |

**Output contract (target):**

```json
{
  "episode_id": 1,
  "segments": [
    { "start": 0.0, "end": 4.2, "speaker": "host", "text": "..." }
  ],
  "metadata": { "title": "...", "show": "...", "audio_url": "..." }
}
```

**Rules:** No hook scores, no narrative labels, no coaching.  
**Integrity:** `report_views_service.detect_transcript_warning()` flags demo/fixture text vs RSS title.

---

## Layer 2 — Signal processing (measurement engine)

| Responsibility | Repo |
|----------------|------|
| Seven metrics | `backend/services/feature_service.py`, `backend/features/rule_based.py` |
| Storage | `episode_features` |

**Output contract:**

```json
{
  "hook_length_seconds": 6,
  "intro_length_seconds": 6,
  "question_count": 3,
  "speaking_turns": 8,
  "host_guest_ratio": 0.5,
  "topic_shift_count": 0,
  "cta_present": true
}
```

**Question answered:** “What happened?” — not why, not good/bad.

**API:** `GET /episodes/{id}/features`

---

## Layer 3 — Intelligence (split internally)

### 3A — Structure classifier

| Responsibility | Repo |
|----------------|------|
| Template A/B/C | `backend/services/translation_service.py` |
| Form labels / playbook | `backend/services/template_classification.py`, `template_c_playbook.py` |

**Output:** `template_id`, short `insight_text`, optional `template_playbook.form`.

**API (thin):** `GET /episodes/{id}/translation` → prefer **`insight_text` + `template_id`** for Layer 3A; full `report` is legacy bundle.

### 3B — Behavior interpreter

Turns metrics into **pattern language** (no new numbers).

| Responsibility | Repo |
|----------------|------|
| Listener experience, trade-offs | `backend/services/coaching_report_service.py` |
| Library / show compare | `library_benchmarks`, `show_variance_service` |

**Not for default UI:** percentile lines, cohort/schema notes (internal only).

### 3C — Editorial coach (Product B)

**Output:** actionable bullets — replay checks, edit flags, next-episode tests.

| Responsibility | Repo |
|----------------|------|
| Playbook `review_these`, producer flags | `coaching_report_service`, `producer_notes_service` |

**API:** `GET /episodes/{id}/report/actions` → `actions[]`, `keep_patterns[]`

---

## Layer 4 — Experience (presentation)

| View | Audience | API |
|------|----------|-----|
| **Producer** | Metrics + structure + patterns (no schema %, no cohort jargon) | `GET /episodes/{id}/report/producer` |
| **Actions** | “Do this next episode” (monetizable) | `GET /episodes/{id}/report/actions` |
| **Full legacy** | Debugging / parity with old `/ui/` | `GET /episodes/{id}/translation` → `report` |
| **Analytics** (V2) | Trends across library | `GET /insights/patterns/weekly`, future dashboards |

**UI rule:** Default episode screen uses **producer + actions + features**; hide `measurement_stamp`, `measurement_cohort_note`, and raw `compared_with_library` percentiles unless “Advanced” is opened.

---

## Data flow

```text
Audio / paste
  → Layer 1 (ingest + transcribe + segments)
  → Layer 2 (features row)
  → Layer 3A (translation row: template + insight_text)
  → Layer 3B+3C (coaching report, built on read — not stored separately yet)
  → Layer 4 (report_views_service shapes JSON per screen)
```

Pipeline entry: `POST /episodes/{id}/process` runs 1→2→3A; coaching report is materialized on `GET /translation` today.

---

## What not to show producers

| Item | Where it stays |
|------|----------------|
| `feature_schema_version`, extraction/aggregation versions | Logs, admin, optional Advanced |
| `measurement_cohort_note` | API `translation.report` only; omitted from `/report/producer` |
| Duplicate metric tables | One block in producer view |
| Demo transcript without banner | `transcript_warning` on producer + actions |

---

## Product decision (locked)

| Primary | Secondary |
|---------|-----------|
| **Editorial producer** — consistent judgment, next-episode actions | **Patterns over time** — hook/question trends, format mix |

Analytics without coaching is commodity; coaching without trustworthy Layer 2 is noise.

---

## Implementation map

| File | Role |
|------|------|
| `backend/services/report_views_service.py` | Layer 4 shaping + transcript warnings |
| `backend/api/routes/report.py` | `/episodes/{id}/report/producer`, `/report/actions` |
| `static/v1-library/index.html` | Tabs: Measurements / Structure / Next episode |
| `docs/lovable/api-client.ts` | `getProducerReport`, `getActionsReport` |

---

## Related docs

- [`SOAPBOXX_V1_TRUTH_CONTRACT.md`](SOAPBOXX_V1_TRUTH_CONTRACT.md) — Layer 1 determinism
- [`SYSTEM_DESIGN_V0_V1.md`](SYSTEM_DESIGN_V0_V1.md) — instrumentation vs coach
- [`SOAPBOXX_EXECUTION_PLAN_V1.md`](../SOAPBOXX_EXECUTION_PLAN_V1.md) — original layer numbering (ingest → measure → pattern → translate)
- [`LOVABLE_INTEGRATION.md`](LOVABLE_INTEGRATION.md) — frontend wiring
