# Episode ingest framework (post-recording product)

SoapBoxx is **not** a recorder. It **imports** episodes that already exist, then runs coach + intelligence.

## The framework (four layers)

```text
1. SOURCE      → Where the episode lives (URL, file, paste)
2. EXTRACT     → Transcript + title + show metadata
3. NORMALIZE   → Clean captions / Tactiq junk / timestamps
4. ANALYZE     → Coach (A–F) + intelligence (metrics, tier, SQLite)
```

You already have layers 3–4. This doc is about making layer 1–2 explicit and expandable.

## Layer 1 — Sources (what to support)

| Priority | Source | Status |
|----------|--------|--------|
| P0 | Paste transcript | ✅ Coach tab |
| P0 | YouTube URL | ✅ `backend/episode_ingest` + Coach Import |
| P0 | `.txt` / `.md` transcript file | ✅ Import file |
| P1 | Audio file upload (mp3/wav) | ✅ transcribe → analyze |
| P2 | Podcast RSS enclosure URL | 🔜 same as audio_file |
| P3 | Spotify / Apple | ❌ not V1 (no reliable transcript API) |

**V1 rule:** one ingestion API → one `IngestResult` shape → one analysis pipeline.

## Layer 2 — Extraction (what you need)

### Already in repo

- `backend/youtube_subtitles.py` — English VTT via yt-dlp
- `backend/youtube_subtitles.download_youtube_best_audio` — ASR fallback
- `backend/transcript_structure_extract.clean_caption_transcript`
- `backend/episode_coach_report.prepare_coach_transcript` — Tactiq/YouTube headers
- `backend/transcript_quality_assess.py` — pick captions vs ASR (CLI intake; wire to ingest `auto` later)
- `scripts/episode_intake.py` — batch v3 export (keep for power users, not desktop UI)

### Unified module (desktop + CLI should call this)

`backend/episode_ingest/`:

- `ingest_from_youtube_url(url, transcript_mode=auto|captions|asr)`
- `ingest_from_transcript_file(path)`
- `ingest_from_audio_file(path)`
- `ingest_from_text(paste)`

Returns `IngestResult`: `transcript`, `title`, `creator`, `source_type`, `warnings`.

### Dependencies (tell users honestly)

- **YouTube captions:** `yt-dlp` (`pip install yt-dlp`)
- **YouTube ASR fallback:** `ffmpeg` on PATH
- **Long audio STT:** OpenAI key and/or local Whisper + Ollama stack

## Layer 3 — Normalize (quality gates)

Before analysis, enforce:

- Minimum word count (e.g. 80 words)
- Optional: `transcript_quality_assess` when both captions + ASR exist
- Strip import headers (Tactiq, URLs, WEBVTT noise)

## Layer 4 — Analyze (unchanged)

`intelligence_v1.pipeline.process_transcript_only` + `FeedbackEngine.generate_episode_coach_report`

## What to build next (framework evolution)

1. **RSS / podcast feed ingest** — parse feed → latest episode audio URL → `ingest_from_audio_file`
2. **Batch folder** — drop 10 transcripts → queue in SQLite → compare show over time
3. **Episode identity** — store `video_id` / URL so re-import updates same row
4. **Ingest UI on Coach** — URL + file buttons (done in app cutover)
5. **Quality mode in Settings** — captions only vs auto vs ASR only

## Product copy (layman)

> “Paste a link, upload audio, or drop a transcript. SoapBoxx pulls the words, cleans them up, and tells you how to make the next episode better — with producer notes and simple stats compared to your type of show.”
