#!/usr/bin/env python3
"""
Minimal UI Test for SoapBoxx
Tests if the basic PyQt6 UI works without backend dependencies
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton, QTabWidget
from PyQt6.QtCore import Qt

class MinimalMainWindow(QMainWindow):
    """Minimal main window to test basic UI functionality"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SoapBoxx - Minimal Test")
        self.setGeometry(100, 100, 800, 600)
        
        # Setup central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Header
        header_label = QLabel("SoapBoxx - AI-Powered Podcast Production Studio")
        header_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2C3E50; padding: 20px;")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header_label)
        
        # Tab widget
        self.tab_widget = QTabWidget()
        
        # SoapBoxx Tab
        soapboxx_tab = QWidget()
        soapboxx_layout = QVBoxLayout()
        soapboxx_label = QLabel("SoapBoxx Tab - Basic Functionality")
        soapboxx_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        soapboxx_layout.addWidget(soapboxx_label)
        soapboxx_tab.setLayout(soapboxx_layout)
        self.tab_widget.addTab(soapboxx_tab, "SoapBoxx")
        
        # Scoop Tab
        scoop_tab = QWidget()
        scoop_layout = QVBoxLayout()
        scoop_label = QLabel("Scoop Tab - Basic Functionality")
        scoop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scoop_layout.addWidget(scoop_label)
        scoop_tab.setLayout(scoop_layout)
        self.tab_widget.addTab(scoop_tab, "Scoop")
        
        # Reverb Tab
        reverb_tab = QWidget()
        reverb_layout = QVBoxLayout()
        reverb_label = QLabel("Reverb Tab - Basic Functionality")
        reverb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        reverb_layout.addWidget(reverb_label)
        reverb_tab.setLayout(reverb_layout)
        self.tab_widget.addTab(reverb_tab, "Reverb")
        
        layout.addWidget(self.tab_widget)
        
        # Test button
        test_button = QPushButton("Test Button - Click Me!")
        test_button.clicked.connect(self._on_test_button_clicked)
        test_button.setStyleSheet("""
            QPushButton {
                background-color: #3498DB;
                color: white;
                border: none;
                padding: 12px 24px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980B9;
            }
        """)
        layout.addWidget(test_button)
        
        # Status
        self.status_label = QLabel("Status: Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        print("✅ MinimalMainWindow: Initialization complete!")
    
    def _on_test_button_clicked(self):
        """Handle test button click"""
        self.status_label.setText("Status: Button clicked! Test successful!")
        print("✅ Test button clicked successfully!")

def main():
    """Main application entry point"""
    try:
        print("🚀 Starting minimal SoapBoxx test...")
        
        print("📱 Creating QApplication...")
        app = QApplication(sys.argv)
        print("✅ QApplication created successfully")
        
        print("🏗️ Creating main window...")
        window = MinimalMainWindow()
        print("✅ Main window created successfully")
        
        print("👁️ Showing main window...")
        window.show()
        print("✅ Main window shown successfully")
        
        print("🔄 Starting application event loop...")
        print("🎯 Application should now be visible and running...")
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"❌ Application failed to start: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
