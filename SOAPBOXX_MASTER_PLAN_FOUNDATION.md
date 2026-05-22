# SoapBoxx Master Plan Foundation (Revised)

**Status:** Source of truth for product purpose, asset model, and analysis progression.  
**Build order (Cursor):** [`SOAPBOXX_V1_7DAY_EXECUTION.md`](SOAPBOXX_V1_7DAY_EXECUTION.md) — 7-day checklist; **current day only**.  
**Spec:** [`SOAPBOXX_EXECUTION_PLAN_V1.md`](SOAPBOXX_EXECUTION_PLAN_V1.md) — layers, pipeline, schema lock.

Related: [`PRODUCT.md`](PRODUCT.md), [`docs/STORAGE.md`](docs/STORAGE.md), [`docs/SYSTEM_DESIGN_V0_V1.md`](docs/SYSTEM_DESIGN_V0_V1.md), [`docs/LIBRARY_AND_BATCH.md`](docs/LIBRARY_AND_BATCH.md), [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Mission

> Build a podcast intelligence library that transforms podcast episodes into structured measurements, organizes them within a knowledge taxonomy, and accumulates patterns that can be used to improve future podcast production.

---

## Core philosophy

SoapBoxx is **not**:

- a podcast host
- a podcast player
- an analytics clone
- an AI critic

SoapBoxx **is**:

> A structured podcast measurement and pattern discovery system.

Hosting platforms (Spotify, Apple, YouTube, RSS) are **sources**. SoapBoxx stores **insights**, not another listening catalog.

---

## Primary asset

The system's most valuable asset is **not**:

- podcasts
- episodes
- transcripts
- AI feedback

The primary asset is:

> **Structured measurements and recurring patterns extracted from podcast conversations.**

Everything else exists to support this asset.

---

## Library hierarchy (target)

```text
Library
│
├── Domain
│
├── Category
│
├── Subcategory
│
├── Topic
│
├── Podcast (Source)
│
├── Episode
│
├── Guest
│
├── Measurements
│
└── Patterns
```

**Current implementation (V1):** simplified shelf — category → author → show (source) → episode → metrics in SQLite. Full taxonomy and pattern tables are Phase 3–4. See [`docs/LIBRARY_AND_BATCH.md`](docs/LIBRARY_AND_BATCH.md).

---

## Knowledge layer vs source layer

### Knowledge layer

How information is organized (concepts):

```text
Business
 └── Entrepreneurship
      └── Startups
```

```text
Health
 └── Nutrition
      └── Weight Loss
```

### Source layer

Where podcasts live (Spotify, Apple, YouTube, RSS, etc.):

```text
My First Million
Acquired
Lex Fridman Podcast
The Diary of a CEO
```

These are **sources** of information. A source may belong to **multiple** topics (many-to-many).

---

## Episode intelligence model

Every episode produces:

### Raw assets (supporting material)

```text
Podcast
Episode
Guest
Transcript
Metadata
```

### Structured measurements (facts, not opinions)

Examples:

```text
Hook Length
Intro Length
Guest Talk Ratio
Host Talk Ratio
Question Count
Topic Shifts
CTA Presence
Episode Duration
```

Implemented today (rule-based, V1): see [`docs/INTELLIGENCE_V1.md`](docs/INTELLIGENCE_V1.md) and `backend/features/rule_based.py`. Cap at **7–10 measurements** until producer validation.

### Structural profiles

Every podcast (source) accumulates a profile over time.

Example:

```text
Interview Format
Average Runtime: 62 minutes
Average Questions: 24
Average Guest Talk Ratio: 68%
Average Hook Length: 41 seconds
```

Profiles describe **structure**. They do not judge quality.

---

## Guest intelligence layer

Guests are first-class entities (schema reserved; light V1).

```text
Guest
 └── Episode Appearances
      └── Measurements
           └── Patterns
```

Future questions:

- Which guests generate longer discussions?
- Which guests trigger more audience-focused questions?
- Which guests appear most frequently across categories?
- Which guest profiles correlate with certain structures?

**V1:** Do not over-engineer guest extraction/deduplication; keep placeholders in schema and docs.

---

## Pattern repository

The long-term asset.

Example:

```text
Business Interviews

Question Count:     15–25
Guest Talk Ratio:   55–70%
Hook Length:        <60 seconds
```

The system stores **patterns**, not opinions. Coach/tier outputs are optional product layers on top — see [`docs/SYSTEM_DESIGN_V0_V1.md`](docs/SYSTEM_DESIGN_V0_V1.md).

---

## Analysis progression

| Phase | Name | Goal |
|-------|------|------|
| 1 | Collection | Store source-linked episode data reliably |
| 2 | Measurement | Convert episodes into measurable structures |
| 3 | Comparison | Compare episodes, podcasts, guests, and categories |
| 4 | Pattern discovery | Identify recurring structural patterns |
| 5 | Recommendations | Use observed patterns for evidence-based guidance |

**Repo mapping today:**

| Phase | Status |
|-------|--------|
| 1 | Ingest + queue + shelf (`backend/episode_ingest/`, `backend/library/`) |
| 2 | Rule-based metrics + SQLite (`backend/intelligence_v1/`) |
| 3 | Category benchmarks (partial) |
| 4–5 | Not core V1; coach/tier optional, not default batch |

---

## Product rulebook

### Rule #1 — Data before AI

### Rule #2 — Measurements before scores

### Rule #3 — Patterns before recommendations

### Rule #4 — Sources support the library

The library (measurements + patterns) is the product. Podcasts are source material.

### Rule #5 — Feature gate

Every feature must answer:

> Does this help us collect, organize, compare, or learn from podcast patterns?

If not, it does not belong in the core platform.

---

## Blueprint review — research required

Before locking full architecture, three areas stay **open** (producer validation, not more code):

### 1. Taxonomy design

- How many domain levels?
- Who assigns categories?
- Can a podcast belong to multiple topics?

**Recommendation:** Domain → Category → Subcategory → Topic, with **many-to-many** source ↔ topic links.

### 2. Feature set v1

Do not exceed **7–10 measurements** initially. Producer interviews should decide what matters vs noise before expanding analytics.

### 3. Guest identification

Strategy needed for extraction, deduplication, and cross-show guest profiles. Reserve schema; minimal V1 implementation.

---

## Freeze statement

Architecture is **~85–90% defined**. Remaining uncertainty is **producer validation**, not framework choice. Next design decisions should come from interviews about what producers look for when evaluating and editing episodes — that feedback should shape the first measurement set before deeper analytics.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-05 | Revised foundation: primary asset = measurements + patterns; sources = hosting platforms; full library hierarchy documented |
