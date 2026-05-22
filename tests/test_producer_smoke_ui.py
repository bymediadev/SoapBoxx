"""
Producer smoke test — Coach tab workflow without manual clicking.

Simulates: set show metadata → paste transcript → queue → batch → library visible.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication, QTreeWidget  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_producer_coach_tab_library_workflow(qapp, qtbot, tmp_path, monkeypatch):
    """Producer path: paste episode → shelf metadata → weekly queue → batch → tree."""
    db_path = tmp_path / "producer_smoke.db"
    monkeypatch.setenv("SOAPBOXX_INTELLIGENCE_DB", str(db_path))

    from frontend.reverb_tab import ReverbTab

    tab = ReverbTab()
    qtbot.addWidget(tab)
    tab.show()
    qtbot.waitExposed(tab, timeout=3000)
    tab.init_ui()
    tab._ui_initialized = True

    assert hasattr(tab, "show_title_input")
    assert hasattr(tab, "author_input")
    assert hasattr(tab, "library_tree")
    assert hasattr(tab, "add_to_queue_btn")
    assert hasattr(tab, "run_batch_btn")

    transcript = (
        "Host: Welcome to the show. Today we talk with a founder about growth.\n"
        "Guest: Thanks for having me. We scaled too fast in year two.\n"
        "Host: What would you do differently?\n"
        "Guest: Hire slower and measure one metric per week.\n"
    ) * 12

    qtbot.keyClicks(tab.show_title_input, "Producer Test Show")
    qtbot.keyClicks(tab.author_input, "Alex Host")
    qtbot.keyClicks(tab.episode_title_input, "Ep 42 - Growth mistakes")
    tab.transcript_input.setPlainText(transcript)

    qtbot.mouseClick(tab.add_to_queue_btn, Qt.MouseButton.LeftButton)
    qtbot.wait(200)

    from backend.library import list_pending_queue

    pending = list_pending_queue()
    assert len(pending) >= 1

    qtbot.mouseClick(tab.run_batch_btn, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: tab.run_batch_btn.isEnabled(), timeout=120000)

    tab.refresh_library_tree()
    qtbot.wait(300)

    tree: QTreeWidget = tab.library_tree
    assert tree.topLevelItemCount() >= 1

    from backend.storage import export_library_snapshot

    snap = export_library_snapshot()
    assert snap["counts"]["episodes"] >= 1
    assert snap["counts"]["with_metrics"] >= 1


def test_main_window_coach_tab_loads(qapp, qtbot):
    from frontend.main_window import MainWindow

    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win, timeout=5000)

    coach = win.ensure_tab_created("Coach")
    assert coach is not None
    assert win.tab_widget.count() >= 1

    names = [win.tab_widget.tabText(i) for i in range(win.tab_widget.count())]
    assert "Coach" in names or "Settings" in names
