# SoapBoxx — Agent guide

Read these first (in order):

1. [`PRODUCT.md`](PRODUCT.md)
2. [`ARCHITECTURE.md`](ARCHITECTURE.md)
3. [`WORKFLOW.md`](WORKFLOW.md)
4. [`RULES.md`](RULES.md)
5. [`BRANCHES.md`](BRANCHES.md)

## Hard constraints

- Core loop: **Record → Transcribe → Improve**
- Do not invent new architecture patterns or parallel AI layers
- Develop on branch **`production`** only; update **`demo-release`** via fast-forward before demo releases
- Do not edit `releases/`, `*-Distribution*/`, or `reports/` as product code
- Desktop canonical path: `SoapBoxxCore` + `transcriber` + `FeedbackEngine`

## Tests

```bash
pytest tests/
```

Evaluation/hardening tasks: see [`docs/CURSOR_HARDENING_EXECUTION_PROMPT.md`](docs/CURSOR_HARDENING_EXECUTION_PROMPT.md) (scope limited to that doc).
