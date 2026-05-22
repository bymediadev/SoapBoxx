# SoapBoxx Production Studio Demo Instructions

## What Testers Get

- A packaged desktop demo (dependencies bundled).
- Demo-only runtime bucket (`demo`) separated from production settings/data.
- Clear branding in-app: `SoapBoxx Production Studio Demo`.

## How To Run (Tester)

1. Download the demo zip from GitHub.
2. **Extract the entire zip** to a folder (e.g. right-click → Extract All).  
   **Do not** double-click the `.bat` from inside WinRAR or 7-Zip — that only extracts the launcher to a temp folder and the app will not start.
3. Open the extracted folder (read `00_EXTRACT_THIS_ZIP_FIRST.txt` if unsure).
4. Run:
   - `Launch SoapBoxx Production Studio Demo.bat` (Windows), or
   - `Launch SoapBoxx Production Studio Demo.ps1`.
5. Verify the window title includes `Production Studio Demo`.

Alternative: open the `SoapBoxxProductionStudioDemo` subfolder and run `SoapBoxx Production Studio Demo.bat`, or run `SoapBoxxProductionStudioDemo.exe` directly.

## Norton / antivirus (important)

PyInstaller demos are often flagged as **unknown publisher**. Norton may **block or quarantine** files under `SoapBoxxProductionStudioDemo\_internal\`, which breaks the SoapBoxx tab (you may see errors like the tab “doesn’t take arguments” or a blank studio).

**Fix:**

1. Extract the full zip to a folder (e.g. `C:\SoapBoxx-Demo\`).
2. In Norton: **Settings → Antivirus → Scans and Risks → Exclusions** (wording may vary).
3. Add an **exclusion** for that entire extracted folder.
4. Restore any quarantined items named `SoapBoxxProductionStudioDemo` or files under `_internal\`.
5. Launch again using the `.bat` in the extracted folder (not from inside WinRAR).

Optional: copy `.env.example` to `.env` in the same folder as the launcher and add API keys for OpenAI STT / Ollama (Settings tab).

## Quick Smoke Test Checklist

- App launches without installing Python or pip packages.
- `SoapBoxx`, `Scoop`, `Reverb`, and `Settings` tabs load.
- STT/TTS controls respond.
- Settings save/reset works.
- Diagnostics report opens and exports.

## If API Budget Is Available

- Add a valid OpenAI key in demo environment or demo config for best STT quality.
- Keep usage limits/billing alerts enabled.

## If API Budget Is Not Available

- Keep OpenAI unset in demo and position this as UI/workflow validation.
- Test local/offline paths and report UX feedback.
- Collect friction points (load time, clarity, errors, onboarding flow).

## Feedback Requested From Testers

- What worked well / what felt confusing.
- Which tab or workflow provided the most value.
- Any blocker that would prevent production adoption.
- Recommended improvements before production rollout.
