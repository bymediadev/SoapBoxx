# SoapBoxx — Branch Strategy

SoapBoxx uses **two active branches**. All other branches are archived.

## Active branches

| Branch | Role | Who commits here |
|--------|------|------------------|
| **`production`** | Product integration line; default for development | Feature PRs merge here only |
| **`demo`** | Tester release pointer; same code as production at each demo drop | **No feature commits** — fast-forward from `production` only |

Short-lived `feature/*` branches off `production` are normal and are not a third product line.

## Archived branches (do not use for new work)

| Branch | Superseded by | Notes |
|--------|---------------|-------|
| `main` | `production` | Legacy default |
| `Local` | `production` | Former active dev line |
| `demo/soapboxx-barebones` | `demo` | Deleted — barebones fork retired |

Optional archive tags: `archive/main-last`, `archive/local-last`, `archive/demo-barebones-last`.

## Workflows

### Daily development

```bash
git checkout production
git pull origin production
# branch feature/my-change off production, PR back to production
```

### Production release

```bash
git checkout production
git tag v1.2.0
git push origin v1.2.0
```

Tags `v*` trigger [`.github/workflows/build.yml`](.github/workflows/build.yml) (Windows `SoapBoxx.exe`).

### Demo release

```bash
git checkout demo
git merge --ff-only production
./package_demo_release.ps1 -Version "1.2.0"
git tag demo-v1.2.0
git push origin demo --tags
```

Demo builds use the **full app** with `SOAPBOXX_BUCKET=demo` and Production Studio Demo branding — not the old barebones modules.

See [`DEMO_INSTRUCTIONS.md`](DEMO_INSTRUCTIONS.md) and [`package_demo_release.ps1`](package_demo_release.ps1).

## Rules

1. Never commit features only on `demo` — fix on `production`, then fast-forward `demo`.
2. Never revive `Local` or `demo/soapboxx-barebones` for new features.
3. Do not edit artifact trees (`releases/`, `*-Distribution*/`, `reports/`) as source code.

## GitHub setup

- **Default branch:** `production`
- **Optional protection:** require PR + CI on `production`; restrict direct pushes to `demo`
