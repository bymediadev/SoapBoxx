# SoapBoxx v1 release checklist

Use this before tagging a **production** release on branch `production`.

## Git and branches

- [ ] Default branch on GitHub is `production`
- [ ] Working tree clean on `production`
- [ ] `demo` fast-forwarded from `production` if shipping a demo build
- [ ] Legacy branches (`main`, `Local`, `demo/soapboxx-barebones`) not used for this release

## Automated tests

From repo root:

```bash
python -m pytest tests/ -q -m "not integration"
```

Optional (requires `NEWS_API_KEY`):

```bash
python -m pytest tests/test_news_api.py -m integration
```

## Manual smoke (desktop core loop)

1. **Launch** — `python -m frontend.main_window` (or packaged `SoapBoxx.exe`)
2. **SoapBoxx tab** — Start record → speak → stop; transcript appears
3. **Reverb tab** — Opens after stop; session feedback runs; output is readable
4. **Scoop tab** — Guest/topic search runs (or shows clear config error without crash)
5. **Export** — Transcript or audio export works if exposed in UI

## Configuration

- [ ] `.env` or user secrets: OpenAI and/or Ollama (`SOAPBOXX_OLLAMA_MODEL`) for transcription/feedback
- [ ] Optional: `NEWS_API_KEY` for Scoop news features

## Production tag

On `production` only:

```bash
git tag v1.0.0
git push origin v1.0.0
```

CI ([`.github/workflows/build.yml`](../.github/workflows/build.yml)) builds on `v*` tags.

## Demo package (optional)

On `demo` after `git merge --ff-only production`:

```powershell
./package_demo_release.ps1 -Version "1.0.0" -ExpiresOn "YYYY-MM-DD"
git tag demo-v1.0.0
git push origin demo --tags
```

## v1 scope (frozen)

**In:** Record, transcribe, Scoop prep, Reverb feedback, export.

**Out:** New tabs, UI wiring to v3/blueprint/atomic batch pipelines, barebones demo branch.

See [`ARCHITECTURE.md`](../ARCHITECTURE.md) and [`PRODUCT.md`](../PRODUCT.md).
