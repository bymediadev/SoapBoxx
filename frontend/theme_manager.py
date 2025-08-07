#!/usr/bin/env python3
"""
Theme Manager for SoapBoxx
Handles dark mode and custom themes
"""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QApplication, QWidget


class ThemeManager(QObject):
    """Manages themes for SoapBoxx"""

    theme_changed = pyqtSignal(str)  # theme name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_theme = "modern_light"
        self.themes = {
            "modern_light": self._get_modern_light_theme(),
            "modern_dark": self._get_modern_dark_theme(),
            "modern_blue": self._get_modern_blue_theme(),
            "modern_green": self._get_modern_green_theme(),
            "light": self._get_light_theme(),
            "dark": self._get_dark_theme(),
            "blue": self._get_blue_theme(),
            "green": self._get_green_theme(),
        }

    def _get_modern_light_theme(self) -> dict:
        """Get modern light theme colors"""
        return {
            "window": "#FFFFFF",
            "window_text": "#2C3E50",
            "base": "#FFFFFF",
            "alternate_base": "#F8F9FA",
            "text": "#2C3E50",
            "button": "#3498DB",
            "button_text": "#FFFFFF",
            "bright_text": "#FFFFFF",
            "highlight": "#3498DB",
            "highlight_text": "#FFFFFF",
            "link": "#3498DB",
            "mid": "#E9ECEF",
            "dark": "#6C757D",
            "shadow": "#495057",
            "success": "#28A745",
            "warning": "#FFC107",
            "error": "#DC3545",
            "info": "#17A2B8",
            "primary": "#3498DB",
            "secondary": "#6C757D",
            "accent": "#E74C3C",
            "background": "#FFFFFF",
            "surface": "#F8F9FA",
            "border": "#DEE2E6",
            "card": "#FFFFFF",
            "card_shadow": "0 2px 4px rgba(0,0,0,0.1)",
        }

    def _get_modern_dark_theme(self) -> dict:
        """Get modern dark theme colors"""
        return {
            "window": "#1A1A1A",
            "window_text": "#FFFFFF",
            "base": "#2D2D2D",
            "alternate_base": "#3A3A3A",
            "text": "#FFFFFF",
            "button": "#3498DB",
            "button_text": "#FFFFFF",
            "bright_text": "#FFFFFF",
            "highlight": "#3498DB",
            "highlight_text": "#FFFFFF",
            "link": "#74B9FF",
            "mid": "#4A4A4A",
            "dark": "#2D2D2D",
            "shadow": "#1A1A1A",
            "success": "#00B894",
            "warning": "#FDCB6E",
            "error": "#E17055",
            "info": "#74B9FF",
            "primary": "#3498DB",
            "secondary": "#6C757D",
            "accent": "#E74C3C",
            "background": "#1A1A1A",
            "surface": "#2D2D2D",
            "border": "#4A4A4A",
            "card": "#2D2D2D",
            "card_shadow": "0 2px 4px rgba(0,0,0,0.3)",
        }

    def _get_modern_blue_theme(self) -> dict:
        """Get modern blue theme colors"""
        return {
            "window": "#E3F2FD",
            "window_text": "#1565C0",
            "base": "#FFFFFF",
            "alternate_base": "#F3F8FF",
            "text": "#1565C0",
            "button": "#2196F3",
            "button_text": "#FFFFFF",
            "bright_text": "#FFFFFF",
            "highlight": "#1976D2",
            "highlight_text": "#FFFFFF",
            "link": "#1565C0",
            "mid": "#BBDEFB",
            "dark": "#1976D2",
            "shadow": "#0D47A1",
            "success": "#4CAF50",
            "warning": "#FF9800",
            "error": "#F44336",
            "info": "#2196F3",
            "primary": "#2196F3",
            "secondary": "#6C757D",
            "accent": "#FF5722",
            "background": "#E3F2FD",
            "surface": "#F3F8FF",
            "border": "#BBDEFB",
            "card": "#FFFFFF",
            "card_shadow": "0 2px 4px rgba(33,150,243,0.1)",
        }

    def _get_modern_green_theme(self) -> dict:
        """Get modern green theme colors"""
        return {
            "window": "#E8F5E8",
            "window_text": "#2E7D32",
            "base": "#FFFFFF",
            "alternate_base": "#F1F8E9",
            "text": "#2E7D32",
            "button": "#4CAF50",
            "button_text": "#FFFFFF",
            "bright_text": "#FFFFFF",
            "highlight": "#388E3C",
            "highlight_text": "#FFFFFF",
            "link": "#2E7D32",
            "mid": "#C8E6C9",
            "dark": "#388E3C",
            "shadow": "#1B5E20",
            "success": "#4CAF50",
            "warning": "#FF9800",
            "error": "#F44336",
            "info": "#2196F3",
            "primary": "#4CAF50",
            "secondary": "#6C757D",
            "accent": "#FF5722",
            "background": "#E8F5E8",
            "surface": "#F1F8E9",
            "border": "#C8E6C9",
            "card": "#FFFFFF",
            "card_shadow": "0 2px 4px rgba(76,175,80,0.1)",
        }

    def _get_light_theme(self) -> dict:
        """Get light theme colors"""
        return {
            "window": "#FFFFFF",
            "window_text": "#000000",
            "base": "#FFFFFF",
            "alternate_base": "#F0F0F0",
            "text": "#000000",
            "button": "#E0E0E0",
            "button_text": "#000000",
            "bright_text": "#FFFFFF",
            "highlight": "#0078D4",
            "highlight_text": "#FFFFFF",
            "link": "#0066CC",
            "mid": "#C0C0C0",
            "dark": "#808080",
            "shadow": "#404040",
            "success": "#28A745",
            "warning": "#FFC107",
            "error": "#DC3545",
            "info": "#17A2B8",
            "primary": "#0078D4",
            "secondary": "#6C757D",
            "accent": "#E74C3C",
            "background": "#FFFFFF",
            "surface": "#F0F0F0",
            "border": "#C0C0C0",
            "card": "#FFFFFF",
            "card_shadow": "0 2px 4px rgba(0,0,0,0.1)",
        }

    def _get_dark_theme(self) -> dict:
        """Get dark theme colors"""
        return {
            "window": "#2D2D30",
            "window_text": "#FFFFFF",
            "base": "#1E1E1E",
            "alternate_base": "#2D2D30",
            "text": "#FFFFFF",
            "button": "#3E3E42",
            "button_text": "#FFFFFF",
            "bright_text": "#FFFFFF",
            "highlight": "#0078D4",
            "highlight_text": "#FFFFFF",
            "link": "#4EC9B0",
            "mid": "#3E3E42",
            "dark": "#2D2D30",
            "shadow": "#1E1E1E",
            "success": "#00B894",
            "warning": "#FDCB6E",
            "error": "#E17055",
            "info": "#74B9FF",
            "primary": "#0078D4",
            "secondary": "#6C757D",
            "accent": "#E74C3C",
            "background": "#1E1E1E",
            "surface": "#2D2D30",
            "border": "#3E3E42",
            "card": "#2D2D30",
            "card_shadow": "0 2px 4px rgba(0,0,0,0.3)",
        }

    def _get_blue_theme(self) -> dict:
        """Get blue theme colors"""
        return {
            "window": "#E3F2FD",
            "window_text": "#000000",
            "base": "#FFFFFF",
            "alternate_base": "#F3F8FF",
            "text": "#000000",
            "button": "#2196F3",
            "button_text": "#FFFFFF",
            "bright_text": "#FFFFFF",
            "highlight": "#1976D2",
            "highlight_text": "#FFFFFF",
            "link": "#1565C0",
            "mid": "#BBDEFB",
            "dark": "#1976D2",
            "shadow": "#0D47A1",
            "success": "#4CAF50",
            "warning": "#FF9800",
            "error": "#F44336",
            "info": "#2196F3",
            "primary": "#2196F3",
            "secondary": "#6C757D",
            "accent": "#FF5722",
            "background": "#E3F2FD",
            "surface": "#F3F8FF",
            "border": "#BBDEFB",
            "card": "#FFFFFF",
            "card_shadow": "0 2px 4px rgba(33,150,243,0.1)",
        }

    def _get_green_theme(self) -> dict:
        """Get green theme colors"""
        return {
            "window": "#E8F5E8",
            "window_text": "#000000",
            "base": "#FFFFFF",
            "alternate_base": "#F1F8E9",
            "text": "#000000",
            "button": "#4CAF50",
            "button_text": "#FFFFFF",
            "bright_text": "#FFFFFF",
            "highlight": "#388E3C",
            "highlight_text": "#FFFFFF",
            "link": "#2E7D32",
            "mid": "#C8E6C9",
            "dark": "#388E3C",
            "shadow": "#1B5E20",
            "success": "#4CAF50",
            "warning": "#FF9800",
            "error": "#F44336",
            "info": "#2196F3",
            "primary": "#4CAF50",
            "secondary": "#6C757D",
            "accent": "#FF5722",
            "background": "#E8F5E8",
            "surface": "#F1F8E9",
            "border": "#C8E6C9",
            "card": "#FFFFFF",
            "card_shadow": "0 2px 4px rgba(76,175,80,0.1)",
        }

    def apply_theme(self, theme_name: str):
        """Apply a theme to the application"""
        if theme_name not in self.themes:
            print(f"Theme '{theme_name}' not found")
            return

        self.current_theme = theme_name
        theme = self.themes[theme_name]

        app = QApplication.instance()
        if not app:
            return

        # Create palette
        palette = QPalette()

        # Set colors
        palette.setColor(QPalette.ColorRole.Window, QColor(theme["window"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(theme["window_text"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(theme["base"]))
        palette.setColor(
            QPalette.ColorRole.AlternateBase, QColor(theme["alternate_base"])
        )
        palette.setColor(QPalette.ColorRole.Text, QColor(theme["text"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(theme["button"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme["button_text"]))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(theme["bright_text"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(theme["highlight"]))
        palette.setColor(
            QPalette.ColorRole.HighlightedText, QColor(theme["highlight_text"])
        )
        palette.setColor(QPalette.ColorRole.Link, QColor(theme["link"]))
        palette.setColor(QPalette.ColorRole.Mid, QColor(theme["mid"]))
        palette.setColor(QPalette.ColorRole.Dark, QColor(theme["dark"]))
        palette.setColor(QPalette.ColorRole.Shadow, QColor(theme["shadow"]))

        # Apply palette
        app.setPalette(palette)

        # Emit signal
        self.theme_changed.emit(theme_name)

        print(f"Theme applied: {theme_name}")

    def get_current_theme(self) -> str:
        """Get current theme name"""
        return self.current_theme

    def get_available_themes(self) -> list:
        """Get list of available themes"""
        return list(self.themes.keys())

    def toggle_dark_mode(self):
        """Toggle between light and dark themes"""
        if self.current_theme == "dark":
            self.apply_theme("light")
        else:
            self.apply_theme("dark")

    def get_theme_colors(self, theme_name: str = None) -> dict:
        """Get colors for a specific theme"""
        if theme_name is None:
            theme_name = self.current_theme

        return self.themes.get(theme_name, self.themes["light"])


class ThemeWidget(QWidget):
    """Widget for theme selection"""

    def __init__(self, theme_manager: ThemeManager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.setup_ui()

    def setup_ui(self):
        """Setup the theme selection UI"""
        from PyQt6.QtWidgets import (QComboBox, QHBoxLayout, QLabel,
                                     QPushButton, QVBoxLayout)

        layout = QVBoxLayout()

        # Theme selection
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(self.theme_manager.get_available_themes())
        self.theme_combo.setCurrentText(self.theme_manager.get_current_theme())
        self.theme_combo.currentTextChanged.connect(self.theme_manager.apply_theme)

        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_combo)
        theme_layout.addStretch()

        # Quick toggle button
        toggle_btn = QPushButton("Toggle Dark Mode")
        toggle_btn.clicked.connect(self.theme_manager.toggle_dark_mode)

        layout.addLayout(theme_layout)
        layout.addWidget(toggle_btn)

        self.setLayout(layout)
