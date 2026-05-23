# Lovable free tier — chat-only prompt

Copy everything inside the block below into **Lovable project chat** (not workspace settings).  
Ask it to apply changes for you — no manual code editor required.

---

```text
Wire this SoapBoxx app to our live FastAPI backend. Do not use mock library data.

API base URL (production):
https://soapboxx-production.up.railway.app

Create src/lib/soapboxx-api.ts with fetch helpers for:
- GET /health
- GET /library/home?activity_limit=20&episodes_limit=25  (stats, pipeline, tree, episodes, activity, patterns in ONE response)
- POST /ingest/rss body { "rss_url": string }
- POST /episodes/{id}/process body {}  (refresh metrics + insight; do NOT use force_retranscribe by default)

Use this base constant (no VITE env required):
const API = "https://soapboxx-production.up.railway.app";

Update the library home screen:
- Initial load: ONE fetch to /library/home — map fields stats, pipeline, tree, episodes, activity, patterns to the UI
- After RSS ingest: refetch /library/home (not six separate endpoints)
- RSS form posts to /ingest/rss then refetches
- To process one episode after ingest: POST /episodes/{id}/process with empty body {} only (fast; reuses stored transcript). Never default to force_retranscribe in the UI.

Show loading and error states when fetch fails.
Remove all fake episode counts and placeholder podcast names.
```

---

If chat is also blocked on your plan, use **[`FREE_FRONTEND_OPTIONS.md`](../FREE_FRONTEND_OPTIONS.md)** — open `https://soapboxx-production.up.railway.app/ui/` instead.
