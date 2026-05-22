# SoapBoxx Phase 1 — Intelligence loop (V1)

Measurement engine only: transcribe → metrics → SQLite → benchmarks → rule-based tier. No Spotify, vectors, or agents.

## Layout (repo mapping)

| Plan name | Repo path |
|-----------|-----------|
| `app/db.py` | `backend/intelligence_v1/db.py` |
| `app/transcribe.py` | `backend/intelligence_v1/transcribe.py` |
| `app/metrics_extractor.py` | `backend/intelligence_v1/metrics_extractor.py` |
| `app/analyzer.py` | `backend/intelligence_v1/analyzer.py` |
| `app/predictor.py` | `backend/intelligence_v1/predictor.py` |
| `app/pipeline.py` | `backend/intelligence_v1/pipeline.py` |
| `data/soapboxx.db` | `data/soapboxx.db` (override: `SOAPBOXX_INTELLIGENCE_DB`) |
| prompts | `prompts/metric_extraction_prompt.txt`, `prompts/coaching_prompt.txt` |

Reuses existing `backend/transcriber.py` and LLM via `llm_service` / OpenAI coach path.

## Run from CLI

```bash
# Audio file
python scripts/run_intelligence_pipeline.py path/to/episode.mp3 --category business --title "Spirit Airlines"

# Transcript file
python scripts/run_intelligence_pipeline.py transcript.txt --transcript --category business
```

## Python API

```python
from backend.intelligence_v1 import process_episode
from backend.intelligence_v1.pipeline import process_transcript_only

report = process_transcript_only(transcript_text, "business", title="My Episode")
print(report["markdown"])
```

## LLM setup

Same as Coach: **Settings → OpenAI key** or `SOAPBOXX_OLLAMA_MODEL` + running Ollama. Without either, metrics use heuristics (tier still runs).

## Categories

Locked list in [`schemas/categories.json`](../schemas/categories.json): `general`, `interview`, `business`, `solo`, `comedy`.

- With **fewer than 2** episodes in a category, comparisons use **category defaults** (not broken averages).
- With **2+** episodes, live avg / p90 / p10 from your SQLite library.

Set default category in **Settings → Default Coach category** or on the **Coach** tab before generating.

## Coach tab UI

After **Generate Episode Coach Report** (or stopping a Studio recording):

1. **Episode Coach Report** (sections A–F)
2. **Intelligence** — category comparison, tier A/B/C, metric-driven actions

## Phases

1. **Done:** measurement + benchmarks + tier + Coach UI block
2. **Later:** learning loop across episodes (not in V1)
