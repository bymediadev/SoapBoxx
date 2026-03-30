# SoapBoxx Demo — GitHub Release (ready-made ZIP)

Build the zip, attach it to a release, then point testers at one URL.

**Whenever you change `SoapBoxx-Demo-Distribution/SoapBoxx-Demo`**, run **`build_demo_release_zip.ps1`** again and upload the **new** zip(s) to GitHub Releases. Testers download the release asset — not your local folder.

## 1. Build the zip (Windows)

From **`demo/soapboxx-barebones`** (or your demo branch), with changes committed:

```powershell
cd SoapBoxx-Demo-Distribution\scripts
.\build_demo_release_zip.ps1 -Version "1.0.0" -AlsoStableName
```

**Outputs** (default **`SoapBoxx-Demo-Distribution\release\`**):

| File | Purpose |
|------|---------|
| **`SoapBoxx-Demo-v1.0.0.zip`** | Versioned asset; align with your Git tag (e.g. `demo-v1.0.0`). |
| **`SoapBoxx-Demo.zip`** | Same contents; stable filename for `.../releases/latest/download/SoapBoxx-Demo.zip`. |

**Included in the zip:** the full **`SoapBoxx-Demo`** tree — **`READ_ME_FIRST.txt`**, **`setup_and_run.bat` / `.ps1` / `.sh` / `.command`**, **`docs/`**, **`frontend/`**, **`backend/`**, **`requirements_demo.txt`**, **`PACKAGE_INFO.json`**, launchers, etc.

**Excluded:** `.env`, `.venv`, `__pycache__`, `.git`, local beta state files (see script source).

**Version only** (no stable copy):

```powershell
.\build_demo_release_zip.ps1 -Version "1.0.0"
```

## 2. Create a GitHub Release

**Web:** [github.com/bymediadev/SoapBoxx/releases](https://github.com/bymediadev/SoapBoxx) → **Draft a new release**

- **Tag:** e.g. `demo-v1.0.0`
- **Title:** e.g. SoapBoxx Demo v1.0.0
- **Attach:** `SoapBoxx-Demo-v1.0.0.zip` and/or `SoapBoxx-Demo.zip`
- Publish

**CLI (gh):**

```bash
gh release create demo-v1.0.0 \
  --repo bymediadev/SoapBoxx \
  --title "SoapBoxx Demo v1.0.0" \
  --notes "See docs in SoapBoxx-Demo/docs/README_DEMO.md" \
  SoapBoxx-Demo-Distribution/release/SoapBoxx-Demo-v1.0.0.zip
```

## 3. Point the app and docs at the asset URL

In **`SoapBoxx-Demo/PACKAGE_INFO.json`**, set **`github_release_demo_zip_url`** to either:

- Versioned: `https://github.com/bymediadev/SoapBoxx/releases/download/demo-v1.0.0/SoapBoxx-Demo-v1.0.0.zip`
- Or stable: `https://github.com/bymediadev/SoapBoxx/releases/latest/download/SoapBoxx-Demo.zip` (only if you always upload an asset named **`SoapBoxx-Demo.zip`**)

## 4. Tester email (one line)

“Download **`SoapBoxx-Demo.zip`** from the latest release, unzip, open **`SoapBoxx-Demo`**, then double-click **`setup_and_run.bat`** (Windows) or **`setup_and_run.command`** (Mac), or run **`setup_and_run.sh`** on Linux — see **`READ_ME_FIRST.txt`**. ”

Full copy: **`SoapBoxx-Demo/docs/TESTER_EMAIL_TEMPLATE.md`**
