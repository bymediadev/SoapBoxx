#!/usr/bin/env python3
"""
SoapBoxx Main Window
Main application window with tabbed interface
"""

import sys
import os
import webbrowser
from pathlib import Path
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QVBoxLayout, 
    QWidget, QMenuBar, QMenu, QMessageBox, QStatusBar,
    QPushButton, QHBoxLayout, QLabel, QDialog,
    QLineEdit, QTextEdit, QComboBox, QDateEdit, QTimeEdit,
    QFormLayout, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QTimer, QDate, QTime
from PyQt6.QtGui import QAction, QKeySequence

# Import tabs
from soapboxx_tab import SoapBoxxTab
from reverb_tab import ReverbTab
from scoop_tab import ScoopTab

# Import new features
from export_manager import ExportManager
from keyboard_shortcuts import ShortcutHandler
from theme_manager import ThemeManager
from batch_processor import BatchProcessorDialog


class BookingDialog(QDialog):
    """Dialog for scheduling a call"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📅 Schedule a Call")
        self.setModal(True)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the booking dialog UI"""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("📅 Schedule a Call")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Form layout
        form_layout = QFormLayout()
        
        # Name field
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Your name")
        form_layout.addRow("Name:", self.name_edit)
        
        # Email field
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("your.email@example.com")
        form_layout.addRow("Email:", self.email_edit)
        
        # Call type
        self.call_type_combo = QComboBox()
        self.call_type_combo.addItems([
            "Podcast Consultation",
            "Content Strategy Session",
            "Technical Support",
            "General Discussion"
        ])
        form_layout.addRow("Call Type:", self.call_type_combo)
        
        # Date picker
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.currentDate().addDays(1))
        self.date_edit.setMinimumDate(QDate.currentDate())
        form_layout.addRow("Date:", self.date_edit)
        
        # Time picker
        self.time_edit = QTimeEdit()
        self.time_edit.setTime(QTime(9, 0))  # 9:00 AM default
        self.time_edit.setDisplayFormat("hh:mm AP")
        form_layout.addRow("Time:", self.time_edit)
        
        # Duration
        self.duration_combo = QComboBox()
        self.duration_combo.addItems(["30 minutes", "1 hour", "1.5 hours", "2 hours"])
        form_layout.addRow("Duration:", self.duration_combo)
        
        # Notes
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(100)
        self.notes_edit.setPlaceholderText("Any additional notes or topics you'd like to discuss...")
        form_layout.addRow("Notes:", self.notes_edit)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_booking_data(self):
        """Get the booking data from the dialog"""
        return {
            "name": self.name_edit.text(),
            "email": self.email_edit.text(),
            "call_type": self.call_type_combo.currentText(),
            "date": self.date_edit.date().toString("yyyy-MM-dd"),
            "time": self.time_edit.time().toString("hh:mm AP"),
            "duration": self.duration_combo.currentText(),
            "notes": self.notes_edit.toPlainText()
        }


