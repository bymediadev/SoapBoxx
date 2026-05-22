# Lovable → SoapBoxx API wireup

Lovable app: [soapboxx.lovable.app](https://soapboxx.lovable.app)  
Backend: Railway FastAPI (`VITE_API_URL`)

## 1. Environment (Lovable project settings)

```text
VITE_API_URL=https://YOUR-APP.up.railway.app
```

No trailing slash. Redeploy Lovable after saving.

## 2. API client

Copy [`api-client.ts`](api-client.ts) into the Lovable repo as `src/lib/soapboxx-api.ts` (or merge into existing fetch helpers).

## 3. Lovable chat prompt (remove mocks)

Paste into Lovable:

```text
Remove ALL hardcoded library stats, podcast names, and episode lists.

Use VITE_API_URL and src/lib/soapboxx-api.ts:

- Library home header: soapboxxApi.libraryStats() + soapboxxApi.pipelineStatus()
- Sidebar tree: soapboxxApi.libraryTree()
- Recent activity: soapboxxApi.activity(12) — show event_type, message, time
- Emerging patterns panel: soapboxxApi.weeklyPatterns()
- Ingestion form submit: soapboxxApi.ingestRss(url) then refetch stats, tree, activity
- Episode rows: status from soapboxxApi.libraryEpisodes() field "status" (queued | transcribing | measured | ready)
- Loading and error states when API fails
- No fake numbers (no 1492 episodes unless API returns it)
```

## 4. Screen → endpoint map

| UI | Call |
|----|------|
| Stats bar | `libraryStats`, `pipelineStatus` |
| Domain tree | `libraryTree` |
| Recent activity | `activity` |
| Patterns | `weeklyPatterns` |
| Add RSS | `ingestRss` |
| Episode detail | `episodeState(id)` |

## 5. CORS

Railway API must set `SOAPBOXX_CORS_ORIGINS=https://soapboxx.lovable.app` (already in repo default list).
