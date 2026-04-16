# Network episode brief — workflow v3 (primary)

**v3 is the primary SoapBoxx episode workflow.** The v2 compact brief JSON/markdown from
`episode_intelligence.generate_episode_brief` remains available as a secondary one-page export.

Single-page **SoapBoxx Episode Report** produced by `backend/episode_report_v3.py`.

## Primary output (coach report)

The exported markdown is built for **podcasters**: diagnose structure, extract insight, and give actionable direction (not recap). Sections **1–10** are the main report.

1. **Episode Diagnosis** — `HIGH_SIGNAL` (clear thesis + support read) or `LOW_SIGNAL` (explicit “no central thesis” + competing threads). Why it matters for retention, clips, growth.
2. **Extracted themes** — 2–4 structured themes (discussed / implying / matters).
3. **What worked** — Real strengths from evidence + production cues.
4. **Where it breaks** — Structure gaps + one simple rule to fix.
5. **Actionable content opportunities** — Spin-off (title + structure), clip moments, segment idea tailored to weakness.
6. **Smarter follow-up questions** — 4–6 sharp, content-tied, on-air usable.
7. **Guest strategy** — Exploratory (low signal) vs expert (high signal).
8. **Segment upgrade** — One custom segment to fix the biggest flaw.
9. **Immediate fix plan** — Three checklist items for the next recording.
10. **Bottom Line** — 2–3 sentences: good / must change / if fixed.

## Appendix (structured JSON fields)

- **Evidence mapping** — Rows: `id`, `claim`, `evidence`, `timestamp`, `type`.
- **Per-claim engagement** — Counterpunch, Validation, Application (for workflow integration).

`report_v3` also includes `signal_mode`, `coach_report` (dict), `clean_insights`, `claims`, `analytics_actionable`, etc.

## API

- `generate_episode_report_v3(transcript, metadata, ...)` — runs v2 brief generation, then v3 enrichment; returns `report_v3`, `markdown_v3`, and optional v2 `markdown`.
- `detect_signal_mode(brief)` — `HIGH_SIGNAL` vs `LOW_SIGNAL` (no fabricated thesis when low).
- `validate_references(report, valid_claim_ids=...)` — ensures every `cN` in the serialized report exists.

Workflow version constant: `REPORT_V3_VERSION` in `episode_report_v3.py`.

## Higher signal (practical defaults)

- **Transcript in one LLM pass:** When `SOAPBOXX_BRIEF_MAX_CHARS` is unset, the brief pipeline defaults to **200000** characters for a single pass. Set `SOAPBOXX_BRIEF_MAX_CHARS` explicitly to match your Ollama context (lower if the model runs out of context).
- **Metadata:** Accurate `title` / `creator` / `genre` in every entry point reduces wrong-template drift.
- **Ollama:** Set `SOAPBOXX_OLLAMA_MODEL` and avoid `SOAPBOXX_OFFLINE=1` when you want a real brief.
- **Workflow:** Keep `SOAPBOXX_WORKFLOW_USE_AI=1` (default) for fuller highlights and evidence; use `SOAPBOXX_WORKFLOW_SKIP_GATE=1` only when you trust the transcript and want to bypass the thin-source gate.
- **Quality bar:** Default reality rules live in `backend/data/v3_reality_expected.json`; tighten with `SOAPBOXX_V3_REALITY_RULES` or `SOAPBOXX_V3_REALITY_STRICT=1` on `scripts/episode_brief.py --v3` for CI-style enforcement.
