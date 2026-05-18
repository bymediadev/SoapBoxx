# SoapBoxx — Backlog

**Product and architecture:** see repo root [`PRODUCT.md`](../PRODUCT.md), [`ARCHITECTURE.md`](../ARCHITECTURE.md), [`WORKFLOW.md`](../WORKFLOW.md), [`RULES.md`](../RULES.md), [`BRANCHES.md`](../BRANCHES.md).

**Alignment plan:** Cursor plan *SoapBoxx Cursor Pack TODO* (Phases 0–6).

## Active engineering priorities

- [ ] Phase 3: Move OpenAI question extraction out of `frontend/soapboxx_tab.py`
- [ ] Phase 3: Move News API calls out of `frontend/scoop_tab.py`
- [ ] Phase 3: Route Reverb LLM usage through backend facade / FeedbackEngine
- [ ] Phase 4: Add `backend/llm_service.py` and migrate AI callers
- [ ] Phase 5: Unified episode/session object across tabs
- [ ] Phase 6: v1 freeze smoke test + production tag

## Optional enhancements (later)

- Advanced transcription backends (Azure, enhanced AssemblyAI)
- Export PDF/CSV expansions
- Additional analytics dashboards

Do not start optional items until core loop items above are done unless explicitly requested.
