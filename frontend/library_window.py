"""
Offline Insights Library shell — same UI as Lovable / bundled ``/ui/``.

Embeds the Insights Library dashboard (``/ui/``) when PyQt WebEngine is available.
"""

from __future__ import annotations

import sys
import webbrowser

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    from .local_api_server import (
        api_base_url,
        configured_library_api_base,
        library_ui_url,
        local_library_ready,
        remote_fallback_enabled,
        remote_fallback_ui_url,
        should_start_local_api,
        start_local_api,
        wait_for_api,
    )
except ImportError:
    from local_api_server import (  # type: ignore
        api_base_url,
        configured_library_api_base,
        library_ui_url,
        local_library_ready,
        remote_fallback_enabled,
        remote_fallback_ui_url,
        should_start_local_api,
        start_local_api,
        wait_for_api,
    )

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    _HAS_WEBENGINE = True
except ImportError:
    QWebEngineView = None  # type: ignore[misc, assignment]
    _HAS_WEBENGINE = False


_LIBRARY_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1a1816;
    color: #ebe4d6;
    font-family: "Inter", "Segoe UI", sans-serif;
}
QLabel#title {
    font-family: "Cormorant Garamond", "Georgia", serif;
    font-size: 28px;
    font-weight: 600;
}
QLabel#tagline {
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 11px;
    letter-spacing: 0.12em;
    color: #9a9080;
}
QLabel#status {
    color: #c4b8a8;
    font-size: 13px;
}
QPushButton {
    background-color: #3d3428;
    color: #f0c878;
    border: 1px solid #5c4f3a;
    border-radius: 6px;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #4a4032;
}
"""


class LibraryOfflineWindow(QMainWindow):
    """Native shell for the V1 Insights Library (Lovable parity via ``/ui/``)."""

    def __init__(self) -> None:
        super().__init__()
        self._web: QWebEngineView | None = None
        self.setWindowTitle("SoapBoxx — Insights Library")
        self.setMinimumSize(1280, 800)
        self.resize(1440, 900)
        self.setStyleSheet(_LIBRARY_STYLESHEET)

        root = QWidget()
        self.setCentralWidget(root)
        self._layout = QVBoxLayout(root)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._status = QLabel("Starting Insights Library…")
        self._status.setObjectName("status")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setContentsMargins(24, 48, 24, 48)
        self._layout.addWidget(self._status, 1)

        self._boot_api()

    def _boot_api(self) -> None:
        remote = configured_library_api_base()
        if remote:
            ui_url = library_ui_url()
            if wait_for_api(remote, timeout=15.0):
                self._open_ui(ui_url)
                return
            if remote_fallback_enabled():
                self._open_ui(
                    remote_fallback_ui_url(),
                    note="Configured API unreachable — using cloud library",
                )
                return
            self._show_boot_failure(f"Could not reach library API at {remote}")
            return

        start_local_api(wait=True, timeout=45.0)
        if local_library_ready():
            self._open_ui(library_ui_url())
            return

        if remote_fallback_enabled():
            self._open_ui(
                remote_fallback_ui_url(),
                note="Local library unavailable — using cloud library (same as Lovable)",
            )
            return

        self._show_boot_failure(
            "Local API is running but the library database is not ready.\n"
            "Start Postgres (scripts/setup_local.ps1 -V1Infra) or set "
            "SOAPBOXX_LIBRARY_API_URL to your Railway API."
        )

    def _open_ui(self, ui_url: str, *, note: str = "") -> None:
        self._status.hide()
        if note:
            banner = QLabel(note)
            banner.setObjectName("tagline")
            banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
            banner.setContentsMargins(12, 8, 12, 8)
            self._layout.addWidget(banner)

        if _HAS_WEBENGINE and QWebEngineView is not None:
            self._web = QWebEngineView()
            self._web.setUrl(QUrl(ui_url))
            self._layout.addWidget(self._web, 1)
            return

        webbrowser.open(ui_url)
        self._show_browser_fallback(ui_url)

    def _show_browser_fallback(self, ui_url: str) -> None:
        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.setSpacing(12)

        title = QLabel("SoapBoxx")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(title)

        tagline = QLabel("INSIGHTS LIBRARY")
        tagline.setObjectName("tagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(tagline)

        hint = QLabel(
            "The library UI opened in your browser.\n"
            "Install PyQt6-WebEngine for an embedded window:\n"
            "pip install PyQt6-WebEngine"
        )
        hint.setObjectName("status")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        panel_layout.addWidget(hint)

        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        open_btn = QPushButton("Open library again")
        open_btn.clicked.connect(lambda: webbrowser.open(ui_url))
        row.addWidget(open_btn)
        panel_layout.addLayout(row)

        api_label = QLabel(f"Library: {ui_url}")
        api_label.setObjectName("tagline")
        api_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        panel_layout.addWidget(api_label)

        self._layout.addWidget(panel, 1)

    def _show_boot_failure(self, detail: str = "") -> None:
        self._status.setText(
            detail
            or (
                "Could not start the Insights Library.\n\n"
                f"Expected local API: {api_base_url()}/health"
            )
        )
        QMessageBox.warning(
            self,
            "SoapBoxx Offline",
            detail
            or (
                "Local library failed to start.\n\n"
                "Option A — local Postgres:\n"
                "  .\\scripts\\setup_local.ps1 -ApiOnly -V1Infra\n\n"
                "Option B — cloud library (same as Lovable):\n"
                "  set SOAPBOXX_LIBRARY_API_URL=https://soapboxx-production.up.railway.app"
            ),
        )

def run_library_offline_app() -> None:
    """Entry point: Lovable-matching ``/ui/`` shell."""
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("SoapBoxx")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("SoapBoxx")

    window = LibraryOfflineWindow()
    window.show()
    sys.exit(app.exec())

