# SoapBoxx Execution Plan (V1 Locked)

**Status:** V1 Locked Spec — pre-implementation alignment  
**Stage:** Execute working system, not complete system  
**Constraint:** No new feature design until V1 is shipped  

**Supersedes:** Ad-hoc scope and “store podcasts” framing.  
**Daily build order (Cursor):** [`SOAPBOXX_V1_7DAY_EXECUTION.md`](SOAPBOXX_V1_7DAY_EXECUTION.md) — execute one day at a time; no redesign.  
**Companion:** [`SOAPBOXX_MASTER_PLAN_FOUNDATION.md`](SOAPBOXX_MASTER_PLAN_FOUNDATION.md) (why), this doc (layers + schema reference).

---

## Version

| Field | Value |
|-------|--------|
| Version | V1 Locked Spec |
| Goal | Build working system, not complete system |
| Rule | No new feature design until V1 ships |

---

## 1. Core definition

SoapBoxx is:

> A structured podcast intelligence system that converts podcast episodes into measurable data, organizes them in a library taxonomy, and translates them into human-readable insights.

---

## 2. System layers (strict separation)

Nothing skips layers. No “future thinking leakage” into lower layers.

### Layer 1 — Source ingestion (reality layer)

**Purpose:** Bring podcast content into the system unchanged.

**Includes:**

- RSS feeds
- Manual uploads
- Episode metadata

**Output:** Raw podcast + episode records.

**Rule:** No analysis in this layer.

---

### Layer 2 — Structural measurement (truth layer)

**Purpose:** Convert episodes into measurable features.

**Examples:** hook length, intro length, speaking ratio, question count, topic shifts, CTA presence.

**Rules:**

- No opinions
- No scoring
- No good/bad
- Only measurable attributes

**Output:** Structured episode dataset.

---

### Layer 3 — Pattern system (comparison layer)

**Purpose:** Compare structure across episodes, podcasts, and categories.

**Includes:** averages, distributions, clustering, trends.

**Output:** Recurring structural patterns.

**Still NOT:** recommendations, coaching, scoring.

---

### Layer 4 — Translation layer (meaning layer)

**Purpose:** Convert structured data into human-readable interpretation.

**Example**

| Raw | Translated |
|-----|------------|
| guest talk ratio: 74% | Guest-led narrative flow |
| question count: 12 | Host uses short guiding questions |

**Rules:**

- No judgment words (good, bad)
- No scoring
- No persuasion
- Only explanation of structure

**Example output**

```text
This episode has a high guest dominance structure, where the guest controls most of the narrative flow. The host contributes primarily through short guiding questions rather than extended commentary.

The structure is consistent with conversational interview formats rather than scripted or segmented shows.
```

---

## 3. Information hierarchy (library model)

```text
Library
│
├── Domain
├── Category
├── Subcategory
├── Podcast (Source)
├── Episode
├── Guest
├── Measurements
├── Patterns
└── Translation Output
```

---

## 4. Taxonomy system (controlled classification)

### Domains (top level)

Business · Technology · Health · Education · Entertainment · Science · Society & Culture · Sports

### Categories (example: Business)

Entrepreneurship · Marketing · Sales · Leadership · Finance

### Rules

- Podcasts may belong to **multiple** categories (many-to-many).
- Episodes inherit podcast categories.
- Categories are **not** user-generated freely (controlled system).

---

## 5. Database core (V1 schema)

Target relational model (Postgres-ready; SQLite acceptable for desktop V1 if migrations mirror this shape).

| Table | Role |
|-------|------|
| `podcasts` | id, name, rss_url |
| `episodes` | id, podcast_id, title, audio_url, duration, published_at |
| `transcript_segments` | episode_id, start_time, end_time, text |
| `episode_features` | episode_id, hook_length, intro_length, question_count, speaking_ratio, topic_shifts, cta_present, … |
| `episode_translations` | episode_id, translated_insight_text |
| `taxonomy_nodes` | id, parent_id, name, type (domain/category/subcategory) |
| `podcast_taxonomy_map` | podcast_id, taxonomy_node_id |

See [`docs/STORAGE.md`](docs/STORAGE.md) for current SQLite mapping vs this target.

---

## 6. Process pipeline (non-negotiable flow)

