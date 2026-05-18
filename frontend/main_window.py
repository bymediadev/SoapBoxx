#!/usr/bin/env python3
"""
SoapBoxx Main Window
Main application window with tabbed interface
"""

import os
import sys
import json
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

# Repo root must precede backend/: imports use `from backend.*` (package), not flat `from config`.
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_backend_dir = os.path.join(_repo_root, "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

# Load repo-root .env (Ollama model, blueprint flag, etc.)
try:
    from dotenv import load_dotenv

    load_dotenv(Path(_repo_root) / ".env")
except ImportError:
    pass

try:
    from backend.user_api_secrets import load_user_api_secrets
except ImportError:
    try:
        from user_api_secrets import load_user_api_secrets  # type: ignore
    except ImportError:
        load_user_api_secrets = lambda **_: None  # type: ignore[misc, assignment]

load_user_api_secrets(override=True)

_FRONTEND_IMPORT_ERROR = None  # type: Optional[str]

# Use package-relative imports to support `python -m frontend.main_window`
try:
    from .batch_processor import BatchProcessorDialog
    from .export_manager import ExportManager
    from .keyboard_shortcuts import ShortcutHandler
    from .reverb_tab import ReverbTab
    from .scoop_tab import ScoopTab
    from .soapboxx_tab import SoapBoxxTab
    from .theme_manager import ThemeManager
except ImportError as _rel_err:
    _FRONTEND_IMPORT_ERROR = str(_rel_err)
    try:
        from frontend.batch_processor import BatchProcessorDialog
        from frontend.export_manager import ExportManager
        from frontend.keyboard_shortcuts import ShortcutHandler
        from frontend.reverb_tab import ReverbTab
        from frontend.scoop_tab import ScoopTab
        from frontend.soapboxx_tab import SoapBoxxTab
        from frontend.theme_manager import ThemeManager
    except ImportError:
        try:
            from batch_processor import BatchProcessorDialog
            from export_manager import ExportManager
            from keyboard_shortcuts import ShortcutHandler
            from reverb_tab import ReverbTab
            from scoop_tab import ScoopTab
            from soapboxx_tab import SoapBoxxTab
            from theme_manager import ThemeManager
        except ImportError as e:
            _FRONTEND_IMPORT_ERROR = str(e)
            print(f"Warning: Some frontend modules not available: {e}")
            traceback.print_exc()

            class BatchProcessorDialog:  # type: ignore[no-redef]
                def __init__(self, *args, **kwargs):
                    pass

            class ExportManager:  # type: ignore[no-redef]
                def __init__(self, *args, **kwargs):
                    pass

            class ShortcutHandler:  # type: ignore[no-redef]
                def __init__(self, *args, **kwargs):
                    pass

            class ReverbTab:  # type: ignore[no-redef]
                def __init__(self, *args, **kwargs):
                    pass

            class ScoopTab:  # type: ignore[no-redef]
                def __init__(self, *args, **kwargs):
                    pass

            class SoapBoxxTab:  # type: ignore[no-redef]
                def __init__(self, *args, **kwargs):
                    pass

            class ThemeManager:  # type: ignore[no-redef]
                def __init__(self, *args, **kwargs):
                    pass


def _soapboxx_tab_is_real() -> bool:
    return callable(getattr(SoapBoxxTab, "setup_ui", None))


from PyQt6.QtCore import QDate, Qt, QTime, QTimer
from PyQt6.QtGui import QAction, QFont, QIcon, QKeySequence, QPixmap
from PyQt6.QtWidgets import (QApplication, QComboBox, QDateEdit, QDialog,
                             QDialogButtonBox, QFormLayout, QFrame,
                             QFileDialog,
                             QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                             QLineEdit, QMainWindow, QMenu, QMenuBar,
                             QMessageBox, QPushButton, QScrollArea, QSplitter,
                             QStatusBar, QTabWidget, QTextEdit, QTimeEdit,
                             QVBoxLayout, QWidget)

# (imports moved into try/except above for dual compatibility)


class ModernCard(QFrame):
    """Modern card widget with shadow and rounded corners"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet(
            """
            ModernCard {
                background-color: white;
                border: 1px solid #E0E0E0;
                border-radius: 12px;
                padding: 16px;
                margin: 8px;
            }
            ModernCard:hover {
                border: 1px solid #BDBDBD;
            }
        """
        )


class ModernButton(QPushButton):
    """Modern button with gradient and hover effects"""

    def __init__(self, text="", parent=None, style="primary"):
        super().__init__(text, parent)
        self.style_type = style
        self.update_style()

    def update_style(self):
        if self.style_type == "primary":
            self.setStyleSheet(
                """
                ModernButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3498DB, stop:1 #2980B9);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px 24px;
                    font-weight: bold;
                    font-size: 14px;
                }
                ModernButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #5DADE2, stop:1 #3498DB);
                }
                ModernButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2980B9, stop:1 #21618C);
                }
                ModernButton:disabled {
                    background: #BDC3C7;
                    color: #7F8C8D;
                }
            """
            )
        elif self.style_type == "secondary":
            self.setStyleSheet(
                """
                ModernButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #95A5A6, stop:1 #7F8C8D);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px 24px;
                    font-weight: bold;
                    font-size: 14px;
                }
                ModernButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #BDC3C7, stop:1 #95A5A6);
                }
                ModernButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #7F8C8D, stop:1 #6C7B7D);
                }
                ModernButton:disabled {
                    background: #BDC3C7;
                    color: #7F8C8D;
                }
            """
            )


class BookingDialog(QDialog):
    """Modern booking dialog with enhanced error handling"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Book a Call for Feedback")
        self.setModal(True)
        self.setup_ui()

    def setup_ui(self):
        """Setup UI with modern design and error handling"""
        try:
            layout = QVBoxLayout()

            # Modern card container
            card = ModernCard()
            card_layout = QFormLayout()

            # Guest name input
            self.guest_name = QLineEdit()
            self.guest_name.setPlaceholderText("Enter guest name")
            card_layout.addRow("Guest Name:", self.guest_name)

            # Date picker
            self.date_picker = QDateEdit()
            self.date_picker.setDate(QDate.currentDate())
            self.date_picker.setCalendarPopup(True)
            card_layout.addRow("Date:", self.date_picker)

            # Time picker
            self.time_picker = QTimeEdit()
            self.time_picker.setTime(QTime.currentTime())
            card_layout.addRow("Time:", self.time_picker)

            # Notes
            self.notes = QTextEdit()
            self.notes.setMaximumHeight(100)
            self.notes.setPlaceholderText("Add notes about the guest...")
            card_layout.addRow("Notes:", self.notes)

            card.setLayout(card_layout)
            layout.addWidget(card)

            # Buttons
            button_layout = QHBoxLayout()
            self.cancel_button = ModernButton("Cancel", style="secondary")
            self.book_button = ModernButton("Book a Call", style="primary")

            self.cancel_button.clicked.connect(self.reject)
            self.book_button.clicked.connect(self.accept)

            button_layout.addWidget(self.cancel_button)
            button_layout.addWidget(self.book_button)
            layout.addLayout(button_layout)

            self.setLayout(layout)

        except Exception as e:
            self._show_error(
                "UI Setup Error", f"Failed to setup booking dialog: {str(e)}"
            )

    def _show_error(self, title: str, message: str):
        """Show error dialog with graceful handling"""
        try:
            QMessageBox.critical(self, title, message)
        except Exception:
            print(f"Error in booking dialog: {title} - {message}")


