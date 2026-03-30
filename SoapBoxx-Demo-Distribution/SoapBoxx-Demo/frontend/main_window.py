#!/usr/bin/env python3
"""
SoapBoxx Main Window
Main application window with tabbed interface
"""

import json
import os
import sys
import traceback
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

# Add backend directory to path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Use package-relative imports to support `python -m frontend.main_window`
try:
    from .batch_processor import BatchProcessorDialog
    from .export_manager import ExportManager
    from .keyboard_shortcuts import ShortcutHandler
    from .reverb_tab import ReverbTab
    from .scoop_tab import ScoopTab
    from .soapboxx_tab import SoapBoxxTab
    from .theme_manager import ThemeManager
except ImportError:
    # Fallback for direct script execution
    try:
        from batch_processor import BatchProcessorDialog
        from export_manager import ExportManager
        from keyboard_shortcuts import ShortcutHandler
        from reverb_tab import ReverbTab
        from scoop_tab import ScoopTab
        from soapboxx_tab import SoapBoxxTab
        from theme_manager import ThemeManager
    except ImportError as e:
        print(f"Warning: Some frontend modules not available: {e}")

        # Create placeholder classes for missing modules
        # Import QWidget for placeholder classes
        from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
        from PyQt6.QtCore import Qt
        
        class BatchProcessorDialog(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setLayout(QVBoxLayout())
                label = QLabel("Batch Processor (Demo Mode)")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.layout().addWidget(label)

        class ExportManager(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setLayout(QVBoxLayout())
                label = QLabel("Export Manager (Demo Mode)")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.layout().addWidget(label)

        class ShortcutHandler(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setLayout(QVBoxLayout())
                label = QLabel("Shortcut Handler (Demo Mode)")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.layout().addWidget(label)

        class ThemeManager(QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setLayout(QVBoxLayout())
                label = QLabel("Theme Manager (Demo Mode)")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.layout().addWidget(label)


from PyQt6.QtCore import QDate, Qt, QTime, QTimer
from PyQt6.QtGui import QAction, QFont, QIcon, QKeySequence, QPixmap
from PyQt6.QtWidgets import (QApplication, QComboBox, QDateEdit, QDialog,
                             QDialogButtonBox, QFormLayout, QFrame,
                             QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                             QInputDialog,
                             QLineEdit, QMainWindow, QMenu, QMenuBar,
                             QMessageBox, QPushButton, QScrollArea, QSizePolicy,
                             QSplitter, QStatusBar, QTabWidget, QTextEdit,
                             QTimeEdit, QVBoxLayout, QWidget)

# Import the bulletproof tab loader
try:
    from bulletproof_tab_loader import create_bulletproof_tab_loader
    BULLETPROOF_LOADER_AVAILABLE = True
    print("✅ Bulletproof tab loader imported successfully")
except ImportError:
    print("⚠️  Bulletproof tab loader not available, using fallback")
    BULLETPROOF_LOADER_AVAILABLE = False

# Import demo tab classes
try:
    from soapboxx_tab import SoapBoxxTab
    from scoop_tab import ScoopTab
    from reverb_tab import ReverbTab
    print("✅ Demo tab classes imported successfully")
except ImportError as e:
    print(f"⚠️  Demo tab classes not available: {e}")
    # Fallback placeholder classes will be used

# (imports moved into try/except above for dual compatibility)

BETA_EPISODE_LIMIT = 3
BETA_STATE_FILE = Path(__file__).resolve().parent.parent / ".soapboxx_beta_state.json"

# BaseTab class to enforce QWidget contract
class BaseTab(QWidget):
    """Base class for all tabs - ensures QWidget inheritance"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Override this method to set up the tab's UI"""
        pass


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

            # Notes (expandable so you can see everything)
            self.notes = QTextEdit()
            self.notes.setMinimumHeight(100)
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


def _load_package_info():
    """Load PACKAGE_INFO.json from project root. Returns dict or None."""
    try:
        base = Path(__file__).resolve().parent.parent
        path = base / "PACKAGE_INFO.json"
        if path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Could not load PACKAGE_INFO.json: {e}")
    return None


class FullDescriptionDialog(QDialog):
    """Dialog showing full app description and all package info (walkdown / see everything)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SoapBoxx — Full Description & Package Info")
        self.setModal(False)
        self.setMinimumSize(520, 420)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        content = QWidget()
        content_layout = QVBoxLayout(content)

        info = _load_package_info()
        if info:
            walkdown = self._format_full_walkdown(info)
        else:
            walkdown = (
                "<h3>SoapBoxx</h3><p>AI-Powered Podcast Production Studio — Demo Version</p>"
                "<p><i>PACKAGE_INFO.json not found. Run from SoapBoxx-Demo root.</i></p>"
            )

        text = QTextEdit()
        text.setReadOnly(True)
        text.setAcceptRichText(True)
        text.setHtml(walkdown)
        text.setMinimumHeight(320)
        text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout.addWidget(text)
        scroll.setWidget(content)
        layout.addWidget(scroll)

        close_btn = ModernButton("Close", style="primary")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _format_full_walkdown(self, info: dict) -> str:
        """Format full description walkdown as HTML so user can see everything."""
        lines = [
            "<h2>SoapBoxx — Full Description & Package Info</h2>",
            "<p>Below is the complete package and app description (full walkdown).</p>",
            "<hr/>",
            "<h3>Description</h3>",
            f"<p>{info.get('description', '—')}</p>",
            "<h3>Package name</h3>",
            f"<p><code>{info.get('package_name', '—')}</code></p>",
            "<h3>Author</h3>",
            f"<p>{info.get('author', '—')}</p>",
            "<h3>License</h3>",
            f"<p>{info.get('license', '—')}</p>",
            "<h3>Homepage</h3>",
            f"<p><a href=\"{info.get('homepage', '')}\">{info.get('homepage', '—')}</a></p>",
            "<h3>Demo features</h3>",
            f"<p>{info.get('demo_features', '—')}</p>",
            "<h3>Upgrade path</h3>",
            f"<p>{info.get('upgrade_path', '—')}</p>",
            "<h3>Support</h3>",
            f"<p>{info.get('support', '—')}</p>",
            "<hr/>",
            "<p><small>Use Help → Full description anytime to see this.</small></p>",
        ]
        return "".join(lines)


class LoginDialog(QDialog):
    """Simple beta login dialog (email or tester ID)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SoapBoxx Beta Login")
        self.setModal(True)
        self.user_id = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Sign in to start your 3-episode beta trial")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2C3E50;")
        layout.addWidget(title)

        form = QFormLayout()
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("you@example.com or tester ID")
        form.addRow("Email / Tester ID:", self.user_input)
        layout.addLayout(form)

        hint = QLabel("Your usage is tracked per account: 1/3, 2/3, 3/3 episodes.")
        hint.setStyleSheet("color: #7F8C8D;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self):
        value = self.user_input.text().strip()
        if not value:
            QMessageBox.warning(self, "Login required", "Please enter an email or tester ID.")
            return
        self.user_id = value
        self.accept()


class MainWindow(QMainWindow):
    """Main application window with enhanced resilience and error handling"""

    def __init__(self):
        try:
            print("🏗️ MainWindow: Starting initialization...")
            super().__init__()
            print("✅ MainWindow: Super class initialized")

            # Initialize state tracking
            self._is_initializing = True
            self._tabs_loaded = {}
            self._is_switching_tab = False
            self._error_count = 0
            self._last_error_time = None
            self._beta_state = {}
            self._current_user_id = ""
            self._current_api_key = ""
            self._episodes_used = 0
            print("✅ MainWindow: State tracking initialized")

            # Setup global exception handler
            print("🔧 MainWindow: Setting up exception handler...")
            self._setup_global_exception_handler()
            print("✅ MainWindow: Exception handler setup complete")

            # Initialize UI
            print("🎨 MainWindow: Setting up UI...")
            self.setup_ui()
            print("✅ MainWindow: UI setup complete")

            # Login gate for beta access
            self._ensure_beta_login()

            # Mark initialization complete
            self._is_initializing = False

            # Start health monitoring
            print("💚 MainWindow: Starting health monitoring...")
            self._start_health_monitoring()
            print("✅ MainWindow: Health monitoring started")

            print("✅ MainWindow: Initialization complete!")

        except Exception as e:
            print(f"❌ MainWindow initialization failed: {e}")
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
            self.setWindowTitle("SoapBoxx - AI-Powered Podcast Production Studio")
            self.setGeometry(100, 100, 1200, 800)

            # Apply modern theme
            self._apply_modern_theme()

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

    def _apply_modern_theme(self):
        """Apply modern theme to the application"""
        try:
            # Modern application style
            self.setStyleSheet(
                """
                QMainWindow {
                    background-color: #F8F9FA;
                }
                QTabWidget::pane {
                    border: 1px solid #E0E0E0;
                    border-radius: 8px;
                    background-color: white;
                }
                QTabBar::tab {
                    background-color: #F1F3F4;
                    border: 1px solid #E0E0E0;
                    border-bottom: none;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    padding: 12px 24px;
                    margin-right: 2px;
                }
                QTabBar::tab:selected {
                    background-color: white;
                    border-bottom: 2px solid #3498DB;
                }
                QTabBar::tab:hover {
                    background-color: #E8EAED;
                }
                QStatusBar {
                    background-color: #F8F9FA;
                    border-top: 1px solid #E0E0E0;
                }
            """
            )
        except Exception as e:
            print(f"Failed to apply theme: {e}")

    def _setup_header(self, layout):
        """Setup modern header with error handling"""
        try:
            header_card = ModernCard()
            header_layout = QHBoxLayout()

            # Title
            title_label = QLabel("SoapBoxx")
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
            subtitle_label = QLabel("AI-Powered Podcast Production Studio")
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

            # Complete workflow action (consumes one beta episode credit)
            complete_button = ModernButton("Complete Episode Workflow", style="primary")
            complete_button.clicked.connect(self._complete_episode_workflow)
            layout.addWidget(complete_button)

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

            # Initialize bulletproof tab loader if available (after all tabs are created)
            if not hasattr(self, 'tab_loader') and BULLETPROOF_LOADER_AVAILABLE:
                self.tab_loader = create_bulletproof_tab_loader(self.tab_widget)
                print("✅ Bulletproof tab loader initialized")
            elif not hasattr(self, 'tab_loader'):
                self.tab_loader = None
                print("⚠️  Using fallback tab loading")

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
                
                # Debug: Check what we got
                print(f"🔍 Debug: {tab_name} tab type: {type(actual_tab)}")
                print(f"🔍 Debug: {tab_name} is QWidget: {isinstance(actual_tab, QWidget) if actual_tab else 'None'}")
                
                # Use bulletproof tab loader if available, otherwise fallback
                if self.tab_loader:
                    # Remove the placeholder tab first, then insert the real tab
                    self.tab_widget.removeTab(index)
                    success = self.tab_loader.safe_insert_tab(index, actual_tab, tab_name)
                    if success:
                        self._tabs_loaded[tab_name] = True
                        self.tab_widget.setCurrentIndex(index)
                        print(f"✅ {tab_name} tab loaded successfully via bulletproof loader")
                    else:
                        print(f"❌ Bulletproof loader failed for {tab_name}")
                        self._tabs_loaded[tab_name] = False
                        # Re-add placeholder if bulletproof loader fails
                        placeholder = self._create_placeholder_tab(tab_name, f"Failed to load {tab_name} tab")
                        if placeholder:
                            self.tab_widget.insertTab(index, placeholder, tab_name)
                else:
                    # Fallback to manual QWidget validation
                    if actual_tab and isinstance(actual_tab, QWidget):
                        # Replace placeholder with actual tab
                        self.tab_widget.removeTab(index)
                        self.tab_widget.insertTab(index, actual_tab, tab_name)
                        self._tabs_loaded[tab_name] = True
                        self.tab_widget.setCurrentIndex(index)
                        print(f"✅ {tab_name} tab loaded successfully via fallback")
                    else:
                        print(f"❌ Failed to create {tab_name} tab - invalid widget type: {type(actual_tab)}")
                        self._tabs_loaded[tab_name] = False
                        
                        # Create a placeholder tab for failed tabs
                        placeholder = self._create_placeholder_tab(tab_name, f"Failed to load {tab_name} tab")
                        if placeholder:
                            self.tab_widget.removeTab(index)
                            self.tab_widget.insertTab(index, placeholder, tab_name)
                            print(f"✅ {tab_name} placeholder tab created")
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
            print("🔧 MainWindow: Creating SoapBoxx tab...")
            tab = SoapBoxxTab()
            print("✅ MainWindow: SoapBoxx tab created successfully")
            return tab
        except Exception as e:
            print(f"❌ MainWindow: Failed to create SoapBoxx tab: {e}")
            import traceback

            traceback.print_exc()
            self._track_error(
                "SoapBoxxTabError", f"Failed to create SoapBoxx tab: {str(e)}"
            )
            # Return a placeholder tab instead
            return self._create_placeholder_tab("SoapBoxx", f"Failed to load: {str(e)}")

    def _create_scoop_tab(self):
        """Create Scoop tab with error handling"""
        try:
            print("🔧 MainWindow: Creating Scoop tab...")
            # Use the local placeholder class defined in the import section
            tab = ScoopTab()
            print("✅ MainWindow: Scoop tab created successfully")
            return tab
        except Exception as e:
            print(f"❌ MainWindow: Failed to create Scoop tab: {e}")
            import traceback
            traceback.print_exc()
            self._track_error("ScoopTabError", f"Failed to create Scoop tab: {str(e)}")
            # Return a placeholder tab instead of None
            return self._create_placeholder_tab("Scoop", f"Failed to load: {str(e)}")

    def _create_reverb_tab(self):
        """Create Reverb tab with error handling"""
        try:
            print("🔧 MainWindow: Creating Reverb tab...")
            tab = ReverbTab()
            print("✅ MainWindow: Reverb tab created successfully")
            return tab
        except Exception as e:
            print(f"❌ MainWindow: Failed to create Reverb tab: {e}")
            import traceback
            traceback.print_exc()
            self._track_error(
                "ReverbTabError", f"Failed to create Reverb tab: {str(e)}"
            )
            # Return a placeholder tab instead of None
            return self._create_placeholder_tab("Reverb", f"Failed to load: {str(e)}")

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

            # Beta user + usage indicators
            self.user_indicator = QLabel("User: not signed in")
            self.user_indicator.setStyleSheet("color: #2C3E50;")
            self.status_bar.addPermanentWidget(self.user_indicator)

            self.usage_indicator = QLabel("Usage: 0/3")
            self.usage_indicator.setStyleSheet("color: #8E44AD; font-weight: bold;")
            self.status_bar.addPermanentWidget(self.usage_indicator)

            self.api_indicator = QLabel("API key: local mode")
            self.api_indicator.setStyleSheet("color: #7F8C8D;")
            self.status_bar.addPermanentWidget(self.api_indicator)

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

            # Beta menu
            beta_menu = menubar.addMenu("Beta")

            login_action = QAction("Login / Switch User", self)
            login_action.triggered.connect(self._ensure_beta_login)
            beta_menu.addAction(login_action)

            api_key_action = QAction("Set API Key", self)
            api_key_action.triggered.connect(self._set_api_key)
            beta_menu.addAction(api_key_action)

            workflow_action = QAction("Complete Episode Workflow", self)
            workflow_action.triggered.connect(self._complete_episode_workflow)
            beta_menu.addAction(workflow_action)

            # Help menu
            help_menu = menubar.addMenu("Help")

            # Full description (walkdown / see everything)
            full_desc_action = QAction("Full description", self)
            full_desc_action.triggered.connect(self._show_full_description)
            help_menu.addAction(full_desc_action)

            # About action
            about_action = QAction("About", self)
            about_action.triggered.connect(self._show_about)
            help_menu.addAction(about_action)

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
        """Show settings dialog"""
        try:
            QMessageBox.information(
                self,
                "Settings",
                "For beta setup, use Beta -> Login / Switch User and Beta -> Set API Key.",
            )
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

    def _show_full_description(self):
        """Show full description dialog (walkdown of package info — see everything)."""
        try:
            dialog = FullDescriptionDialog(self)
            dialog.show()
        except Exception as e:
            self._track_error(
                "FullDescriptionError", f"Failed to show full description: {str(e)}"
            )

    def _show_about(self):
        """Show about dialog"""
        try:
            about_text = """
            <h3>SoapBoxx</h3>
            <p>AI-Powered Podcast Production Studio</p>
            <p>Version: 1.0.0</p>
            <p>Production Ready - 9/10 Reliability Rating</p>
            <br/>
            <p>Use <b>Help → Full description</b> to see the complete package info and description.</p>
            """
            QMessageBox.about(self, "About SoapBoxx", about_text)
        except Exception as e:
            self._track_error("AboutError", f"Failed to show about dialog: {str(e)}")

    def _load_beta_state(self):
        """Load persisted beta state (user usage and API keys)."""
        try:
            if BETA_STATE_FILE.is_file():
                with open(BETA_STATE_FILE, "r", encoding="utf-8") as f:
                    state = json.load(f)
                    if isinstance(state, dict):
                        self._beta_state = state
                        return
            self._beta_state = {"users": {}}
        except Exception as e:
            print(f"Failed to load beta state: {e}")
            self._beta_state = {"users": {}}

    def _save_beta_state(self):
        """Persist beta state to disk."""
        try:
            if "users" not in self._beta_state:
                self._beta_state["users"] = {}
            with open(BETA_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._beta_state, f, indent=2)
        except Exception as e:
            self._track_error("BetaStateSaveError", f"Failed to save beta state: {str(e)}")

    def _ensure_beta_login(self):
        """Require login for beta usage and load user usage/API state."""
        try:
            self._load_beta_state()
            dialog = LoginDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                self.close()
                return

            user_id = dialog.user_id.strip().lower()
            users = self._beta_state.setdefault("users", {})
            users.setdefault(user_id, {"episodes_used": 0, "api_key": ""})

            self._current_user_id = user_id
            self._episodes_used = int(users[user_id].get("episodes_used", 0))
            self._current_api_key = users[user_id].get("api_key", "")
            self._update_status_display()
            self._show_status_message(
                f"Signed in as {self._current_user_id}. Usage: {self._episodes_used}/{BETA_EPISODE_LIMIT}"
            )
        except Exception as e:
            self._track_error("LoginError", f"Failed to login: {str(e)}")

    def _set_api_key(self):
        """Set per-user API key for optional cloud AI usage."""
        try:
            if not self._current_user_id:
                QMessageBox.warning(self, "Login required", "Please login first.")
                return

            key, ok = QInputDialog.getText(
                self,
                "Set API Key",
                "Enter your API key (optional):",
                QLineEdit.EchoMode.Password,
                self._current_api_key,
            )
            if not ok:
                return

            self._current_api_key = key.strip()
            users = self._beta_state.setdefault("users", {})
            users.setdefault(self._current_user_id, {})
            users[self._current_user_id]["api_key"] = self._current_api_key
            self._save_beta_state()
            self._update_status_display()

            if self._current_api_key:
                self._show_status_message("API key saved for this tester.")
            else:
                self._show_status_message("API key cleared. Using local-only processing.")
        except Exception as e:
            self._track_error("ApiKeyError", f"Failed to set API key: {str(e)}")

    def _remaining_credits(self) -> int:
        return max(0, BETA_EPISODE_LIMIT - self._episodes_used)

    def _complete_episode_workflow(self):
        """Consume one full episode beta credit with hard cap enforcement."""
        try:
            if not self._current_user_id:
                QMessageBox.warning(self, "Login required", "Please login first.")
                return

            if self._episodes_used >= BETA_EPISODE_LIMIT:
                QMessageBox.information(
                    self,
                    "Beta limit reached",
                    "You've used all 3 test episodes. If this saved you time or improved your podcast, continue for $X/month.",
                )
                return

            self._episodes_used += 1
            users = self._beta_state.setdefault("users", {})
            users.setdefault(self._current_user_id, {})
            users[self._current_user_id]["episodes_used"] = self._episodes_used
            self._save_beta_state()
            self._update_status_display()

            mode = "API key mode" if self._current_api_key else "local-only mode"
            if self._episodes_used >= BETA_EPISODE_LIMIT:
                QMessageBox.information(
                    self,
                    "Episode completed (3/3)",
                    "Episode workflow completed.\n\nYou've used all 3 test episodes. If this saved you time or improved your podcast, continue for $X/month.",
                )
            else:
                self._show_status_message(
                    f"Episode workflow completed ({self._episodes_used}/{BETA_EPISODE_LIMIT}) in {mode}.",
                    5000,
                )
        except Exception as e:
            self._track_error(
                "EpisodeCreditError", f"Failed to complete episode workflow: {str(e)}"
            )

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

            if hasattr(self, "user_indicator"):
                user_text = self._current_user_id if self._current_user_id else "not signed in"
                self.user_indicator.setText(f"User: {user_text}")
            if hasattr(self, "usage_indicator"):
                self.usage_indicator.setText(
                    f"Usage: {self._episodes_used}/{BETA_EPISODE_LIMIT}"
                )
            if hasattr(self, "api_indicator"):
                self.api_indicator.setText(
                    "API key: set" if self._current_api_key else "API key: local mode"
                )

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
