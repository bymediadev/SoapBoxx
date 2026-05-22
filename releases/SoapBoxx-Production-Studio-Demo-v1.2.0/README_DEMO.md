# SoapBoxx Production Studio Demo

Packaged demo release for external testers with a clear separation from production.

## What Changed

- Demo and production are now split by bucket:
  - `demo` bucket for demo builds/runs
  - `production` bucket for normal product runs
- Demo app is visibly labeled in the UI as:
  - `SoapBoxx Production Studio Demo`
- Demo runtime can be time-boxed (2-week trial window) via expiry date.

## One-Command Packaging (Maintainer)

From repository root on Windows PowerShell:

```powershell
./package_demo_release.ps1 -Version "1.1.0" -ExpiresOn "2026-05-20"
```

This command:

- Builds a bundled desktop executable with PyInstaller.
- Forces demo runtime defaults inside the packaged app.
- Creates a release folder in `releases/`.
- Creates a zip ready for GitHub Releases.

## What Testers Run

After unzipping the release package:

- `Launch SoapBoxx Production Studio Demo.bat` (recommended on Windows), or
- `Launch SoapBoxx Production Studio Demo.ps1`.

No Python/pip setup should be required for testers.

## Demo Runtime Policy

- Demo launches in `demo` bucket.
- Expiry is controlled by `SOAPBOXX_DEMO_EXPIRES_ON`.
- Expired demo builds stop at startup with a clear message.

## API Budget Guidance

- **If budget is available**: provide a valid demo OpenAI key for best STT/analysis experience.
- **If budget is not available**: run as UX/workflow demo and collect interface feedback.

## Supporting Docs

- `DEMO_INSTRUCTIONS.md` for test plan and operator notes
- `TUTORIAL_DEMO.md` for walkthrough-style usage
