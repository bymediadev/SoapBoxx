# SoapBoxx

> SoapBoxx is a private producer library where finished podcast episodes become structured reports that can be stored, compared, and analyzed over time.

## The private library for podcast performance reports

Every episode becomes a **report** you can revisit, compare, and learn from.

Unlike podcast hosting platforms that store episodes for **listeners**, SoapBoxx stores **measurements, structure, and performance insights** for **producers**.

Build a searchable archive of episode reports and uncover patterns that only appear over time.

**The report is the product.** Measurement, transcription, and classification are how each report gets made — not the product itself.

---

## What SoapBoxx is

SoapBoxx **stores podcast reports** — it does not merely “analyze and forget.”

Each finished episode you bring in becomes a **persistent report** on the shelf: seven structural metrics, a template classification (A / B / C), and fixed structural insight text. Reports stay in your library; value compounds as the archive grows.

**Public catalog vs private library**

| | Hosting (Spotify, Apple, RSS) | SoapBoxx |
|--|-------------------------------|----------|
| **Audience** | Listeners | Producers |
| **Stores** | Episodes for playback | Reports for improvement |
| **Value over time** | Catalog size | Pattern insight from your archive |

Organize by domain → category → show → episode report.

**Bring material in** (finished episodes only):

- **RSS feeds** — ingest show metadata and audio URLs
- **Audio** — `audio_url` (from RSS or manual create); transcribe when needed
- **Transcripts** — paste on process to skip STT

SoapBoxx does **not** record audio (by default) and does **not** replace your recorder, DAW, or host platform.

---

## Category

SoapBoxx does not fit neatly into recording, editing, hosting, analytics dashboards, or chat assistants.

It is closer to:

- **Podcast performance library** (primary framing)
- Podcast intelligence archive
- Producer insights repository

The distinction: **the report is persistent.** Analysis is an event; the library is the asset.

---

## The problem it solves

Most tools treat feedback as a **one-time event**: upload an episode, read output, leave. Nothing accumulates.

Producers repeat the same structural mistakes because there is no **closed loop** and no **archive** to compare against.

SoapBoxx creates a loop that **builds an asset**:

> **Import → Transcribe (if needed) → Measure → Report on shelf → Compare over time → Improve the next episode**

---

## How reports get made

### 1. Input

Finished episode material — RSS, audio URL, or pasted transcript.

### 2. Text (when needed)

Speech becomes text; content is split into measurable components (questions, turns, segments).

### 3. Measurement → report

Deterministic structure, not vibes:

- Opening hook length, intro block, question density
- Host vs guest talk share, turn count, topic shifts, CTA presence
- Template **A / B / C** with consistent structural insight copy

Repeatable outputs you can trust and **file next to other reports** in the same show.

### 4. Library

Browse shows and taxonomy, pipeline status (queued / measured), compare episodes, optional weekly pattern snapshot as volume grows.

Optional **coaching reports** (host behavior, rewrites, next actions) exist elsewhere in the codebase and on the roadmap — separate from the core measurement reports.

### 5. Use on the next episode

Read a report in a few minutes, change how you produce the next one — wherever you record (Riverside, OBS, Descript, etc.). SoapBoxx sits in the stack as **archive and reference**, not production.

---

## What SoapBoxx is not

- Not a recording studio or live podcast tool
- Not a DAW (Audition, Descript editing mode)
- Not OBS or streaming software
- Not Spotify, Apple Podcasts, or YouTube (those stay your **listener catalog**)
- Not a chatbot or AI copilot — no disposable conversation; **stored reports**
- Not transcription-only — measurement and structure are what you keep

It does not capture content. It **archives reports** about finished content.

---

## Where it fits in your workflow

| Tool | Role |
|------|------|
| Riverside / OBS / local recorder | Capture |
| Descript / Audition | Edit |
| Spotify / YouTube / RSS host | Distribute (listener catalog) |
| ChatGPT | Ad-hoc questions (no archive) |
| **SoapBoxx** | **Private library of episode performance reports** |

---

## Mental model

- **Athletes** → game tape on the shelf, reviewed before the next game
- **Podcasters** → episode structure reports (rarely kept in one searchable place)

Hosting platforms publish for listeners. SoapBoxx is the **producer archive** — measurement → report → history → patterns.

---

## Key value proposition

> Most tools help you **produce** episodes.  
> SoapBoxx helps you **build a library** of how you make them.

Success: open a report, compare it to past episodes on the shelf, and know what to change on the **next** recording.

---

## Demo & API

| | |
|--|--|
| **Production API** | [soapboxx-production.up.railway.app](https://soapboxx-production.up.railway.app) |
| **Demo UI** | [soapboxx.lovable.app](https://soapboxx.lovable.app) — live API only (`soapboxxApi`; no mocks) |
| **Built-in dashboard** | `/ui/` on the API host |

Typical flow: ingest RSS → run episode pipeline → **report lands on the shelf**.

Lovable client: [`docs/lovable/api-client.ts`](docs/lovable/api-client.ts). Optional local API: `VITE_API_URL=http://127.0.0.1:8000` (defaults to Railway if unset).

Developer docs: [`docs/RAILWAY_DEPLOY.md`](docs/RAILWAY_DEPLOY.md) · [`docs/LOVABLE_INTEGRATION.md`](docs/LOVABLE_INTEGRATION.md)

---

## Setup (developers)

```bash
git clone https://github.com/bymediadev/SoapBoxx.git
cd SoapBoxx
pip install -r requirements.txt
docker compose -f docker-compose.v1.yml up -d
alembic upgrade head
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Optional: `GROQ_API_KEY` or `OPENAI_API_KEY` for cloud transcription when processing audio.

For automatic RSS-triggered processing, run the queue worker in a second terminal:

```bash
python scripts/run_celery_worker.py
```

```bash
python -m pytest tests/ -q -m "not integration"
```

---

## Documentation

| Doc | |
|-----|--|
| [`PRODUCT.md`](PRODUCT.md) | Product definition |
| [`SOAPBOXX_V1_7DAY_EXECUTION.md`](SOAPBOXX_V1_7DAY_EXECUTION.md) | V1 scope |
| [`docs/SOAPBOXX_V1_TRUTH_CONTRACT.md`](docs/SOAPBOXX_V1_TRUTH_CONTRACT.md) | Layer 1 reports (metrics + templates) |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System design |
| [`docs/INTELLIGENCE_V1.md`](docs/INTELLIGENCE_V1.md) | Metrics layer (desktop path) |

---

## Support

- [GitHub Issues](https://github.com/bymediadev/SoapBoxx/issues)
- Contributing: [`AGENTS.md`](AGENTS.md) · [`RULES.md`](RULES.md)

---

*Built with Python, FastAPI, Postgres, and optional cloud STT (Groq / OpenAI)*

