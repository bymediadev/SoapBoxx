# SoapBoxx — Agent guide

Read these first (in order):

1. [`SOAPBOXX_V1_7DAY_EXECUTION.md`](SOAPBOXX_V1_7DAY_EXECUTION.md) — **build today from this only** (7-day checklist + contract)
2. [`SOAPBOXX_EXECUTION_PLAN_V1.md`](SOAPBOXX_EXECUTION_PLAN_V1.md) — V1 locked: layers, pipeline, must/must-not
3. [`SOAPBOXX_MASTER_PLAN_FOUNDATION.md`](SOAPBOXX_MASTER_PLAN_FOUNDATION.md) — measurements + patterns are the product; podcasts are sources
4. [`PRODUCT.md`](PRODUCT.md)
5. [`docs/SYSTEM_DESIGN_V0_V1.md`](docs/SYSTEM_DESIGN_V0_V1.md) — instrumentation vs coach layers (coach **out of V1**)
5b. [`docs/SOAPBOXX_V1_TRUTH_CONTRACT.md`](docs/SOAPBOXX_V1_TRUTH_CONTRACT.md) — Layer 1 invariants; no LLM in translation/features
6. [`ARCHITECTURE.md`](ARCHITECTURE.md)
7. [`docs/STORAGE.md`](docs/STORAGE.md) — storage model (migrating to Postgres per 7-day plan)
8. [`WORKFLOW.md`](WORKFLOW.md)
9. [`RULES.md`](RULES.md)
10. [`BRANCHES.md`](BRANCHES.md)
11. [`docs/V1_TEST_SUITE.md`](docs/V1_TEST_SUITE.md) — daily PASS/FAIL tests per 7-day plan

## Hard constraints

- Core loop: **Record → Transcribe → Improve**
- Do not invent new architecture patterns or parallel AI layers
- Develop on branch **`production`** only; update **`demo`** via fast-forward before demo releases
- Do not edit `releases/`, `*-Distribution*/`, or `reports/` as product code
- Desktop canonical path: `SoapBoxxCore` + `transcriber` + `FeedbackEngine`

## Tests

```bash
python -m pytest tests/ -q -m "not integration"
```

Pre-release: [`docs/V1_RELEASE_CHECKLIST.md`](docs/V1_RELEASE_CHECKLIST.md)

Evaluation/hardening tasks: see [`docs/CURSOR_HARDENING_EXECUTION_PROMPT.md`](docs/CURSOR_HARDENING_EXECUTION_PROMPT.md) (scope limited to that doc).
