# Free demo pipeline (no OpenAI bill)

V1 needs a **transcript** before metrics and translation. Paid path: download RSS audio → OpenAI Whisper API. **Free path: paste text** and skip STT.

## What costs money

| Step | Free? | Notes |
|------|-------|--------|
| RSS ingest | ✅ | Metadata only — you already did this |
| Transcribe from `audio_url` | ✅ **Groq** | Free tier, no credit card — see below |
| Transcribe with **pasted text** | ✅ | No STT call |
| Features (7 metrics) | ✅ | Rule-based on transcript |
| Translation (A/B/C templates) | ✅ | No LLM |

## Closest to OpenAI without paying: **Groq Whisper**

Same API shape as OpenAI (`audio.transcriptions.create`), runs in the cloud on Railway.

1. Sign up: [console.groq.com](https://console.groq.com) (free tier, no card).
2. Create API key → Railway API service variable: `GROQ_API_KEY=gsk_...`
3. Optional: `SOAPBOXX_TRANSCRIPTION_SERVICE=groq` (auto-selected when Groq key is set and OpenAI is not).
4. Optional model: `SOAPBOXX_GROQ_WHISPER_MODEL=whisper-large-v3-turbo` (default, fast).

Limits (free tier): ~25MB per file, rate limits (~20 req/min). Long Planet Money episodes may need shorter clips or local Whisper.

Then: `POST /episodes/{id}/process` with empty body (downloads RSS audio → Groq → features → translate).

## Recommended demo flow (zero API spend)

### 1. Ingest + UI (already working)

- `/ui/` on Railway — library, stats, episode list (mostly `queued`).

### 2. Process **one** episode with sample text

**Railway shell** (or local with `DATABASE_URL` pointing at prod):

```bash
python scripts/demo_process_episode.py --episode-id 1
```

**Or Swagger** `POST /episodes/1/process` body:

```json
{
  "transcript": "Host: Welcome...\nGuest: Thanks...\n..."
}
```

Use [`tests/fixtures/sample_transcript.txt`](../tests/fixtures/sample_transcript.txt) or any podcast text you have rights to show.

### 3. Verify

- `GET /episodes/1/translation` → `insight_text` + `template_id`
- Refresh `/ui/` → **Measured** ≥ 1, one row **ready**
- Lovable can show real insight for processed episodes; rest stay `queued` (honest for demo)

### 4. Talk track for investors/users

> “We ingested the catalog from RSS. Here’s one episode fully measured and translated. At scale we turn on cloud STT; the pipeline is the same.”

## Local dev: free audio STT (optional)

On your PC only (not slim Railway API image):

```powershell
pip install -r requirements-desktop.txt
$env:SOAPBOXX_TRANSCRIPTION_SERVICE = "local"
$env:SOAPBOXX_LOCAL_WHISPER_MODEL = "base"
```

Then `POST /episodes/{id}/process` with empty body downloads audio and runs **local Whisper** (slow on CPU, no API fee).

## When you have budget (optional upgrade)

Use `OPENAI_API_KEY` instead of Groq if you prefer OpenAI billing. Set `SOAPBOXX_TRANSCRIPTION_SERVICE=openai`.

## Do not

- Process all 355 episodes without STT budget (time + cost).
- Expect Railway free tier to run Whisper in the API container (image is API-only).

See also: [`FREE_FRONTEND_OPTIONS.md`](FREE_FRONTEND_OPTIONS.md), [`RAILWAY_POSTGRES_CRON.md`](RAILWAY_POSTGRES_CRON.md) (pipeline section).
