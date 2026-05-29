# Lovable — full frontend audit (paste once)

Copy **this entire file** plus the full contents of [`api-client.ts`](api-client.ts) into **one** Lovable chat message.

Start with:

```text
Frontend only. Full audit and fix pass. Use the live API contract below. Do not invent endpoints or mock data.
```

---

## Goal

Audit the entire SoapBoxx Lovable app and fix anything that blocks a **demo-ready** experience against production:

`https://soapboxx-production.up.railway.app`

When done, publish and return a short **audit report** (pass/fail per section + files changed).

---

## Critical flags

```text
AUTH_ENABLED = false   (in src/lib/feature-flags.ts or equivalent)
```

- App must **not** call `/auth/me`, `/auth/google/login`, or any auth route on startup.
- App shell must **not** require `user` / `session` objects.
- Auth UI may remain in codebase behind the flag but must not block routing.

---

## Live API truth (sanity check)

After wiring, the library home must match production approximately:

| Field | Expected (today) |
|-------|------------------|
| `episodes_total` | ~355 |
| `shows_total` | ~1 |
| `domains_total` | 0 (taxonomy may be empty) |
| `measured_pct` | ~1–2% |
| `queued_count` | ~351 |
| `ready` in pipeline | ~4 |
| Episode show name | **Planet Money** |
| Fake data to REMOVE | 1492 episodes, 128 shows, Lenny's Podcast, Acquired, 87% measured, Business/Tech domain tree unless API returns them |

If the UI shows Lenny's Podcast, Acquired, or ~1492 episodes, it is still on **mock data** — delete mocks and wire `soapboxxApi.libraryHome()`.

---

## API client rules

- Use `src/lib/soapboxx-api.ts` exactly (paste provided file).
- Base URL: `import.meta.env.VITE_API_URL` or default `https://soapboxx-production.up.railway.app`
- Do **not** use `import.meta.env.DEV` to switch to localhost in Lovable preview.
- On API failure: show `ErrorBlock` / error UI — **never** fall back to hardcoded library data.

Optional env in Lovable:

```text
VITE_API_URL=https://soapboxx-production.up.railway.app
```

---

## Screen-by-screen audit

### 1. App boot

- [ ] No white screen on load
- [ ] No startup request to `/auth/me` or auth endpoints
- [ ] Router has `defaultErrorComponent` and `defaultNotFoundComponent`
- [ ] `AUTH_ENABLED === false` → render app routes directly

### 2. Library / home

- [ ] Single preferred fetch: `soapboxxApi.libraryHome(15, 25)`
- [ ] Stats from `home.stats` (not constants)
- [ ] Pipeline chips from `home.pipeline.by_status`
- [ ] Activity from `home.activity`
- [ ] Patterns from `home.patterns` (library-wide, not per-episode)
- [ ] Episode table from `home.episodes` with real titles and statuses
- [ ] Each episode row links to `/episode/:id` (numeric id)
- [ ] Refresh refetches `libraryHome`
- [ ] Loading + error states (no mock fallback)

### 3. RSS ingest

- [ ] Submit calls `soapboxxApi.ingestRss(url)`
- [ ] Success shows `episodes_created`, `episodes_skipped`, `episodes_dispatched`
- [ ] Refetch library after ingest
- [ ] Errors shown inline, not silent

### 4. Episode detail `/episode/:id`

- [ ] Parse `id` as number
- [ ] `getEpisode(id)` — title, optional transcript excerpt
- [ ] `episodeState(id)` — status badge + steps
- [ ] `getTranslation(id)` — if 404, show "Not processed yet" + Run pipeline button (not a crash)
- [ ] If 200: show **Structural insight** = `template_id` + `insight_text` only (Layer 1, not coaching chat)
- [ ] **Measurements**: seven metrics from `processEpisode(id, {})` → `steps.find(s => s.step === "features")?.metrics` OR `GET /episodes/{id}/features` if you add a thin client method — never hardcode metrics
- [ ] **Run pipeline** → `processEpisode(id, {})` with empty body; never default `force_retranscribe: true`
- [ ] Demo tip: episodes with `status: "ready"` (ids 1–4) should show insight without STT

### 5. Shows / catalog (if present)

- [ ] `listPodcasts()` or `home.tree` from API only
- [ ] No fake domain tree unless `home.tree` is non-empty from API

### 6. Insights page (if present)

- [ ] `weeklyPatterns()` or `home.patterns` — library aggregates, not fake cards

### 7. Network verification (required)

Open preview → DevTools → Network → hard refresh.

Must see:

```text
GET https://soapboxx-production.up.railway.app/library/home → 200
```

On episode detail (ready episode, e.g. id 2):

```text
GET .../episodes/2/state → 200
GET .../episodes/2/translation → 200   (ready episodes)
```

Must **not** see mock JSON or zero network calls on library load.

---

## Remove completely

Search codebase and delete/stop using:

- `mock`, `placeholder`, `sampleData`, `dummy`, `fake`
- Hardcoded stats (1492, 128, 87.4%, etc.)
- Hardcoded shows (Lenny's Podcast, Acquired, etc.)
- Fallback arrays used when API fails
- Supabase / Clerk / Firebase auth (not in V1)
- Calls to endpoints not in `soapboxx-api.ts`

---

## Out of scope (do not add)

- Auth gate enabled (`AUTH_ENABLED` true) — backend auth not deployed
- Coach / scoring / narrative AI sections
- `force_retranscribe` in main UI
- New API routes not in the client

---

## Deliverable

When finished, reply with:

```markdown
## SoapBoxx frontend audit report

### Pass
- ...

### Fixed
- file: change

### Blocked / needs backend
- ...

### Network proof
- screenshot or list of key requests + status codes

### Demo recommendation
- Which episode id to click for live insight (e.g. id 2, status ready)
```

Publish the app after fixes.

---

## Reference: production endpoints (soapboxxApi)

| Action | Method | Path |
|--------|--------|------|
| Health | GET | `/health` |
| Library home | GET | `/library/home` |
| Ingest RSS | POST | `/ingest/rss` |
| Episode | GET | `/episodes/{id}` |
| Episode state | GET | `/episodes/{id}/state` |
| Translation | GET | `/episodes/{id}/translation` |
| Run pipeline | POST | `/episodes/{id}/process` body `{}` |
| Podcasts | GET | `/podcasts` |
| Weekly patterns | GET | `/insights/patterns/weekly` |

Auth endpoints exist in plans only — **do not call** until backend ships.
