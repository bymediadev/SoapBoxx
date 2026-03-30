# Tester invite — copy into your email

Use the **plain text** block below as-is, or replace `<YOUR_NAME>`.

---

**Subject (example):** SoapBoxx demo — how to run it

---

Hi,

**Repository (official):** https://github.com/bymediadev/SoapBoxx  

**Clone with Git (pick one):**

- HTTPS: `git clone https://github.com/bymediadev/SoapBoxx.git`
- SSH: `git clone git@github.com:bymediadev/SoapBoxx.git`

Then:

```text
cd SoapBoxx
git checkout demo/soapboxx-barebones
```

Open the **`SoapBoxx-Demo`** folder (usually `SoapBoxx-Demo-Distribution/SoapBoxx-Demo` inside the repo).

Thanks for trying **SoapBoxx Demo** — a desktop preview of the podcast workflow (SoapBoxx, Scoop, Reverb) with local/mock backends so you can explore the UI without a full production setup.

**What you need**

- **Python 3.8+** on Windows, Mac, or Linux  
- A few minutes to install dependencies and start the app

**If you don’t use Git:** download the repo as a ZIP from the green **Code** button on GitHub, unzip, and find **`SoapBoxx-Demo`** inside (you may need the **`demo/soapboxx-barebones`** branch for the latest demo layout — cloning is more reliable).

**Run it**

1. Open a terminal in the **`SoapBoxx-Demo`** folder (the one with `frontend/`, `requirements_demo.txt`).  
2. Install: `python -m pip install -r requirements_demo.txt`  
3. Start: `python frontend/main_window.py`  

**Windows:** double-click **`run_demo.bat`** in **`SoapBoxx-Demo`** instead.

**First launch**

You’ll see a **sign-in / sign-up** screen, then the main window. You have **3 episode credits** for the “Complete Episode Workflow” demo. Optional **API keys**: **Settings** or **Beta → API Keys** — not required to try the UI.

**Full instructions**

See **`docs/README_DEMO.md`** in the package (download, optional email, playground mode, troubleshooting).

If anything fails, reply with your OS, Python version (`python --version`), and the error text from the terminal.

Thanks,  
`<YOUR_NAME>`

---

## Short version (chat / Slack)

**Repo:** https://github.com/bymediadev/SoapBoxx — `git clone` (HTTPS or `git@github.com:bymediadev/SoapBoxx.git` for SSH) → `git checkout demo/soapboxx-barebones` → **`SoapBoxx-Demo`** → `pip install -r requirements_demo.txt` → `python frontend/main_window.py` (Windows: **`run_demo.bat`**). Sign in on first launch; 3 episode credits for the workflow demo. Full guide: **`docs/README_DEMO.md`**.
