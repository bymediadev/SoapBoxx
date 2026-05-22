# SoapBoxx system design — V0 → V1 (instrumentation first)

> **Product foundation:** [`SOAPBOXX_MASTER_PLAN_FOUNDATION.md`](../SOAPBOXX_MASTER_PLAN_FOUNDATION.md) — primary asset = measurements + patterns; episodes/podcasts are source material.

> **Anchor:** A system that turns podcast episodes into **structured, measurable data** so patterns can be analyzed over time.

Not: “AI that judges podcasts.” Not: a ranking engine. Think **instrumentation for audio content** — like analytics for episode *structure*.

---

## Core principle (do not skip)

### Rule 1: No opinions in V0/V1 measurement

Everything in the **measurement layer** must be:

- measurable
- observable
- reproducible (same transcript → same numbers)

If a feature requires judgment → it belongs in a **later layer**, not V1 instrumentation.

| Layer | Opinion? | Example |
|-------|----------|---------|
| V0 ingest + transcript | No | URL → text |
| V1 rule-based features | No | `question_count` via `?` |
| V1 benchmarks | No | avg hook time in category |
| Coach report (A–F) | Yes (product) | “weak moment” prose |
| LLM metric estimates | Yes (optional) | only if `SOAPBOXX_LLM_METRICS=1` |
| A/B/C tier | Yes (heuristic) | only if `SOAPBOXX_ENABLE_TIER=1` |

---

## Four blocks (target architecture)

```text
[1] INGESTION        → episode_ingest (URL, file, paste)
[2] TRANSCRIPTION    → transcriber + segments when available
[3] STRUCTURE        → backend/features (rule-based, no LLM)
[4] STORAGE + QUERY  → intelligence_v1 SQLite (V1); Postgres later
```

**Optional product layers (not instrumentation):**

```text
[5] COACH            → episode_coach_report (producer prose)
[6] COMPARISON UI    → Coach tab
```

Build order: **1 → 2 → 3 → 4**, then validate with producers. Layer 5 is parallel, not a substitute for 3.

---

## V0 — minimal working system

**Goal:** One episode in structured form.

| Capability | Repo today |
|------------|------------|
| Ingest URL / file / paste | `backend/episode_ingest/` |
| Transcribe audio | `backend/transcriber.py`, `intelligence_v1/transcribe.py` |
| Store episode + transcript | `data/soapboxx.db` → `episodes` |
| List / reload episodes | `IntelligenceDB` |

**V0 outputs (no intelligence opinions):**

- Show transcript
- Show source (YouTube, file, paste)
- List episodes in DB

---

## V1 — structure extraction (measurement only)

**Goal:** 5–10 **rule-based** features per episode.

### Canonical feature set (V1 tight list)

| Feature | How (rule-based) | Module |
|---------|------------------|--------|
| `hook_time_seconds` | Timestamps if present; else words-until-first-shift @ ~2.5 wps | `features/hook.py` |
| `question_count` | `?` + interrogative lines | `features/engagement.py` |
| `followup_question_count` | question after prior line with `?` | `features/engagement.py` |
| `topic_changes` | shift markers + paragraph breaks | `features/structure.py` |
| `cta_present` | subscribe / patreon / link phrases | `features/engagement.py` |
| `guest_talk_percentage` | `Host:` / `Guest:` line word counts | `features/pacing.py` |
| `host_talk_percentage` | complement of guest | `features/pacing.py` |
| `avg_sentence_length` | words / sentences | `features/pacing.py` |
| `speaking_turns` | speaker-labeled lines or paragraph blocks | `features/structure.py` |

**Deferred (need diarization or good segments):**

- `intro_length_seconds` — needs reliable segment boundaries
- `interruptions` — needs overlap detection
- `story_count` — judgment-heavy; keep out of V1 instrumentation

### Feature engine layout

```text
backend/features/
  __init__.py          → extract_rule_features()
  hook.py
  pacing.py
  structure.py
  engagement.py
```

Each metric is an isolated function. **No LLM in this package.**

### Storage (today: SQLite, not Postgres)

Table `metrics` in `data/soapboxx.db` maps to design doc `episode_features`.  
`raw_json` stores `feature_source: "rule_based"` and full feature dict.

Postgres + `transcript_segments` table = **V1.5** when you need multi-user or RSS at scale.

---

## What the repo does today (honest map)

| Your doc | SoapBoxx path | Notes |
|----------|---------------|-------|
| Ingestion service | `episode_ingest/` | YouTube, file, paste |
| Transcription | `transcriber.py` | Segments not stored yet |
| Structure extraction | `features/` (new) + `metrics_extractor.py` | Default → rule-based |
| Storage | `intelligence_v1/db.py` | SQLite |
| Coach / opinions | `episode_coach_report.py` | Product layer — optional |
| Tier A/B/C | `predictor.py` | Off by default (`SOAPBOXX_ENABLE_TIER`) |

Batch v3 (`episode_intake.py`, `episode_report_v3.py`) = **research/export**, not desktop instrumentation.

---

## Build order (do not reorder)

1. Ingestion + transcription ✅  
2. Store episodes cleanly ✅  
3. Rule-based features ✅ (default)  
4. Compare across episodes (category benchmarks) ✅  
5. **STOP** — producer validation  

Then:

6. Producer interviews → refine feature list  
7. Segments table + hook/intro from timestamps  
8. RSS ingest  
9. Coach copy tuned to **measured** features (cite numbers, not vibes)

---

## Discovery phase — producer questions

Before adding features, ask producers only:

1. What do you look at when judging an episode?
2. What tells you it’s working within 30 seconds?
3. What do you change most often in editing?

You are collecting **feature candidates**, not product opinions.

---

## Dashboard metaphor

| Phase | Analogy |
|-------|---------|
| V0 | Engine runs |
| V1 | Speed, RPM, fuel gauge (rule-based) |
| V2 | Driving patterns (cross-episode trends) |
| V3 | Coaching / suggestions (LLM, tier — optional) |

You are building the **dashboard**. Coach is the **driving instructor** — useful, but not the speedometer.

---

## Env flags (instrumentation vs product)

| Variable | Default | Meaning |
|----------|---------|---------|
| `SOAPBOXX_LLM_METRICS` | off | LLM estimates for metrics (opinion-adjacent) |
| `SOAPBOXX_ENABLE_TIER` | off | A/B/C tier block in intelligence report |
| Coach | on in UI | A–F producer report (separate from instrumentation) |

---

## Related docs

- [`EPISODE_INGEST_FRAMEWORK.md`](EPISODE_INGEST_FRAMEWORK.md) — import paths  
- [`INTELLIGENCE_V1.md`](INTELLIGENCE_V1.md) — CLI + pipeline  
- [`PRODUCT.md`](../PRODUCT.md) — user-facing positioning  
