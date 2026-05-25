# Lovable — one-shot wireup prompt

**Current state (production UI):** [soapboxx.lovable.app](https://soapboxx.lovable.app) is wired to Railway via `soapboxxApi` only — library home, ingestion, episodes index, shows, insights, and episode detail; no mock data. Episode detail uses `getEpisode` + `episodeState` + `getTranslation`, with **Run pipeline** → `processEpisode(id, {})` and metrics from the `features` step.

Use the prompt below only to **re-wire** a broken preview or a new Lovable project.

Copy **the entire block below** (from `Wire this SoapBoxx` through the end) into **Lovable project chat** once.  
No separate follow-up prompts needed.

**Env:** `VITE_API_URL` in Lovable Settings (or `.env`) points at `http://127.0.0.1:8000` for local API; if unset, client defaults to `https://soapboxx-production.up.railway.app`. See [`.env.lovable.example`](.env.lovable.example).

---

## Before you send (required)

1. **Same message:** Paste the full [`api-client.ts`](api-client.ts) under Step 2 in the chat block. Do **not** send the prompt with only the bracket placeholder — Lovable will improvise the client.
2. **Metrics rule** is in Step 4 (ready episodes need `processEpisode(id, {})` once to show metrics).
3. **API-only rule** is in Step 5 (no invented endpoints or mock data).

---

```text
Wire this SoapBoxx app to our live FastAPI backend. Remove ALL mock/hardcoded library data (fake episode counts, placeholder podcast names, sample stats).

Production API base URL:
https://soapboxx-production.up.railway.app

=== STEP 1 — Create src/lib/vite-env.d.ts ===

/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}

=== STEP 2 — Create src/lib/soapboxx-api.ts (exact file) ===

Create this file exactly as written. Do not use a different base URL unless VITE_API_URL is set for local dev.

REQUIRED: The sender must paste the full contents of docs/lovable/api-client.ts from the SoapBoxx repo in this same chat message immediately below this line. Do not implement soapboxxApi from memory. Do not omit exports. If the TypeScript file is not pasted here, stop and ask for it — do not guess paths or response shapes.

[PASTE FULL api-client.ts HERE — same message as this prompt]

=== STEP 3 — Library home, episodes index, shows, insights ===

Library home — on load (and Refresh):
- const home = await soapboxxApi.libraryHome(15, 25)
- Map home.stats → stats cards (episodes_total, shows_total, measured_pct, queued_count, processing_count)
- Map home.pipeline.by_status → pipeline chips
- Map home.tree → sidebar catalog (recursive taxonomy; each node: id, name, node_type, children[], optional podcasts[] with id, name, episode_count)
- Map home.activity → activity rail
- Map home.patterns → weekly patterns panel
- Map home.episodes → episodes table: columns title, podcast_name, status
- Make each episode row clickable → navigate to /episode/:id using episode.id (number)

Episodes index:
- soapboxxApi.libraryEpisodes(limit) OR home.episodes from libraryHome()
- Optional filter: libraryEpisodes with podcast_id query via libraryEpisodes if exposed; else filter client-side

Shows:
- soapboxxApi.listPodcasts() for shows list; taxonomy shows also in home.tree[].…podcasts

Insights:
- home.patterns from libraryHome() OR soapboxxApi.weeklyPatterns()

RSS ingest form:
- On submit: await soapboxxApi.ingestRss(url) then refetch libraryHome()
- Show success: episodes_created / episodes_skipped

Loading and error states when API fails. No fake numbers. No mock data on any screen.

=== STEP 4 — Episode detail screen (/episode/:id) ===

Parse route param id as a number for API calls.

On load:
- getEpisode(id) — title, transcript excerpt (first 500 chars of full_transcript if present)
- episodeState(id) — status badge + steps (transcribed, measured, insight_ready)
- Try getTranslation(id):
  - If 200: show template_id and full insight_text (main content)
  - If 404 (fetch error status 404): show "Not processed yet" + button "Run pipeline"

Metrics (seven feature metrics):
- getEpisode, episodeState, and getTranslation do NOT return metrics.
- If metrics are required and not already available from data loaded in this session, call processEpisode(id, {}) once to retrieve them.
- Extract metrics from the response: steps.find(s => s.step === "features")?.metrics
- Never use force_retranscribe by default.
- Never generate or hardcode mock metrics.
- For already-ready episodes, processEpisode(id, {}) is expected to be fast (reuses stored transcript); show loading while it runs.

Button "Run pipeline":
- await soapboxxApi.processEpisode(id, {})  — empty body only, NEVER force_retranscribe by default
- On success: show insight_preview, template_id, and metrics from steps (features step as above)
- Refetch getTranslation(id) and episodeState(id)

Optional: show processEpisode step reasons (e.g. existing_transcript, reused, transcript_source) for transparency.

UI labeling (Layer 1 only — do not blur measurement vs commentary):
- Section "Structural insight": template_id + insight_text from getTranslation only. This is deterministic measured output, not AI chat.
- Section "Measurements": the seven metrics from processEpisode features step. Label as measurements, not "AI insight."
- Do not add a coaching, narrative, or "tips to improve" section — no /enhance endpoint exists in V1. Do not invent commentary.

=== STEP 5 — Rules ===

- Use only the endpoints and methods exported from soapboxx-api.ts (soapboxxApi). Do not create additional API routes or fetch URLs not in that file.
- Do not create mock data, placeholder episodes, or inferred response fields.
- If data is unavailable, show an empty state or an error state — do not invent values.
- All data from soapboxxApi / production API only
- Default pipeline call is POST /episodes/{id}/process with {} (fast, reuses stored transcript)
- Do not add force_retranscribe toggle unless hidden in advanced/dev settings
- Use React Router (or existing router) for /episode/:id
- Publish when done

=== Verify in browser Network tab ===

- GET .../library/home → 200
- Click episode → GET .../episodes/{id}/translation and/or POST .../episodes/{id}/process → 200
```

---

## How to send attempt #1

1. Copy the **entire** `text` block above (from `Wire this SoapBoxx` through the Verify section).
2. Replace `[PASTE FULL api-client.ts HERE — same message as this prompt]` with the **complete** contents of [`api-client.ts`](api-client.ts) (no omissions).
3. Send as **one** Lovable chat message (prompt + inlined TypeScript).

Do not send the prompt alone. Do not send Step 2 as a placeholder.

---

## After Lovable applies

1. Publish the Lovable app.
2. Railway API must have `SOAPBOXX_CORS_ORIGINS` including `https://soapboxx.lovable.app` (repo default; confirm in Variables).
3. Smoke test: library home shows real counts; open episode 1 → insight or Run pipeline; ready episode shows metrics after processEpisode({}).

Fallback (no Lovable): `https://soapboxx-production.up.railway.app/ui/` (dashboard only; no episode detail).