class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SoapBoxx - Podcast Production Studio")
        self.setGeometry(100, 100, 1200, 800)
        
        # Initialize components
        self.init_components()
        self.setup_ui()
        self.setup_menu()
        self.setup_status_bar()
        self.setup_shortcuts()
        
        # Apply default theme
        self.theme_manager.apply_theme("light")
        
        # Show welcome message
        self.show_welcome_message()
    
    def init_components(self):
        """Initialize all components"""
        # Theme manager
        self.theme_manager = ThemeManager(self)
        
        # Export manager
        self.export_manager = ExportManager(self)
        self.export_manager.export_completed.connect(self.on_export_completed)
        self.export_manager.export_failed.connect(self.on_export_failed)
        
        # Shortcut handler
        self.shortcut_handler = ShortcutHandler(self)
        
        # Batch processor
        self.batch_processor = BatchProcessorDialog(self)
        
        # Tab widgets
        self.soapboxx_tab = SoapBoxxTab()
        self.reverb_tab = ReverbTab()
        self.scoop_tab = ScoopTab()
    
    def setup_ui(self):
        """Setup the main UI"""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout(central_widget)
        
        # Header with booking button
        header_layout = QHBoxLayout()
        
        # Title
        title = QLabel("🎤 SoapBoxx - Podcast Production Studio")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Booking button
        self.booking_btn = QPushButton("📅 Schedule a Call")
        self.booking_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.booking_btn.clicked.connect(self.schedule_call)
        header_layout.addWidget(self.booking_btn)
        
        layout.addLayout(header_layout)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.soapboxx_tab, "🎤 SoapBoxx")
        self.tab_widget.addTab(self.reverb_tab, "🎯 Reverb")
        self.tab_widget.addTab(self.scoop_tab, "📰 Scoop")
        
        layout.addWidget(self.tab_widget)
    
    def setup_menu(self):
        """Setup the menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        # Export submenu
        export_menu = file_menu.addMenu("&Export")
        
        export_transcript_action = QAction("Export &Transcript", self)
        export_transcript_action.setShortcut("Ctrl+E")
        export_transcript_action.triggered.connect(self.export_transcript)
        export_menu.addAction(export_transcript_action)
        
        export_feedback_action = QAction("Export &Feedback", self)
        export_feedback_action.setShortcut("Ctrl+Shift+E")
        export_feedback_action.triggered.connect(self.export_feedback)
        export_menu.addAction(export_feedback_action)
        
        export_all_action = QAction("Export &All", self)
        export_all_action.setShortcut("Ctrl+Alt+E")
        export_all_action.triggered.connect(self.export_all)
        export_menu.addAction(export_all_action)
        
        file_menu.addSeparator()
        
        # Batch processing
        batch_action = QAction("&Batch Processing", self)
        batch_action.triggered.connect(self.show_batch_processing)
        file_menu.addAction(batch_action)
        
        file_menu.addSeparator()
        
        # Exit
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        clear_action = QAction("&Clear Results", self)
        clear_action.setShortcut("Ctrl+L")
        clear_action.triggered.connect(self.clear_results)
        edit_menu.addAction(clear_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        # Theme submenu
        theme_menu = view_menu.addMenu("&Theme")
        
        light_theme_action = QAction("&Light", self)
        light_theme_action.triggered.connect(lambda: self.theme_manager.apply_theme("light"))
        theme_menu.addAction(light_theme_action)
        
        dark_theme_action = QAction("&Dark", self)
        dark_theme_action.triggered.connect(lambda: self.theme_manager.apply_theme("dark"))
        theme_menu.addAction(dark_theme_action)
        
        blue_theme_action = QAction("&Blue", self)
        blue_theme_action.triggered.connect(lambda: self.theme_manager.apply_theme("blue"))
        theme_menu.addAction(blue_theme_action)
        
        green_theme_action = QAction("&Green", self)
        green_theme_action.triggered.connect(lambda: self.theme_manager.apply_theme("green"))
        theme_menu.addAction(green_theme_action)
        
        view_menu.addSeparator()
        
        toggle_dark_action = QAction("Toggle &Dark Mode", self)
        toggle_dark_action.triggered.connect(self.theme_manager.toggle_dark_mode)
        view_menu.addAction(toggle_dark_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        shortcuts_action = QAction("&Keyboard Shortcuts", self)
        shortcuts_action.setShortcut("Ctrl+?")
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)
        
        help_menu.addSeparator()
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_status_bar(self):
        """Setup the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Shortcuts are handled by ShortcutHandler
        pass
    
    def show_welcome_message(self):
        """Show welcome message"""
        self.status_bar.showMessage("Welcome to SoapBoxx! Press Ctrl+? for keyboard shortcuts.")
    
    # Export methods
    def export_transcript(self):
        """Export current transcript"""
        # Get transcript from current tab
        current_tab = self.tab_widget.currentWidget()
        if hasattr(current_tab, 'get_transcript'):
            transcript = current_tab.get_transcript()
            if transcript:
                self.export_manager.export_transcript(transcript)
            else:
                QMessageBox.information(self, "Export", "No transcript available to export.")
        else:
            QMessageBox.information(self, "Export", "Transcript export not available in this tab.")
    
    def export_feedback(self):
        """Export current feedback"""
        # Get feedback from current tab
        current_tab = self.tab_widget.currentWidget()
        if hasattr(current_tab, 'get_feedback'):
            feedback = current_tab.get_feedback()
            if feedback:
                self.export_manager.export_feedback(feedback)
            else:
                QMessageBox.information(self, "Export", "No feedback available to export.")
        else:
            QMessageBox.information(self, "Export", "Feedback export not available in this tab.")
    
    def export_all(self):
        """Export all available data"""
        # This would export transcript, feedback, and analytics
        QMessageBox.information(self, "Export", "Export all functionality coming soon!")
    
    def show_batch_processing(self):
        """Show batch processing dialog"""
        dialog = self.batch_processor.show_batch_options()
        if dialog:
            dialog.exec()
    
    def clear_results(self):
        """Clear results in current tab"""
        current_tab = self.tab_widget.currentWidget()
        if hasattr(current_tab, 'clear_results'):
            current_tab.clear_results()
            self.status_bar.showMessage("Results cleared.")
        else:
            QMessageBox.information(self, "Clear", "Clear functionality not available in this tab.")
    
    def show_shortcuts(self):
        """Show keyboard shortcuts help"""
        self.shortcut_handler.shortcuts.show_shortcuts_help()
    
    def show_about(self):
        """Show about dialog"""
        about_text = """
        <h2>SoapBoxx - Podcast Production Studio</h2>
        <p>Version: 1.0.0</p>
        <p>A comprehensive podcast production platform with AI-powered features.</p>
        <p><b>Features:</b></p>
        <ul>
            <li>🎤 Real-time audio recording and transcription</li>
            <li>🎯 AI-powered feedback and coaching</li>
            <li>📰 Research and content discovery</li>
            <li>📊 Podcast analytics and insights</li>
            <li>🔍 Guest research and background information</li>
        </ul>
        <p><b>Keyboard Shortcuts:</b> Press Ctrl+? to view all shortcuts</p>
        """
        QMessageBox.about(self, "About SoapBoxx", about_text)
    
    def on_export_completed(self, filename: str, format_type: str):
        """Handle export completion"""
        self.status_bar.showMessage(f"Exported to {filename} ({format_type})")
        QMessageBox.information(self, "Export Complete", f"Successfully exported to:\n{filename}")
    
    def on_export_failed(self, error: str):
        """Handle export failure"""
        self.status_bar.showMessage(f"Export failed: {error}")
        QMessageBox.critical(self, "Export Failed", f"Export failed:\n{error}")
    
    # Tab navigation methods
    def next_tab(self):
        """Switch to next tab"""
        current_index = self.tab_widget.currentIndex()
        next_index = (current_index + 1) % self.tab_widget.count()
        self.tab_widget.setCurrentIndex(next_index)
    
    def previous_tab(self):
        """Switch to previous tab"""
        current_index = self.tab_widget.currentIndex()
        prev_index = (current_index - 1) % self.tab_widget.count()
        self.tab_widget.setCurrentIndex(prev_index)
    
    def switch_to_tab(self, index: int):
        """Switch to specific tab"""
        if 0 <= index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(index)
    
    def schedule_call(self):
        """Open the booking dialog and schedule a call"""
        try:
            dialog = BookingDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                booking_data = dialog.get_booking_data()
                self.create_calendar_event(booking_data)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open booking dialog: {str(e)}")
    
    def create_calendar_event(self, booking_data):
        """Create a Google Calendar event for the booking"""
        try:
            # Format the date and time
            date_str = booking_data['date']
            time_str = booking_data['time']
            
            # Create Google Calendar URL
            event_title = f"SoapBoxx: {booking_data['call_type']} - {booking_data['name']}"
            event_description = f"""
Call Type: {booking_data['call_type']}
Name: {booking_data['name']}
Email: {booking_data['email']}
Duration: {booking_data['duration']}

Notes:
{booking_data['notes']}

Booked via SoapBoxx Application
            """.strip()
            
            # Parse date and time
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            time_obj = datetime.strptime(time_str, "%I:%M %p").time()
            start_datetime = datetime.combine(date_obj.date(), time_obj)
            
            # Calculate end time based on duration
            duration_minutes = {
                "30 minutes": 30,
                "1 hour": 60,
                "1.5 hours": 90,
                "2 hours": 120
            }.get(booking_data['duration'], 60)
            
            end_datetime = start_datetime + timedelta(minutes=duration_minutes)
            
            # Format for Google Calendar URL
            start_str = start_datetime.strftime("%Y%m%dT%H%M%S")
            end_str = end_datetime.strftime("%Y%m%dT%H%M%S")
            
            # Create Google Calendar URL
            calendar_url = (
                "https://calendar.google.com/calendar/render?"
                f"action=TEMPLATE&text={event_title.replace(' ', '+')}&"
                f"dates={start_str}/{end_str}&"
                f"details={event_description.replace(' ', '+').replace(chr(10), '%0A')}&"
                "sf=true&output=xml"
            )
            
            # Open in browser
            webbrowser.open(calendar_url)
            
            # Show success message
            QMessageBox.information(
                self, 
                "Booking Created", 
                f"Calendar event created successfully!\n\n"
                f"Event: {event_title}\n"
                f"Date: {date_str}\n"
                f"Time: {time_str}\n"
                f"Duration: {booking_data['duration']}\n\n"
                f"The event has been opened in your browser for review and confirmation."
            )
            
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Booking Error", 
                f"Failed to create calendar event: {str(e)}\n\n"
                f"Please try again or contact support."
            )


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("SoapBoxx")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("SoapBoxx")
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Start application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
