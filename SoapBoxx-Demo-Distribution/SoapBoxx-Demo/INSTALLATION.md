# SoapBoxx Demo — Installation

**Canonical guide:** **[docs/README_DEMO.md](docs/README_DEMO.md)** (download options, first launch, beta credits, optional email, playground mode).

**Get the source:** [https://github.com/bymediadev/SoapBoxx](https://github.com/bymediadev/SoapBoxx) — clone with HTTPS (`git clone https://github.com/bymediadev/SoapBoxx.git`) or SSH (`git clone git@github.com:bymediadev/SoapBoxx.git`), then `git checkout demo/soapboxx-barebones`, then open **`SoapBoxx-Demo`** as described in the canonical guide.

This file is a short OS-specific install checklist. **All commands assume your current directory is the `SoapBoxx-Demo` folder** (the one that contains `frontend/`, `backend/`, and `requirements_demo.txt`).

---

## Prerequisites

- **Python 3.8+** on PATH  
- **Git** (optional, for cloning)  
- **4GB RAM** minimum (8GB recommended)  
- **~500MB** disk space  

---

## Windows

### Option 1 — Plug-and-play (recommended for release ZIP)

1. Extract or clone so you have the **`SoapBoxx-Demo`** folder.  
2. Double-click **`setup_and_run.bat`** — it installs **`requirements_demo.txt`** and starts the app (steps print in the window).  
3. Or use **`run_demo.bat`** if dependencies are already installed.

**Mac:** **`setup_and_run.command`** (see **`READ_ME_FIRST.txt`**). **Linux:** `chmod +x setup_and_run.sh && ./setup_and_run.sh`.

### Option 2 — Manual

```cmd
cd path\to\SoapBoxx-Demo
python -m pip install -r requirements_demo.txt
python frontend\main_window.py
```

---

## macOS

### Option 1 — Shell script (if present)

```bash
cd path/to/SoapBoxx-Demo
chmod +x scripts/run_demo.sh
./scripts/run_demo.sh
```

### Option 2 — Manual

```bash
cd path/to/SoapBoxx-Demo
python3 -m pip install -r requirements_demo.txt
python3 frontend/main_window.py
```

---

## Linux

### Option 1 — Shell script (if present)

```bash
cd path/to/SoapBoxx-Demo
chmod +x scripts/run_demo.sh
./scripts/run_demo.sh
```

### Option 2 — Manual

```bash
cd path/to/SoapBoxx-Demo
# Ubuntu/Debian example:
sudo apt update && sudo apt install -y python3-pip python3-venv
python3 -m pip install -r requirements_demo.txt
python3 frontend/main_window.py
```

---

## Verify (optional)

If **`test_barebones_modules.py`** exists in **`SoapBoxx-Demo`**:

```bash
python test_barebones_modules.py
```

---

## Troubleshooting

| Issue | What to try |
|--------|-------------|
| **Python not found** | Install from [python.org](https://www.python.org/) and check “Add to PATH”. |
| **PyQt6 fails** | `python -m pip install --upgrade pip` then retry; on Linux, install distro Qt/Python packages if needed. |
| **Wrong folder** | You must be **inside** `SoapBoxx-Demo` when running `python frontend/main_window.py`. |
| **Module not found** | See **[docs/README_DEMO.md](docs/README_DEMO.md)** troubleshooting. |

---

## After install

- First launch: **sign-in / sign-up** portal, then main window.  
- **3 episode credits** for **Complete Episode Workflow** (unless **`SOAPBOXX_DEV_PLAYGROUND=1`** or playground launcher).  
- Optional **`.env`** for email: copy **`.env.example`** — details in **`docs/README_DEMO.md`**.
