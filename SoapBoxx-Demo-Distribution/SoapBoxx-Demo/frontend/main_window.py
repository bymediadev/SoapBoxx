#!/usr/bin/env python3
"""
SoapBoxx Main Window
Main application window with tabbed interface
"""

import json
import os
import re
import sys
import traceback
import webbrowser
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Project root so `from backend.notify_client import ...` resolves (IDE + runtime).
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
# Legacy: top-level imports like `import notify_client` (same as before)
backend_dir = os.path.join(_project_root, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Avoid Windows cp1252 crashes when printing unicode symbols.
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

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

# Normal beta: 3 episodes. Set SOAPBOXX_DEV_PLAYGROUND=1 to relax limits while testing locally.
def _episode_limit_for_build():
    v = os.environ.get("SOAPBOXX_DEV_PLAYGROUND", "").strip().lower()
    if v in ("1", "true", "yes"):
        return 999
    return 3


BETA_EPISODE_LIMIT = _episode_limit_for_build()
BETA_STATE_FILE = Path(__file__).resolve().parent.parent / ".soapboxx_beta_state.json"
BETA_CONFIG_FILE = Path(__file__).resolve().parent.parent / "beta_config.json"
BETA_EVENTS_JSONL = Path(__file__).resolve().parent.parent / "beta_events.jsonl"


def _load_beta_config():
    """Optional admin email + notes. No SMTP in demo — see beta_events.jsonl for local tracking."""
    defaults = {
        "admin_email": "",
        "notes": "Optional: recipient for alerts if MAIL_TO is unset in .env. Use a different address than your sending Gmail unless you want self-copies.",
    }
    try:
        if BETA_CONFIG_FILE.is_file():
            with open(BETA_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    defaults.update(data)
    except Exception as e:
        print(f"beta_config: {e}")
    return defaults


def _log_beta_event(event: str, user_id: str, detail=None):
    """Append-only local log + optional admin email (see backend/notify_client.py, .env)."""
    cfg = _load_beta_config()
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "user_id": user_id,
        "admin_email_configured": bool((cfg.get("admin_email") or "").strip()),
    }
    if detail:
        row["detail"] = detail
    try:
        with open(BETA_EVENTS_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"beta_events log failed: {e}")
    try:
        from backend.notify_client import notify_admin_async

        notify_admin_async(event, user_id, detail)
    except Exception as e:
        print(f"notify_client: {e}")

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


def _get_github_setup_urls():
    """Repo page and ZIP for local setup from PACKAGE_INFO."""
    info = _load_package_info() or {}
    repo = (info.get("github_repo_url") or info.get("homepage") or "").strip()
    zip_url = (info.get("github_zip_url") or "").strip()
    branch = (info.get("github_clone_branch") or "main").strip()
    release_demo_zip = (info.get("github_release_demo_zip_url") or "").strip()
    if repo and not zip_url:
        m = re.match(r"https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", repo.rstrip("/"))
        if m:
            zip_url = f"https://github.com/{m.group(1)}/{m.group(2)}/archive/refs/heads/{branch}.zip"
    return {
        "repo": repo,
        "zip": zip_url,
        "branch": branch,
        "release_demo_zip": release_demo_zip,
    }


def _default_user_record():
    return {
        "episodes_used": 0,
        "api_key": "",
        "api_keys": {
            "openai": "",
            "google": "",
            "other_name": "",
            "other_key": "",
        },
    }


def _migrate_user_record(user: dict):
    """Merge legacy single api_key into api_keys."""
    if not isinstance(user, dict):
        return
    if "api_keys" not in user or not isinstance(user["api_keys"], dict):
        user["api_keys"] = {
            "openai": (user.get("api_key") or "").strip(),
            "google": "",
            "other_name": "",
            "other_key": "",
        }
    else:
        legacy = (user.get("api_key") or "").strip()
        if legacy and not (user["api_keys"].get("openai") or "").strip():
            user["api_keys"]["openai"] = legacy


def _apply_api_keys_to_environ(keys: dict):
    """Expose keys to backend code that reads os.environ."""
    oa = (keys.get("openai") or "").strip()
    ga = (keys.get("google") or "").strip()
    ok = (keys.get("other_key") or "").strip()
    if oa:
        os.environ["OPENAI_API_KEY"] = oa
    else:
        os.environ.pop("OPENAI_API_KEY", None)
    if ga:
        os.environ["GOOGLE_API_KEY"] = ga
    else:
        os.environ.pop("GOOGLE_API_KEY", None)
    if ok:
        os.environ["CUSTOM_AI_API_KEY"] = ok
        on = (keys.get("other_name") or "custom").strip()
        os.environ["CUSTOM_AI_PROVIDER"] = on
    else:
        os.environ.pop("CUSTOM_AI_API_KEY", None)
        os.environ.pop("CUSTOM_AI_PROVIDER", None)


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
        repo_url = (info.get("github_repo_url") or info.get("homepage") or "").strip()
        repo_parts = []
        if repo_url:
            repo_parts.append(f"<p><a href=\"{repo_url}\">{repo_url}</a></p>")
        https_git = ""
        if repo_url.startswith("https://github.com/"):
            https_git = repo_url.rstrip("/")
            if not https_git.endswith(".git"):
                https_git = https_git + ".git"
        if https_git:
            repo_parts.append(
                f"<p><strong>Clone (HTTPS):</strong> <code>git clone {https_git}</code></p>"
            )
        ssh = (info.get("github_repo_ssh") or "").strip()
        if ssh:
            repo_parts.append(
                f"<p><strong>Clone (SSH):</strong> <code>git clone {ssh}</code></p>"
                "<p><small>Requires GitHub SSH keys.</small></p>"
            )
        repo_html = "".join(repo_parts) if repo_parts else "<p>—</p>"
        zip_url = (info.get("github_zip_url") or "").strip()
        release_demo = (info.get("github_release_demo_zip_url") or "").strip()
        branch = (info.get("github_clone_branch") or "").strip()
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
            "<h3>Repository</h3>",
            repo_html,
            "<h3>Source download (ZIP)</h3>",
            f"<p><a href=\"{zip_url}\">{zip_url}</a></p>" if zip_url else "<p>—</p>",
            "<h3>Release ZIP (ready-made demo folder)</h3>",
            (
                f"<p><a href=\"{release_demo}\">{release_demo}</a></p>"
                if release_demo
                else "<p>—</p>"
            ),
            "<h3>Default clone branch</h3>",
            f"<p><code>{branch}</code></p>" if branch else "<p>—</p>",
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


class AuthPortalDialog(QDialog):
    """Login + sign-up portal shown before the main window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SoapBoxx — Sign in")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.user_id = ""
        self.auth_method = "id"
        self.is_signup = False
        self._setup_ui()

    def _load_users_state(self):
        try:
            if BETA_STATE_FILE.is_file():
                with open(BETA_STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "users" in data:
                        return data
        except Exception:
            pass
        return {"users": {}}

    def _save_users_state(self, state):
        try:
            with open(BETA_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Save error", f"Could not save account data: {e}")

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("SoapBoxx Beta")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #2C3E50;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Sign in or create an account to start your 3-episode trial.\n"
            "Signups/logins are recorded locally in beta_events.jsonl (no email is sent from this demo)."
        )
        subtitle.setStyleSheet("color: #7F8C8D;")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        tabs = QTabWidget()
        # --- Login tab ---
        login_page = QWidget()
        login_layout = QVBoxLayout(login_page)

        lg = QGroupBox("Sign in")
        lg_form = QFormLayout()
        self.login_email = QLineEdit()
        self.login_email.setPlaceholderText("you@example.com")
        lg_form.addRow("Email:", self.login_email)

        self.magic_link_button = ModernButton("Send Magic Link", style="secondary")
        self.magic_link_button.clicked.connect(self._send_magic_link)
        lg_form.addRow("", self.magic_link_button)

        self.login_tester_id = QLineEdit()
        self.login_tester_id.setPlaceholderText("Or use tester ID (e.g. tester-001)")
        lg_form.addRow("Tester ID:", self.login_tester_id)

        lg.setLayout(lg_form)
        login_layout.addWidget(lg)

        login_btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        login_btns.accepted.connect(self._on_login)
        login_btns.rejected.connect(self.reject)
        login_layout.addWidget(login_btns)

        tabs.addTab(login_page, "Login")

        # --- Sign up tab ---
        signup_page = QWidget()
        signup_layout = QVBoxLayout(signup_page)

        sg = QGroupBox("Create account")
        sg_form = QFormLayout()
        self.signup_email = QLineEdit()
        self.signup_email.setPlaceholderText("you@example.com")
        sg_form.addRow("Email:", self.signup_email)

        self.signup_email_confirm = QLineEdit()
        self.signup_email_confirm.setPlaceholderText("confirm email")
        sg_form.addRow("Confirm email:", self.signup_email_confirm)

        self.signup_password = QLineEdit()
        self.signup_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.signup_password.setPlaceholderText("optional (local demo)")
        sg_form.addRow("Password:", self.signup_password)

        self.signup_password_confirm = QLineEdit()
        self.signup_password_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        sg_form.addRow("Confirm password:", self.signup_password_confirm)

        sg.setLayout(sg_form)
        signup_layout.addWidget(sg)

        su_btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        su_btns.accepted.connect(self._on_signup)
        su_btns.rejected.connect(self.reject)
        signup_layout.addWidget(su_btns)

        tabs.addTab(signup_page, "Sign up")

        # --- Setup tab ---
        setup_page = QWidget()
        setup_layout = QVBoxLayout(setup_page)

        setup_info = QLabel(
            "Configure local setup and API keys before opening the main app."
        )
        setup_info.setWordWrap(True)
        setup_info.setStyleSheet("color: #7F8C8D;")
        setup_layout.addWidget(setup_info)

        setup_group = QGroupBox("Portal settings")
        setup_form = QFormLayout()
        self.setup_identity = QLineEdit()
        self.setup_identity.setPlaceholderText("email or tester ID")
        setup_form.addRow("Account:", self.setup_identity)

        setup_group.setLayout(setup_form)
        setup_layout.addWidget(setup_group)

        setup_buttons = QHBoxLayout()
        setup_api_btn = ModernButton("Set API Keys", style="primary")
        setup_api_btn.clicked.connect(self._open_portal_api_keys)
        setup_buttons.addWidget(setup_api_btn)

        setup_git_btn = ModernButton("GitHub Local Setup", style="secondary")
        setup_git_btn.clicked.connect(self._open_portal_local_setup)
        setup_buttons.addWidget(setup_git_btn)
        setup_layout.addLayout(setup_buttons)

        setup_hint = QLabel(
            "Tip: If account doesn't exist yet, we create it automatically when saving API keys."
        )
        setup_hint.setWordWrap(True)
        setup_hint.setStyleSheet("color: #7F8C8D; font-size: 12px;")
        setup_layout.addWidget(setup_hint)

        tabs.addTab(setup_page, "Setup")

        layout.addWidget(tabs)

        hint = QLabel("Usage is tracked per account: 1/3, 2/3, 3/3 full episodes.")
        hint.setStyleSheet("color: #7F8C8D; font-size: 12px;")
        layout.addWidget(hint)

    def _send_magic_link(self):
        email = self.login_email.text().strip()
        if not email:
            QMessageBox.information(
                self, "Email required", "Enter your email first, then click Send Magic Link."
            )
            return
        _log_beta_event(
            "magic_link_demo",
            email.lower(),
            {"note": "No real email sent; configure SMTP + MAIL_TO in .env for alerts to your chosen recipient."},
        )
        cfg = _load_beta_config()
        admin = (cfg.get("admin_email") or "").strip()
        extra = (
            f"\n\nAlert recipient configured (beta_config): {admin}"
            if admin
            else "\n\nSet MAIL_TO in .env (who receives alerts). Use a different address than your sending Gmail if you prefer."
        )
        QMessageBox.information(
            self,
            "Magic Link (demo)",
            f"This demo does not send a real email.\n"
            f"We logged this request for {email}.\n"
            f"Go to Login and click OK to continue.{extra}",
        )

    def _on_login(self):
        email = self.login_email.text().strip()
        tester_id = self.login_tester_id.text().strip()

        value = ""
        if email:
            value = email
            self.auth_method = "magic_link"
        elif tester_id:
            value = tester_id
            self.auth_method = "id"

        if not value:
            QMessageBox.warning(
                self, "Login required", "Enter your email or a tester ID."
            )
            return

        if "@" in value:
            if "." not in value.split("@")[-1]:
                QMessageBox.warning(self, "Invalid email", "Please enter a valid email address.")
                return
        uid = value.strip().lower()
        state = self._load_users_state()
        users = state.setdefault("users", {})
        if uid not in users:
            QMessageBox.information(
                self,
                "No account",
                "No account found for that sign-in. Use the Sign up tab first.",
            )
            return

        self.user_id = uid
        self.is_signup = False
        _log_beta_event("login", uid, {"auth_method": self.auth_method})
        self.accept()

    def _on_signup(self):
        e1 = self.signup_email.text().strip()
        e2 = self.signup_email_confirm.text().strip()
        p1 = self.signup_password.text()
        p2 = self.signup_password_confirm.text()

        if not e1 or not e2:
            QMessageBox.warning(self, "Sign up", "Enter and confirm your email.")
            return
        if e1.lower() != e2.lower():
            QMessageBox.warning(self, "Sign up", "Emails do not match.")
            return
        if "@" not in e1 or "." not in e1.split("@")[-1]:
            QMessageBox.warning(self, "Sign up", "Please enter a valid email address.")
            return
        if p1 or p2:
            if p1 != p2:
                QMessageBox.warning(self, "Sign up", "Passwords do not match.")
                return

        uid = e1.lower()
        state = self._load_users_state()
        users = state.setdefault("users", {})
        if uid in users:
            QMessageBox.information(
                self,
                "Account exists",
                "An account with this email already exists. Use the Login tab.",
            )
            return

        rec = _default_user_record()
        if p1:
            rec["password_hint"] = "set"
        users[uid] = rec
        self._save_users_state(state)

        self.user_id = uid
        self.auth_method = "signup"
        self.is_signup = True
        _log_beta_event("signup", uid, {"has_password": bool(p1)})
        self.accept()

    def _open_portal_local_setup(self):
        """Open GitHub local setup dialog from auth portal."""
        try:
            LocalSetupDialog(self).exec()
        except Exception as e:
            QMessageBox.warning(self, "Setup error", f"Could not open local setup: {e}")

    def _open_portal_api_keys(self):
        """Configure API keys from auth portal before entering app."""
        try:
            identity = self.setup_identity.text().strip().lower()
            if not identity:
                # Fallback to login form values if present
                identity = (
                    self.login_email.text().strip().lower()
                    or self.login_tester_id.text().strip().lower()
                )
            if not identity:
                QMessageBox.information(
                    self,
                    "Account needed",
                    "Enter an email or tester ID in the Setup tab first.",
                )
                return

            state = self._load_users_state()
            users = state.setdefault("users", {})
            if identity not in users:
                users[identity] = _default_user_record()
            _migrate_user_record(users[identity])

            dlg = ApiKeysDialog(users[identity].get("api_keys", {}), self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return

            new_keys = dlg.get_keys()
            users[identity]["api_keys"] = new_keys
            users[identity]["api_key"] = new_keys.get("openai", "")
            self._save_users_state(state)
            _log_beta_event(
                "api_keys_saved_portal",
                identity,
                {
                    "has_openai": bool(new_keys.get("openai")),
                    "has_google": bool(new_keys.get("google")),
                    "has_other": bool(new_keys.get("other_key")),
                },
            )
            QMessageBox.information(
                self,
                "Saved",
                f"API keys saved for {identity}. You can now log in and continue.",
            )
        except Exception as e:
            QMessageBox.warning(self, "Setup error", f"Could not save API keys: {e}")


class ApiKeysDialog(QDialog):
    """Configure OpenAI, Google, and custom provider keys anytime."""

    def __init__(self, keys: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API Keys — AI services")
        self.setModal(True)
        self._keys = dict(keys)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Add keys for cloud AI when you want them. Leave blank to use local-only processing."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #7F8C8D;")
        layout.addWidget(intro)

        form = QFormLayout()
        self.openai_edit = QLineEdit()
        self.openai_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_edit.setText(self._keys.get("openai", ""))
        self.openai_edit.setPlaceholderText("sk-...")
        form.addRow("OpenAI:", self.openai_edit)

        self.google_edit = QLineEdit()
        self.google_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.google_edit.setText(self._keys.get("google", ""))
        form.addRow("Google API:", self.google_edit)

        self.other_name = QLineEdit()
        self.other_name.setText(self._keys.get("other_name", ""))
        self.other_name.setPlaceholderText("e.g. Anthropic, Azure, custom")
        form.addRow("Other provider name:", self.other_name)

        self.other_key = QLineEdit()
        self.other_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.other_key.setText(self._keys.get("other_key", ""))
        form.addRow("Other API key:", self.other_key)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_keys(self) -> dict:
        return {
            "openai": self.openai_edit.text().strip(),
            "google": self.google_edit.text().strip(),
            "other_name": self.other_name.text().strip(),
            "other_key": self.other_key.text().strip(),
        }


class LocalSetupDialog(QDialog):
    """Open GitHub repo / ZIP and copy clone command for local setup."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download from GitHub — local setup")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        urls = _get_github_setup_urls()
        repo = urls["repo"] or "(set github_repo_url in PACKAGE_INFO.json)"
        zip_u = urls["zip"] or ""
        branch = urls["branch"]
        rel = urls.get("release_demo_zip") or ""

        info = QLabel(
            "Clone the repo or download source ZIP. "
            "Testers can use a GitHub Release ZIP (ready-made SoapBoxx-Demo folder) when configured — no branch checkout."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        if rel:
            layout.addWidget(
                QLabel("Release ZIP (testers — unzip, then open SoapBoxx-Demo):")
            )
            rel_row = QHBoxLayout()
            open_rel = ModernButton("Open release ZIP", style="primary")
            open_rel.clicked.connect(
                lambda: webbrowser.open(rel) if rel.startswith("http") else None
            )
            rel_row.addWidget(open_rel)
            layout.addLayout(rel_row)

        layout.addWidget(QLabel(f"Repository: {repo}"))
        if zip_u:
            layout.addWidget(QLabel(f"Source ZIP (branch archive): {zip_u}"))

        row = QHBoxLayout()
        open_repo = ModernButton("Open repository page", style="secondary")
        open_repo.clicked.connect(lambda: webbrowser.open(repo) if repo.startswith("http") else None)
        row.addWidget(open_repo)

        open_zip = ModernButton("Download source ZIP", style="secondary")
        open_zip.clicked.connect(lambda: webbrowser.open(zip_u) if zip_u.startswith("http") else None)
        row.addWidget(open_zip)
        layout.addLayout(row)

        clone_cmd = ""
        if repo.startswith("https://github.com/"):
            base = repo.rstrip("/").replace(".git", "")
            clone_cmd = f"git clone -b {branch} {base}.git"
        self.clone_label = QLabel(clone_cmd or "git clone <your-repo-url>")
        self.clone_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(QLabel("Clone command:"))
        layout.addWidget(self.clone_label)

        copy_btn = ModernButton("Copy clone command", style="secondary")
        copy_btn.clicked.connect(self._copy_clone)
        layout.addWidget(copy_btn)

        close_btn = ModernButton("Close", style="primary")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _copy_clone(self):
        text = self.clone_label.text()
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copied", "Clone command copied to clipboard.")


class AppSettingsDialog(QDialog):
    """In-app settings hub for account, API keys, and local setup."""

    def __init__(self, user_id: str, episodes_used: int, limit: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SoapBoxx Settings")
        self.setModal(True)
        self.setMinimumWidth(520)
        self._user_id = user_id
        self._episodes_used = episodes_used
        self._limit = limit
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # Account tab
        account_page = QWidget()
        account_layout = QFormLayout(account_page)
        account_layout.addRow("Signed in user:", QLabel(self._user_id or "not signed in"))
        account_layout.addRow("Episode usage:", QLabel(f"{self._episodes_used}/{self._limit}"))
        tabs.addTab(account_page, "Account")

        # API tab
        api_page = QWidget()
        api_layout = QVBoxLayout(api_page)
        api_desc = QLabel("Manage OpenAI, Google, and custom provider keys.")
        api_desc.setStyleSheet("color: #7F8C8D;")
        api_layout.addWidget(api_desc)
        api_btn = ModernButton("Open API Keys", style="primary")
        api_btn.clicked.connect(self._open_api_keys)
        api_layout.addWidget(api_btn)
        api_layout.addStretch()
        tabs.addTab(api_page, "API Keys")

        # Local setup tab
        setup_page = QWidget()
        setup_layout = QVBoxLayout(setup_page)
        setup_desc = QLabel("Download/clone everything needed for local setup.")
        setup_desc.setStyleSheet("color: #7F8C8D;")
        setup_layout.addWidget(setup_desc)
        setup_btn = ModernButton("Open GitHub Local Setup", style="secondary")
        setup_btn.clicked.connect(self._open_local_setup)
        setup_layout.addWidget(setup_btn)
        setup_layout.addStretch()
        tabs.addTab(setup_page, "Local Setup")

        layout.addWidget(tabs)

        close_btn = ModernButton("Close", style="primary")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _open_api_keys(self):
        if self.parent() and hasattr(self.parent(), "_set_api_key"):
            self.parent()._set_api_key()

    def _open_local_setup(self):
        if self.parent() and hasattr(self.parent(), "_show_local_setup_dialog"):
            self.parent()._show_local_setup_dialog()


class MainWindow(QMainWindow):
    """Main application window with enhanced resilience and error handling"""

    def __init__(self, pre_auth_user_id=None, pre_auth_method=None, pre_signup=False):
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

            # Session (startup auth runs in main() before this window is shown)
            if pre_auth_user_id:
                self._apply_user_session(pre_auth_user_id, pre_auth_method, pre_signup)
            else:
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

            github_button = ModernButton("GitHub setup", style="secondary")
            github_button.clicked.connect(self._show_local_setup_dialog)
            layout.addWidget(github_button)

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

            # Download everything bundle
            download_all_action = QAction("Download Everything", self)
            download_all_action.triggered.connect(self._download_everything)
            file_menu.addAction(download_all_action)

            github_setup_action = QAction("Download from GitHub (local setup)", self)
            github_setup_action.triggered.connect(self._show_local_setup_dialog)
            file_menu.addAction(github_setup_action)

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

            api_key_action = QAction("API Keys…", self)
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
        """Show in-app settings portal."""
        try:
            dlg = AppSettingsDialog(
                self._current_user_id, self._episodes_used, BETA_EPISODE_LIMIT, self
            )
            dlg.exec()
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

    def _download_everything(self):
        """Create a zip bundle of the demo project data for easy download/sharing."""
        try:
            project_root = Path(__file__).resolve().parent.parent
            downloads_dir = project_root / "Downloads"
            downloads_dir.mkdir(exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_path = downloads_dir / f"soapboxx_everything_{stamp}.zip"

            excluded_dirs = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules"}
            excluded_suffixes = {".pyc", ".pyo"}

            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for file_path in project_root.rglob("*"):
                    if not file_path.is_file():
                        continue
                    if any(part in excluded_dirs for part in file_path.parts):
                        continue
                    if file_path.suffix.lower() in excluded_suffixes:
                        continue
                    if file_path.resolve() == zip_path.resolve():
                        continue
                    arcname = file_path.relative_to(project_root)
                    zf.write(file_path, arcname)

            QMessageBox.information(
                self,
                "Download Everything",
                f"Bundle created successfully:\n{zip_path}",
            )
            self._show_status_message(f"Download bundle created: {zip_path}", 8000)
        except Exception as e:
            self._track_error(
                "DownloadEverythingError",
                f"Failed to create full download bundle: {str(e)}",
            )
            self._show_user_friendly_error(
                "Download error",
                "Failed to create the full download bundle.",
                str(e),
            )

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

    def _get_user_api_keys_dict(self) -> dict:
        """Return api_keys for the signed-in user."""
        if not self._current_user_id:
            return {}
        users = self._beta_state.setdefault("users", {})
        u = users.get(self._current_user_id)
        if not u:
            return {}
        _migrate_user_record(u)
        return u.get("api_keys", {})

    def _has_any_api_key(self) -> bool:
        k = self._get_user_api_keys_dict()
        return any((k.get(x) or "").strip() for x in ("openai", "google", "other_key"))

    def _apply_user_session(self, user_id, auth_method=None, pre_signup=False):
        """Load credits and API keys for this account and sync environment."""
        try:
            self._load_beta_state()
            uid = (user_id or "").strip().lower()
            if not uid:
                return
            users = self._beta_state.setdefault("users", {})
            if uid not in users:
                users[uid] = _default_user_record()
            _migrate_user_record(users[uid])
            self._current_user_id = uid
            self._episodes_used = int(users[uid].get("episodes_used", 0))
            keys = self._get_user_api_keys_dict()
            _apply_api_keys_to_environ(keys)
            self._current_api_key = (keys.get("openai") or "").strip()
            self._update_status_display()
            if pre_signup:
                label = "new account"
            elif auth_method == "magic_link":
                label = "email"
            elif auth_method == "signup":
                label = "sign-up"
            else:
                label = "tester ID"
            self._show_status_message(
                f"Signed in ({label}) as {self._current_user_id}. Usage: {self._episodes_used}/{BETA_EPISODE_LIMIT}",
                5000,
            )
        except Exception as e:
            self._track_error("SessionError", f"Failed to apply user session: {str(e)}")

    def _ensure_beta_login(self):
        """Switch user / login from menu (does not quit the app on cancel)."""
        try:
            dialog = AuthPortalDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            self._apply_user_session(
                dialog.user_id, getattr(dialog, "auth_method", None), dialog.is_signup
            )
        except Exception as e:
            self._track_error("LoginError", f"Failed to login: {str(e)}")

    def _set_api_key(self):
        """Configure OpenAI, Google, and custom API keys (anytime)."""
        try:
            if not self._current_user_id:
                QMessageBox.warning(self, "Login required", "Please login first.")
                return

            self._load_beta_state()
            keys = self._get_user_api_keys_dict()
            dlg = ApiKeysDialog(keys, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return

            new_keys = dlg.get_keys()
            users = self._beta_state.setdefault("users", {})
            users.setdefault(self._current_user_id, _default_user_record())
            _migrate_user_record(users[self._current_user_id])
            users[self._current_user_id]["api_keys"] = new_keys
            users[self._current_user_id]["api_key"] = new_keys.get("openai", "")
            self._save_beta_state()
            _apply_api_keys_to_environ(new_keys)
            self._current_api_key = (new_keys.get("openai") or "").strip()
            self._update_status_display()
            self._show_status_message("API keys saved. They apply for this user on this machine.")
            _log_beta_event(
                "api_keys_saved_app",
                self._current_user_id,
                {
                    "has_openai": bool(new_keys.get("openai")),
                    "has_google": bool(new_keys.get("google")),
                    "has_other": bool(new_keys.get("other_key")),
                },
            )
        except Exception as e:
            self._track_error("ApiKeyError", f"Failed to set API key: {str(e)}")

    def _show_local_setup_dialog(self):
        """GitHub clone / ZIP for full local setup."""
        try:
            LocalSetupDialog(self).exec()
        except Exception as e:
            self._track_error("LocalSetupError", f"Failed to show local setup: {str(e)}")

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
                    f"You've used all {BETA_EPISODE_LIMIT} test episode(s). If this saved you time or improved your podcast, continue for $X/month.",
                )
                return

            self._episodes_used += 1
            users = self._beta_state.setdefault("users", {})
            users.setdefault(self._current_user_id, {})
            users[self._current_user_id]["episodes_used"] = self._episodes_used
            self._save_beta_state()
            self._update_status_display()

            mode = "API keys configured" if self._has_any_api_key() else "local-only mode"
            _log_beta_event(
                "episode_workflow",
                self._current_user_id,
                {"episodes_used": self._episodes_used, "limit": BETA_EPISODE_LIMIT},
            )
            if self._episodes_used >= BETA_EPISODE_LIMIT:
                QMessageBox.information(
                    self,
                    f"Episode completed ({BETA_EPISODE_LIMIT}/{BETA_EPISODE_LIMIT})",
                    "Episode workflow completed.\n\n"
                    "You've used all test episodes for this build. If this saved you time or improved your podcast, continue for $X/month.",
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
                    "API keys: configured"
                    if self._has_any_api_key()
                    else "API keys: local mode"
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

        # Login / sign-up portal first (before main window)
        print("Showing login portal...")
        portal = AuthPortalDialog()
        if portal.exec() != QDialog.DialogCode.Accepted:
            print("Login cancelled.")
            sys.exit(0)

        # Create and show main window
        print("Creating main window...")
        try:
            window = MainWindow(
                pre_auth_user_id=portal.user_id,
                pre_auth_method=getattr(portal, "auth_method", None),
                pre_signup=portal.is_signup,
            )
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
