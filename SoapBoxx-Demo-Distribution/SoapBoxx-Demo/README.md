# SoapBoxx Demo — AI podcast workflow (local / mock)

Self-contained **Python + PyQt6** desktop demo: **SoapBoxx**, **Scoop**, and **Reverb** tabs with sign-in, optional API keys, and a **3-episode credit** limit for the “Complete Episode Workflow” action (unless you use playground mode).

**Repository:** [github.com/bymediadev/SoapBoxx](https://github.com/bymediadev/SoapBoxx) — `git clone https://github.com/bymediadev/SoapBoxx.git` or `git clone git@github.com:bymediadev/SoapBoxx.git`, then `git checkout demo/soapboxx-barebones`.

See **`docs/README_DEMO.md`** for the full, current story.

## Quick start

**Always run commands from the `SoapBoxx-Demo` folder** (the one that contains `frontend/` and `requirements_demo.txt`).

### Windows

- **First time / release ZIP:** double-click **`setup_and_run.bat`** (installs dependencies, then launches — uses PowerShell under the hood).  
- **After deps are installed:** **`run_demo.bat`**, or `scripts\run_demo.bat`, or:
```bash
python -m pip install -r requirements_demo.txt
python frontend/main_window.py
```

### macOS / Linux

- **First time / release ZIP:** **`setup_and_run.command`** (Mac, double-click) or **`chmod +x setup_and_run.sh && ./setup_and_run.sh`** (Linux / Mac terminal).  
- **Or** manual:
```bash
python3 -m pip install -r requirements_demo.txt
python3 frontend/main_window.py
```

**Internal testing (unlimited episode credits):** `run_playground.bat` / `scripts/run_playground.bat`, or set `SOAPBOXX_DEV_PLAYGROUND=1`.

## What you get

- **SoapBoxx / Scoop / Reverb** — full UI with local/mock backends (no cloud required for the core tour).
- **Login / sign-up** portal on first launch; **Settings** and **Beta → API Keys** for optional OpenAI / Google keys.
- **File** menu: export, zip local folder, GitHub local-setup links.
- **Help** menu: full description (from `PACKAGE_INFO.json`), About.

## Documentation

- **[docs/README_DEMO.md](docs/README_DEMO.md)** — **Start here:** download, install, run, credits, email, troubleshooting.
- **[docs/TUTORIAL_DEMO.md](docs/TUTORIAL_DEMO.md)** — Longer UI walkthrough.
- **[docs/TESTER_EMAIL_TEMPLATE.md](docs/TESTER_EMAIL_TEMPLATE.md)** — Copy-paste text for tester emails.
- **[../GITHUB_UPLOAD_GUIDE.md](../GITHUB_UPLOAD_GUIDE.md)** — Maintainers: after any change under **`SoapBoxx-Demo`**, run **`../scripts/build_demo_release_zip.ps1`** and upload the new zip from **`../release/`** to GitHub Releases.

## 🧪 Testing

Test all modules before running:
```bash
python test_barebones_modules.py
```

## 🎯 Perfect For

- **Podcast creators** exploring production tools
- **Content marketers** evaluating AI assistance
- **Educators** teaching podcast production
- **Sales teams** demonstrating capabilities
- **Anyone** wanting to experience SoapBoxx without setup

## 🔧 System Requirements

- Python 3.8 or higher
- Windows 10/11, macOS 10.14+, or Linux
- 4GB RAM minimum (8GB recommended)
- 500MB disk space

## 🚫 Demo Limitations

- **AI Analysis**: Uses local text analysis, not GPT
- **Guest Research**: Sample data, not real web scraping
- **Transcription**: Mock results, not actual audio processing
- **TTS**: File path generation, not real audio creation

## Getting help

1. **[docs/README_DEMO.md](docs/README_DEMO.md)** — download, run, credits, optional email, troubleshooting  
2. Run **`python test_barebones_modules.py`** if present, to verify barebones modules  
3. **Help** menu in the app — full description, About

---

**🎯 Ready to create amazing podcasts? Start with the demo, then upgrade to the full SoapBoxx experience!**

*This is the SoapBoxx Demo version. For full functionality with real AI analysis and transcription, visit the main SoapBoxx repository.*
