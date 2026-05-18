# SoapBoxx — Backlog

**Product and architecture:** see repo root [`PRODUCT.md`](../PRODUCT.md), [`ARCHITECTURE.md`](../ARCHITECTURE.md), [`WORKFLOW.md`](../WORKFLOW.md), [`RULES.md`](../RULES.md), [`BRANCHES.md`](../BRANCHES.md).

**Alignment plan:** Cursor plan *SoapBoxx Cursor Pack TODO* (Phases 0–6).

## Active engineering priorities

- [x] Phase 3: Move OpenAI question extraction out of `frontend/soapboxx_tab.py` → `backend/question_extraction.py`
- [x] Phase 3: Move News API calls out of `frontend/scoop_tab.py` → `backend/scoop_news.py`
- [x] Phase 3: Route Reverb search-summary LLM through `backend/llm_service.py`
- [ ] Phase 4: Migrate remaining AI callers to `llm_service` (feedback_engine, guest_research, episode_intelligence, v3 internals)
- [x] Phase 5: RecordingSession extended (audio_path, metadata, to_dict); handoff SoapBoxx → Reverb
- [ ] Phase 6: v1 freeze smoke test + production tag

## Optional enhancements (later)

- Advanced transcription backends (Azure, enhanced AssemblyAI)
- Export PDF/CSV expansions
- Additional analytics dashboards

Do not start optional items until core loop items above are done unless explicitly requested.
