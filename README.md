# SoapBoxx

## Podcast Performance Intelligence System

Turn finished podcast episodes into **structured measurements and insights** that help you improve the next one.

---

## What SoapBoxx is

SoapBoxx is a **post-episode analysis system** for podcasters and producers.

Bring in episodes via:

- **RSS feeds** (shows you already publish)
- **Audio files**
- **Transcripts** (paste or upload)

SoapBoxx turns them into:

- **Structured measurements** — hook length, question density, host/guest balance, pacing signals, and more
- **Structural insights** — how the episode is organized (interview vs narrative vs guest-led patterns)
- **A feedback loop across episodes** — compare structure over time in a library, not one-off chat

SoapBoxx does **not** record audio and does **not** replace your recorder, DAW, or host platform. It improves what happens **after** the episode exists.

---

## The problem it solves

Most podcasters publish, maybe edit, and rarely analyze **structure** systematically. The same patterns repeat because there is no closed loop between episodes.

SoapBoxx creates that loop:

> **Import → Transcribe (if needed) → Measure → Insight → Improve the next episode**

---

## How it works

### 1. Input

Connect or upload finished episode material — RSS, audio, or transcript.

### 2. Understanding

When needed, speech is converted to text. Content is broken into measurable components: questions, turns, segments, and flow.

### 3. Analysis (core value)

SoapBoxx evaluates **structure**, not vibes:

- How long is the opening hook?
- How balanced is host vs guest talk time?
- How dense are guiding questions?
- Does the episode read as interview-shaped, Q&A-heavy, or narrative-driven?
- How do patterns compare across episodes in your library?

V1 produces **seven deterministic metrics** and classifies each episode into structural templates **A / B / C** with consistent insight text — repeatable outputs you can trust and compare.

### 4. Output

- Episode-level **measurements**
- **Structural insight** (template + explanation of conversation shape)
- **Library view** — shows, categories, pipeline status, trends over time

Deeper **coaching reports** (host behavior, rewrites, next-episode actions) exist in the broader SoapBoxx codebase and are on the roadmap as an optional enhancement layer — separate from the core measurement contract.

### 5. Iteration

Use insights on the **next** episode wherever you record (Riverside, OBS, Descript, etc.). SoapBoxx sits in the stack as intelligence, not production.

---

## What SoapBoxx is not

- Not a recording studio or live podcast tool
- Not a DAW (Audition, Descript editing mode)
- Not OBS or streaming software
- Not Spotify, Apple Podcasts, or YouTube (those stay your catalog)
- Not transcription-only — measurement and structure are the product

It does not capture content. It analyzes **finished** content.

---

## Where it fits in your workflow

| Tool | Role |
|------|------|
| Riverside / OBS / local recorder | Capture |
| Descript / Audition | Edit |
| Spotify / YouTube / RSS host | Distribute |
| ChatGPT | Ad-hoc questions |
| **SoapBoxx** | **Post-episode intelligence + improvement loop** |

---

## Mental model

- **Athletes** → game tape review  
- **Podcasters** → episode structure review (rarely done well today)

SoapBoxx is the missing **measurement and coach layer** for podcasting — starting with facts and structure, not generic AI chat.

---

## Key value proposition

> Most tools help you **produce** episodes.  
> SoapBoxx helps you **improve** how you make them.

Success: read the output in a few minutes and know what to change on the **next** episode.

---

## Demo & API

| | |
|--|--|
| **Production API** | [soapboxx-production.up.railway.app](https://soapboxx-production.up.railway.app) |
| **Demo UI** | [soapboxx.lovable.app](https://soapboxx.lovable.app) (library + episode views) |
| **Built-in dashboard** | `/ui/` on the API host |

Typical flow: ingest RSS → run episode pipeline → view measurements and structural insight.

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

```bash
python -m pytest tests/ -q -m "not integration"
```

---

## Documentation

| Doc | |
|-----|--|
| [`PRODUCT.md`](PRODUCT.md) | Product definition |
| [`SOAPBOXX_V1_7DAY_EXECUTION.md`](SOAPBOXX_V1_7DAY_EXECUTION.md) | V1 scope |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | System design |
| [`docs/INTELLIGENCE_V1.md`](docs/INTELLIGENCE_V1.md) | Metrics and intelligence layer |

---

## Support

- [GitHub Issues](https://github.com/bymediadev/SoapBoxx/issues)
- Contributing: [`AGENTS.md`](AGENTS.md) · [`RULES.md`](RULES.md)

---

## One-line definition

> SoapBoxx is a post-episode podcast intelligence system that turns finished episodes into structured measurements and insights so you can improve every future episode.

---

*Built with Python, FastAPI, Postgres, and optional cloud STT (Groq / OpenAI)*
