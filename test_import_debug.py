#!/usr/bin/env python3
"""
Debug import issues with frontend modules
"""

import sys
import traceback

def test_imports():
    """Test importing frontend modules step by step"""
    print("🧪 Testing imports step by step...")
    
    # Test 1: Basic PyQt6 imports
    try:
        print("1️⃣ Testing PyQt6 imports...")
        from PyQt6.QtWidgets import QWidget, QApplication
        from PyQt6.QtCore import QTimer
        print("✅ PyQt6 imports successful")
    except Exception as e:
        print(f"❌ PyQt6 imports failed: {e}")
        return False
    
    # Test 2: Import ModernCard and ModernButton
    try:
        print("2️⃣ Testing ModernCard/ModernButton imports...")
        from frontend.soapboxx_tab import ModernCard, ModernButton
        print("✅ ModernCard/ModernButton imports successful")
    except Exception as e:
        print(f"❌ ModernCard/ModernButton imports failed: {e}")
        return False
    
    # Test 3: Import SoapBoxxTab class (not instance)
    try:
        print("3️⃣ Testing SoapBoxxTab class import...")
        from frontend.soapboxx_tab import SoapBoxxTab
        print("✅ SoapBoxxTab class import successful")
    except Exception as e:
        print(f"❌ SoapBoxxTab class import failed: {e}")
        return False
    
    # Test 4: Create QApplication
    try:
        print("4️⃣ Testing QApplication creation...")
        app = QApplication(sys.argv)
        print("✅ QApplication created successfully")
    except Exception as e:
        print(f"❌ QApplication creation failed: {e}")
        return False
    
    # Test 5: Create SoapBoxxTab instance
    try:
        print("5️⃣ Testing SoapBoxxTab instance creation...")
        tab = SoapBoxxTab()
        print("✅ SoapBoxxTab instance created successfully")
        
        # Clean up
        app.quit()
        return True
        
    except Exception as e:
        print(f"❌ SoapBoxxTab instance creation failed: {e}")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    if success:
        print("\n🎉 All import tests passed!")
    else:
        print("\n⚠️ Some import tests failed. Check the output above.")
