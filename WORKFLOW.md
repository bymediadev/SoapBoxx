# SoapBoxx — User Workflow

> **UI naming:** The recording tab is labeled **SoapBoxx** in the app; product docs call this module **Studio**.

## First-time user flow

1. Open app
2. See SoapBoxx tab (Studio / recording — default)
3. Plug in microphone
4. Click Record
5. Speak naturally
6. Stop recording
7. Transcript is generated automatically
8. User sees AI feedback (Reverb tab)

## Core recording flow

```text
START
  → User clicks Record
  → Audio captured + buffered
  → User speaks episode
  → Stop recording
  → Audio saved as session / episode
  → Transcription triggered
  → Transcript displayed
  → Reverb analysis runs
  → Feedback displayed
```

## Feedback flow (Reverb)

1. Take transcript
2. Analyze: clarity, structure, pacing, question handling
3. Generate: score (0–100), insights, improvement suggestions
4. Display results in structured format

## Scoop flow (pre-recording)

1. User selects guest/topic
2. System generates: background info, talking points, suggested questions
3. Output used as reference during recording

## Export flow

User can export:

- Transcript (.txt / .md)
- Audio file
- Analysis report

## Design principle

Every workflow must end with:

> a usable improvement artifact
