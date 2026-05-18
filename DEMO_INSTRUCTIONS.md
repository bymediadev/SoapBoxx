# SoapBoxx Production Studio Demo Instructions

## What Testers Get

- A packaged desktop demo (dependencies bundled).
- Demo-only runtime bucket (`demo`) separated from production settings/data.
- Clear branding in-app: `SoapBoxx Production Studio Demo`.

## How To Run (Tester)

1. Download and unzip the demo release from GitHub.
2. Open the unzipped folder.
3. Run:
   - `Launch SoapBoxx Production Studio Demo.bat` (Windows), or
   - `Launch SoapBoxx Production Studio Demo.ps1`.
4. Verify the window title includes `Production Studio Demo`.

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
