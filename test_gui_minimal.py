#!/usr/bin/env python3
"""
Minimal PyQt6 GUI test to isolate the issue
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt

class MinimalWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        print("🏗️ MinimalWindow: Starting initialization...")
        
        self.setWindowTitle("Minimal Test Window")
        self.setGeometry(100, 100, 400, 300)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create layout
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Add a simple label
        label = QLabel("Hello, this is a minimal test!")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        
        print("✅ MinimalWindow: Initialization complete!")

def main():
    try:
        print("🚀 Starting minimal PyQt6 test...")
        
        print("📱 Creating QApplication...")
        app = QApplication(sys.argv)
        print("✅ QApplication created successfully")

        print("🏗️ Creating minimal window...")
        window = MinimalWindow()
        print("✅ Minimal window created successfully")
        
        print("👁️ Showing minimal window...")
        window.show()
        print("✅ Minimal window shown successfully")

        print("🔄 Starting application event loop...")
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"❌ Minimal test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
