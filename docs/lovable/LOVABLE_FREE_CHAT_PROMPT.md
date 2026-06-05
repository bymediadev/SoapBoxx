# Lovable — one-shot wireup prompt (parity with `/ui/`)

**Reference UI:** bundled dashboard at `https://soapboxx-production.up.railway.app/ui/` (source: `static/v1-library/index.html`).

**Current state ([soapboxx.lovable.app](https://soapboxx.lovable.app)):** 3-column home (pipeline + catalog / stats + ingest + paginated episodes / activity + patterns), coaching report v2 on episode detail, `getEpisodeFeatures` on open (no `processEpisode` for metrics), `libraryHome(15, 5)` + `libraryEpisodes({ limit: 50, … })`.

Use the prompt below only to **re-wire** a broken preview, a new Lovable project, or when the UI has drifted from `/ui/`.

Copy **the entire block below** (from `Wire this SoapBoxx` through the end) into **Lovable project chat** once.

**Env:** `VITE_API_URL=http://127.0.0.1:8000` for local API; if unset, client defaults to `https://soapboxx-production.up.railway.app`. See [`.env.lovable.example`](.env.lovable.example).

---

## Before you send (required)

1. Paste the full [`api-client.ts`](api-client.ts) under Step 2 in the **same** chat message (no placeholder).
2. Step 3–4 describe `/ui/` parity — do not strip sections down to “insight_text only.”
3. After publish, compare side-by-side with `/ui/` on the same API host.

---

```text
Wire this SoapBoxx app to our live FastAPI backend. Match the production bundled UI at /ui/ (Insights Library). Remove ALL mock/hardcoded library data.

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

Create this file exactly as written. Import isNotFoundError from the same module for optional GETs (translation, features).

REQUIRED: Paste the full contents of docs/lovable/api-client.ts from the SoapBoxx repo immediately below. Do not implement soapboxxApi from memory.

[PASTE FULL api-client.ts HERE — same message as this prompt]

=== STEP 3 — Visual theme + shell (match /ui/) ===

Dark “library terminal” theme — same feel as /ui/:
- Background ~oklch(0.16 0.012 60), cards ~oklch(0.195 0.013 60), amber primary ~oklch(0.78 0.14 75)
- Fonts: Cormorant Garamond (headings), Inter (body), JetBrains Mono (labels, chips, uppercase section titles)
- Subtle dot-grid overlay on body (optional)
- Disclaimer on episode report: “We show how the episode is built — not a quality verdict.”

Layout (desktop): 3 columns
- Left sidebar (~260px): logo “SoapBoxx”, tagline “Insights library”, Pipeline chips (from home.pipeline), Catalog tree (from home.tree — domain/category nesting; **search input** filters show names in tree; podcast rows clickable to filter episodes)
- Center workspace: topbar “Production library” + health pill + “Process next 10” + “Refresh”; stats row; Ingest RSS card; Episodes table with toolbar
- Right rail (~300px): Activity list, Weekly patterns cards

Health: poll soapboxxApi.health() every 30s; pill text “live” when status ok, “offline” on error (show last error in title/tooltip).

Refresh (topbar): Promise.all([health(), libraryHome(15, 5)]) then loadEpisodes() — see below. Re-render stats, pipeline, tree, activity, patterns from home.

Process next 10: soapboxxApi.processNextBatch(10) then refresh; show succeeded/attempted inline.

=== STEP 4 — Library home data wiring ===

On load and Refresh:
- const home = await soapboxxApi.libraryHome(15, 5)
- home.stats → stat cards: episodes_total (with measured_pct progress bar), shows_total, domains_total, measured_count, queued_count, processing_count
- home.pipeline.by_status → sidebar pipeline chips (+ active count if processing_count > 0)
- home.tree → catalog sidebar; clicking a podcast sets podcast filter and reloads episode table
- home.activity → right rail (click row with episode_id → open episode detail)
- home.patterns → right rail weekly patterns (summary + pattern cards)

Episodes table (main content) — NOT only home.episodes (that is 5 preview rows). Use paginated API:
- soapboxxApi.libraryEpisodes({ limit: 50, offset, podcast_id?, status? })
- Toolbar: **Category** filter (top-level domains from home.tree), Show filter (podcasts in selected category), Status filter (ready | measured | queued | transcribing | All), Search (client-side **episode title or show name** on current page)
- Pagination: Prev/Next, label “Showing X–Y of total · page N of M”
- Columns: Title, Show, Status; row click → /episode/:id (numeric id)
- Status pills styled by status string (ready, queued, etc.)

Ingest by name or RSS URL (single field + Ingest button — same as /ui/):
- Import `isRssUrlInput`, `formatIngestMessage` from soapboxx-api.ts
- On Ingest: if `isRssUrlInput(q)` → `ingestRss(q)`; else `searchPodcasts(q, 15)`
  - 0 hits → error
  - 1 hit → `ingestRss(hit.rss_url)` (no silent wrong-show risk)
  - 2+ hits → show picker list; user taps "Add feed" on one row → `ingestRss(hit.rss_url)` — **never auto-ingest the first search result**
- Success message: `formatIngestMessage(r)` — `podcast_name` from API; `created: 0` + `skipped > 0` means feed already in library; `episodes_dispatched` is pipeline queue (includes backlog drain, not only new episodes)

Loading and error states on every data surface. No mock numbers. No fake podcast names.

**Real titles only:** Episode table and catalog must come from `libraryEpisodes` / `libraryHome` API responses. Delete any hardcoded episode rows, placeholder titles (`Episode 1`, `Untitled`, Lenny's Podcast, Acquired, etc.), or fallback arrays when the API fails. Show names and titles must match `podcast_name` + `title` from the backend.

=== STEP 5 — Episode detail (/episode/:id) — Layer 4 views first ===

Parse id as number. Page or full-screen modal.

**Primary UI (tabs):** Signals | Editorial readout | Next episode

On load (parallel):
- getProducerReport(id) — transcript_warning if present; tab Signals = .measurements only; tab Editorial readout = structure_label + editorial_readout (what_happening, why_it_matters — no duplicate listener/playbook sections)
- getActionsReport(id) — tab Next episode: actions[] + keep_patterns[] (from editorial_readout.what_to_try_next)
- getEpisode(id) — title in header
- episodeState(id) — meta line (episode #, podcast_name, status); pipeline steps row: Ingested | Transcript | Measured | Insight (booleans from state.steps)
- getEpisodeFeatures(id) — catch with isNotFoundError: 404 → hide measurement grids; 200 → render metrics (see below). Do NOT call processEpisode on open just to load metrics.
- getTranslation(id) — catch isNotFoundError: 404 → show empty state + Run pipeline; 200 → render report

Do NOT show measurement_stamp, measurement_cohort_note, or compared_with_library percentile lines in the default view.

**Advanced (collapsed):** optional getTranslation(id).report — full coaching v2 for power users only.

Legacy report rendering — if translation.report has episode_structure OR listener_experience (inside Advanced only):
Show these sections when data present (hide empty sections):
- measurement_cohort_note, measurement_stamp (schema / extraction / aggregation versions)
- transcript_limitations (paragraph)
- structural_identity (lines)
- leverage_points (list + hint: structural bands, not rankings)
- narrative_engine: engine_notes, timeline (time_label — label : detail), open_loops
- producer_notes: bullets, metrics table (metric, value, note), edit_flags
- producer_view: motion_notes, motion_track timeline, fusion_notes; if !audio_available or empty motion_track show hint “No audio motion yet — run extractAudioMotion when audio is available”
- Collapsible “Structural fingerprints (detail)”: episode_structure table, conversation_dynamics table (columns Metric, Value, Benchmark; optional coaching sub-row per metric)
- compared_with_library, structural_variance (“Your show”), listener_experience, topic_shift_note, editorial_tradeoffs
- template_playbook if present: form name, tagline, feels_like, how_its_built, review_these; else fallback section “Pattern” from what_this_means
- similar_to / playbook.similar_form
- When features loaded: collapsible “All measurements” grid with all seven metrics (hook, intro, questions, turns, guest ratio, transitions, CTA)

If translation exists but report is empty/minimal: fallback “Insight” box with insight_text only (legacy).

If no translation: “No insight yet. Run the pipeline…” + Run pipeline button.

Seven metrics from EpisodeFeatures (when loaded):
- Hero “Opening”: hook_length_seconds, intro_length_seconds, question_count (format seconds for hook/intro)
- “Conversation shape”: topic_shift_count, cta_present, speaking_turns
- Full grid in “All measurements” when coaching report shown

Run pipeline button:
- await soapboxxApi.processEpisode(id, {}) — never default force_retranscribe
- If result.status === "queued": poll episodeState every 3s until status ready or steps.insight_ready (max ~40 attempts), then reload detail
- Else reload detail immediately
- Show result message inline

Optional: Previous / Next episode within current table page (same order as episode list).

Optional dev: button to soapboxxApi.extractAudioMotion(id) when producer_view missing motion — not required for v1 parity.

=== STEP 6 — Rules ===

- Only soapboxxApi methods from the pasted client — no invented fetch URLs
- No mock data; empty/error states when API fails
- Do not use import.meta.env.DEV to pick API URL
- AUTH_ENABLED false if auth flag exists — no /auth/me on startup
- TanStack Router (or existing): /episode/:id with notFound on 404 episode
- Publish when done

=== Verify in Network tab ===

- GET .../health → 200
- GET .../library/home?activity_limit=15&episodes_limit=5 → 200
- GET .../library/episodes?limit=50&offset=0 → 200
- Open ready episode: GET .../episodes/{id}/state, GET .../features, GET .../translation → 200
- Run pipeline only when needed: POST .../episodes/{id}/process body {}
```

---

## How to send

1. Copy the entire `text` block above.
2. Replace `[PASTE FULL api-client.ts HERE — same message as this prompt]` with the complete [`api-client.ts`](api-client.ts).
3. Send as **one** Lovable message.

---

## After Lovable applies

1. Publish the Lovable app.
2. Confirm `SOAPBOXX_CORS_ORIGINS` includes `https://soapboxx.lovable.app`.
3. Side-by-side smoke test against `https://soapboxx-production.up.railway.app/ui/`:
   - Same stats and pipeline chips
   - Episodes table filters/pagination work
   - Ready episode shows full coaching report sections (not insight-only)
   - Metrics load via `GET /episodes/{id}/features` without running pipeline on open

**Fallback:** use `/ui/` on the API host if Lovable preview is blocked.
