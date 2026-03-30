# SoapBoxx Demo — Guide

**SoapBoxx Demo** is a self-contained desktop app (Python + PyQt6) that shows the SoapBoxx-style workflow: **SoapBoxx**, **Scoop**, and **Reverb** tabs with **local / mock** backends so testers can explore the UI and flows without a full production stack.

This document is the **up-to-date** overview: how the demo works, how to get it, how to run it, and what is real vs simulated.

**Official repository (bymediadev/SoapBoxx)**

- **Web:** [https://github.com/bymediadev/SoapBoxx](https://github.com/bymediadev/SoapBoxx)  
- **Clone (HTTPS):** `git clone https://github.com/bymediadev/SoapBoxx.git`  
- **Clone (SSH):** `git clone git@github.com:bymediadev/SoapBoxx.git` (if you use SSH keys with GitHub)  
- **Demo branch:** `demo/soapboxx-barebones` — checkout after cloning, then go to **`SoapBoxx-Demo`** (usually `SoapBoxx-Demo-Distribution/SoapBoxx-Demo`).

---

## What you get (in one minute)

| Topic | Summary |
|--------|---------|
| **Offline-first** | Core demo runs without cloud AI; optional API keys add cloud features later. |
| **Sign-in** | On first launch you see a **Login / Sign up** portal (and optional **Setup** tab for API keys and GitHub links). |
| **Beta credits** | **3 full episode credits** per account (hard limit) for the “Complete Episode Workflow” action, unless you use playground mode (see below). |
| **Tabs** | **SoapBoxx** — recording / export style UI (demo). **Scoop** — search / research style UI (sample data). **Reverb** — analysis / feedback style UI (local mock metrics). |
| **Settings** | **Settings** button and **Beta → API Keys** — OpenAI, Google, optional “other” provider; stored per user on this machine. |
| **Email (optional)** | If you configure `.env` with Gmail SMTP (or Resend/SendGrid), the app can send **welcome/login-style** mail to **addresses people use when they sign up**. See [Email (optional)](#email-optional). |

---

## Download the demo

**Option A — GitHub Release ZIP (easiest for testers — no Git, no branch)**

1. Open **[Releases](https://github.com/bymediadev/SoapBoxx/releases)**.
2. Download the attached **`SoapBoxx-Demo-vX.Y.Z.zip`** (or **`SoapBoxx-Demo.zip`** if you publish a stable asset name).
3. Unzip. You should see a single top-level folder **`SoapBoxx-Demo`** with `frontend/`, `requirements_demo.txt`, **`READ_ME_FIRST.txt`**, and the setup scripts below.
4. Go to [Install and run](#install-and-run) — **use the plug-and-play scripts** if you want one double-click / one command (no copy-paste into a terminal).

**Maintainers — build the zip** (on branch `demo/soapboxx-barebones`, from repo root):

```text
SoapBoxx-Demo-Distribution\scripts\build_demo_release_zip.ps1 -Version "1.0.0"
```

Optional **`-AlsoStableName`**: also writes **`SoapBoxx-Demo.zip`** so testers can use a stable URL:

`https://github.com/bymediadev/SoapBoxx/releases/latest/download/SoapBoxx-Demo.zip`

After publishing, set **`github_release_demo_zip_url`** in **`PACKAGE_INFO.json`** to that URL (or the versioned asset URL). Then **File → Download from GitHub** can open the release ZIP directly.

---

**Option B — Git (good for updates and developers)**

Use HTTPS or SSH, then check out the demo branch.

```bash
# HTTPS
git clone https://github.com/bymediadev/SoapBoxx.git
cd SoapBoxx

# or SSH (same repo)
# git clone git@github.com:bymediadev/SoapBoxx.git
# cd SoapBoxx

git checkout demo/soapboxx-barebones
```

Then open **`SoapBoxx-Demo`** (usually `SoapBoxx-Demo-Distribution/SoapBoxx-Demo`).

---

**Option C — “Code → Download ZIP” on GitHub (full repo tree)**

1. Open **[github.com/bymediadev/SoapBoxx](https://github.com/bymediadev/SoapBoxx)**.
2. **Code → Download ZIP** (often **`main`** only). You may still need **`demo/soapboxx-barebones`** to see the latest demo layout — **Option A or B** is more reliable.

---

**Option D — From inside the app**

**File → Download from GitHub (local setup)** — repo page, source ZIP, and (if configured) **release ZIP**. **File → Download Everything** zips your local demo folder for backup.

If you **fork**, update **`PACKAGE_INFO.json`** (`github_repo_url`, `github_repo_ssh`, `github_zip_url`, `github_release_demo_zip_url`).

---

## Install and run

### Requirements

- **Python 3.8+**
- **Windows**, **macOS**, or **Linux**
- Internet optional for the UI; **only needed** if you use cloud APIs or SMTP.

### Plug-and-play (recommended — especially for the GitHub Release ZIP)

From inside **`SoapBoxx-Demo`** (open **`READ_ME_FIRST.txt`** for the same steps):

| OS | What to run |
|----|----------------|
| **Windows** | Double-click **`setup_and_run.bat`** — runs **`setup_and_run.ps1`**, installs **`requirements_demo.txt`**, then starts the app. |
| **macOS** | Double-click **`setup_and_run.command`** (first time you may need **Right-click → Open**, or run `chmod +x setup_and_run.command` in Terminal). |
| **Linux** | In a terminal: `chmod +x setup_and_run.sh && ./setup_and_run.sh` |

These scripts print each step so you can see **install deps → launch app**. They do **not** require Git.

### Manual install (if you prefer the terminal yourself)

From **`SoapBoxx-Demo`**:

```bash
python -m pip install -r requirements_demo.txt
python frontend/main_window.py
```

On macOS/Linux, use **`python3`** if **`python`** is not available. A virtual environment is optional: `python -m venv .venv` then activate it.

### Other launchers (after deps are installed)

- **Windows:** **`run_demo.bat`** at the **SoapBoxx-Demo** root (calls **`scripts\run_demo.bat`**). Skips full `pip install -r` if PyQt6 is already present; use **`setup_and_run.bat`** for a clean first run from a fresh unzip.

### Playground mode (unlimited episode credits for testing)

For internal testing only:

- **Windows:** **`run_playground.bat`** or **`scripts\run_playground.bat`**
- Or set **`SOAPBOXX_DEV_PLAYGROUND=1`** before starting the app.

---

## First launch — what to expect

1. **Sign in / Sign up** — Create an account or sign in (email or tester ID).  
2. **Setup tab (optional)** — Configure API keys or open **GitHub local setup** before entering the main window.  
3. **Main window** — Tabs **SoapBoxx**, **Scoop**, **Reverb**; header **Settings**, **GitHub setup**, **Complete Episode Workflow**; status bar shows user, **usage (0/3)**, and API key status.  
4. **Menus** — **File** (export, download bundle, GitHub setup, exit), **Beta** (switch user, API keys, episode workflow), **Help** (full description, about).

---

## Demo vs production (honest list)

### Works in the demo (real)

- Full **PyQt6** UI, tabs, menus, dialogs.
- **Local** state: sign-in, credits, API keys (saved under **`SoapBoxx-Demo`** — see `.soapboxx_beta_state.json` and `.env` handling).
- **Mock** analysis / research / audio flows that match the **product** feel without real cloud transcription.

### Simulated or simplified

- **No real GPT** in the barebones path — local / placeholder analysis.
- **Guest research** — sample data, not live web scraping.
- **Transcription / TTS** — mock or simplified paths unless you wire a full backend.
- **“Magic link”** in the portal is a **demo** flow; real magic links need your auth backend.

---

## Beta credits and workflow

- Each account has **3 episode credits** (hard cap) for **Complete Episode Workflow** (header button or **Beta** menu).
- **Usage** shows in the status bar (`1/3`, `2/3`, `3/3`).
- After the third episode, a **paywall-style** message appears (copy is configurable in code).

---

## API keys (optional)

- **Settings** or **Beta → API Keys** — OpenAI, Google, custom label + key.
- Keys are stored **per user** in local state and applied to **`os.environ`** for backends that read `OPENAI_API_KEY`, `GOOGLE_API_KEY`, etc.
- **No keys required** to click through the demo UI.

---

## Email (optional)

The demo can send **plain-text** emails via **Gmail SMTP** (or Resend / SendGrid / a small webhook server — see `backend/notify_client.py`).

1. Copy **`.env.example`** to **`.env`** in **`SoapBoxx-Demo`** or use **`SoapBoxx/.env`** at the monorepo root (both are loaded; demo `.env` overrides if both exist).  
2. Set **`MAIL_FROM`**, **`SMTP_USER`**, **`SMTP_PASSWORD`** (Gmail [App Password](https://myaccount.google.com/apppasswords)), and SMTP host/port.  
3. **Sign-ups with an email** receive messages at **that address** (welcome / login notices). **`MAIL_TO`** is a **fallback** for tester IDs or if you set **`NOTIFY_USER_EMAILS=0`**.  
4. To disable all outbound mail: **`NOTIFY_DISABLED=1`**.  
5. Local logs: **`beta_events.jsonl`** (same folder as the demo).

Details: see **`.env.example`** and **`beta_config.json`**.

---

## Menu reference (current build)

| Menu | Items |
|------|--------|
| **File** | Export Data, Download Everything, Download from GitHub (local setup), Exit |
| **Beta** | Login / Switch User, API Keys, Complete Episode Workflow |
| **Help** | Full description, About |

---

## Troubleshooting

| Issue | What to try |
|--------|-------------|
| **`Module not found`** on optional modules | Demo stubs exist for some modules; run from **`SoapBoxx-Demo`** — `python frontend/main_window.py`. |
| **Import errors for `notify_client`** | Run from **`SoapBoxx-Demo`**; project root is on `sys.path`. |
| **Email not sending** | Check terminal for `notify smtp:` lines; verify App Password, spam folder, **`NOTIFY_DISABLED`**. |
| **Blank tabs** | Wait for lazy load; switch tab and back; see console for errors. |

---

## Project layout (important paths)

```
SoapBoxx-Demo/
├── READ_ME_FIRST.txt           # 3-step quick start after unzip
├── setup_and_run.bat           # Windows: double-click (runs .ps1)
├── setup_and_run.ps1           # Windows: pip install + launch (verbose)
├── setup_and_run.sh            # macOS / Linux: chmod +x && ./setup_and_run.sh
├── setup_and_run.command       # macOS: double-click in Finder
├── frontend/
│   └── main_window.py          # Entry point
├── backend/
│   ├── notify_client.py        # Optional email
│   └── *_barebones.py          # Mock / local backends
├── docs/
│   ├── README_DEMO.md          # This file
│   ├── TUTORIAL_DEMO.md        # Longer walkthrough
│   └── TESTER_EMAIL_TEMPLATE.md # Copy-paste for invites
├── requirements_demo.txt
├── run_demo.bat                # launcher (root)
├── run_playground.bat
├── scripts/
│   ├── run_demo.bat
│   └── run_playground.bat
├── PACKAGE_INFO.json           # github_release_demo_zip_url = release asset URL (optional)
├── .env.example
└── beta_config.json
```

---

## Upgrade to full SoapBoxx

1. Use the **main** branch and full **`requirements.txt`** from the main repo.  
2. Configure real API keys and services.  
3. Replace barebones modules with production integrations as documented in the main project.

---

## More reading

- **[TUTORIAL_DEMO.md](TUTORIAL_DEMO.md)** — Step-by-step UI tour (some sections may still reference older menu names; **README_DEMO.md** is authoritative for the current build).  
- **[TESTER_EMAIL_TEMPLATE.md](TESTER_EMAIL_TEMPLATE.md)** — Short text you can paste into an email to testers.  
- **[../../GITHUB_UPLOAD_GUIDE.md](../../GITHUB_UPLOAD_GUIDE.md)** (maintainers) — build the release ZIP and attach it to GitHub Releases.

---

## License

Same as the main SoapBoxx project unless otherwise stated in **`PACKAGE_INFO.json`**.
