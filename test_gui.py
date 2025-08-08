#!/usr/bin/env python3
"""
Simple test script to check if PyQt6 and basic GUI work
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test Window")
        self.setGeometry(100, 100, 400, 300)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create layout
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Add test label
        label = QLabel("PyQt6 Test Window - If you see this, the GUI is working!")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        
        # Add another label
        label2 = QLabel("Close this window to exit the test")
        label2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label2)

def main():
    """Test PyQt6 application"""
    try:
        print("Starting PyQt6 test application...")
        app = QApplication(sys.argv)
        
        print("Creating test window...")
        window = TestWindow()
        window.show()
        
        print("Starting application event loop...")
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"Test application failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
