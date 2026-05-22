#!/usr/bin/env python3
"""
Producer smoke test (automated).

Runs Coach-tab workflow: metadata → paste → queue → batch → verify pull.
Exit 0 = pass, 1 = fail.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TRANSCRIPT = (
    "Host: Welcome back. Our guest built a seven figure business in eighteen months.\n"
    "Guest: The hard part was not revenue. It was hiring before we had a repeatable sales motion.\n"
    "Host: If you started over today, what would you change first?\n"
    "Guest: I would document one playbook before adding headcount.\n"
    "Host: How do you measure progress week to week?\n"
    "Guest: One leading indicator per team. Nothing else until it stabilizes.\n"
) * 10

FAILURES: list[str] = []
CHECKS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        CHECKS.append(f"PASS  {name}" + (f" — {detail}" if detail else ""))
    else:
        FAILURES.append(f"{name}: {detail or 'failed'}")


def main() -> int:
    print("=== SoapBoxx producer smoke test ===\n")

    # 1) UI widgets import
    try:
        from frontend.reverb_tab import ReverbTab
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        tab = ReverbTab()
        tab.init_ui()
        tab._ui_initialized = True
        check(
            "Coach tab UI loads",
            all(
                hasattr(tab, x)
                for x in (
                    "transcript_input",
                    "show_title_input",
                    "author_input",
                    "library_tree",
                    "add_to_queue_btn",
                    "run_batch_btn",
                    "generate_coach_btn",
                )
            ),
        )
    except Exception as e:
        check("Coach tab UI loads", False, str(e))

    # 2) Producer workflow (backend + same calls as UI)
    try:
        from backend.library import (
            enqueue_episode,
            get_library_tree,
            list_pending_queue,
            run_weekly_batch,
        )
        from backend.storage import export_library_snapshot, pull_episode

        ref = "producer-smoke-" + TRANSCRIPT[:48]
        r = enqueue_episode(
            source_type="paste",
            source_ref=TRANSCRIPT + ref,
            category="business",
            show_title="Producer Smoke Show",
            author="Jordan Lee",
            episode_title="Ep 7 — Hiring before playbook",
        )
        check("Add to weekly queue", not r.get("duplicate") or r.get("queue_id"), str(r))

        pending = list_pending_queue()
        check("Queue has pending", len(pending) >= 1, f"{len(pending)} item(s)")

        summary = run_weekly_batch(limit=5)
        check(
            "Weekly batch",
            summary.get("processed", 0) >= 1 and summary.get("failed", 0) == 0,
            f"processed={summary.get('processed')} failed={summary.get('failed')}",
        )

        tree = get_library_tree()
        check("Library tree", len(tree) >= 1, f"{len(tree)} categor(ies)")

        snap = export_library_snapshot()
        check(
            "Episodes stored with metrics",
            snap["counts"]["episodes"] >= 1 and snap["counts"]["with_metrics"] >= 1,
            json.dumps(snap["counts"]),
        )

        if tree:
            ep_id = tree[0]["authors"][0]["shows"][0]["episodes"][0]["id"]
            pulled = pull_episode(int(ep_id))
            check(
                "Pull episode (producer archive)",
                pulled
                and pulled.get("transcript")
                and pulled.get("measurements"),
                f"episode_id={ep_id}",
            )
    except Exception as e:
        check("Producer workflow", False, str(e))

    # 3) Intelligence / measurements (no coach required for producer structure test)
    try:
        from backend.intelligence_v1.pipeline import process_transcript_only

        report = process_transcript_only(
            TRANSCRIPT, "business", title="Smoke intelligence"
        )
        check(
            "Structure metrics generated",
            bool(report.get("episode_id")) and "markdown" in report,
            f"episode_id={report.get('episode_id')}",
        )
    except Exception as e:
        check("Structure metrics generated", False, str(e))

    # 4) Main window
    try:
        from frontend.main_window import MainWindow

        app = QApplication.instance() or QApplication([])
        win = MainWindow()
        coach = win.ensure_tab_created("Coach")
        check("Main window + Coach tab", coach is not None)
    except Exception as e:
        check("Main window + Coach tab", False, str(e))

    print("\n".join(CHECKS))
    if FAILURES:
        print("\n--- FAILURES ---")
        for f in FAILURES:
            print(f"FAIL  {f}")
        print(f"\n{len(FAILURES)} failed, {len(CHECKS) - len(FAILURES)} passed")
        return 1
    print(f"\nAll {len(CHECKS)} checks passed.")
    print("\nOpen UI: python -m frontend.main_window  →  Coach tab  →  Insights library")
    return 0


if __name__ == "__main__":
    sys.exit(main())
