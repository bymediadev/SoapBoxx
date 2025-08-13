#!/usr/bin/env python3
"""
BaseTab - Foundation for all SoapBoxx tabs
==========================================

This class ensures that every tab properly inherits from QWidget
and follows the correct initialization pattern for PyQt6.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

class BaseTab(QWidget):
    """
    Base class for all tabs - ensures QWidget inheritance and proper initialization.
    
    All tabs must inherit from this class to guarantee PyQt6 compatibility.
    """
    
    def __init__(self, parent=None):
        """Initialize the base tab with proper QWidget setup"""
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """
        Override this method to set up the tab's UI.
        
        This method is called automatically after QWidget initialization.
        """
        # Default implementation creates a placeholder
        layout = QVBoxLayout()
        label = QLabel(f"{self.__class__.__name__} - Override setup_ui() to customize")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(label)
        self.setLayout(layout)
    
    def refresh(self):
        """
        Override this method to refresh the tab's content.
        
        Called when the tab becomes active or needs updating.
        """
        pass
    
    def cleanup(self):
        """
        Override this method to clean up resources when the tab is closed.
        
        Called when the tab is about to be destroyed.
        """
        pass