```text
Ingest → Transcribe → Segment → Measure → Store → Pattern Analysis → Translate
```

Order matters. Nothing skips ahead.

---

## 7. Feature ruleset

### Allowed in V1

- Measurable
- Repeatable
- Structural
- Descriptive

### Not allowed in V1

- Scoring
- Ranking
- Good/bad labels
- AI coaching advice
- Optimization suggestions

---

## 8. Translation layer rules (differentiator)

### Can

- Explain structure
- Describe communication patterns
- Summarize behavioral patterns in episodes

### Cannot

- Evaluate quality
- Recommend changes
- Assign value judgments

---

## 9. System design principles

| # | Principle |
|---|-----------|
| 1 | Data before intelligence |
| 2 | Structure before interpretation |
| 3 | Patterns before meaning |
| 4 | Meaning before recommendations |

---

## 10. MVP scope lock (critical)

### V1 must have

- [ ] RSS ingestion
- [ ] Transcription
- [ ] Segmentation (`transcript_segments`)
- [ ] Feature extraction (`episode_features`)
- [ ] Taxonomy system (`taxonomy_nodes`, `podcast_taxonomy_map`)
- [ ] Basic pattern aggregation
- [ ] Translation layer (`episode_translations`)

### V1 must not have

- AI coaching (Episode Coach A–F)
- Scoring systems (A/B/C tier)
- Ranking podcasts
- “Best episode” detection
- Optimization advice engine

> **Repo note:** Coach/tier exist behind flags for demo/legacy paths. They are **out of V1 scope** per this lock; do not expand them during V1 execution.

---

## 11. V1 success criteria

You can:

1. Ingest a podcast feed (RSS)
2. Break episodes into structure (segments)
3. Measure each episode consistently (features)
4. Organize podcasts in library taxonomy
5. Show patterns across episodes
6. Translate structure into readable insight (no judgment)

That is the full V1 product.

---

## 12. Final summary

> SoapBoxx is a structured podcast library system that transforms episodes into measurable data, organizes them into a taxonomy-based knowledge graph, and translates structural patterns into human-readable insights.

---

## 13. Build order checklist (execution sequence)

Do not parallelize layers out of order.

| Step | Layer | Deliverable | Exit criterion |
|------|--------|-------------|----------------|
| 1 | 1 | RSS + manual ingest → `podcasts`, `episodes` | Feed ingested; episodes listed with metadata |
| 2 | 1 | Transcribe → full transcript stored | Every episode has transcript text |
| 3 | 1 | Segment → `transcript_segments` | Time-bounded segments queryable |
| 4 | 2 | Measure → `episode_features` | 7–10 features per episode, reproducible |
| 5 | 4 | Taxonomy tables + `podcast_taxonomy_map` | Shows mapped to domain/category |
| 6 | 3 | Pattern aggregation | Category/show ranges in DB or views |
| 7 | 4 | Translation → `episode_translations` | Insight text per episode, no judgment words |
| 8 | — | Pull API + library UI read path | `pull_episode` returns all layers |

**Stop line:** When step 8 passes for one RSS show end-to-end, V1 is shippable. No new tables or layers until then.

---

## 14. Repo status vs V1 lock (honest map)

| V1 requirement | Repo today | Action |
|----------------|------------|--------|
| RSS ingestion | Not built | Step 1 |
| Transcription | `transcriber`, ingest | Wire to V1 episode rows |
| Segmentation | Not in DB | Add `transcript_segments` |
| Feature extraction | `metrics` / rule_based | Rename/align → `episode_features` |
| Taxonomy | Flat `categories.json` | Migrate → `taxonomy_nodes` + map |
| Pattern aggregation | `benchmarks` only | Extend to pattern ranges |
| Translation layer | Not built | New; replace coach as V1 “meaning” |
| Coach / tier | Optional UI/flags | **Frozen out of V1** |
| SQLite + pull | `data/soapboxx.db`, `backend/storage/` | Keep; evolve schema toward §5 |

---

## 15. Next artifacts (after freeze — do not block V1 start)

Optional follow-ups **only when requested**:

1. Day-by-day Cursor checklist (derived from §13)
2. FastAPI spec (endpoints + contracts)
3. Postgres migration scripts

**Do not** start these until this document is agreed frozen.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-05 | V1 locked execution plan consolidated from master plan + storage model |
