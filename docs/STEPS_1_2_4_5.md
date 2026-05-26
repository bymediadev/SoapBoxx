# Steps 1, 2, 4, 5 (no Lovable)

Lovable deferred. Finish these in order.

---

## 1 — Groq on Railway + redeploy

**You do this in the Railway dashboard** (not in code).

| Step | Action |
|------|--------|
| 1 | API service → **Variables** → `GROQ_API_KEY` = your rotated key |
| 2 | Do **not** set `OPENAI_API_KEY` unless you want paid OpenAI |
| 3 | **Redeploy** API service (commit `1e06c96`+ must be live) |
| 4 | Confirm in [Swagger](https://soapboxx-production.up.railway.app/docs): `POST /episodes/{id}/process` exists |

**Pass:** `GET /health` → 200; deploy logs show latest commit.

---

## 2 — Prove full audio → insight (1–3 episodes)

After step 1:

```http
POST https://soapboxx-production.up.railway.app/pipeline/process?limit=1
```

Or Swagger: `POST /episodes/2/process` body `{}`.

**Pass:**

- Response `status: "ready"` and `template_id` A/B/C
- `GET /episodes/2/translation` → insight text
- `/ui/` → **Measured** count increases

**If Groq fails** (25MB, rate limit): use pasted transcript once:

```http
POST /episodes/3/process
{ "transcript": "Host: ...\nGuest: ..." }
```

Or Railway shell: `python scripts/demo_process_episode.py --episode-id 3`

---

## 4 — Taxonomy (Domains + catalog tree)

RSS does **not** create domains. Run once against production DB:

**Railway shell** on API service (or local with prod `DATABASE_URL`):

```bash
python scripts/seed_taxonomy.py
```

Edit mappings in [`data/taxonomy_seed.json`](../data/taxonomy_seed.json) (e.g. Planet Money → Business → Economics).

**Pass:**

- Script prints `Domains in DB: 4` (or similar)
- `/ui/` sidebar **Catalog** shows domains + Planet Money under Business
- `GET /library/home` → `tree` non-empty; `stats.domains_total` > 0

---

## 5 — Automation (queue worker)

New RSS episodes start processing without you clicking Swagger.

### A. New Railway service `soapboxx-worker`

| Setting | Value |
|---------|--------|
| Same repo / branch `production` | yes |
| Config file | `railway.worker.toml` |
| Variables | `DATABASE_URL` + `REDIS_URL` + `GROQ_API_KEY` (same references as API/Redis) |
| Start command | `python scripts/run_celery_worker.py` |
| Networking | no public domain needed |

This service stays up and consumes `soapboxx.process_episode` jobs pushed by RSS ingest.

### B. Feed sync remains separate

Keep RSS re-ingest on the existing cron service (`soapboxx-sync` / `railway.cron.toml`).
That service checks stored feeds; the worker service consumes queued processing jobs.

### C. Pass criteria

- Worker deploy logs show Celery boot + task consumption
- `POST /ingest/rss` returns `episodes_dispatched > 0` for brand-new feed entries
- Activity feed shows processing events without a manual `/process` click

---

## Order summary

```text
1 Groq + redeploy  →  2 manual /process test  →  4 seed_taxonomy  →  5 worker service
```

Step **4** can run anytime after ingest (even before Groq). Step **5** needs step **1** for real audio (or `SOAPBOXX_DEMO_TRANSCRIPT=1` for free).

---

## What you already have

- 355 ingested episodes (Planet Money)
- Episode 1 **ready** (translator proven via paste)
- API + `/ui/` live
