#!/usr/bin/env python3
"""
Keyboard Shortcuts Manager for SoapBoxx
Handles hotkeys for common actions
"""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QWidget, QMainWindow


class KeyboardShortcuts(QObject):
    """Manages keyboard shortcuts for SoapBoxx"""
    
    shortcut_triggered = pyqtSignal(str)  # action name
    
    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.shortcuts = {}
        self.parent = parent
        self.setup_shortcuts()
    
    def setup_shortcuts(self):
        """Setup all keyboard shortcuts"""
        if not self.parent:
            return
        
        # Recording shortcuts
        self.add_shortcut("start_recording", "Ctrl+R", "Start/Stop Recording")
        self.add_shortcut("pause_recording", "Ctrl+P", "Pause/Resume Recording")
        
        # Navigation shortcuts
        self.add_shortcut("next_tab", "Ctrl+Tab", "Next Tab")
        self.add_shortcut("previous_tab", "Ctrl+Shift+Tab", "Previous Tab")
        self.add_shortcut("soapboxx_tab", "Ctrl+1", "SoapBoxx Tab")
        self.add_shortcut("reverb_tab", "Ctrl+2", "Reverb Tab")
        self.add_shortcut("scoop_tab", "Ctrl+3", "Scoop Tab")
        
        # Export shortcuts
        self.add_shortcut("export_transcript", "Ctrl+E", "Export Transcript")
        self.add_shortcut("export_feedback", "Ctrl+Shift+E", "Export Feedback")
        self.add_shortcut("export_all", "Ctrl+Alt+E", "Export All")
        
        # Analysis shortcuts
        self.add_shortcut("content_analysis", "Ctrl+A", "Content Analysis")
        self.add_shortcut("performance_coaching", "Ctrl+C", "Performance Coaching")
        self.add_shortcut("guest_research", "Ctrl+G", "Guest Research")
        
        # Utility shortcuts
        self.add_shortcut("clear_results", "Ctrl+L", "Clear Results")
        self.add_shortcut("save_session", "Ctrl+S", "Save Session")
        self.add_shortcut("open_export_folder", "Ctrl+O", "Open Export Folder")
        
        # Help shortcuts
        self.add_shortcut("show_help", "F1", "Show Help")
        self.add_shortcut("show_shortcuts", "Ctrl+?", "Show Shortcuts")
    
    def add_shortcut(self, action_name: str, key_sequence: str, description: str):
        """Add a keyboard shortcut"""
        if not self.parent:
            return
        
        try:
            shortcut = QShortcut(QKeySequence(key_sequence), self.parent)
            shortcut.activated.connect(lambda: self.shortcut_triggered.emit(action_name))
            self.shortcuts[action_name] = {
                "shortcut": shortcut,
                "key_sequence": key_sequence,
                "description": description
            }
        except Exception as e:
            print(f"Failed to add shortcut {action_name}: {e}")
    
    def get_shortcuts_list(self) -> list:
        """Get list of all shortcuts"""
        shortcuts_list = []
        for action_name, shortcut_info in self.shortcuts.items():
            shortcuts_list.append({
                "action": action_name,
                "key": shortcut_info["key_sequence"],
                "description": shortcut_info["description"]
            })
        return shortcuts_list
    
    def show_shortcuts_help(self):
        """Show shortcuts help dialog"""
        shortcuts_list = self.get_shortcuts_list()
        
        help_text = "🎯 SoapBoxx Keyboard Shortcuts\n\n"
        
        # Group shortcuts by category
        categories = {
            "Recording": ["start_recording", "pause_recording"],
            "Navigation": ["next_tab", "previous_tab", "soapboxx_tab", "reverb_tab", "scoop_tab"],
            "Export": ["export_transcript", "export_feedback", "export_all"],
            "Analysis": ["content_analysis", "performance_coaching", "guest_research"],
            "Utility": ["clear_results", "save_session", "open_export_folder"],
            "Help": ["show_help", "show_shortcuts"]
        }
        
        for category, actions in categories.items():
            help_text += f"📁 {category}\n"
            help_text += "─" * (len(category) + 4) + "\n"
            
            for action in actions:
                for shortcut_info in shortcuts_list:
                    if shortcut_info["action"] == action:
                        help_text += f"  {shortcut_info['key']:<15} {shortcut_info['description']}\n"
                        break
            
            help_text += "\n"
        
        # Show help dialog
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox()
        msg.setWindowTitle("Keyboard Shortcuts")
        msg.setText(help_text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()


class ShortcutHandler:
    """Handles shortcut actions"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.shortcuts = KeyboardShortcuts(main_window)
        self.shortcuts.shortcut_triggered.connect(self.handle_shortcut)
    
    def handle_shortcut(self, action_name: str):
        """Handle shortcut actions"""
        try:
            if action_name == "start_recording":
                self.main_window.start_recording()
            elif action_name == "pause_recording":
                self.main_window.pause_recording()
            elif action_name == "next_tab":
                self.main_window.next_tab()
            elif action_name == "previous_tab":
                self.main_window.previous_tab()
            elif action_name == "soapboxx_tab":
                self.main_window.switch_to_tab(0)
            elif action_name == "reverb_tab":
                self.main_window.switch_to_tab(1)
            elif action_name == "scoop_tab":
                self.main_window.switch_to_tab(2)
            elif action_name == "export_transcript":
                self.main_window.export_transcript()
            elif action_name == "export_feedback":
                self.main_window.export_feedback()
            elif action_name == "export_all":
                self.main_window.export_all()
            elif action_name == "content_analysis":
                self.main_window.content_analysis()
            elif action_name == "performance_coaching":
                self.main_window.performance_coaching()
            elif action_name == "guest_research":
                self.main_window.guest_research()
            elif action_name == "clear_results":
                self.main_window.clear_results()
            elif action_name == "save_session":
                self.main_window.save_session()
            elif action_name == "open_export_folder":
                self.main_window.open_export_folder()
            elif action_name == "show_help":
                self.main_window.show_help()
            elif action_name == "show_shortcuts":
                self.shortcuts.show_shortcuts_help()
            else:
                print(f"Unknown shortcut action: {action_name}")
                
        except Exception as e:
            print(f"Error handling shortcut {action_name}: {e}")
    
    def get_shortcuts_list(self) -> list:
        """Get list of all shortcuts"""
        return self.shortcuts.get_shortcuts_list() 