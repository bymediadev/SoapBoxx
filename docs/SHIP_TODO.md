# SoapBoxx — Ship checklist

Work on branch **`production`**. Check off as you go.

## Done (verified)

- [x] Cursor Pack docs (`PRODUCT.md`, `ARCHITECTURE.md`, `WORKFLOW.md`, `RULES.md`, `BRANCHES.md`)
- [x] `.cursor/rules/soapboxx.mdc` + alignment phases 0–6 (code + docs)
- [x] Branches: `production`, `demo`; removed `Local`, `demo/soapboxx-barebones`, `demo-release`
- [x] Local `production` synced with `origin/production`
- [x] `pytest tests/ -q -m "not integration"` — **590 passed**
- [x] Offscreen UI smoke: `MainWindow` instantiates without crash
- [x] Backend import smoke passed

## Before you tag

### Git & GitHub

- [ ] `git status` on `production` — working tree clean
- [ ] GitHub branches page shows only: `production`, `demo`, `main` (no `Local`, `demo-release`, barebones)
- [ ] Choose default branch: keep `main` **or** set **`production`** as default
- [ ] `demo` fast-forwarded from `production` (if demo zip planned):
  ```bash
  git checkout demo && git merge --ff-only production && git push origin demo
  ```

### Manual smoke (required)

```bash
python -m frontend.main_window
```

- [ ] App launches without crash
- [ ] **SoapBoxx:** record → stop → transcript appears (or clear STT error)
- [ ] **Reverb:** feedback runs after stop (or clear “no API/Ollama” message)
- [ ] **Scoop:** search works or clean config error (no hang)
- [ ] **Export:** one path you use (optional if unused)

### Environment

- [ ] `.env` / secrets: transcription backend configured
- [ ] Feedback: OpenAI and/or `SOAPBOXX_OLLAMA_MODEL`
- [ ] Optional: `NEWS_API_KEY` for Scoop news

## Ship

### Production release

```bash
git checkout production
git pull
git tag v1.2.0
git push origin v1.2.0
```

Use **v1.2.0** (not v1.0.0) — `production` is ahead of existing tags.

- [ ] Tag pushed — CI builds Windows exe (see Actions)

### Demo package (optional)

On `demo` after ff-merge from `production`:

```powershell
./package_demo_release.ps1 -Version "1.0.0"
git tag demo-v1.0.0
git push origin demo --tags
```

- [ ] Demo zip built and uploaded if sending to testers

## After ship (later, not blocking v1)

- [ ] Fix httpx `verify=<str>` deprecation warnings (3 tests)
- [ ] GitHub default → `production` if still on `main`
- [ ] Delete or archive stale `main` only if nothing links to it
