# System state layer

**Purpose:** Make SoapBoxx feel like a **living intelligence system**, not a static DB viewer.

## Layers

| Layer | Responsibility |
|-------|----------------|
| Ingestion | RSS → `podcasts` + `episodes` (metadata only) |
| Pipeline | transcribe → features → translate |
| **System state** | `pipeline_status` + `system_events` |
| UI (Lovable) | Reflect motion: processing, activity, patterns |

## Episode lifecycle

| Status | Meaning |
|--------|---------|
| `new` | Manually created, not ingested |
| `ingested` | Reserved / legacy |
| `queued` | Metadata (or transcript) waiting for next step |
| `transcribing` | Active transcription |
| `measured` | Features stored |
| `ready` | Translation stored |
| `failed` | Last step failed (`pipeline_error`) |

`GET /episodes/{id}/state` returns `status`, `steps`, `next_action`.

## Activity feed

Append-only `system_events`:

- `ingest.started`, `ingest.completed`, `episode.ingested`
- `pipeline.transcribing`, `pipeline.transcribed`, `pipeline.measured`, `pipeline.ready`, `pipeline.failed`

`GET /system/activity?limit=50`

## Patterns (v1)

`GET /insights/patterns/weekly` — rule-based aggregates over last 7 days (no LLM).

## API summary

```text
GET  /pipeline/status
GET  /system/activity
GET  /episodes/{id}/state
POST /episodes/{id}/queue
GET  /insights/patterns/weekly
```

See [`LOVABLE_INTEGRATION.md`](LOVABLE_INTEGRATION.md).
