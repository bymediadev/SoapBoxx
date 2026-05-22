# V1 Day 6 — Taxonomy + library tree

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/taxonomy/nodes` | Create domain / category / subcategory |
| POST | `/taxonomy/map` | Link podcast → taxonomy node |
| GET | `/library/tree` | Browse Domain → Category → Subcategory → podcasts |

Hierarchy: **Domain → Category → Subcategory** (e.g. Business → Entrepreneurship → Startups).

Episodes inherit taxonomy via their podcast.

## Tests

```powershell
pytest tests/test_day6_taxonomy.py -v
```

## Next

Day 7 — translation templates from features
