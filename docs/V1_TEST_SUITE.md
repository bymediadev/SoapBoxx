# SoapBoxx V1 — Automated test suite

**Contract:** Each build day has a PASS/FAIL definition of done enforced by tests.  
**Plan:** [`SOAPBOXX_V1_7DAY_EXECUTION.md`](../SOAPBOXX_V1_7DAY_EXECUTION.md)

## Global rules

1. No mocking core DB logic unless a test explicitly says so.
2. Each test file validates **one layer** of the system.
3. No AI scoring validation — structure and output shape only.

## Layout

```text
tests/
├── conftest.py              # v1_db_ready, v1_client
├── test_day1_foundation.py  # PASS today
├── test_day2_core_entities.py
├── test_day3_rss_ingestion.py
├── test_day4_transcription.py
├── test_day5_feature_extraction.py
├── test_day6_taxonomy.py
├── test_day7_translation.py
├── test_system_health.py    # E2E when SOAPBOXX_V1_E2E=1
├── fixtures/
│   ├── sample_rss.xml
│   ├── sample_episode.json
│   └── sample_transcript.txt
└── utils/
    ├── db_reset.py
    ├── seed_data.py
    └── v1_helpers.py
```

## Run

```powershell
# Day 1 only (needs Postgres; Redis optional for full health test)
docker compose -f docker-compose.v1.yml up -d
.\scripts\v1_day01_up.ps1
pytest tests/test_day1_foundation.py -v

# Full V1 suite (Days 1–7 + optional E2E)
pytest tests/test_day1_foundation.py tests/test_day2_core_entities.py tests/test_day3_rss_ingestion.py tests/test_day4_transcription.py tests/test_day5_feature_extraction.py tests/test_day6_taxonomy.py tests/test_day7_translation.py -v

# E2E full pipeline
$env:SOAPBOXX_V1_E2E = "1"
pytest tests/test_system_health.py -v
```

## Day status

| Day | File | Status |
|-----|------|--------|
| 1 | `test_day1_foundation.py` | **Active** — API, DB ping, tables |
| 2 | `test_day2_core_entities.py` | **Active** — podcast + episode CRUD |
| 3 | `test_day3_rss_ingestion.py` | **Active** — RSS parse, ingest, dedupe |
| 4 | `test_day4_transcription.py` | **Active** — transcript + segments |
| 5 | `test_day5_feature_extraction.py` | **Active** — 7 metrics |
| 6 | `test_day6_taxonomy.py` | **Active** — tree + map |
| 7 | `test_day7_translation.py` | **Active** — templates, no forbidden words |
| E2E | `test_system_health.py` | **Active** with `SOAPBOXX_V1_E2E=1` |

## PASS criteria (summary)

| Day | PASS when |
|-----|-----------|
| 1 | API up, DB connected, 6 tables exist |
| 2 | Podcast + episode CRUD |
| 3 | RSS → episodes, no duplicates |
| 4 | Transcript + segments, non-empty |
| 5 | 7 metrics per episode, numeric |
| 6 | Taxonomy tree + podcast map |
| 7 | Translation exists, no forbidden words |

## CI

`.github/workflows/v1-tests.yml` runs Days 1–7 on push to `production` / `demo` (Postgres + Redis services).

```yaml
pytest tests/test_day1_foundation.py ... tests/test_day7_translation.py -q
```
