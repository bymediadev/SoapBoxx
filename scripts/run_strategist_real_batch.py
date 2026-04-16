#!/usr/bin/env python3
"""
Re-run real-episode strategist batch (single LLM call per episode + same post-process as blueprint).
Env:
  SOAPBOXX_OLLAMA_MODEL  (default: llama3.2:3b for validation throughput)
  SOAPBOXX_OLLAMA_HTTP_TIMEOUT  (default: 240)
"""
from __future__ import annotations

import json
import os
import re
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "real_batch_llm_validation"
EPISODES = [
    ("DfTU5LA_kw8", "Joe Rogan Experience #2138 - Tucker Carlson"),
    ("SwQhKFMxmDY", "Rich Roll Podcast - Andrew Huberman"),
    ("PDiCcQyQVnI", "Club Shay Shay - Chris Tucker"),
    ("Bb-eLRjU7uQ", "Conan O'Brien Needs A Friend - Elizabeth Banks"),
    ("wm3VMuTK2Z4", "Meet the Press Full Episode"),
]


def vtt_to_text(vtt_path: Path) -> str:
    lines = vtt_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out: list[str] = []
    last = ""
    for line in lines:
        s = line.strip()
        if not s or s.startswith("WEBVTT") or "-->" in s or re.fullmatch(r"\d+", s):
            continue
        s = re.sub(r"<[^>]+>", "", s).strip()
        if not s:
            continue
        if s != last:
            out.append(s)
            last = s
    return "\n".join(out)


def main() -> int:
    os.environ.setdefault("SOAPBOXX_OLLAMA_MODEL", "llama3.2:3b")
    os.environ.setdefault("SOAPBOXX_OLLAMA_HTTP_TIMEOUT", "240")

    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / "backend"))
    from youtube_subtitles import download_youtube_en_vtt

    from blueprint_v1 import pipeline as bp
    from blueprint_v1.llm_runner import run_json_prompt
    from blueprint_v1.prompts import MASTER_STRATEGIST_PROMPT

    rows: list[dict] = []
    skipped: list[dict] = []

    for eid, title in EPISODES:
        print(f"\n=== {eid} :: {title} ===", flush=True)
        try:
            vtt_path = download_youtube_en_vtt(
                f"https://www.youtube.com/watch?v={eid}",
                OUT,
                video_id=eid,
            )
            if vtt_path is None:
                skipped.append({"id": eid, "title": title, "reason": "missing_en_subtitles"})
                print("skip: no English subtitles", flush=True)
                continue

            raw = vtt_to_text(vtt_path)
            words = raw.split()
            clipped = " ".join(words[:450])
            (OUT / f"{eid}.txt").write_text(clipped, encoding="utf-8")
            inp = bp.EpisodicInput.from_metadata_transcript(
                clipped, title=title, creator="YouTube", genre="Podcast"
            )

            classification = bp._heuristic_classification(inp)
            narrative = bp._fallback_narrative(inp)
            analytical = bp._fallback_analytical(inp)
            thesis_obj = bp._fallback_thesis(inp, narrative, analytical)
            clips = bp._fallback_clips(inp)
            synthesis = bp._fallback_synthesis(narrative, analytical)

            mode = bp._select_strategist_mode(inp, analytical, clips)
            strategist_input = {
                "mode": mode,
                "title": inp.title,
                "show": (inp.entities[0] if inp.entities else ""),
                "transcript": bp._excerpt(inp.transcript),
                "claims": analytical.claims,
                "topics": inp.topics,
                "segments": [c.text for c in clips],
                "thesis": thesis_obj.thesis,
                "synthesis": synthesis.model_dump(),
            }

            # Large enough for a full strategist JSON object; small caps truncate mid-JSON and force None + fallback.
            strategist_raw = run_json_prompt(
                f"{MASTER_STRATEGIST_PROMPT}\n\nINPUT_JSON:\n{json.dumps(strategist_input, ensure_ascii=False)[:12000]}",
                system="You are a strict JSON emitter. Return valid JSON only.",
                max_tokens=2048,
            )

            strategist_report = bp._build_strategist_report(
                data=strategist_raw,
                inp=inp,
                classification=classification,
                thesis_obj=thesis_obj,
                narrative=narrative,
                analytical=analytical,
                synthesis=synthesis,
                clips=clips,
            )
            strategist_report = bp._apply_mode_profile(
                strategist_report=strategist_report,
                mode=mode,
                inp=inp,
                analytical=analytical,
                clips=clips,
            )

            cb = strategist_report.get("core_breakdown") or {}
            row = {
                "id": eid,
                "title": title,
                "ollama_model": os.environ.get("SOAPBOXX_OLLAMA_MODEL", ""),
                "overall_score": (strategist_report.get("snapshot") or {}).get("overall_score"),
                "signal_strength": (strategist_report.get("snapshot") or {}).get("signal_strength"),
                "mode": strategist_report.get("report_mode"),
                "core_problem": (strategist_report.get("core_problem") or "")[:200],
                "thesis_preview": (cb.get("thesis") or "")[:160],
                "conviction_preview": (strategist_report.get("conviction_statement") or "")[:160],
                "claims_count": len((cb.get("key_claims") or [])),
                "anchors_count": len((cb.get("evidence_anchors") or [])),
                "llm_used": strategist_raw is not None,
            }
            rows.append(row)

            payload = {
                "strategist_report": strategist_report,
                "product_positioning": "Layer 2 strategist",
                "report_mode": strategist_report.get("report_mode"),
                "llm_raw_present": strategist_raw is not None,
            }
            (OUT / f"{eid}.blueprint.json").write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            (OUT / f"{eid}.result.json").write_text(
                json.dumps(row, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(
                f"result: score={row['overall_score']} mode={row['mode']} llm={row['llm_used']}",
                flush=True,
            )

        except Exception as e:
            err = {
                "id": eid,
                "title": title,
                "reason": "processing_error",
                "error": str(e),
                "trace": traceback.format_exc()[-3000:],
            }
            skipped.append(err)
            (OUT / f"{eid}.error.json").write_text(json.dumps(err, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"error: {e}", flush=True)

    rows_sorted = sorted(rows, key=lambda r: -(r.get("overall_score") or 0))
    summary = {
        "batch_size": len(rows_sorted),
        "skipped": skipped,
        "results_sorted": rows_sorted,
        "model": os.environ.get("SOAPBOXX_OLLAMA_MODEL"),
        "http_timeout_sec": os.environ.get("SOAPBOXX_OLLAMA_HTTP_TIMEOUT"),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n=== DONE ===", flush=True)
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
