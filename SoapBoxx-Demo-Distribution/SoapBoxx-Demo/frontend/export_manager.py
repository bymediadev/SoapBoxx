#!/usr/bin/env python3
"""Demo stub — optional full implementation may exist in the main SoapBoxx repo."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ExportManager(QWidget):
    """Placeholder export UI for the demo distribution."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("Export Manager (Demo Mode)")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
