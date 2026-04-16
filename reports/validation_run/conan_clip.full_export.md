# SoapBoxx — insufficient signal for a full report

This run did not meet the minimum bar for a network-grade episode export. The pipeline stopped before synthesizing scores, clips, or growth packaging that could read as authoritative.

**Episode:** Conan O'Brien Needs A Friend - Elizabeth Banks

## Why export was withheld
- grounded evidence rows 0 < 2 (workflow=0, report_v3=0)
- segments 0 < 1 (workflow and report_v3)

## What usually fixes this
- Longer or cleaner transcript (manual captions, ASR repair, or Whisper)
- Enable Ollama and a capable local model (`SOAPBOXX_OLLAMA_MODEL`) for enrichment
- Re-run when the episode has a clearer argumentative spine in the tape

*No scores or strategic sections are shown because they would not be grounded in verified structure.*
