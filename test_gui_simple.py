#!/usr/bin/env python3
"""
Simple GUI test to debug PyQt6 application exit issue
"""

import sys
import traceback
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton
from PyQt6.QtCore import Qt

def test_basic_pyqt6():
    """Test basic PyQt6 functionality"""
    print("🧪 Testing basic PyQt6 functionality...")
    
    try:
        app = QApplication(sys.argv)
        print("✅ QApplication created successfully")
        
        window = QMainWindow()
        window.setWindowTitle("Basic PyQt6 Test")
        window.setGeometry(100, 100, 400, 300)
        
        central_widget = QWidget()
        window.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        label = QLabel("PyQt6 is working!")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        
        button = QPushButton("Click me!")
        button.clicked.connect(lambda: print("Button clicked!"))
        layout.addWidget(button)
        
        window.show()
        print("✅ Basic window shown successfully")
        
        # Run for a few seconds to test
        print("🔄 Running for 3 seconds...")
        QTimer = app.property("QTimer")  # Get QTimer from app
        if QTimer:
            timer = QTimer()
            timer.singleShot(3000, app.quit)
        
        result = app.exec()
        print(f"✅ Application exited with code: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Basic PyQt6 test failed: {e}")
        traceback.print_exc()
        return False

def test_soapboxx_tab_creation():
    """Test SoapBoxxTab creation without QApplication"""
    print("\n🧪 Testing SoapBoxxTab creation without QApplication...")
    
    try:
        # Try to import and create SoapBoxxTab
        from frontend.soapboxx_tab import SoapBoxxTab
        print("✅ SoapBoxxTab imported successfully")
        
        # This should fail because there's no QApplication
        tab = SoapBoxxTab()
        print("❌ SoapBoxxTab creation should have failed but didn't")
        return False
        
    except Exception as e:
        print(f"✅ SoapBoxxTab creation failed as expected: {e}")
        return True

def test_soapboxx_tab_with_app():
    """Test SoapBoxxTab creation with QApplication"""
    print("\n🧪 Testing SoapBoxxTab creation with QApplication...")
    
    try:
        app = QApplication(sys.argv)
        print("✅ QApplication created successfully")
        
        from frontend.soapboxx_tab import SoapBoxxTab
        print("✅ SoapBoxxTab imported successfully")
        
        tab = SoapBoxxTab()
        print("✅ SoapBoxxTab created successfully")
        
        # Create a simple window to hold the tab
        window = QMainWindow()
        window.setWindowTitle("SoapBoxxTab Test")
        window.setGeometry(100, 100, 800, 600)
        
        central_widget = QWidget()
        window.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        layout.addWidget(tab)
        
        window.show()
        print("✅ SoapBoxxTab window shown successfully")
        
        # Run for a few seconds
        print("🔄 Running for 5 seconds...")
        QTimer = app.property("QTimer")
        if QTimer:
            timer = QTimer()
            timer.singleShot(5000, app.quit)
        
        result = app.exec()
        print(f"✅ Application exited with code: {result}")
        return True
        
    except Exception as e:
        print(f"❌ SoapBoxxTab test failed: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Starting PyQt6 GUI tests...")
    
    # Test 1: Basic PyQt6 functionality
    test1_result = test_basic_pyqt6()
    
    # Test 2: SoapBoxxTab creation without QApplication (should fail)
    test2_result = test_soapboxx_tab_creation()
    
    # Test 3: SoapBoxxTab creation with QApplication (should work)
    if test1_result:
        test3_result = test_soapboxx_tab_with_app()
    else:
        print("⏭️ Skipping test 3 because test 1 failed")
        test3_result = False
    
    print(f"\n📊 Test Results:")
    print(f"   Test 1 (Basic PyQt6): {'✅ PASS' if test1_result else '❌ FAIL'}")
    print(f"   Test 2 (Tab without App): {'✅ PASS' if test2_result else '❌ FAIL'}")
    print(f"   Test 3 (Tab with App): {'✅ PASS' if test3_result else '❌ FAIL'}")
    
    if test1_result and test2_result and test3_result:
        print("\n🎉 All tests passed! PyQt6 is working correctly.")
    else:
        print("\n⚠️ Some tests failed. Check the output above for details.")
