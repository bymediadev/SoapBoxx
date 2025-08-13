#!/usr/bin/env python3
"""
Bulletproof Tab Loader - PyQt6-safe tab management
==================================================

This module provides a robust tab loading system that:
1. Automatically wraps non-QWidget tabs
2. Handles PyQt6 compatibility issues
3. Provides fallback placeholder tabs
4. Logs all operations for debugging
"""

import sys
import traceback
from typing import Optional, Callable, Any
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTabWidget
from PyQt6.QtCore import Qt

class TabLoadError(Exception):
    """Custom exception for tab loading errors"""
    pass

class BulletproofTabLoader:
    """
    Bulletproof tab loader that handles all PyQt6 edge cases.
    
    This class ensures that tabs are always properly inserted into QTabWidget
    regardless of how they're implemented.
    """
    
    def __init__(self, tab_widget: QTabWidget):
        self.tab_widget = tab_widget
        self._loaded_tabs = {}
        self._error_count = 0
    
    def safe_insert_tab(self, index: int, tab_instance: Any, label: str, 
                        icon=None, fallback_message: str = None) -> bool:
        """
        Safely insert a tab into the tab widget with automatic QWidget wrapping.
        
        Args:
            index: Position to insert the tab
            tab_instance: The tab widget instance (can be any type)
            label: Tab label text
            icon: Optional tab icon
            fallback_message: Message to show if tab creation fails
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Step 1: Validate and wrap the tab instance
            safe_tab = self._ensure_qwidget(tab_instance, label, fallback_message)
            
            if not safe_tab:
                print(f"❌ Failed to create safe tab for {label}")
                return False
            
            # Step 2: Insert the tab with proper PyQt6 signature
            if icon:
                self.tab_widget.insertTab(index, safe_tab, icon, label)
            else:
                self.tab_widget.insertTab(index, safe_tab, label)
            
            # Step 3: Mark as loaded and log success
            self._loaded_tabs[label] = True
            print(f"✅ Tab '{label}' inserted successfully at index {index}")
            
            return True
            
        except Exception as e:
            self._error_count += 1
            error_msg = f"Failed to insert tab '{label}': {str(e)}"
            print(f"❌ {error_msg}")
            traceback.print_exc()
            
            # Create emergency fallback tab
            try:
                fallback = self._create_emergency_tab(label, error_msg)
                if fallback:
                    self.tab_widget.insertTab(index, fallback, label)
                    print(f"⚠️  Emergency fallback tab created for '{label}'")
                    return True
            except Exception as fallback_error:
                print(f"❌ Even fallback tab failed: {fallback_error}")
            
            return False
    
    def _ensure_qwidget(self, tab_instance: Any, label: str, 
                       fallback_message: str = None) -> Optional[QWidget]:
        """
        Ensure the tab instance is a proper QWidget, wrapping if necessary.
        
        Args:
            tab_instance: The tab instance to validate
            label: Tab label for error messages
            fallback_message: Message to show if wrapping fails
            
        Returns:
            A guaranteed QWidget instance, or None if all attempts fail
        """
        try:
            # Case 1: Already a QWidget - use as-is
            if isinstance(tab_instance, QWidget):
                print(f"✅ {label}: Valid QWidget instance")
                return tab_instance
            
            # Case 2: Has a layout method - wrap it
            if hasattr(tab_instance, 'layout') and callable(getattr(tab_instance, 'layout')):
                print(f"🔄 {label}: Wrapping widget with layout")
                return self._wrap_widget_with_layout(tab_instance)
            
            # Case 3: Has a setParent method - might be a QWidget subclass
            if hasattr(tab_instance, 'setParent'):
                print(f"🔄 {label}: Widget has setParent, attempting to use")
                try:
                    # Try to use it directly - might work
                    return tab_instance
                except Exception:
                    print(f"⚠️  {label}: setParent widget failed, wrapping")
                    return self._wrap_widget_generic(tab_instance)
            
            # Case 4: Generic object - wrap it
            print(f"🔄 {label}: Generic object, wrapping generically")
            return self._wrap_widget_generic(tab_instance)
            
        except Exception as e:
            print(f"❌ {label}: Failed to ensure QWidget: {e}")
            # Create a fallback tab
            return self._create_fallback_tab(label, fallback_message or f"Failed to load: {str(e)}")
    
    def _wrap_widget_with_layout(self, widget: Any) -> QWidget:
        """Wrap a widget that has a layout method"""
        try:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            
            # Try to get the widget's layout and add it
            if hasattr(widget, 'layout'):
                widget_layout = widget.layout()
                if widget_layout:
                    # Transfer all widgets from the original layout
                    while widget_layout.count() > 0:
                        child = widget_layout.takeAt(0)
                        if child.widget():
                            layout.addWidget(child.widget())
                        elif child.layout():
                            layout.addLayout(child.layout())
            
            # If no layout or empty, add the widget itself
            if layout.count() == 0:
                layout.addWidget(widget)
            
            return container
            
        except Exception as e:
            print(f"⚠️  Layout wrapping failed: {e}")
            return self._wrap_widget_generic(widget)
    
    def _wrap_widget_generic(self, widget: Any) -> QWidget:
        """Generic widget wrapper for any object type"""
        try:
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            
            # Try to add the widget directly
            try:
                layout.addWidget(widget)
            except Exception:
                # If that fails, create a representation
                label = QLabel(f"Widget: {type(widget).__name__}")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(label)
            
            return container
            
        except Exception as e:
            print(f"⚠️  Generic wrapping failed: {e}")
            return None
    
    def _create_fallback_tab(self, label: str, message: str) -> QWidget:
        """Create a fallback tab when the original fails"""
        try:
            container = QWidget()
            layout = QVBoxLayout(container)
            
            # Error message
            error_label = QLabel(f"⚠️  {message}")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setStyleSheet("""
                QLabel {
                    color: #E74C3C;
                    font-size: 14px;
                    padding: 20px;
                    background-color: #FDF2F2;
                    border: 1px solid #F5B7B1;
                    border-radius: 8px;
                }
            """)
            layout.addWidget(error_label)
            
            # Widget type info
            type_label = QLabel(f"Type: {type(label).__name__}")
            type_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            type_label.setStyleSheet("color: #7F8C8D; font-size: 12px;")
            layout.addWidget(type_label)
            
            layout.addStretch()
            return container
            
        except Exception as e:
            print(f"❌ Even fallback tab creation failed: {e}")
            return None
    
    def _create_emergency_tab(self, label: str, error_msg: str) -> QWidget:
        """Create an emergency tab when everything else fails"""
        try:
            container = QWidget()
            layout = QVBoxLayout(container)
            
            emergency_label = QLabel("🚨 EMERGENCY TAB")
            emergency_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            emergency_label.setStyleSheet("""
                QLabel {
                    color: #E74C3C;
                    font-size: 16px;
                    font-weight: bold;
                    padding: 40px;
                    background-color: #FDF2F2;
                    border: 2px solid #E74C3C;
                    border-radius: 12px;
                }
            """)
            layout.addWidget(emergency_label)
            
            error_label = QLabel(f"Tab '{label}' failed to load:\n{error_msg}")
            error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_label.setWordWrap(True)
            error_label.setStyleSheet("color: #7F8C8D; font-size: 12px; padding: 20px;")
            layout.addWidget(error_label)
            
            return container
            
        except Exception as e:
            print(f"❌ Emergency tab creation failed: {e}")
            return None
    
    def get_error_count(self) -> int:
        """Get the total number of tab loading errors"""
        return self._error_count
    
    def get_loaded_tabs(self) -> dict:
        """Get the status of all loaded tabs"""
        return self._loaded_tabs.copy()
    
    def reset_error_count(self):
        """Reset the error counter"""
        self._error_count = 0

# Convenience function for easy integration
def create_bulletproof_tab_loader(tab_widget: QTabWidget) -> BulletproofTabLoader:
    """Create a bulletproof tab loader for the given tab widget"""
    return BulletproofTabLoader(tab_widget)
