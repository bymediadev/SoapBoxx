# Free frontend options (no Lovable paid tier)

Lovable’s **paid** plan locks manual code edits. You can still ship a working UI without paying.

## Recommended: built-in UI on your API (free, redesigned)

A polished dashboard lives at **`/ui/`** — dark oxblood/amber “library terminal” theme (matches Lovable shadcn tokens), sidebar catalog, episodes table, activity, patterns. No build step, no Lovable.

The repo includes a zero-config web UI served by the same FastAPI process as the API.

| URL (local) | `http://127.0.0.1:8000/ui/` |
| URL (Railway) | `https://soapboxx-production.up.railway.app/ui/` |

**No Lovable, no env vars, no CORS** — browser and API share one origin.

```powershell
.\scripts\setup_local.ps1 -ApiOnly -V1Infra   # Docker Postgres + migrations
uvicorn main:app --reload --host 127.0.0.1 --port 8000
# open http://127.0.0.1:8000/ui/
```

DB connection refused? See [`DATABASE_URL_LOCAL_VS_RAILWAY.md`](DATABASE_URL_LOCAL_VS_RAILWAY.md).

After Railway `/health/live` is 200, open `/ui/` on production.

**“Application failed to respond” on `/ui/`** means the API container is not running (same as `/health/live` failing). Fix deploy first — [`RAILWAY_502_FIX.md`](RAILWAY_502_FIX.md) — not the HTML UI.

Source: [`static/v1-library/index.html`](../static/v1-library/index.html) — edit this file to customize the UI.

---

## Other free UI builders (optional)

| Service | Cost | Notes |
|---------|------|--------|
| **This repo `/ui/`** | Free | Same deploy as API; best default |
| **Swagger `/docs`** | Free | API testing, not a product UI |
| **v0.dev** | Free tier | Generate React; export and host on Vercel/Netlify |
| **GitHub Pages** | Free | Copy `static/v1-library/` to a `gh-pages` branch |
| **Netlify / Cloudflare Pages** | Free tier | Drag-drop the `static/v1-library` folder |
| **Lovable chat** | If chat works on free | See [`lovable/LOVABLE_FREE_CHAT_PROMPT.md`](lovable/LOVABLE_FREE_CHAT_PROMPT.md) |

Paid Lovable is optional polish — not required for a usable library UI.

---

## Always free: Swagger

`https://YOUR-API.up.railway.app/docs` — test every endpoint without a custom UI.

---

## Lovable free tier (chat only)

If you can use **Lovable chat** but not the code editor:

1. Open the project chat (not Account/Workspace settings).
2. Paste the prompt from [`docs/lovable/LOVABLE_FREE_CHAT_PROMPT.md`](lovable/LOVABLE_FREE_CHAT_PROMPT.md).
3. Let Lovable generate `src/lib/soapboxx-api.ts` and wire screens.

That uses AI edits, not manual paste. Success depends on your Lovable plan allowing chat-driven code changes.

---

## Host static HTML elsewhere (free)

Copy [`static/v1-library/index.html`](../static/v1-library/index.html) and change the script line:

```js
const API = "https://soapboxx-production.up.railway.app";
```

Deploy to **GitHub Pages**, **Cloudflare Pages**, or **Netlify** (free tiers).

Add your Pages URL to Railway:

```text
SOAPBOXX_CORS_ORIGINS=https://soapboxx.lovable.app,https://YOUR_USER.github.io
```

---

## What to skip on free Lovable

| Paid / blocked | Free alternative |
|----------------|------------------|
| Paste `api-client.ts` | `/ui/` on Railway or chat prompt |
| Cloud / Secrets `VITE_API_URL` | Hardcoded URL in static HTML or same-origin `/ui/` |
| Custom deploy from Lovable | API-hosted `/ui/` or GitHub Pages |

---

## Priority

1. Fix Railway **502** → `/health` returns 200  
2. Use **`/ui/`** or **`/docs`** (no Lovable required)  
3. Optionally improve Lovable later via chat or paid editor
