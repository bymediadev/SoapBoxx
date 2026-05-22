# V1 Day 5 — Feature extraction (7 metrics)

## Endpoint

`POST /episodes/{id}/features`

Requires transcript + segments (Day 4).

## Metrics (exactly 7)

| Field | Meaning |
|-------|---------|
| `hook_length_seconds` | Opening segment duration |
| `intro_length_seconds` | Intro block duration |
| `question_count` | `?` in transcript |
| `speaking_turns` | Speaker changes |
| `host_guest_ratio` | Host vs guest talk share |
| `topic_shift_count` | Structural topic boundaries |
| `cta_present` | Call-to-action detected |

Stored in `episode_features` (one row per episode). No scoring or ranking.

## Tests

```powershell
pytest tests/test_day5_feature_extraction.py -v
```

## Next

Day 6 — taxonomy + library tree
