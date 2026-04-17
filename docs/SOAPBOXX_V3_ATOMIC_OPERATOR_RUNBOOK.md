# SoapBoxx v3 — Atomic operator runbook (ship gate)

**Audience:** operators (e.g. Christopher) running acceptance before ship.  
**Goal:** confirm the system is **atomic-first**, enrichment **cannot overwrite** structured truth, and tests are green — without reading architecture docs.

---

## 0. One rule to remember

**Product logic that depends on facts, guests, topics, or clips must read:**

| Need | Read this in JSON |
|------|-------------------|
| Claims | `report_v3.claims` (from atomic when ON) and/or `report_v3.atomic_pipeline.claims` |
| Topic graph | `report_v3.atomic_pipeline.topic_graph` |
| Guests (canonical) | `report_v3.atomic_pipeline.guest_recommendations` and/or v3 `guests` built from that path |
| Clips (canonical) | **`report_v3.atomic_pipeline.clips`** |
| Workflow evidence rows | `workflow_report.evidence_map` (locked when atomic-backed) |

**Do not** treat coach markdown strings or `coach_report.opportunities.clip_moments` as SSOT for clips — they are presentation-only and may differ from `atomic_pipeline.clips`.

---

## 1. Hard gate — tests (run from repo root)

```bash
cd /path/to/SoapBoxx
python -m pytest tests/ -q
```

**Pass criteria:** `242 passed` (or current baseline), `1 skipped`. Any failure = **NO-GO** until fixed.

---

## 2. Environment — atomic ON/OFF

| Variable | Meaning |
|----------|---------|
| `SOAPBOXX_V3_ATOMIC_GROUND_TRUTH=1` or unset | Atomic path **ON** (default) |
| `SOAPBOXX_V3_ATOMIC_GROUND_TRUTH=0` | Atomic path **OFF** (legacy brief claims only) |
| `SOAPBOXX_V3_QUALITY_SIGNAL_CAP` | Max **deduped** non-blocking reality notes per stream (default **6**, clamped 1–25). WARN / DEGRADED lines beyond this get one summary line instead of spam. |

**Ship default:** leave unset or set to `1`. Only use `0` for legacy debugging or tests that require brief-only claims.

---

## 3. Acceptance checklist (tick in PR / release notes)

### System of truth

- [ ] With atomic ON, structured claims come from `run_atomic_pipeline` (see `build_v3_report` + `meta.structured_intelligence_source == "atomic_pipeline"` when active).
- [ ] With atomic ON, v3 does not re-extract claims, re-cluster topics, or add narrative `recommend_guests` filler (`atomic_env is None` is the legacy branch).

### Immutability (workflow AI)

- [ ] When the v3 report is atomic-backed, enrichment does **not** replace `evidence_map` or `guest_recommendations` (`_atomic_structure_lock_from_report_v3`, restore at end of `enrich_workflow_report_with_ai`; minimal path skips overwriting evidence when locked).
- [ ] `metadata.atomic_structure_lock_applied` is set after a successful enrich when that lock applied (`soapboxx_v3_workflow_local`).
- [ ] `metadata.v3_reality_check`: `failures` = blocking only (e.g. zero evidence rows); `degraded_notes` = thin evidence vs `min_evidence_rows` (non-blocking). `would_ship` ignores `WARN:` lines.

### Enrichment when locked

- [ ] `generate_evidence_map`, `generate_anchor_evidence_map`, and `generate_guest_recommendations` are not used to overwrite SSOT (guarded in code; covered by `tests/test_atomic_workflow_enrichment_lock.py`).

### Output contract (atomic ON)

- [ ] `report_v3["atomic_pipeline"]` present (envelope JSON) when atomic ran successfully.
- [ ] Guests on the atomic path come from atomic guest recommendations + topic graph, not brief-only guest synthesis.

### Pipeline wiring

- [ ] `generate_episode_report_v3(..., atomic_ground_truth=...)` forwards to `build_v3_report`.

---

## 4. Final smoke test (manual, ~5 minutes)

**Requires:** same transcript file twice, Python with repo `backend` on path.

### 4a — Determinism (atomic ON)

```bash
set SOAPBOXX_V3_ATOMIC_GROUND_TRUTH=1
```

Run twice (replace `TRANSCRIPT.txt`):

```bash
python -c "
import json, hashlib, sys
sys.path.insert(0, 'backend')
from atomic_pipeline import run_atomic_pipeline, envelope_to_json
with open('TRANSCRIPT.txt', encoding='utf-8') as f:
    t = f.read()
a = envelope_to_json(run_atomic_pipeline(t))
blob = json.dumps(a, sort_keys=True, ensure_ascii=False)
print(hashlib.sha256(blob.encode('utf-8')).hexdigest())
"
```

**Pass:** both runs print the **same** SHA-256 hash.

### 4b — Atomic OFF still usable

```bash
set SOAPBOXX_V3_ATOMIC_GROUND_TRUTH=0
```

Generate a v3 report for a real episode (your usual CLI or script). **Pass:** report builds without crash; claims follow brief path (no `structured_intelligence_source == atomic_pipeline`).

### 4c — Enrichment (optional, if Ollama + workflow AI on)

With atomic ON, run workflow once; confirm `workflow_report.evidence_map` and `guest_recommendations` match the pre-enrich snapshot from `workflow_report_from_v3_report` (same claim ids / guest rows as v3-derived body). If `metadata.atomic_structure_lock_applied` is true, lock was active.

---

## 5. Presentation / markdown

- Editorial pass (`maybe_editorial_pass_unified_markdown`) is **wording polish** only by policy; it does not re-run atomic pipeline.
- Operators must **not** paste edited markdown back into structured JSON as new claims.

---

## 6. GO / NO-GO

| Condition | GO |
|-----------|-----|
| pytest green at repo baseline | |
| Atomic ON is default for ship | |
| Smoke 4a: identical hash twice | |
| Smoke 4b: atomic OFF runs | |
| Team agrees: product uses `atomic_pipeline.clips` for clip logic | |

If any **NO** → fix or document exception before ship.

---

## 7. One-sentence status

When the above passes: **SoapBoxx v3 is a stable atomic-first intelligence pipeline with presentation layering on top and enforced immutability of structured fields under workflow enrichment.**