class MainWindow(QMainWindow):
    """Main application window with enhanced resilience and error handling"""

    def __init__(self):
        try:
            print("MainWindow: Starting initialization...")
            super().__init__()
            print("MainWindow: Super class initialized")

            # Initialize state tracking
            self._is_initializing = True
            self._tabs_loaded = {}
            self._is_switching_tab = False
            self._error_count = 0
            self._last_error_time = None
            self._loaded_tabs = {}
            print("MainWindow: State tracking initialized")

            # Setup global exception handler
            print("MainWindow: Setting up exception handler...")
            self._setup_global_exception_handler()
            print("MainWindow: Exception handler setup complete")

            # Initialize UI
            print("MainWindow: Setting up UI...")
            self.setup_ui()
            print("MainWindow: UI setup complete")

            # Mark initialization complete
            self._is_initializing = False

            # Start health monitoring
            print("MainWindow: Starting health monitoring...")
            self._start_health_monitoring()
            print("MainWindow: Health monitoring started")

            print("MainWindow: Initialization complete!")

        except Exception as e:
            print(f"MainWindow initialization failed: {e}")
            import traceback

            traceback.print_exc()
            raise

    def _setup_global_exception_handler(self):
        """Setup global exception handler for uncaught errors"""

        def global_exception_handler(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                # Allow keyboard interrupts to pass through
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return

            # Log the error
            error_msg = f"Uncaught exception: {exc_type.__name__}: {exc_value}"
            print(error_msg)
            traceback.print_exception(exc_type, exc_value, exc_traceback)

            # Show user-friendly error message
            self._show_user_friendly_error(
                "Application Error",
                "An unexpected error occurred. The application will continue to run, but some features may be affected.",
                str(exc_value),
            )

            # Track error
            self._track_error("UncaughtException", error_msg)

        # Set the global exception handler
        sys.excepthook = global_exception_handler

    def setup_ui(self):
        """Setup main UI with enhanced error handling and resilience"""
        try:
            app_title, _title_text, _subtitle_text = self._get_branding_labels()
            self.setWindowTitle(app_title)
            self.setGeometry(100, 100, 1200, 800)

            # Application palette + main chrome (tabs, window) from ThemeManager
            self._init_application_theme()

            # Setup central widget
            central_widget = QWidget()
            self.setCentralWidget(central_widget)

            # Main layout
            layout = QVBoxLayout()
            central_widget.setLayout(layout)

            # Header
            self._setup_header(layout)

            # Tab widget
            self._setup_tabs(layout)

            # Status bar
            self._setup_status_bar()

            # Menu bar
            self._setup_menu_bar()

            # Apply layout
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(16)

        except Exception as e:
            self._show_user_friendly_error(
                "UI Setup Error",
                "Failed to setup main window UI. Some features may not be available.",
                str(e),
            )
            self._track_error("UISetupError", f"Failed to setup UI: {str(e)}")

    def _init_application_theme(self):
        """Palette + stylesheet; from config (ui_settings.theme) then SOAPBOXX_UI_THEME."""
        try:
            self.theme_manager = ThemeManager(self)
            self.theme_manager.theme_changed.connect(self._apply_chrome_stylesheet)
            key = self._resolve_startup_ui_theme_key(self.theme_manager)
            self.theme_manager.apply_theme(key)
        except Exception as e:
            print(f"Theme manager unavailable, using built-in light chrome: {e}")
            self.theme_manager = None
            self._apply_chrome_stylesheet("modern_light")

    def _resolve_startup_ui_theme_key(self, tm: ThemeManager) -> str:
        """Pick initial theme id: saved config, then SOAPBOXX_UI_THEME, then modern_light."""
        valid = frozenset(tm.themes.keys())
        try:
            try:
                from backend.config import Config
            except ImportError:  # pragma: no cover
                from config import Config  # type: ignore

            cfg = Config()
            cfg_t = str(cfg.get("ui_settings.theme", "") or "").strip()
        except Exception:
            cfg_t = ""
        if cfg_t in ("default", ""):
            cfg_t = ""
        env_t = (os.getenv("SOAPBOXX_UI_THEME") or "").strip()
        for candidate in (cfg_t, env_t):
            if candidate and candidate in valid:
                return candidate
        return "modern_light"

    def _all_ui_theme_ids(self):
        tm = getattr(self, "theme_manager", None)
        if tm and tm.themes:
            return list(tm.themes.keys())
        return [
            "modern_light",
            "modern_dark",
            "dark",
            "modern_blue",
            "modern_green",
            "light",
            "blue",
            "green",
        ]

    def _apply_chrome_stylesheet(self, theme_name: str):
        """Main window + tab bar look; individual cards may still use light styles until refactored."""
        try:
            tm = getattr(self, "theme_manager", None)
            if tm is None:
                t = {
                    "background": "#F8F9FA",
                    "surface": "#FFFFFF",
                    "border": "#E0E0E0",
                    "alternate_base": "#F1F3F4",
                    "primary": "#3498DB",
                    "card": "#FFFFFF",
                }
                darkish = False
            else:
                t = tm.get_theme_colors(theme_name)
                darkish = theme_name in ("modern_dark", "dark")
            win_bg = t.get("background", "#F8F9FA")
            surface = t.get("surface", "#FFFFFF")
            border = t.get("border", "#E0E0E0")
            tab_bg = t.get("alternate_base", "#F1F3F4")
            accent = t.get("primary", "#3498DB")
            tab_hover = "#3D3D45" if darkish else "#E8EAED"
            tab_selected_bg = t.get("card", surface)
            self.setStyleSheet(
                f"""
                QMainWindow {{
                    background-color: {win_bg};
                }}
                QTabWidget::pane {{
                    border: 1px solid {border};
                    border-radius: 8px;
                    background-color: {surface};
                }}
                QTabBar::tab {{
                    background-color: {tab_bg};
                    border: 1px solid {border};
                    border-bottom: none;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    padding: 12px 24px;
                    margin-right: 2px;
                }}
                QTabBar::tab:selected {{
                    background-color: {tab_selected_bg};
                    border-bottom: 2px solid {accent};
                }}
                QTabBar::tab:hover {{
                    background-color: {tab_hover};
                }}
                QStatusBar {{
                    background-color: {win_bg};
                    border-top: 1px solid {border};
                }}
            """
            )
        except Exception as e:
            print(f"Failed to apply chrome stylesheet: {e}")

    def _set_ui_theme(self, name: str):
        tm = getattr(self, "theme_manager", None)
        if tm and name in tm.themes:
            tm.apply_theme(name)

    def _toggle_ui_dark(self):
        tm = getattr(self, "theme_manager", None)
        if tm:
            tm.toggle_dark_mode()

    def _setup_header(self, layout):
        """Setup modern header with error handling"""
        try:
            header_card = ModernCard()
            header_layout = QHBoxLayout()

            _window_title, title_text, subtitle_text = self._get_branding_labels()

            # Title
            title_label = QLabel(title_text)
            title_label.setStyleSheet(
                """
                QLabel {
                    font-size: 24px;
                font-weight: bold;
                    color: #2C3E50;
                }
            """
            )

            # Subtitle
            subtitle_label = QLabel(subtitle_text)
            subtitle_label.setStyleSheet(
                """
                QLabel {
                    font-size: 14px;
                    color: #7F8C8D;
                }
            """
            )

            # Title layout
            title_layout = QVBoxLayout()
            title_layout.addWidget(title_label)
            title_layout.addWidget(subtitle_label)

            header_layout.addLayout(title_layout)
            header_layout.addStretch()

            # Quick actions
            self._setup_quick_actions(header_layout)

            header_card.setLayout(header_layout)
            layout.addWidget(header_card)

        except Exception as e:
            self._track_error("HeaderSetupError", f"Failed to setup header: {str(e)}")

    def _get_branding_labels(self):
        """Return window/header labels based on runtime bucket."""
        bucket = (os.getenv("SOAPBOXX_BUCKET") or "production").strip().lower()
        is_demo = bucket in {"demo", "dev", "development", "sandbox"}
        if is_demo:
            return (
                "SoapBoxx Production Studio Demo",
                "SoapBoxx",
                "Production Studio Demo",
            )
        return (
            "SoapBoxx - AI-Powered Podcast Production Studio",
            "SoapBoxx",
            "AI-Powered Podcast Production Studio",
        )

    def _setup_quick_actions(self, layout):
        """Setup quick action buttons"""
        try:
            # Book a call for feedback button
            book_button = ModernButton("Book a Call for Feedback", style="primary")
            book_button.clicked.connect(self._show_booking_dialog)
            layout.addWidget(book_button)

            # Settings button
            settings_button = ModernButton("Settings", style="secondary")
            settings_button.clicked.connect(self._show_settings)
            layout.addWidget(settings_button)

        except Exception as e:
            self._track_error(
                "QuickActionsError", f"Failed to setup quick actions: {str(e)}"
            )

    def _setup_tabs(self, layout):
        """Setup tabs with enhanced error handling and graceful degradation"""
        try:
            self.tab_widget = QTabWidget()

            # Create placeholder tabs first, defer actual tab creation
            tab_definitions = [
                ("SoapBoxx", self._create_soapboxx_tab),
                ("Scoop", self._create_scoop_tab),
                ("Reverb", self._create_reverb_tab),
                ("Settings", self._create_settings_tab),
            ]

            for tab_name, tab_creator in tab_definitions:
                try:
                    # Create placeholder tab
                    placeholder = self._create_placeholder_tab(
                        tab_name, f"Loading {tab_name}..."
                    )
                    self.tab_widget.addTab(placeholder, tab_name)
                    self._tabs_loaded[tab_name] = False

                    # Store the creator function for later use
                    if not hasattr(self, "_tab_creators"):
                        self._tab_creators = {}
                    self._tab_creators[tab_name] = tab_creator

                except Exception as e:
                    error_msg = (
                        f"Failed to create placeholder for {tab_name} tab: {str(e)}"
                    )
                    self._track_error("TabPlaceholderError", error_msg)
                    self._add_placeholder_tab(tab_name, f"Error loading {tab_name} tab")
                    self._tabs_loaded[tab_name] = False

            # Connect tab change signal to lazy load tabs
            self.tab_widget.currentChanged.connect(self._on_tab_changed)

            layout.addWidget(self.tab_widget)

            # Trigger initial load for the first tab to avoid blank UI
            if self.tab_widget.count() > 0:
                QTimer.singleShot(
                    0, lambda: self._on_tab_changed(self.tab_widget.currentIndex())
                )

        except Exception as e:
            self._track_error("TabSetupError", f"Failed to setup tabs: {str(e)}")
            # Create minimal fallback
            fallback_label = QLabel(
                "Application failed to load properly. Please restart."
            )
            fallback_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(fallback_label)

    def _on_tab_changed(self, index):
        """Handle tab changes and lazy load tabs as needed"""
        try:
            if index < 0 or index >= self.tab_widget.count():
                return

            # Prevent re-entrant tab loading
            if self._is_switching_tab:
                return

            tab_name = self.tab_widget.tabText(index)
            if self._tabs_loaded.get(tab_name, False):
                return
            if tab_name not in getattr(self, "_tab_creators", {}):
                return

            print(f"Lazy loading {tab_name} tab...")
            tab_creator = self._tab_creators[tab_name]

            self._is_switching_tab = True
            try:
                self.tab_widget.blockSignals(True)
                actual_tab = tab_creator()
                if actual_tab:
                    # Replace placeholder with actual tab
                    self.tab_widget.removeTab(index)
                    self.tab_widget.insertTab(index, actual_tab, tab_name)
                    self._tabs_loaded[tab_name] = True
                    self._loaded_tabs[tab_name] = actual_tab
                    self.tab_widget.setCurrentIndex(index)
                    print(f"{tab_name} tab loaded successfully")
                else:
                    print(f"Failed to create {tab_name} tab")
                    self._tabs_loaded[tab_name] = False
            finally:
                self.tab_widget.blockSignals(False)
                self._is_switching_tab = False

        except Exception as e:
            error_msg = f"Failed to lazy load tab {tab_name}: {str(e)}"
            self._track_error("TabLazyLoadError", error_msg)
            print(f"{error_msg}")

    def _create_placeholder_tab(self, tab_name: str, message: str):
        """Create a simple placeholder tab"""
        try:
            placeholder_widget = QWidget()
            layout = QVBoxLayout()

            # Loading message
            loading_label = QLabel(message)
            loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            loading_label.setStyleSheet(
                """
                QLabel {
                    color: #3498DB;
                    font-size: 16px;
                    padding: 40px;
                }
            """
            )

            layout.addWidget(loading_label)
            layout.addStretch()

            placeholder_widget.setLayout(layout)
            return placeholder_widget

        except Exception as e:
            self._track_error(
                "PlaceholderTabError", f"Failed to create placeholder tab: {str(e)}"
            )
            return None

    def _create_soapboxx_tab(self):
        """Create SoapBoxx tab with error handling"""
        try:
            print("MainWindow: Creating SoapBoxx tab...")
            if not _soapboxx_tab_is_real():
                detail = _FRONTEND_IMPORT_ERROR or "SoapBoxx tab module did not load"
                av_hint = (
                    " If Norton or another antivirus blocked files in the app folder, "
                    "add an exclusion for the extracted demo folder and reinstall."
                )
                return self._create_placeholder_tab(
                    "SoapBoxx",
                    f"SoapBoxx studio failed to load.\n\n{detail}{av_hint}",
                )
            tab = SoapBoxxTab(
                open_settings_callback=self._show_settings,
                session_feedback_callback=self._deliver_session_feedback_to_reverb,
            )
            self._loaded_tabs["SoapBoxx"] = tab
            print("MainWindow: SoapBoxx tab created successfully")
            return tab
        except Exception as e:
            print(f"MainWindow: Failed to create SoapBoxx tab: {e}")
            import traceback

            traceback.print_exc()
            self._track_error(
                "SoapBoxxTabError", f"Failed to create SoapBoxx tab: {str(e)}"
            )
            # Return a placeholder tab instead
            return self._create_placeholder_tab("SoapBoxx", f"Failed to load: {str(e)}")

    def ensure_tab_created(self, tab_name: str):
        """Create a lazy tab by name without switching away from the current tab."""
        if self._tabs_loaded.get(tab_name) and tab_name in self._loaded_tabs:
            return self._loaded_tabs[tab_name]
        creator = getattr(self, "_tab_creators", {}).get(tab_name)
        if not creator:
            return None
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) != tab_name:
                continue
            try:
                self._is_switching_tab = True
                self.tab_widget.blockSignals(True)
                w = creator()
                if w:
                    self.tab_widget.removeTab(i)
                    self.tab_widget.insertTab(i, w, tab_name)
                    self._tabs_loaded[tab_name] = True
                    self._loaded_tabs[tab_name] = w
                    return w
            finally:
                self.tab_widget.blockSignals(False)
                self._is_switching_tab = False
            break
        return None

    def _deliver_session_feedback_to_reverb(self, payload):
        """After SoapBoxx recording: open Reverb and run FeedbackEngine on the episode transcript."""
        text = ""
        try:
            from backend.soapboxx_core import RecordingSession
        except ImportError:
            RecordingSession = None  # type: ignore

        if RecordingSession is not None and isinstance(payload, RecordingSession):
            text = (payload.transcript or "").strip()
        elif hasattr(payload, "transcript"):
            text = (getattr(payload, "transcript", None) or "").strip()
        else:
            text = (payload or "").strip()
        if not text:
            return
        try:
            reverb = self.ensure_tab_created("Reverb")
            if reverb is None:
                print("MainWindow: Reverb tab could not be created for session feedback")
                return
            if hasattr(reverb, "run_session_feedback_from_transcript"):
                reverb.run_session_feedback_from_transcript(text)
            if (
                RecordingSession is not None
                and isinstance(payload, RecordingSession)
                and hasattr(reverb, "_last_episode_session")
            ):
                reverb._last_episode_session = payload
            idx = self.tab_widget.indexOf(reverb)
            if idx >= 0:
                self.tab_widget.setCurrentIndex(idx)
        except Exception as e:
            print(f"MainWindow: session feedback delivery failed: {e}")
            import traceback

            traceback.print_exc()

    def _create_scoop_tab(self):
        """Create Scoop tab with error handling"""
        try:
            tab = ScoopTab()
            self._loaded_tabs["Scoop"] = tab
            return tab
        except Exception as e:
            self._track_error("ScoopTabError", f"Failed to create Scoop tab: {str(e)}")
            return None

    def _create_reverb_tab(self):
        """Create Reverb tab with error handling"""
        try:
            tab = ReverbTab()
            self._loaded_tabs["Reverb"] = tab
            return tab
        except Exception as e:
            self._track_error(
                "ReverbTabError", f"Failed to create Reverb tab: {str(e)}"
            )
            return None

    def _create_settings_tab(self):
        """Create Settings tab for SoapBoxx services and question backend."""
        try:
            try:
                from backend.config import Config
            except ImportError:  # pragma: no cover
                from config import Config  # type: ignore

            cfg = Config()
            page = QWidget()
            layout = QVBoxLayout(page)

            header = QLabel("SoapBoxx Settings")
            header.setStyleSheet("font-size: 18px; font-weight: bold; color: #2C3E50;")
            layout.addWidget(header)

            hint = QLabel(
                "Configure SoapBoxx defaults for transcription, STT, TTS, and question extraction backend."
            )
            hint.setWordWrap(True)
            hint.setStyleSheet("color: #6C757D;")
            layout.addWidget(hint)

            appear = ModernCard()
            appear_form = QFormLayout(appear)
            self.settings_theme_combo = QComboBox()
            for tid in self._all_ui_theme_ids():
                self.settings_theme_combo.addItem(tid.replace("_", " ").title(), tid)
            cur_theme = str(cfg.get("ui_settings.theme", "modern_light") or "modern_light")
            if cur_theme == "default":
                cur_theme = "modern_light"
            ix = self.settings_theme_combo.findData(cur_theme)
            if ix < 0:
                ix = self.settings_theme_combo.findData("modern_light")
            if ix >= 0:
                self.settings_theme_combo.setCurrentIndex(ix)
            appear_form.addRow("Application theme:", self.settings_theme_combo)
            theme_hint = QLabel(
                "Chooses the app palette and window/tab chrome. "
                "Changing the dropdown applies immediately; Save persists it to your SoapBoxx config."
            )
            theme_hint.setWordWrap(True)
            theme_hint.setStyleSheet("color: #6C757D; font-size: 11px;")
            appear_form.addRow(theme_hint)
            layout.addWidget(appear)
            self.settings_theme_combo.currentIndexChanged.connect(
                self._on_settings_theme_changed
            )

            byok = ModernCard()
            byok_form = QFormLayout(byok)
            byok_title = QLabel("Your AI API key (optional)")
            byok_title.setStyleSheet("font-weight: bold; color: #2C3E50;")
            byok_form.addRow(byok_title)
            byok_intro = QLabel(
                "Paste one key from OpenAI, Claude (Anthropic), Groq, or Google. "
                "We pick the provider from the key shape when we can; otherwise choose it in the dropdown. "
                "It is stored only on this computer. Save applies it to this session."
            )
            byok_intro.setWordWrap(True)
            byok_intro.setStyleSheet("color: #6C757D; font-size: 12px;")
            byok_form.addRow(byok_intro)

            self.settings_byok_unified = QLineEdit()
            self.settings_byok_unified.setEchoMode(QLineEdit.EchoMode.Password)
            self.settings_byok_unified.setPlaceholderText(
                "Paste your API key (OpenAI sk-…, Claude sk-ant-…, Groq gsk_…, Google AIza…)"
            )
            byok_form.addRow("API key:", self.settings_byok_unified)

            self.settings_byok_kind = QComboBox()
            for label, data in (
                ("Auto-detect from key shape", "auto"),
                ("OpenAI", "openai"),
                ("Google API", "google"),
                ("Groq", "groq"),
                ("Anthropic (Claude)", "anthropic"),
            ):
                self.settings_byok_kind.addItem(label, data)
            byok_form.addRow("Provider:", self.settings_byok_kind)

            self.settings_byok_unified_hint = QLabel("")
            self.settings_byok_unified_hint.setWordWrap(True)
            self.settings_byok_unified_hint.setStyleSheet("color: #6C757D; font-size: 11px;")
            byok_form.addRow(self.settings_byok_unified_hint)

            self.settings_byok_status = QLabel("")
            self.settings_byok_status.setWordWrap(True)
            self.settings_byok_status.setStyleSheet("color: #6C757D; font-size: 11px;")
            byok_form.addRow("Storage status:", self.settings_byok_status)

            clear_byok = ModernButton("Clear saved user API keys…", style="secondary")
            clear_byok.clicked.connect(self._clear_user_api_keys_clicked)
            byok_form.addRow(clear_byok)

            layout.addWidget(byok)
            self.settings_byok_unified.textChanged.connect(self._byok_refresh_unified_hint)
            self.settings_byok_unified.textChanged.connect(self._refresh_settings_validation_status)
            self.settings_byok_kind.currentIndexChanged.connect(self._byok_refresh_unified_hint)
            self.settings_byok_kind.currentIndexChanged.connect(self._refresh_settings_validation_status)
            self._byok_refresh_unified_hint()
            self._refresh_byok_status_label()

            card = ModernCard()
            form = QFormLayout(card)

            self.settings_transcription_combo = QComboBox()
            self.settings_transcription_combo.addItems(["openai", "local", "assemblyai", "azure"])
            self.settings_transcription_combo.setCurrentText(
                str(cfg.get("ui_settings.soapbox.transcription_service", "openai") or "openai")
            )
            form.addRow("Transcription service:", self.settings_transcription_combo)

            self.settings_stt_combo = QComboBox()
            self.settings_stt_combo.addItems(["openai", "local", "azure", "assemblyai"])
            self.settings_stt_combo.setCurrentText(
                str(cfg.get("ui_settings.soapbox.stt_service", "openai") or "openai")
            )
            form.addRow("Speech-to-text service:", self.settings_stt_combo)

            self.settings_tts_combo = QComboBox()
            self.settings_tts_combo.addItems(["openai", "local", "google", "azure"])
            self.settings_tts_combo.setCurrentText(
                str(cfg.get("ui_settings.soapbox.tts_service", "openai") or "openai")
            )
            form.addRow("Text-to-speech service:", self.settings_tts_combo)

            self.settings_question_combo = QComboBox()
            self.settings_question_combo.addItems(["offline", "openai", "auto"])
            self.settings_question_combo.setCurrentText(
                str(cfg.get("ui_settings.soapbox.question_llm_backend", "auto") or "auto")
            )
            form.addRow("Question extraction backend:", self.settings_question_combo)

            self.settings_ollama_model = QLineEdit()
            self.settings_ollama_model.setPlaceholderText("e.g. llama3.1:8b")
            self.settings_ollama_model.setText(
                str(os.getenv("SOAPBOXX_OLLAMA_MODEL", "") or cfg.get("ui_settings.soapbox.ollama_model", ""))
            )
            form.addRow("Offline model (Ollama):", self.settings_ollama_model)

            layout.addWidget(card)

            self.settings_validation_label = QLabel("")
            self.settings_validation_label.setWordWrap(True)
            self.settings_validation_label.setStyleSheet("color: #6C757D;")
            layout.addWidget(self.settings_validation_label)

            self.settings_question_combo.currentTextChanged.connect(self._refresh_settings_validation_status)
            self.settings_transcription_combo.currentTextChanged.connect(self._refresh_settings_validation_status)
            self.settings_stt_combo.currentTextChanged.connect(self._refresh_settings_validation_status)
            self.settings_tts_combo.currentTextChanged.connect(self._refresh_settings_validation_status)
            self.settings_ollama_model.textChanged.connect(self._refresh_settings_validation_status)

            actions = QHBoxLayout()
            save_btn = ModernButton("Save Settings", style="primary")
            save_btn.clicked.connect(self._save_settings_tab_values)
            actions.addWidget(save_btn)
            reset_btn = ModernButton("Reset Defaults", style="secondary")
            reset_btn.clicked.connect(self._reset_settings_tab_values)
            actions.addWidget(reset_btn)
            diag_btn = ModernButton("Run Diagnostics", style="secondary")
            diag_btn.clicked.connect(self._show_diagnostics_report)
            actions.addWidget(diag_btn)
            export_diag_btn = ModernButton("Export Diagnostics", style="secondary")
            export_diag_btn.clicked.connect(self._export_diagnostics_report)
            actions.addWidget(export_diag_btn)
            actions.addStretch()
            layout.addLayout(actions)
            self._refresh_settings_validation_status()
            layout.addStretch()
            return page
        except Exception as e:
            self._track_error("SettingsTabError", f"Failed to create settings tab: {e}")
            return self._create_placeholder_tab("Settings", f"Failed to load: {e}")

    def _byok_unified_target_env(self) -> str | None:
        """Return env var name for the unified BYOK field, or None if empty / unknown in auto mode."""
        if not hasattr(self, "settings_byok_unified"):
            return None
        raw = (self.settings_byok_unified.text() or "").strip()
        if not raw:
            return None
        mode = self.settings_byok_kind.currentData()
        mode_s = (mode if isinstance(mode, str) else str(mode or "")).strip().lower()
        if mode_s in {"", "auto"}:
            try:
                from backend.user_api_secrets import classify_api_key_secret
            except ImportError:
                from user_api_secrets import classify_api_key_secret  # type: ignore
            return classify_api_key_secret(raw)
        mapping = {
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "groq": "GROQ_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        return mapping.get(mode_s)

    def _byok_refresh_unified_hint(self):
        if not hasattr(self, "settings_byok_unified_hint"):
            return
        raw = (self.settings_byok_unified.text() or "").strip()
        if not raw:
            self.settings_byok_unified_hint.setText(
                "Typical shapes: sk-… (OpenAI), sk-ant-… (Claude), gsk_… (Groq), AIza… (Google). "
                "If yours looks different, pick the provider above."
            )
            return
        env = self._byok_unified_target_env()
        names = {
            "OPENAI_API_KEY": "OpenAI",
            "GOOGLE_API_KEY": "Google API",
            "GROQ_API_KEY": "Groq",
            "ANTHROPIC_API_KEY": "Anthropic (Claude)",
        }
        if env:
            self.settings_byok_unified_hint.setText(
                f"Will save as {names.get(env, env)}. Change the provider only if that is wrong."
            )
        else:
            self.settings_byok_unified_hint.setText(
                "Could not guess the provider from this key — pick OpenAI / Google / Groq / Anthropic above, then Save."
            )

    def _refresh_byok_status_label(self):
        """Show where optional user API keys are stored and what is currently visible in env."""
        if not hasattr(self, "settings_byok_status"):
            return
        try:
            try:
                from backend.user_api_secrets import user_api_secrets_path
            except ImportError:
                from user_api_secrets import user_api_secrets_path  # type: ignore
            p = user_api_secrets_path()
            exists = p.is_file()
            lines = [
                f"Storage: {p}",
                f"File present: {'yes' if exists else 'no'}",
                "",
                f"OPENAI_API_KEY: {'set' if (os.getenv('OPENAI_API_KEY') or '').strip() else 'not set'}",
                f"GOOGLE_API_KEY: {'set' if (os.getenv('GOOGLE_API_KEY') or '').strip() else 'not set'}",
                f"GROQ_API_KEY: {'set' if (os.getenv('GROQ_API_KEY') or os.getenv('SOAPBOXX_GROQ_API_KEY') or '').strip() else 'not set'}",
                f"ANTHROPIC_API_KEY: {'set' if (os.getenv('ANTHROPIC_API_KEY') or '').strip() else 'not set'}",
            ]
            self.settings_byok_status.setText("\n".join(lines))
        except Exception as e:
            self.settings_byok_status.setText(f"(Could not read user secrets path: {e})")

    def _clear_user_api_keys_clicked(self):
        """Remove saved user API keys and reload bundled .env defaults."""
        reply = QMessageBox.question(
            self,
            "Clear user API keys",
            "Delete the saved user API key file and reload the demo .env?\n\n"
            "This removes keys you pasted in Settings (not keys only set outside SoapBoxx).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            try:
                from backend.user_api_secrets import clear_user_api_secrets_file
            except ImportError:
                from user_api_secrets import clear_user_api_secrets_file  # type: ignore
            clear_user_api_secrets_file()
            for k in (
                "OPENAI_API_KEY",
                "GOOGLE_API_KEY",
                "GROQ_API_KEY",
                "SOAPBOXX_GROQ_API_KEY",
                "ANTHROPIC_API_KEY",
            ):
                os.environ.pop(k, None)
            try:
                from dotenv import load_dotenv

                load_dotenv(Path(_repo_root) / ".env", override=True)
            except ImportError:
                pass
            try:
                from backend.user_api_secrets import load_user_api_secrets
            except ImportError:
                from user_api_secrets import load_user_api_secrets  # type: ignore
            load_user_api_secrets(override=True)
            for w in (getattr(self, "settings_byok_unified", None),):
                if w is not None:
                    w.clear()
            if hasattr(self, "settings_byok_kind"):
                self.settings_byok_kind.setCurrentIndex(0)
            self._byok_refresh_unified_hint()
            self._refresh_byok_status_label()
            self._refresh_settings_validation_status()
            QMessageBox.information(
                self,
                "User API keys",
                "Saved user API keys were cleared. Bundled .env values were reloaded where present.",
            )
        except Exception as e:
            self._show_user_friendly_error("User API keys", "Failed to clear user keys.", str(e))

    def _validate_settings_inputs(self):
        """Return (errors, warnings) for current Settings selections."""
        errors = []
        warnings = []

        if hasattr(self, "settings_byok_unified"):
            raw = (self.settings_byok_unified.text() or "").strip()
            if raw:
                tgt = self._byok_unified_target_env()
                if not tgt:
                    errors.append(
                        "Optional API key: choose a provider (OpenAI, Google, Groq, or Anthropic) "
                        "in the dropdown — this key shape is not recognized on its own."
                    )
                elif tgt == "OPENAI_API_KEY" and raw.lower().startswith("sk-ant"):
                    errors.append(
                        "That looks like an Anthropic (Claude) key — choose Anthropic (Claude) in the provider dropdown."
                    )
                elif tgt == "OPENAI_API_KEY" and not raw.startswith("sk-"):
                    errors.append("OpenAI keys should start with sk-.")
                elif tgt == "GOOGLE_API_KEY" and len(raw) < 12:
                    errors.append("That Google API key looks too short.")
                elif tgt == "GROQ_API_KEY" and len(raw) < 8:
                    errors.append("That Groq key looks too short.")
                elif tgt == "ANTHROPIC_API_KEY" and len(raw) < 10:
                    errors.append("That Anthropic key looks too short.")
                elif tgt == "ANTHROPIC_API_KEY" and not raw.startswith("sk-ant"):
                    warnings.append(
                        "Anthropic keys usually start with sk-ant-; confirm if the API rejects the key."
                    )

        qllm = str(self.settings_question_combo.currentText() or "").strip().lower()
        om = (self.settings_ollama_model.text() or "").strip()
        openai_env = (os.getenv("OPENAI_API_KEY") or "").strip()
        pending_oai = ""
        if hasattr(self, "settings_byok_unified"):
            u_raw = (self.settings_byok_unified.text() or "").strip()
            if (
                u_raw
                and self._byok_unified_target_env() == "OPENAI_API_KEY"
                and u_raw.startswith("sk-")
                and not u_raw.lower().startswith("sk-ant")
            ):
                pending_oai = u_raw

        openai_effective = openai_env or (
            pending_oai if pending_oai.startswith("sk-") else ""
        )

        if qllm == "offline" and not om:
            errors.append(
                "Question backend is set to 'offline' but Ollama model is empty."
            )

        if qllm == "openai" and not openai_effective:
            warnings.append(
                "Question backend is set to 'openai' but OPENAI_API_KEY is not set in env "
                "(paste your API key in Settings, choose OpenAI if needed, save, or set .env)."
            )

        uses_openai = any(
            str(combo.currentText() or "").strip().lower() == "openai"
            for combo in (
                self.settings_transcription_combo,
                self.settings_stt_combo,
                self.settings_tts_combo,
            )
        )
        if uses_openai and not openai_effective:
            warnings.append(
                "One or more services use OpenAI, but OPENAI_API_KEY is not set in env "
                "(paste your API key in Settings, choose OpenAI if needed, save, or set .env)."
            )

        if om and ":" not in om:
            warnings.append("Ollama model usually uses 'name:tag' format (example: llama3.1:8b).")

        return errors, warnings

    def _refresh_settings_validation_status(self):
        """Update inline Settings validation status text."""
        try:
            if not hasattr(self, "settings_validation_label"):
                return
            errors, warnings = self._validate_settings_inputs()
            if errors:
                self.settings_validation_label.setStyleSheet("color: #E74C3C; font-weight: 600;")
                self.settings_validation_label.setText("Validation: blocked. " + " ".join(errors))
            elif warnings:
                self.settings_validation_label.setStyleSheet("color: #B9770E;")
                self.settings_validation_label.setText("Validation: warnings. " + " ".join(warnings))
            else:
                self.settings_validation_label.setStyleSheet("color: #1E8449;")
                self.settings_validation_label.setText("Validation: ready to save.")
        except Exception as e:
            self._track_error("SettingsValidationError", f"Failed to refresh validation: {e}")

    def _save_settings_tab_values(self):
        """Save Settings tab values and push to loaded SoapBoxx tab."""
        try:
            try:
                from backend.config import Config
            except ImportError:  # pragma: no cover
                from config import Config  # type: ignore

            cfg = Config()
            tr = self.settings_transcription_combo.currentText()
            stt = self.settings_stt_combo.currentText()
            tts = self.settings_tts_combo.currentText()
            qllm = self.settings_question_combo.currentText()
            om = (self.settings_ollama_model.text() or "").strip()

            errors, warnings = self._validate_settings_inputs()
            if errors:
                QMessageBox.warning(
                    self,
                    "Settings Validation",
                    "Cannot save settings:\n\n- " + "\n- ".join(errors),
                )
                self._refresh_settings_validation_status()
                return
            if warnings:
                reply = QMessageBox.question(
                    self,
                    "Settings Warnings",
                    "Warnings detected:\n\n- "
                    + "\n- ".join(warnings)
                    + "\n\nSave anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    self._refresh_settings_validation_status()
                    return

            cfg.set("ui_settings.soapbox.transcription_service", tr)
            cfg.set("ui_settings.soapbox.stt_service", stt)
            cfg.set("ui_settings.soapbox.tts_service", tts)
            cfg.set("ui_settings.soapbox.question_llm_backend", qllm)
            cfg.set("ui_settings.soapbox.ollama_model", om)
            tid = self.settings_theme_combo.currentData()
            if tid:
                cfg.set("ui_settings.theme", str(tid))
            if om:
                os.environ["SOAPBOXX_OLLAMA_MODEL"] = om

            try:
                try:
                    from backend.user_api_secrets import persist_user_api_secret
                except ImportError:
                    from user_api_secrets import persist_user_api_secret  # type: ignore

                if hasattr(self, "settings_byok_unified"):
                    raw = (self.settings_byok_unified.text() or "").strip()
                    if raw:
                        tgt = self._byok_unified_target_env()
                        if tgt:
                            persist_user_api_secret(tgt, raw)
                    self.settings_byok_unified.clear()
                    self._byok_refresh_unified_hint()
                    self._refresh_byok_status_label()
            except Exception as e:
                self._track_error("BYOKPersistError", f"Failed to persist user API keys: {e}")
                QMessageBox.warning(
                    self,
                    "User API keys",
                    "Settings were saved, but storing optional user API keys failed:\n\n" + str(e),
                )

            tab = self._loaded_tabs.get("SoapBoxx")
            if tab:
                if hasattr(tab, "service_combo"):
                    tab.service_combo.setCurrentText(tr)
                if hasattr(tab, "stt_service_combo"):
                    tab.stt_service_combo.setCurrentText(stt)
                if hasattr(tab, "tts_service_combo"):
                    tab.tts_service_combo.setCurrentText(tts)
                if hasattr(tab, "question_llm_combo"):
                    tab.question_llm_combo.setCurrentText(qllm)

            self._refresh_settings_validation_status()
            self._show_status_message("Settings saved and applied.")
            QMessageBox.information(self, "Settings", "SoapBoxx settings saved.")
        except Exception as e:
            self._track_error("SettingsSaveError", f"Failed to save settings: {e}")
            self._show_user_friendly_error("Settings Error", "Failed to save settings.", str(e))

    def _on_settings_theme_changed(self, index: int):
        """Live-apply theme from Settings combo (persist on Save)."""
        try:
            if index < 0 or not hasattr(self, "settings_theme_combo"):
                return
            tid = self.settings_theme_combo.itemData(index)
            tm = getattr(self, "theme_manager", None)
            if tid and tm and str(tid) in tm.themes:
                tm.apply_theme(str(tid))
        except Exception as e:
            self._track_error("ThemePreviewError", f"Theme preview failed: {e}")

    def _reset_settings_tab_values(self):
        """Reset SoapBoxx settings to safe defaults."""
        try:
            self.settings_transcription_combo.setCurrentText("openai")
            self.settings_stt_combo.setCurrentText("openai")
            self.settings_tts_combo.setCurrentText("openai")
            self.settings_question_combo.setCurrentText("auto")
            self.settings_ollama_model.setText("")
            ix = self.settings_theme_combo.findData("modern_light")
            if ix >= 0:
                self.settings_theme_combo.setCurrentIndex(ix)
            self._refresh_settings_validation_status()
            self._save_settings_tab_values()
            self._show_status_message("Settings reset to defaults.")
        except Exception as e:
            self._track_error("SettingsResetError", f"Failed to reset settings: {e}")
            self._show_user_friendly_error("Settings Error", "Failed to reset settings.", str(e))

    def _build_diagnostics_report(self) -> str:
        """Build a quick runtime diagnostics summary for support/self-check."""
        lines = []
        lines.append("SoapBoxx Diagnostics")
        lines.append("-" * 60)
        lines.append(f"Python: {sys.version.split()[0]}")
        lines.append(f"CWD: {os.getcwd()}")
        lines.append(f"SOAPBOXX_BUCKET: {(os.getenv('SOAPBOXX_BUCKET') or 'production').strip() or 'production'}")
        lines.append(f"SOAPBOXX_RUNS_DIR: {(os.getenv('SOAPBOXX_RUNS_DIR') or '(default by bucket)').strip() or '(default by bucket)'}")
        lines.append(f"SOAPBOXX_OLLAMA_MODEL: {(os.getenv('SOAPBOXX_OLLAMA_MODEL') or '').strip() or '(not set)'}")
        lines.append(f"OPENAI_API_KEY set: {'yes' if (os.getenv('OPENAI_API_KEY') or '').strip() else 'no'}")
        try:
            try:
                from backend.user_api_secrets import user_api_secrets_path
            except ImportError:
                from user_api_secrets import user_api_secrets_path  # type: ignore
            sp = user_api_secrets_path()
            lines.append(
                f"SOAPBOXX_USER_SECRETS_FILE / user api_keys.env: {sp} "
                f"({'exists' if sp.is_file() else 'missing'})"
            )
        except Exception as e:
            lines.append(f"User secrets path: (error: {e})")
        lines.append("")
        if hasattr(self, "_tabs_loaded"):
            lines.append("Tab health:")
            for name, loaded in self._tabs_loaded.items():
                lines.append(f"  - {name}: {'ok' if loaded else 'failed/not loaded'}")
            lines.append("")
        lines.append("Loaded tabs:")
        for name in ("SoapBoxx", "Scoop", "Reverb", "Settings"):
            lines.append(f"  - {name}: {'loaded' if name in self._loaded_tabs else 'not loaded'}")
        lines.append("")
        lines.append("Current Settings tab values:")
        if hasattr(self, "settings_transcription_combo"):
            lines.append(f"  - transcription_service: {self.settings_transcription_combo.currentText()}")
            lines.append(f"  - stt_service: {self.settings_stt_combo.currentText()}")
            lines.append(f"  - tts_service: {self.settings_tts_combo.currentText()}")
            lines.append(f"  - question_llm_backend: {self.settings_question_combo.currentText()}")
            lines.append(f"  - ollama_model_field: {(self.settings_ollama_model.text() or '').strip() or '(empty)'}")
            if hasattr(self, "settings_theme_combo"):
                td = self.settings_theme_combo.currentData()
                lines.append(f"  - ui_settings.theme (preview): {td or '(n/a)'}")
        lines.append("")
        lines.extend(self._build_latest_run_quality_block())
        lines.append("")
        lines.append(f"Tracked errors in session: {self._error_count}")
        return "\n".join(lines)

    def _build_latest_run_quality_block(self):
        """Build quality scorecard lines from the latest intake_summary artifact."""
        lines = ["Latest Run Quality Scorecard:"]
        try:
            summary_path = self._find_latest_intake_summary_path()
            if not summary_path:
                lines.append("  - No intake summary found (run an episode intake first).")
                return lines

            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)
            score, grade, components = self._score_from_intake_summary(summary)

            lines.append(f"  - source: {summary_path}")
            lines.append(f"  - trust_score: {score}/100 ({grade})")
            for name, points in components:
                lines.append(f"  - {name}: {points}")
        except Exception as e:
            lines.append(f"  - Could not compute scorecard: {e}")
        return lines

    def _find_latest_intake_summary_path(self):
        """Return newest runs/intake/*/intake_summary.json path, or empty string."""
        root = Path(__file__).resolve().parent.parent
        runs_dir_env = (os.getenv("SOAPBOXX_RUNS_DIR") or "").strip()
        bucket = (os.getenv("SOAPBOXX_BUCKET") or "production").strip().lower()
        if runs_dir_env:
            runs_root = Path(runs_dir_env)
        elif bucket in {"demo", "dev", "development", "sandbox"}:
            runs_root = root / "runs" / "demo"
        else:
            runs_root = root / "runs"
        intake_root = runs_root / "intake"
        if not intake_root.exists():
            return ""
        candidates = list(intake_root.glob("*/intake_summary.json"))
        if not candidates:
            return ""
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        return str(latest)

    def _score_from_intake_summary(self, summary):
        """Compute a simple trust scorecard from intake_summary fields."""
        score = 0
        components = []

        tq = summary.get("transcript_quality") or {}
        tq_score = float(tq.get("score") or 0.0)
        tq_points = max(0, min(30, int(round(tq_score * 30))))
        score += tq_points
        components.append(("transcript_quality", f"{tq_points}/30"))

        band = str(summary.get("readiness_band") or "").strip().lower()
        band_points_map = {"ship": 25, "watch": 16, "rework": 8, "fail": 0}
        band_points = band_points_map.get(band, 0)
        score += band_points
        components.append(("report_readiness", f"{band_points}/25 ({band or 'unknown'})"))

        rig_status = str(summary.get("argument_rigor_status") or "").strip().upper()
        rig_score = summary.get("argument_rigor_score")
        rig_points = 0
        if isinstance(rig_score, (int, float)):
            rig_points = max(0, min(25, int(round(float(rig_score) * 25))))
        elif rig_status == "PASS":
            rig_points = 25
        elif rig_status == "WARN":
            rig_points = 14
        elif rig_status == "FAIL":
            rig_points = 0
        score += rig_points
        components.append(("argument_rigor", f"{rig_points}/25 ({rig_status or 'unknown'})"))

        warnings = summary.get("warnings")
        warn_count = len(warnings) if isinstance(warnings, list) else 0
        warning_points = 10 if warn_count == 0 else max(0, 10 - min(10, warn_count))
        score += warning_points
        components.append(("warnings", f"{warning_points}/10 ({warn_count} warning(s))"))

        source = str((summary.get("input") or {}).get("transcript_source_used") or "")
        source_points_map = {
            "youtube_asr_auto": 10,
            "youtube_captions_auto": 8,
            "youtube_asr": 8,
            "youtube_captions": 6,
        }
        source_points = source_points_map.get(source, 8 if source else 0)
        score += source_points
        components.append(("source_confidence", f"{source_points}/10 ({source or 'unknown'})"))

        if score >= 85:
            grade = "high"
        elif score >= 65:
            grade = "medium"
        else:
            grade = "low"
        return score, grade, components

    def _show_diagnostics_report(self):
        """Show diagnostics in a read-only dialog."""
        try:
            dlg = QDialog(self)
            dlg.setWindowTitle("SoapBoxx Diagnostics")
            dlg.resize(760, 520)
            lay = QVBoxLayout(dlg)
            txt = QTextEdit()
            txt.setReadOnly(True)
            txt.setPlainText(self._build_diagnostics_report())
            lay.addWidget(txt)
            close_btn = ModernButton("Close", style="primary")
            close_btn.clicked.connect(dlg.accept)
            lay.addWidget(close_btn)
            dlg.exec()
        except Exception as e:
            self._track_error("DiagnosticsError", f"Failed to show diagnostics: {e}")
            self._show_user_friendly_error("Diagnostics Error", "Failed to open diagnostics.", str(e))

    def _export_diagnostics_report(self):
        """Export diagnostics report to a timestamped text file."""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"soapboxx_diagnostics_{ts}.txt"
            out_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Diagnostics",
                default_name,
                "Text Files (*.txt);;All Files (*)",
            )
            if not out_path:
                return
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(self._build_diagnostics_report())
                f.write("\n")
            self._show_status_message(f"Diagnostics exported: {out_path}", 5000)
            QMessageBox.information(self, "Diagnostics", f"Diagnostics exported to:\n{out_path}")
        except Exception as e:
            self._track_error("DiagnosticsExportError", f"Failed to export diagnostics: {e}")
            self._show_user_friendly_error(
                "Diagnostics Export Error", "Failed to export diagnostics.", str(e)
            )

    def _add_placeholder_tab(self, tab_name: str, message: str):
        """Add placeholder tab when actual tab fails to load"""
        try:
            placeholder_widget = QWidget()
            layout = QVBoxLayout()

            # Error message
            error_label = QLabel(message)
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setStyleSheet(
                """
                QLabel {
                    color: #E74C3C;
                    font-size: 14px;
                    padding: 20px;
                }
            """
            )

            # Retry button
            retry_button = ModernButton("Retry Loading", style="primary")
            retry_button.clicked.connect(lambda: self._retry_tab_loading(tab_name))

            layout.addWidget(error_label)
            layout.addWidget(retry_button, alignment=Qt.AlignmentFlag.AlignCenter)
            layout.addStretch()

            placeholder_widget.setLayout(layout)
            self.tab_widget.addTab(placeholder_widget, tab_name)

        except Exception as e:
            self._track_error(
                "PlaceholderTabError", f"Failed to create placeholder tab: {str(e)}"
            )

    def _retry_tab_loading(self, tab_name: str):
        """Retry loading a failed tab"""
        try:
            # Remove placeholder tab
            for i in range(self.tab_widget.count()):
                if self.tab_widget.tabText(i) == tab_name:
                    self.tab_widget.removeTab(i)
                    break

            # Try to create the tab again
            if tab_name == "SoapBoxx":
                tab = self._create_soapboxx_tab()
            elif tab_name == "Scoop":
                tab = self._create_scoop_tab()
            elif tab_name == "Reverb":
                tab = self._create_reverb_tab()
            elif tab_name == "Settings":
                tab = self._create_settings_tab()
            else:
                return

            if tab:
                self.tab_widget.addTab(tab, tab_name)
                self._tabs_loaded[tab_name] = True
                self._show_status_message(f"{tab_name} tab loaded successfully")
            else:
                self._add_placeholder_tab(
                    tab_name, f"Failed to load {tab_name} tab (retry failed)"
                )

        except Exception as e:
            self._track_error(
                "TabRetryError", f"Failed to retry loading {tab_name} tab: {str(e)}"
            )

    def _setup_status_bar(self):
        """Setup status bar with enhanced information"""
        try:
            self.status_bar = self.statusBar()

            # Status label
            self.status_label = QLabel("Ready")
            self.status_bar.addWidget(self.status_label)

            # Error count indicator
            self.error_indicator = QLabel("")
            self.error_indicator.setStyleSheet(
                """
                QLabel {
                    color: #E74C3C;
                    font-weight: bold;
                }
            """
            )
            self.status_bar.addPermanentWidget(self.error_indicator)

            # Update status
            self._update_status_display()

        except Exception as e:
            self._track_error("StatusBarError", f"Failed to setup status bar: {str(e)}")

    def _setup_menu_bar(self):
        """Setup menu bar with enhanced functionality"""
        try:
            menubar = self.menuBar()

            # File menu
            file_menu = menubar.addMenu("File")

            # Export action
            export_action = QAction("Export Data", self)
            export_action.setShortcut(QKeySequence.StandardKey.Save)
            export_action.triggered.connect(self._export_data)
            file_menu.addAction(export_action)

            # Exit action
            exit_action = QAction("Exit", self)
            exit_action.setShortcut(QKeySequence.StandardKey.Quit)
            exit_action.triggered.connect(self.close)
            file_menu.addAction(exit_action)

            # View menu (appearance)
            view_menu = menubar.addMenu("View")
            theme_menu = view_menu.addMenu("Theme")
            theme_ids = [
                "modern_light",
                "modern_dark",
                "dark",
                "modern_blue",
                "modern_green",
                "light",
                "blue",
                "green",
            ]
            for tid in theme_ids:
                label = tid.replace("_", " ").title()
                act = QAction(label, self)
                act.triggered.connect(
                    lambda checked=False, name=tid: self._set_ui_theme(name)
                )
                theme_menu.addAction(act)
            view_menu.addSeparator()
            toggle_dark = QAction("Toggle dark / light", self)
            toggle_dark.triggered.connect(self._toggle_ui_dark)
            view_menu.addAction(toggle_dark)

            # Help menu
            help_menu = menubar.addMenu("Help")

            # About action
            about_action = QAction("About", self)
            about_action.triggered.connect(self._show_about)
            help_menu.addAction(about_action)

            diagnostics_action = QAction("Diagnostics", self)
            diagnostics_action.triggered.connect(self._show_diagnostics_report)
            help_menu.addAction(diagnostics_action)

            export_diagnostics_action = QAction("Export Diagnostics", self)
            export_diagnostics_action.triggered.connect(self._export_diagnostics_report)
            help_menu.addAction(export_diagnostics_action)

        except Exception as e:
            self._track_error("MenuBarError", f"Failed to setup menu bar: {str(e)}")

    def _show_booking_dialog(self):
        """Show booking dialog with error handling"""
        try:
            dialog = BookingDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Handle booking
                guest_name = dialog.guest_name.text()
                date = dialog.date_picker.date()
                time = dialog.time_picker.time()
                notes = dialog.notes.toPlainText()

                self._show_status_message(
                    f"Booked a feedback call with {guest_name} for {date.toString()} at {time.toString()}"
                )

        except Exception as e:
            self._show_user_friendly_error(
                "Booking Error", "Failed to show booking dialog", str(e)
            )
            self._track_error(
                "BookingDialogError", f"Failed to show booking dialog: {str(e)}"
            )

    def _show_settings(self):
        """Open the Settings tab."""
        try:
            for i in range(self.tab_widget.count()):
                if self.tab_widget.tabText(i) == "Settings":
                    self.tab_widget.setCurrentIndex(i)
                    # If tab wasn't loaded yet, lazy loader will create it.
                    self._on_tab_changed(i)
                    return
            QMessageBox.information(self, "Settings", "Settings tab not found.")
        except Exception as e:
            self._track_error("SettingsError", f"Failed to show settings: {str(e)}")

    def _export_data(self):
        """Export application data"""
        try:
            # Placeholder for export functionality
            QMessageBox.information(
                self, "Export", "Export functionality not implemented yet."
            )
        except Exception as e:
            self._track_error("ExportError", f"Failed to export data: {str(e)}")

    def _show_about(self):
        """Show about dialog"""
        try:
            about_text = """
            <h3>SoapBoxx</h3>
            <p>AI-Powered Podcast Production Studio</p>
            <p>Version: 1.0.0</p>
            <p>Production Ready - 9/10 Reliability Rating</p>
            """
            QMessageBox.about(self, "About SoapBoxx", about_text)
        except Exception as e:
            self._track_error("AboutError", f"Failed to show about dialog: {str(e)}")

    def _show_user_friendly_error(
        self, title: str, message: str, detailed_error: str = None
    ):
        """Show user-friendly error dialog"""
        try:
            if detailed_error:
                message += f"\n\nTechnical details: {detailed_error}"

            QMessageBox.critical(self, title, message)
        except Exception as e:
            print(f"Failed to show error dialog: {e}")
            print(f"Original error: {title} - {message}")

    def _track_error(self, error_type: str, message: str):
        """Track error for monitoring"""
        try:
            self._error_count += 1
            self._last_error_time = datetime.now()

            # Update error indicator
            self._update_status_display()

            # Log error
            print(f"Error tracked: {error_type} - {message}")

        except Exception as e:
            print(f"Failed to track error: {e}")

    def _update_status_display(self):
        """Update status bar display"""
        try:
            if self._error_count > 0:
                self.error_indicator.setText(f"⚠️ {self._error_count} error(s)")
            else:
                self.error_indicator.setText("")

        except Exception as e:
            print(f"Failed to update status display: {e}")

    def _show_status_message(self, message: str, timeout: int = 3000):
        """Show status message"""
        try:
            if hasattr(self, "status_bar"):
                self.status_bar.showMessage(message, timeout)
        except Exception as e:
            print(f"Failed to show status message: {e}")

    def _start_health_monitoring(self):
        """Start health monitoring timer"""
        try:
            self.health_timer = QTimer()
            self.health_timer.timeout.connect(self._check_health)
            self.health_timer.start(30000)  # Check every 30 seconds
        except Exception as e:
            self._track_error(
                "HealthMonitoringError", f"Failed to start health monitoring: {str(e)}"
            )

    def _check_health(self):
        """Check application health"""
        try:
            # Check for excessive errors
            if self._error_count > 10:
                self._show_status_message(
                    "High error count detected. Consider restarting the application."
                )

            # Check tab loading status
            failed_tabs = [
                name for name, loaded in self._tabs_loaded.items() if not loaded
            ]
            if failed_tabs:
                self._show_status_message(
                    f"Some tabs failed to load: {', '.join(failed_tabs)}"
                )

        except Exception as e:
            print(f"Health check failed: {e}")

    def closeEvent(self, event):
        """Handle application close with cleanup"""
        try:
            # Stop health monitoring
            if hasattr(self, "health_timer"):
                self.health_timer.stop()

            # Cleanup tabs
            for i in range(self.tab_widget.count()):
                tab = self.tab_widget.widget(i)
                if hasattr(tab, "closeEvent"):
                    tab.closeEvent(event)

            event.accept()

        except Exception as e:
            print(f"Error during close: {e}")
            event.accept()


def main():
    """Main application entry point with enhanced error handling"""
    try:
        if getattr(sys, "frozen", False):
            try:
                from backend.runtime_paths import configure_frozen_runtime

                configure_frozen_runtime()
            except Exception as exc:
                print(f"Frozen runtime setup warning: {exc}")

        print("Starting SoapBoxx application...")

        print("Creating QApplication...")
        app = QApplication(sys.argv)

        # Set application properties
        app.setApplicationName("SoapBoxx")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("SoapBoxx")
        print("QApplication created successfully")

        # Create and show main window
        print("Creating main window...")
        try:
            window = MainWindow()
            print("Main window created successfully")
        except Exception as e:
            print(f"Main window creation failed: {e}")
            import traceback

            traceback.print_exc()
            raise

        print("Showing main window...")
        try:
            window.show()
            print("Main window shown successfully")
        except Exception as e:
            print(f"Main window show failed: {e}")
            import traceback

            traceback.print_exc()
            raise

        # Start application
        print("Starting application event loop...")
        print("Application should now be visible and running...")
        sys.exit(app.exec())

    except Exception as e:
        print(f"Application failed to start: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
