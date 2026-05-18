# SoapBoxx — Branch Strategy

SoapBoxx uses **two active branches**. All other branches are archived.

## Active branches

| Branch | Role | Who commits here |
|--------|------|------------------|
| **`production`** | Product integration line; default for development | Feature PRs merge here only |
| **`demo-release`** | Tester release pointer; same code as production at each demo drop | **No feature commits** — fast-forward from `production` only |

> **Note:** Branch name is `demo-release` (not `demo`) because `demo/soapboxx-barebones` still exists on the remote and Git cannot create a `demo` ref until that branch is deleted. After deleting `demo/soapboxx-barebones` on GitHub, you may rename: `git branch -m demo-release demo`.

Short-lived `feature/*` branches off `production` are normal and are not a third product line.

## Archived branches (do not use for new work)

| Branch | Superseded by | Notes |
|--------|---------------|-------|
| `main` | `production` | Legacy default |
| `Local` | `production` | Former active dev line |
| `demo/soapboxx-barebones` | `demo-release` | Barebones fork; use full app + demo env instead |

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
git checkout demo-release
git merge --ff-only production
./package_demo_release.ps1 -Version "1.2.0" -ExpiresOn "YYYY-MM-DD"
git tag demo-v1.2.0
git push origin demo-release --tags
```

Demo builds use the **full app** with `SOAPBOXX_DEMO_EXPIRES_ON` and Production Studio Demo branding — not the old barebones modules.

See [`DEMO_INSTRUCTIONS.md`](DEMO_INSTRUCTIONS.md) and [`package_demo_release.ps1`](package_demo_release.ps1).

## Rules

1. Never commit features only on `demo-release` — fix on `production`, then fast-forward `demo-release`.
2. Never revive `Local` or `demo/soapboxx-barebones` for new features.
3. Do not edit artifact trees (`releases/`, `*-Distribution*/`, `reports/`) as source code.

## GitHub setup

- **Default branch:** `production`
- **Optional protection:** require PR + CI on `production`; restrict direct pushes to `demo-release`
