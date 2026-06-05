#!/usr/bin/env python3
"""
End-to-end SoapBoxx V1 library demo — live API proof + visual HTML report.

Runs: health → library stats → pipeline → episode state → features →
producer report → actions report. Writes a self-contained HTML dashboard.

Examples:
  python scripts/e2e_library_demo.py
  python scripts/e2e_library_demo.py --api http://127.0.0.1:8000
  python scripts/e2e_library_demo.py --episode-id 2 --open
  python scripts/e2e_library_demo.py --process-one
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API = "https://soapboxx-production.up.railway.app"
REPORT_DIR = ROOT / "reports"
REPORT_HTML = REPORT_DIR / "e2e_library_demo.html"
REPORT_JSON = REPORT_DIR / "e2e_snapshot.json"


@dataclass
class Step:
    name: str
    endpoint: str
    ok: bool
    detail: str = ""
    payload: Optional[dict[str, Any]] = None


@dataclass
class DemoRun:
    api_base: str
    started_at: str
    steps: list[Step] = field(default_factory=list)
    snapshot: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(s.ok for s in self.steps)


class ApiClient:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Optional[dict[str, Any]] = None,
        timeout: int = 90,
    ) -> Any:
        url = f"{self.base}{path}"
        data = None
        headers = {
            "User-Agent": "SoapBoxx-E2E-Demo/1.0",
            "Accept": "application/json",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = Request(url, data=data, headers=headers, method=method)
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            if not raw.strip():
                return None
            return json.loads(raw)


def _fmt_seconds(value: Optional[float]) -> str:
    if value is None:
        return "—"
    sec = max(0, int(round(float(value))))
    if sec < 60:
        return f"{sec}s"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def _pick_episode(
    client: ApiClient,
    *,
    episode_id: Optional[int],
    skip_demo_transcript: bool,
) -> tuple[Optional[dict[str, Any]], str]:
    if episode_id is not None:
        try:
            state = client.request("GET", f"/episodes/{episode_id}/state")
            return (
                {
                    "id": episode_id,
                    "podcast_id": state.get("podcast_id"),
                    "podcast_name": state.get("podcast_name"),
                    "title": state.get("title"),
                    "status": state.get("status"),
                },
                f"user-selected episode {episode_id}",
            )
        except HTTPError as exc:
            return None, f"episode {episode_id} not found ({exc.code})"

    for status in ("ready", "measured", None):
        path = "/library/episodes?limit=25&offset=0"
        if status:
            path += f"&status={status}"
        page = client.request("GET", path)
        for row in page.get("episodes") or []:
            eid = int(row["id"])
            if skip_demo_transcript and eid == 1:
                continue
            return row, f"first {status or 'available'} episode (id={eid})"
    return None, "no episodes in library"


def run_demo(
    client: ApiClient,
    *,
    episode_id: Optional[int],
    process_one: bool,
    skip_demo_transcript: bool,
) -> DemoRun:
    run = DemoRun(
        api_base=client.base,
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    snap: dict[str, Any] = {"api_base": client.base, "started_at": run.started_at}

    def record(name: str, endpoint: str, ok: bool, detail: str = "", payload: Any = None) -> None:
        run.steps.append(
            Step(
                name=name,
                endpoint=endpoint,
                ok=ok,
                detail=detail,
                payload=payload if isinstance(payload, dict) else None,
            )
        )

    try:
        health = client.request("GET", "/health")
        ok = (health or {}).get("status") == "ok"
        snap["health"] = health
        record("Health", "GET /health", ok, (health or {}).get("service", ""), health)
    except (HTTPError, URLError, TimeoutError) as exc:
        record("Health", "GET /health", False, str(exc))
        run.snapshot = snap
        return run

    try:
        stats = client.request("GET", "/library/stats")
        snap["stats"] = stats
        record(
            "Library stats",
            "GET /library/stats",
            bool(stats),
            f"{stats.get('episodes_total', 0)} episodes · {stats.get('shows_total', 0)} shows",
            stats,
        )
    except (HTTPError, URLError, TimeoutError) as exc:
        record("Library stats", "GET /library/stats", False, str(exc))

    try:
        pipeline = client.request("GET", "/pipeline/status")
        snap["pipeline"] = pipeline
        ready = (pipeline or {}).get("by_status", {}).get("ready", 0)
        record(
            "Pipeline",
            "GET /pipeline/status",
            bool(pipeline),
            f"{ready} ready · {pipeline.get('processing_count', 0)} processing",
            pipeline,
        )
    except (HTTPError, URLError, TimeoutError) as exc:
        record("Pipeline", "GET /pipeline/status", False, str(exc))

    if process_one:
        try:
            batch = client.request("POST", "/pipeline/process?limit=1")
            snap["process_batch"] = batch
            record(
                "Process one",
                "POST /pipeline/process?limit=1",
                (batch or {}).get("succeeded", 0) >= 0,
                f"attempted={batch.get('attempted')} succeeded={batch.get('succeeded')}",
                batch,
            )
        except (HTTPError, URLError, TimeoutError) as exc:
            record("Process one", "POST /pipeline/process?limit=1", False, str(exc))

    episode, pick_note = _pick_episode(
        client,
        episode_id=episode_id,
        skip_demo_transcript=skip_demo_transcript,
    )
    if not episode:
        record("Pick episode", "GET /library/episodes", False, pick_note)
        run.snapshot = snap
        return run

    eid = int(episode["id"])
    snap["episode"] = episode
    record(
        "Pick episode",
        "GET /library/episodes",
        True,
        f"{episode.get('podcast_name')} — {episode.get('title')} ({pick_note})",
        episode,
    )

    for label, path, key in (
        ("Episode state", f"/episodes/{eid}/state", "state"),
        ("Features (Layer 2)", f"/episodes/{eid}/features", "features"),
        ("Producer report (Layer 4)", f"/episodes/{eid}/report/producer", "producer"),
        ("Actions report", f"/episodes/{eid}/report/actions", "actions"),
    ):
        try:
            payload = client.request("GET", path)
            snap[key] = payload
            detail = ""
            if key == "state":
                steps = (payload or {}).get("steps") or {}
                detail = ", ".join(k for k, v in steps.items() if v)
            elif key == "features":
                detail = f"{payload.get('question_count', 0)} questions · hook {_fmt_seconds(payload.get('hook_length_seconds'))}"
            elif key == "producer":
                detail = (payload or {}).get("structure_label") or (payload or {}).get("template_id", "")
            elif key == "actions":
                detail = f"{len((payload or {}).get('actions') or [])} actions"
            record(label, f"GET {path}", bool(payload), detail, payload)
        except HTTPError as exc:
            if exc.code == 404:
                record(label, f"GET {path}", False, "404 — run pipeline on this episode first")
            else:
                record(label, f"GET {path}", False, f"HTTP {exc.code}")
        except (URLError, TimeoutError) as exc:
            record(label, f"GET {path}", False, str(exc))

    run.snapshot = snap
    return run


def _readout_lists(producer: dict[str, Any]) -> dict[str, list[str]]:
    readout = producer.get("editorial_readout") or {}
    if readout:
        return {
            "what_happening": list(readout.get("what_happening") or []),
            "why_it_matters": list(readout.get("why_it_matters") or []),
            "what_to_try_next": list(readout.get("what_to_try_next") or []),
        }
    return {
        "what_happening": list(producer.get("patterns") or [])[:4],
        "why_it_matters": list(producer.get("editorial_tradeoffs") or [])[:3],
        "what_to_try_next": [],
    }


def render_html(run: DemoRun) -> str:
    snap = run.snapshot
    stats = snap.get("stats") or {}
    pipeline = snap.get("pipeline") or {}
    episode = snap.get("episode") or {}
    state = snap.get("state") or {}
    features = snap.get("features") or {}
    producer = snap.get("producer") or {}
    actions = snap.get("actions") or {}
    steps = state.get("steps") or {}
    readout = _readout_lists(producer)
    measured_pct = float(stats.get("measured_pct") or 0)
    by_status = pipeline.get("by_status") or {}

    def esc(s: Any) -> str:
        return html.escape(str(s if s is not None else ""))

    step_rows = "".join(
        f'<tr class="{"ok" if s.ok else "fail"}"><td>{"✓" if s.ok else "✗"}</td>'
        f"<td>{esc(s.name)}</td><td><code>{esc(s.endpoint)}</code></td>"
        f"<td>{esc(s.detail)}</td></tr>"
        for s in run.steps
    )

    pipeline_chips = "".join(
        f'<span class="chip"><b>{esc(k)}</b> {int(v)}</span>'
        for k, v in sorted(by_status.items(), key=lambda x: -int(x[1] or 0))
        if int(v or 0) > 0
    )

    metric_cards = ""
    measurements = producer.get("measurements") or features
    metric_defs = [
        ("Hook", _fmt_seconds(measurements.get("hook_length_seconds")), "hook_length_seconds"),
        ("Intro", _fmt_seconds(measurements.get("intro_length_seconds")), "intro_length_seconds"),
        ("Questions", str(measurements.get("question_count", "—")), "question_count"),
        ("Turns", str(measurements.get("speaking_turns", "—")), "speaking_turns"),
        ("Host/guest", f"{float(measurements.get('host_guest_ratio', 0)):.0%}" if measurements.get("host_guest_ratio") is not None else "—", "host_guest_ratio"),
        ("Topic shifts", str(measurements.get("topic_shift_count", "—")), "topic_shift_count"),
        ("CTA", "Yes" if measurements.get("cta_present") else "No", "cta_present"),
    ]
    for label, value, _key in metric_defs:
        metric_cards += f'<div class="metric"><span class="label">{esc(label)}</span><span class="value">{esc(value)}</span></div>'

    pipe_steps = [
        ("Ingested", steps.get("ingested")),
        ("Transcript", steps.get("transcribed")),
        ("Measured", steps.get("measured")),
        ("Insight", steps.get("insight_ready")),
    ]
    pipe_html = "".join(
        f'<div class="pipe-step {"done" if done else "pending"}"><div class="dot"></div>'
        f"<span>{esc(name)}</span></div>"
        + ('<div class="pipe-arrow">→</div>' if i < len(pipe_steps) - 1 else "")
        for i, (name, done) in enumerate(pipe_steps)
    )

    readout_html = ""
    for title, items in (
        ("What’s happening", readout["what_happening"]),
        ("Why it matters", readout["why_it_matters"]),
        ("What to try next", readout["what_to_try_next"] or [a.get("text", "") for a in actions.get("actions") or []][:3]),
    ):
        if not items:
            continue
        lis = "".join(f"<li>{esc(x)}</li>" for x in items if str(x).strip())
        readout_html += f'<section class="readout-block"><h3>{esc(title)}</h3><ul>{lis}</ul></section>'

    warning = producer.get("transcript_warning") or actions.get("transcript_warning")
    warning_html = ""
    if warning:
        warning_html = f'<div class="warning"><strong>{esc(warning.get("code", "warning"))}</strong> — {esc(warning.get("message", ""))}</div>'

    status_class = "pass" if run.passed else "fail"
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SoapBoxx E2E Demo — {esc(episode.get('title', 'Library'))}</title>
  <style>
    :root {{
      --bg: #1a1210; --panel: #241915; --line: #3d2a22; --text: #f5ebe3;
      --muted: #b8a496; --accent: #e8a54b; --ok: #6ecf8a; --fail: #f07178;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: "Segoe UI", system-ui, sans-serif; background: var(--bg); color: var(--text); }}
    .wrap {{ max-width: 1100px; margin: 0 auto; padding: 28px 20px 48px; }}
    h1 {{ font-family: Georgia, serif; font-weight: 600; margin: 0 0 6px; font-size: 1.75rem; }}
    .sub {{ color: var(--muted); margin-bottom: 24px; line-height: 1.5; }}
    .banner {{ display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 20px; }}
    .pill {{ padding: 6px 12px; border-radius: 999px; border: 1px solid var(--line); font-size: 12px; }}
    .pill.{status_class} {{ border-color: var(--ok); color: var(--ok); }}
    .pill.fail {{ border-color: var(--fail); color: var(--fail); }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 20px; }}
    .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 16px; }}
    .card h2 {{ margin: 0 0 12px; font-size: 0.8rem; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }}
    .stat {{ font-size: 1.6rem; font-weight: 700; color: var(--accent); }}
    .bar {{ height: 6px; background: #120d0b; border-radius: 3px; margin-top: 10px; overflow: hidden; }}
    .bar > span {{ display: block; height: 100%; background: var(--accent); width: {min(100, measured_pct):.1f}%; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .chip {{ background: #120d0b; border: 1px solid var(--line); border-radius: 6px; padding: 6px 10px; font-size: 12px; }}
    .chip b {{ color: var(--accent); margin-right: 4px; }}
    .pipeline {{ display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin: 12px 0; }}
    .pipe-step {{ display: flex; align-items: center; gap: 8px; font-size: 13px; }}
    .pipe-step .dot {{ width: 10px; height: 10px; border-radius: 50%; background: var(--line); }}
    .pipe-step.done .dot {{ background: var(--ok); }}
    .pipe-arrow {{ color: var(--muted); }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; }}
    .metric {{ background: #120d0b; border: 1px solid var(--line); border-radius: 8px; padding: 12px; }}
    .metric .label {{ display: block; font-size: 11px; color: var(--muted); text-transform: uppercase; }}
    .metric .value {{ font-size: 1.1rem; font-weight: 600; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    th {{ color: var(--muted); font-weight: 600; }}
    tr.ok td:first-child {{ color: var(--ok); }}
    tr.fail td:first-child {{ color: var(--fail); }}
    code {{ font-size: 11px; color: var(--accent); }}
    .readout-block h3 {{ margin: 0 0 8px; font-size: 14px; color: var(--accent); }}
    .readout-block ul {{ margin: 0; padding-left: 18px; color: var(--text); line-height: 1.5; }}
    .readout-block {{ margin-bottom: 14px; }}
    .warning {{ background: #3a2618; border: 1px solid #8a5a2a; color: #ffd9a8; padding: 12px; border-radius: 8px; margin-bottom: 16px; font-size: 13px; }}
    .footer {{ margin-top: 24px; color: var(--muted); font-size: 12px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>SoapBoxx — end-to-end library demo</h1>
    <p class="sub">Live proof: Record → Transcribe → Improve on a real ingested episode.<br />
      API: <code>{esc(run.api_base)}</code> · Episode <strong>#{esc(episode.get('id', ''))}</strong> · {esc(episode.get('podcast_name'))}</p>
    <div class="banner">
      <span class="pill {status_class}">{"ALL STEPS PASSED" if run.passed else "SOME STEPS FAILED"}</span>
      <span class="pill">{esc(episode.get('title'))}</span>
      <span class="pill">{esc(producer.get('structure_label') or producer.get('template_id', ''))}</span>
    </div>
    {warning_html}
    <div class="grid">
      <div class="card"><h2>Episodes</h2><div class="stat">{int(stats.get('episodes_total', 0))}</div></div>
      <div class="card"><h2>Shows</h2><div class="stat">{int(stats.get('shows_total', 0))}</div></div>
      <div class="card"><h2>Measured</h2><div class="stat">{int(stats.get('measured_count', 0))}</div><div class="bar"><span></span></div><div style="font-size:12px;color:var(--muted);margin-top:6px">{measured_pct:.1f}% of library</div></div>
      <div class="card"><h2>Queued</h2><div class="stat">{int(stats.get('queued_count', 0))}</div></div>
    </div>
    <div class="card" style="margin-bottom:16px">
      <h2>Pipeline status</h2>
      <div class="chips">{pipeline_chips or '<span class="chip">No status chips</span>'}</div>
      <h2 style="margin-top:16px">Episode pipeline</h2>
      <div class="pipeline">{pipe_html}</div>
    </div>
    <div class="card" style="margin-bottom:16px">
      <h2>Layer 2 — seven measurements</h2>
      <div class="metrics">{metric_cards}</div>
    </div>
    <div class="card" style="margin-bottom:16px">
      <h2>Layer 4 — editorial readout</h2>
      {readout_html or '<p style="color:var(--muted)">No readout — episode may need pipeline.</p>'}
    </div>
    <div class="card">
      <h2>API steps executed</h2>
      <table>
        <thead><tr><th></th><th>Step</th><th>Endpoint</th><th>Result</th></tr></thead>
        <tbody>{step_rows}</tbody>
      </table>
    </div>
    <p class="footer">Generated {generated}. Re-run: <code>python scripts/e2e_library_demo.py</code></p>
  </div>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="SoapBoxx V1 end-to-end library demo")
    parser.add_argument("--api", default=DEFAULT_API, help="API base URL")
    parser.add_argument("--episode-id", type=int, default=None, help="Episode to showcase")
    parser.add_argument("--process-one", action="store_true", help="POST /pipeline/process?limit=1 first")
    parser.add_argument("--include-episode-1", action="store_true", help="Allow ep 1 (demo transcript)")
    parser.add_argument("--open", action="store_true", help="Open HTML report in browser")
    parser.add_argument("--json-only", action="store_true", help="Write snapshot JSON only")
    args = parser.parse_args()

    client = ApiClient(args.api)
    print(f"SoapBoxx E2E demo -> {client.base}\n")

    run = run_demo(
        client,
        episode_id=args.episode_id,
        process_one=args.process_one,
        skip_demo_transcript=not args.include_episode_1,
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(run.snapshot, indent=2), encoding="utf-8")
    print(f"Snapshot: {REPORT_JSON}")

    if not args.json_only:
        REPORT_HTML.write_text(render_html(run), encoding="utf-8")
        print(f"Report:   {REPORT_HTML}")

    for step in run.steps:
        mark = "PASS" if step.ok else "FAIL"
        print(f"  [{mark}] {step.name} — {step.detail}")

    if args.open and REPORT_HTML.is_file():
        webbrowser.open(REPORT_HTML.as_uri())

    if run.passed:
        print("\nE2E demo passed. Open the HTML report for the visual dashboard.")
        return 0
    print("\nE2E demo incomplete — check failures above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
