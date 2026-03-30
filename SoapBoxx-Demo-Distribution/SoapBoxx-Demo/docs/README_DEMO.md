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

**Option A — Git (recommended for updates)**

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

Then open the folder that contains **`SoapBoxx-Demo`** (usually `SoapBoxx-Demo-Distribution/SoapBoxx-Demo` inside the repo).

**Option B — ZIP from GitHub**

1. Open **[github.com/bymediadev/SoapBoxx](https://github.com/bymediadev/SoapBoxx)**.
2. **Code → Download ZIP** (downloads the default branch; you still need the **`SoapBoxx-Demo`** path inside the tree), **or** use a release ZIP if you publish one.
3. Unzip and navigate to **`SoapBoxx-Demo`** (folder with `frontend/`, `backend/`, `requirements_demo.txt`). If your ZIP is only `main` and the demo folder is on another branch, clone with Git instead (Option A).

**Option C — From inside the app**

After install: **File → Download from GitHub (local setup)** opens the repo page and ZIP; **File → Download Everything** zips your local demo folder for backup (not a substitute for cloning from GitHub).

If you **fork** the repo, update **`PACKAGE_INFO.json`** (`github_repo_url`, `github_repo_ssh`, `github_zip_url`) so in-app links match your fork.

---

## Install and run

### Requirements

- **Python 3.8+**
- **Windows**, **macOS**, or **Linux**
- Internet optional for the UI; **only needed** if you use cloud APIs or SMTP.

### Install dependencies

From the **`SoapBoxx-Demo`** directory (the folder that contains `frontend` and `requirements_demo.txt`):

```bash
python -m pip install -r requirements_demo.txt
```

(Using a virtual environment is recommended: `python -m venv .venv` then activate it.)

### Windows — quick launch

- Double-click **`run_demo.bat`** in the **SoapBoxx-Demo** folder, **or**
- `scripts\run_demo.bat` (must be run with the current directory set to **SoapBoxx-Demo**).

### Run manually (all platforms)

```bash
cd SoapBoxx-Demo
python frontend/main_window.py
```

### Playground mode (unlimited episode credits for testing)

For internal testing only:

- **Windows:** `run_playground.bat` or `scripts\run_playground.bat`
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
├── PACKAGE_INFO.json
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

---

## License

Same as the main SoapBoxx project unless otherwise stated in **`PACKAGE_INFO.json`**.
