# Tester invite — copy into your email

Replace `<YOUR_NAME>`. Prefer **Option 1** if you have published a GitHub Release with a ZIP.

---

**Subject (example):** SoapBoxx demo — how to run it

---

Hi,

**Option 1 — Easiest (GitHub Release ZIP)**

1. Open **https://github.com/bymediadev/SoapBoxx/releases** and download **`SoapBoxx-Demo.zip`** or **`SoapBoxx-Demo-vX.Y.Z.zip`** from the latest release.  
2. Unzip. You should get a folder **`SoapBoxx-Demo`**. Open **`READ_ME_FIRST.txt`** inside it — same steps as below.  
3. **Plug-and-play (recommended):**  
   - **Windows:** double-click **`setup_and_run.bat`** (it runs PowerShell: installs dependencies, then starts the app — you’ll see each step in the window).  
   - **Mac:** double-click **`setup_and_run.command`** (if macOS blocks it the first time, right-click → **Open**, or run `chmod +x setup_and_run.command` in Terminal, then double-click again).  
   - **Linux:** in a terminal, `cd` into **`SoapBoxx-Demo`**, then: `chmod +x setup_and_run.sh && ./setup_and_run.sh`  

4. **Manual alternative:** open a terminal in **`SoapBoxx-Demo`**, then:

```text
python -m pip install -r requirements_demo.txt
python frontend/main_window.py
```

(On Mac/Linux, use **`python3`** if **`python`** isn’t found. On Windows you can still use **`run_demo.bat`** after dependencies are installed.)

---

**Option 2 — Git (developers)**

**Repository:** https://github.com/bymediadev/SoapBoxx  

```bash
git clone https://github.com/bymediadev/SoapBoxx.git
# or: git clone git@github.com:bymediadev/SoapBoxx.git
cd SoapBoxx
git checkout demo/soapboxx-barebones
```

Open **`SoapBoxx-Demo`** (usually `SoapBoxx-Demo-Distribution/SoapBoxx-Demo`), then use **`setup_and_run`** as above or the manual **`pip`** / **`python`** commands.

---

**First launch:** sign-in / sign-up, then the main window. **3 episode credits** for “Complete Episode Workflow.” API keys optional (**Settings** or **Beta → API Keys**).

**Full guide:** **`docs/README_DEMO.md`** in the package.

If something fails, reply with your OS, `python --version`, and the terminal error.

Thanks,  
`<YOUR_NAME>`

---

## Short version (chat / Slack)

**Releases:** https://github.com/bymediadev/SoapBoxx/releases — download **`SoapBoxx-Demo.zip`**, unzip → open **`SoapBoxx-Demo`** → **Windows:** double-click **`setup_and_run.bat`** · **Mac:** **`setup_and_run.command`** · **Linux:** `chmod +x setup_and_run.sh && ./setup_and_run.sh`. Details: **`docs/README_DEMO.md`**.
