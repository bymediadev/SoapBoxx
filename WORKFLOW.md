# SoapBoxx — User Workflow

> Default app: **Coach** + **Settings**. Studio recording is off unless `SOAPBOXX_SHOW_STUDIO=1`.

## First-time flow

1. Open app → **Coach** tab
2. **Settings** → add OpenAI API key (or Ollama model) → Save
3. Import an episode (YouTube URL, file, or paste)
4. Choose **category** → **Generate Episode Coach Report**
5. Read **Coach** (A–F) and **Intelligence** (comparison + tier)

## Import paths

| Method | What happens |
|--------|----------------|
| **YouTube URL** | yt-dlp captions → clean text; optional audio ASR if thin |
| **Transcript file** | Load `.txt` / `.md` |
| **Audio file** | Transcribe (OpenAI or local Whisper) |
| **Paste** | Tactiq/YouTube exports cleaned automatically |

## Analysis (after import)

1. **Producer coach** — sections A–F
2. **Intelligence** — metrics vs category, tier, actions; saved to `data/soapboxx.db`

## Categories

`general`, `interview`, `business`, `solo`, `comedy` — set on Coach tab or in Settings as default. Fewer than 2 episodes in a category uses **sensible defaults** until your library grows.

## Design principle

Every session ends with:

> a usable improvement artifact for the **next** episode
