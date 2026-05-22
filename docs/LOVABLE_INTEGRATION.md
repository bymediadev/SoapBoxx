# SoapBoxx — Lovable frontend + V1 API

**Frontend:** [https://soapboxx.lovable.app](https://soapboxx.lovable.app) (hosted on Lovable, independent deploy)  
**Backend:** FastAPI + Postgres + Redis (your system of record — updates via RSS ingest + pipeline)

The Lovable app is the **UI shell**. The API is the **live brain**. They deploy separately; the site calls your API over HTTPS.

---

## Architecture

```text
soapboxx.lovable.app  ──HTTPS──►  api.soapboxx.com (FastAPI)
                                      │
                                      ▼
                                 Postgres (podcasts, episodes, metrics)
                                      ▲
                                 RSS cron / POST /ingest/rss
```

- Lovable does **not** store the library database.
- Ingestion and measurements live on the API host.
- Re-deploying Lovable only changes UI; data persists in Postgres.

---

## 1. Deploy the API (required)

Expose FastAPI publicly, e.g. Railway, Render, Fly.io, or a VPS:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Environment:

| Variable | Example |
|----------|---------|
| `DATABASE_URL` | `postgresql+psycopg2://...` |
| `REDIS_URL` | `redis://...` |
| `SOAPBOXX_CORS_ORIGINS` | `https://soapboxx.lovable.app` |

Run migrations on deploy: `alembic upgrade head`.

Verify: `GET https://YOUR_API/health` → `"status": "ok"`.

---

## 2. Lovable environment variable

In the Lovable project **Settings → Environment**:

```text
VITE_API_URL=https://YOUR_PUBLIC_API_HOST
```

Example client (in Lovable-generated code):

```typescript
const API = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

export async function ingestRss(rssUrl: string) {
  const r = await fetch(`${API}/ingest/rss`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rss_url: rssUrl }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
```

Use `fetch` to the API base URL only — no local SQLite, no mock JSON in production.

---

## 3. System state layer (motion, not just rows)

```text
RSS → Ingestion → Pipeline → Postgres
                      ↓
              system_events + pipeline_status
                      ↓
                 Lovable UI
```

UI must show **state**, not only clean CRUD:

| Concept | API |
|---------|-----|
| Lifecycle per episode | `GET /episodes/{id}/state` |
| Counts by state | `GET /pipeline/status` |
| Activity feed | `GET /system/activity` |
| Weekly patterns | `GET /insights/patterns/weekly` |

### Episode lifecycle (`pipeline_status`)

```text
new → ingested → queued → transcribing → measured → ready
                              ↓
                           failed
```

After RSS ingest, episodes start as **`queued`**. Ingest emits `ingest.started` / `ingest.completed` / `episode.ingested` events.

---

## 4. Endpoint map (UI → API)

| Lovable screen | API |
|----------------|-----|
| Library stats + “processing” | `GET /library/stats` (`processing_count`, `queued_count`) |
| Domain tree sidebar | `GET /library/tree` |
| Shows under a branch | `tree[].children[].podcasts` |
| Recent activity list | `GET /library/episodes?limit=20` + `GET /system/activity` |
| Status chips | `status` on episode + `GET /episodes/{id}/state` for steps |
| “5 episodes processing” | `GET /pipeline/status` → `processing_count` |
| Emerging patterns panel | `GET /insights/patterns/weekly` |
| Ingestion — add RSS | `POST /ingest/rss` → refresh activity + pipeline status |
| Queue episode | `POST /episodes/{id}/queue` |
| Run pipeline steps | `POST .../transcribe`, `/features`, `/translate` |
| Settings / health | `GET /health` |

---

## 4. Auto-update (RSS)

The UI does not need to “download a database.”

1. **On demand:** Ingestion page calls `POST /ingest/rss` when the user adds a feed.
2. **Scheduled (recommended):** On the API host, cron or Celery beat every N hours:
   - For each `podcasts.rss_url`, call `ingest_rss_feed(db, url)`.
3. Lovable **refetches** `GET /library/stats` and `GET /library/episodes` on interval or on focus.

That gives you an independently updating system without redeploying the frontend.

---

## 5. CORS

The API allows:

- Origins in `SOAPBOXX_CORS_ORIGINS`
- Any `https://*.lovable.app` preview URL (regex)

If the browser blocks requests, add your exact Lovable preview URL to `SOAPBOXX_CORS_ORIGINS`.

---

## 6. Replace mock data in Lovable

The [Library UI](https://soapboxx.lovable.app) currently shows sample numbers (1,492 episodes, Lenny’s Podcast, etc.). In Lovable chat, paste:

```text
Remove all hardcoded library mock data. Use VITE_API_URL as base.

- Library home: GET /library/stats and GET /library/tree
- Branch view: filter tree node, show podcasts from tree response
- Recent activity: GET /library/episodes?limit=12
- Ingestion form: POST /ingest/rss, then refresh stats + tree
- Episode page: GET /episodes/:id, optional pipeline POSTs for transcribe/features/translate
- Show loading and error states when API is down
```

---

## 7. Local dev loop

```powershell
# Terminal 1 — API
docker compose -f docker-compose.v1.yml up -d
alembic upgrade head
uvicorn main:app --reload --port 8000

# Terminal 2 — point Lovable preview or local Vite at API
# VITE_API_URL=http://127.0.0.1:8000
```

---

## 8. Security (before public launch)

- Add API key or JWT when moving off single-user demo.
- Do not expose Postgres publicly; only the API port.
- Rate-limit `POST /ingest/rss`.

---

## Quick checklist

- [ ] API deployed with public HTTPS URL
- [ ] `alembic upgrade head` on production DB
- [ ] `SOAPBOXX_CORS_ORIGINS` includes `https://soapboxx.lovable.app`
- [ ] Lovable `VITE_API_URL` set to that API URL
- [ ] Mock data removed; screens wired to endpoints above
- [ ] RSS re-ingest scheduled on server (optional but recommended)
