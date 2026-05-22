# V1 Day 7 — Translation layer

## Migration

```powershell
alembic upgrade head   # adds episode_translations (003)
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/episodes/{id}/translate` | Generate insight from `episode_features` |
| GET | `/episodes/{id}/translation` | Read stored translation |

Templates A/B/C describe **structure only** (guest-led, structured interview, narrative). No advice, scoring, or optimization language.

## Tests

```powershell
pytest tests/test_day7_translation.py -v
```

## Full pipeline (E2E)

```powershell
$env:SOAPBOXX_V1_E2E = "1"
pytest tests/test_system_health.py -v
```

## V1 complete

RSS ingest → transcribe → features → taxonomy map → translate → library tree.
