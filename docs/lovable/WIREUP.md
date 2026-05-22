# Lovable → SoapBoxx API wireup

## Fastest path (under 2 minutes)

1. **No Lovable edits:** open **`https://soapboxx-production.up.railway.app/ui/`** — bundled `/library/home` loads the dashboard in **2 HTTP calls** (health + home).  
   If you see **Application failed to respond**, the API is down — test `/health/live` first ([`RAILWAY_502_FIX.md`](../RAILWAY_502_FIX.md)), not a UI-only bug.
2. **Lovable:** paste the block in **[`LOVABLE_FREE_CHAT_PROMPT.md`](LOVABLE_FREE_CHAT_PROMPT.md)** into project chat → publish.
3. Copy [`api-client.ts`](api-client.ts) → `src/lib/soapboxx-api.ts`; use **`soapboxxApi.libraryHome()`** on the library screen (one fetch, not five).

**No Lovable paid plan?** See [`FREE_FRONTEND_OPTIONS.md`](../FREE_FRONTEND_OPTIONS.md).

Lovable app: [soapboxx.lovable.app](https://soapboxx.lovable.app) (optional)  
Backend: Railway FastAPI

## 1. API base URL (pick one)

### Fast path (recommended if Cloud/Secrets is hidden)

Use [`api-client.ts`](api-client.ts) as-is: defaults to Railway; no Lovable env UI required.

```ts
// SOAPBOXX_API_BASE → https://soapboxx-production.up.railway.app
// Local .env: VITE_API_URL=http://127.0.0.1:8000
// Or set SOAPBOXX_API_BASE = LOCAL_API in the pasted file
```

Do **not** use `import.meta.env.DEV` to pick the URL — Lovable preview can mis-route to localhost.

Redeploy/publish Lovable after changing the client.

### Later (optional): Lovable Secrets / `.env`

```text
VITE_API_URL=https://soapboxx-production.up.railway.app
```

Only after Railway `GET /health` returns 200 — otherwise the UI will still fail regardless of env config.

## 2. API client

Copy [`api-client.ts`](api-client.ts) into the Lovable repo as `src/lib/soapboxx-api.ts` (or merge into existing fetch helpers).

## 3. Lovable chat prompt (remove mocks)

Paste into Lovable:

```text
Remove ALL hardcoded library stats, podcast names, and episode lists.

Use src/lib/soapboxx-api.ts (production URL baked in; no Lovable env required):

- Library home (one call): const home = await soapboxxApi.libraryHome(12, 25) — use home.stats, home.pipeline, home.tree, home.activity, home.patterns, home.episodes
- Or separate calls: libraryStats(), pipelineStatus(), libraryTree(), activity(), weeklyPatterns()
- Ingestion form submit: soapboxxApi.ingestRss(url) then refetch stats, tree, activity
- Episode rows: status from soapboxxApi.libraryEpisodes() field "status" (queued | transcribing | measured | ready)
- Loading and error states when API fails
- No fake numbers (no 1492 episodes unless API returns it)
```

## 4. Screen → endpoint map

| UI | Call |
|----|------|
| **Whole home screen** | `libraryHome()` |
| Stats bar | `libraryStats`, `pipelineStatus` (or `home.stats`, `home.pipeline`) |
| Domain tree | `libraryTree` (or `home.tree`) |
| Recent activity | `activity` (or `home.activity`) |
| Patterns | `weeklyPatterns` (or `home.patterns`) |
| Add RSS | `ingestRss` |
| Episode detail | `episodeState(id)` |

## 5. CORS

Railway API must set `SOAPBOXX_CORS_ORIGINS=https://soapboxx.lovable.app` (already in repo default list).
