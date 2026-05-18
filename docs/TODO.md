# SoapBoxx — Backlog

**Product and architecture:** see repo root [`PRODUCT.md`](../PRODUCT.md), [`ARCHITECTURE.md`](../ARCHITECTURE.md), [`WORKFLOW.md`](../WORKFLOW.md), [`RULES.md`](../RULES.md), [`BRANCHES.md`](../BRANCHES.md).

**Alignment plan:** Cursor plan *SoapBoxx Cursor Pack TODO* (Phases 0–6).

## Active engineering priorities

- [x] Phase 3: Move OpenAI question extraction out of `frontend/soapboxx_tab.py` → `backend/question_extraction.py`
- [x] Phase 3: Move News API calls out of `frontend/scoop_tab.py` → `backend/scoop_news.py`
- [x] Phase 3: Route Reverb search-summary LLM through `backend/llm_service.py`
- [x] Phase 4: `feedback_engine` + `blueprint_v1/llm_runner` use `llm_service` (episode_intelligence brief path unchanged)
- [x] Phase 5: RecordingSession extended (audio_path, metadata, to_dict); handoff SoapBoxx → Reverb
- [x] Phase 6: [`docs/V1_RELEASE_CHECKLIST.md`](V1_RELEASE_CHECKLIST.md); pytest `590 passed` (not integration)

## Optional enhancements (later)

- Advanced transcription backends (Azure, enhanced AssemblyAI)
- Export PDF/CSV expansions
- Additional analytics dashboards

Do not start optional items until core loop items above are done unless explicitly requested.
