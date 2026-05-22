# Library & weekly batch

Aligns with [`SOAPBOXX_MASTER_PLAN_FOUNDATION.md`](../SOAPBOXX_MASTER_PLAN_FOUNDATION.md): the **library product** is measurements and patterns; shows/episodes are **sources**.

## Hosting platforms vs SoapBoxx

| Layer | What it is | Examples |
|-------|------------|----------|
| **Host catalog** | Where podcasts live and listeners find them | Spotify, Apple Podcasts, YouTube, RSS |
| **SoapBoxx insights library** | Local shelf of **measurements and coach notes** tied to those shows | `data/soapboxx.db`, Coach tab tree |

SoapBoxx **does not** compete with Spotify or other hosts. It **pulls from** them (YouTube today; RSS/feed links next), runs a **weekly batch**, and builds **your** archive of structural insights — category → author → show → episodes.

SoapBoxx stores analyzed episodes like a **library shelf**, not a flat paste list.

## Shelf layout (V1 implementation)

Target hierarchy (full): Domain → Category → Subcategory → Topic → Source → Episode → Guest → Measurements → Patterns.

**V1 shelf (implemented today):**

```text
Category (interview, business, …)
  └── Author / host
        └── Show (podcast source)
              └── Episodes → measurements (patterns accumulate in Phase 4)
```

- **Category** — same locked list as Intelligence V1 (`schemas/categories.json`).
- **Author** — host or primary creator for the show.
- **Show** — one podcast series under that author.
- **Episode** — transcript + rule-based metrics in SQLite (`data/soapboxx.db`).

## Weekly batch

1. **Enqueue** episodes (YouTube URL, file path, or paste id) with show + author + category.
2. **Run batch** — processes all `pending` queue rows: ingest → metrics → shelf. No coach unless `SOAPBOXX_BATCH_COACH=1`.
3. **Batch label** — ISO week, e.g. `2026-W21`, stored in `batch_runs`.

### CLI

```powershell
python -m backend.library.batch_cli
python -m backend.library.batch_cli --enqueue-youtube "https://youtube.com/..." --show "My Show" --author "Host Name" --category interview
```

### UI (Coach tab)

- **Show / Author** fields when adding to queue.
- **Add to weekly queue** — current import or paste.
- **Run weekly batch** — processes queue and refreshes the library tree.

## Tables (SQLite)

| Table | Role |
|-------|------|
| `podcasts` | Show shelf (category + author + title) |
| `episodes` | + `podcast_id`, `author`, `batch_id` |
| `episode_queue` | Pending work for next batch |
| `batch_runs` | Weekly run log |

Legacy episodes without `podcast_id` stay in the DB; only linked episodes appear in the library tree.

## Roadmap (hosting as source)

| Source | Role |
|--------|------|
| YouTube URL | Ingest today (captions / ASR) |
| RSS / podcast feed | Map feed → show shelf; batch new episodes weekly |
| Spotify / Apple | Link show for identity; ingest via RSS or publisher URL where available |

`podcasts.rss_url` is reserved for binding a shelf row to the host feed. Platform-specific IDs can be added when feed/RSS ingestion ships.
