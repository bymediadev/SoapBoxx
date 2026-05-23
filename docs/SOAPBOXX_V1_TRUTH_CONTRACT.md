# SoapBoxx V1 — Truth contract

**Status:** Locked for V1  
**Authority:** Complements [`SOAPBOXX_V1_7DAY_EXECUTION.md`](../SOAPBOXX_V1_7DAY_EXECUTION.md) Day 7. If a change would violate this doc, it is **V2+** or requires an explicit contract revision — not a drive-by “smartness upgrade.”

---

## What V1 is

SoapBoxx V1 is a **measurement + reporting system** with optional narrative augmentation later. It is **not** a generative “understand my podcast” assistant in the core layer.

The core compresses a transcript into fixed buckets:

1. **Seven metrics** (deterministic feature extraction)
2. **Template A / B / C** (rule-based classification)
3. **Fixed `insight_text`** (static copy per template)

That compression function must be **mathematically stable** given fixed inputs.

---

## Layers

| Layer | Name | Role | Groq / LLM? | Defines product behavior? |
|-------|------|------|-------------|---------------------------|
| **0** | Perception (STT) | Audio → transcript | Yes (optional) | No — input quality only |
| **1** | Core (measurement) | Metrics → template → insight | **Never** | **Yes** |
| **2** | Enhancement (commentary) | Coaching, narrative, “why it matters” | Yes (future) | No — must not feed Layer 1 |

```text
INPUT (audio)
   ↓
[Layer 0 — STT]           ← perception only (Groq OK)
   ↓
TRANSCRIPT
   ↓
[Layer 1 — features]      ← deterministic measurement
   ↓
[Layer 1 — translation]   ← A/B/C + fixed insight_text
   ↓
OUTPUT (V1 contract)

(optional, V1.5+)
   ↓
[Layer 2 — enhancement]   ← commentary only; separate storage/API
```

**Forbidden path:** `Reality → LLM → "truth"`  
**Required path:** `Reality → measure → (optional) explain`

---

## Hard product law (Layer 1)

For a **fixed transcript** and **fixed `episode_features`**:

| Output | Requirement |
|--------|-------------|
| `template_id` | Identical across every run |
| `insight_text` | Identical across every run |
| Influences | **Only** feature values and rule code in `translation_service.py` |

**Violation:** If two runs of `POST /episodes/{id}/process` with `{}` produce different `template_id` or `insight_text` **without** a change in stored features or translation rules, the architecture is **broken** — not “needs tuning.”

**Legitimate change:** Re-transcribe (`force_retranscribe`) or edit transcript → new text → new metrics → new template. That is **data change**, not Layer 1 randomness.

---

## Code boundaries (V1)

| Component | Path | Layer | Notes |
|-----------|------|-------|-------|
| STT | `backend/transcriber.py`, pipeline transcribe step | 0 | Groq/OpenAI OK |
| Features | `backend/services/feature_service.py` | 1 | Rule-based; no LLM |
| Translation | `backend/services/translation_service.py` | 1 | Templates A/B/C only; no LLM |
| Storage | `episode_features`, `episode_translations` | 1 | Core contract |
| Coach / synth | `backend/coach_synth.py`, v3 workflow | 2 | **Not** V1 API; do not wire into `/translation` |

Day 7 rules (unchanged): **no scoring, no advice, no optimization** in Layer 1 output.

---

## Seven metrics (Layer 1 inputs to templates)

From `run_feature_extraction` → `features` object:

- `hook_length_seconds`
- `intro_length_seconds`
- `question_count`
- `speaking_turns`
- `host_guest_ratio`
- `topic_shift_count`
- `cta_present`

Template selection (current rules):

- **A:** `host_guest_ratio >= 0.62` and `question_count < 14`
- **B:** `question_count >= 18` and `speaking_turns >= 8`
- **C:** otherwise

---

## V1 API contract (Layer 1 only)

These endpoints define what Lovable and other clients treat as **measured structure**:

| Method | Path | Layer |
|--------|------|-------|
| GET | `/episodes/{id}/translation` | 1 |
| POST | `/episodes/{id}/process` (body `{}`) | 0→1 |
| GET | `/library/home` | 1 + library metadata |

Metrics appear in `POST /process` response: `steps.find(s => s.step === "features")?.metrics`. There is **no** `GET /episodes/{id}/features` in V1.

---

## Forbidden changes (without contract revision)

- Calling Groq/LLM inside `translation_service.py` or `feature_service.py`
- Letting Layer 2 output **overwrite** `episode_translations.template_id` or `insight_text`
- Adding “coaching” or freeform insight to `GET /translation`
- Defaulting `force_retranscribe: true` in UI or batch jobs
- Treating STT variability as acceptable drift in **template** output for the same stored transcript

---

## Allowed evolution

| Change | OK when |
|--------|---------|
| New template D or adjusted thresholds | Explicit rule version + tests updated |
| Layer 2 `/enhance` endpoint | Separate table/fields; env-gated; never writes Layer 1 rows |
| Richer UI copy labels | “Structural insight” vs “Coaching” — see [`lovable/LOVABLE_FREE_CHAT_PROMPT.md`](lovable/LOVABLE_FREE_CHAT_PROMPT.md) |

---

## Tests that guard the contract

```bash
python -m pytest tests/test_day7_translation.py tests/test_episode_pipeline.py -q -m "not integration"
```

Expectations:

- Translation output has no forbidden coach/scoring language
- Pipeline `{}` reuses existing transcript when present
- Same features → same template (covered by deterministic rules + pipeline tests)

---

## Layer 2 (V1.5+ — not built in V1)

When added:

- New persistence (e.g. `episode_enhancements`), not overwriting `EpisodeTranslation`
- New route (`GET/POST /episodes/{id}/enhance`) or optional post-process step **after** `run_translation`
- Inputs: `template_id` + metrics JSON + canonical `insight_text`
- Outputs: narrative/coaching only
- Default **off** so `POST /process` with `{}` stays fast and deterministic

Implement leak guards (no LLM imports in Layer 1 services, CI check) **when Layer 2 ships**, not before.

---

## One-line summary

> **Layer 1 is measurement under fixed assumptions — not intelligence. Protect it from generative “improvements.”**
