# SoapBoxx storage model

**V1 target schema:** [`SOAPBOXX_EXECUTION_PLAN_V1.md`](../SOAPBOXX_EXECUTION_PLAN_V1.md) §5 (Postgres-shaped tables).  
**Principle ([`SOAPBOXX_MASTER_PLAN_FOUNDATION.md`](../SOAPBOXX_MASTER_PLAN_FOUNDATION.md)):** Store everything needed to **access and pull** the intelligence library. V1 adds `transcript_segments`, `episode_features`, `episode_translations`, taxonomy tables; coach is **not** V1.

---

## Where data lives

| Store | Path | What |
|-------|------|------|
| **Canonical DB** | `data/soapboxx.db` | Episodes, metrics, benchmarks, sources (podcasts), queue, batches, coach reports, source metadata |
| **Ingest cache** | `data/ingest_cache/{video_id}/` | YouTube captions (`.vtt`), yt-dlp metadata JSON (re-fetch without re-downloading audio) |
| **Config override** | `SOAPBOXX_INTELLIGENCE_DB` | Alternate SQLite path |
| **Cache override** | `SOAPBOXX_INGEST_CACHE` | Alternate ingest cache root |
| **Exports** (optional) | `Exports/` | User-driven JSON exports (not auto-written by core loop today) |

Single machine, local-first. No cloud DB in V1.

---

## SQLite schema (pullable layers)

### Source layer (where episodes come from)

| Table | Pull use |
|-------|----------|
| `podcasts` | Show shelf: category, author, title, `rss_url` |
| `episodes` | Title, category, **full transcript**, `source_type`, `source_ref`, `source_path`, `metadata_json`, `podcast_id`, `author`, `published_at`, `batch_id` |
| `episode_queue` | Pending / failed work; links to `episode_id` when done |

### Knowledge + measurements (primary asset)

| Table | Pull use |
|-------|----------|
| `metrics` | Structured measurements per episode + `raw_json` (full feature dict) |
| `benchmarks` | Category aggregates (avg / p90 / p10) |
| `predictions` | Optional tier (if `SOAPBOXX_ENABLE_TIER=1`) |

### Product layers (optional, on demand)

| Table | Pull use |
|-------|----------|
| `coach_reports` | Persisted Episode Coach Report (markdown + JSON) per episode |

### Operations

| Table | Pull use |
|-------|----------|
| `batch_runs` | Weekly batch history + `summary_json` |

### Planned (schema reserved in docs, not V1 tables)

| Table | Phase |
|-------|-------|
| `guests`, `episode_guests` | Guest intelligence |
| `patterns` | Phase 4 pattern repository |
| Taxonomy (`domains`, `topics`, M2M podcast↔topic) | Full knowledge layer |

---

## What gets stored on each path

| Action | Stored automatically |
|--------|----------------------|
| **Weekly batch** | Ingest → episode row + metrics + podcast link + source metadata + batch_id |
| **Generate coach + intelligence (UI)** | Episode + metrics + benchmarks; **coach report** if intelligence ran (same `episode_id`) |
| **YouTube import** | Cache files under `ingest_cache/`; metadata in `episodes.metadata_json` when saved via batch/pipeline |
| **Coach only (no pipeline)** | UI text only until pipeline runs — coach not tied to an episode_id |

---

## Pull API (code)

```python
from backend.storage import pull_episode, pull_podcast, export_library_snapshot

# Everything for one episode
bundle = pull_episode(episode_id)

# All episodes under a show
show = pull_podcast(podcast_id)

# Full library JSON (tree + episodes + metrics counts)
snapshot = export_library_snapshot()
```

CLI:

```powershell
python -m backend.storage.pull_cli --episode 1
python -m backend.storage.pull_cli --library
```

---

## Retention rules

1. **Transcripts** — in SQLite (V1). Required to re-run metrics and coach.
2. **Measurements** — always in `metrics` + `raw_json`; never only on screen.
3. **Source refs** — `source_type` + `source_ref` (URL, file path, or paste hash) for dedupe and re-ingest.
4. **Coach** — persisted when generated with a known `episode_id`; pullable from `coach_reports`.
5. **Patterns** — computed/stored in Phase 4; until then, derive from `benchmarks` + episode metrics.

---

## Not stored (by design)

- Spotify/Apple playback streams
- Full video files (YouTube: captions + optional ASR audio temp files, not kept in DB)
- Opinions without an episode row (ephemeral UI only)

---

## Related

- [`docs/LIBRARY_AND_BATCH.md`](LIBRARY_AND_BATCH.md)
- [`docs/INTELLIGENCE_V1.md`](INTELLIGENCE_V1.md)
- [`backend/intelligence_v1/db.py`](../backend/intelligence_v1/db.py)
- [`backend/storage/`](../backend/storage/)
