# SoapBoxx Demo — GitHub Release (ready-made ZIP)

Build the zip, attach it to a release, then point testers at one URL.

## 1. Build the zip (Windows)

From `demo/soapboxx-barebones` (or your demo branch):

```powershell
cd SoapBoxx-Demo-Distribution\scripts
.\build_demo_release_zip.ps1 -Version "1.0.0"
```

Output: **`SoapBoxx-Demo-Distribution\release\SoapBoxx-Demo-v1.0.0.zip`**

Optional **stable filename** for every release (same download URL):

```powershell
.\build_demo_release_zip.ps1 -Version "1.0.0" -AlsoStableName
```

Also creates **`SoapBoxx-Demo.zip`** — upload **this** as the asset if you want:

`https://github.com/bymediadev/SoapBoxx/releases/latest/download/SoapBoxx-Demo.zip`

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
