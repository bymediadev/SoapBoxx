#!/usr/bin/env python3
"""
Test Scoop Tab - Verify the Scoop tab class works
=================================================

This script tests just the Scoop tab class to see if it's working properly.
"""

import sys
import os

# Add frontend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'frontend'))

def test_scoop_tab():
    """Test the Scoop tab class"""
    try:
        from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
        from PyQt6.QtCore import Qt
        
        print("🚀 Testing Scoop Tab Class")
        print("=" * 40)
        
        # Create application
        app = QApplication([])
        print("✅ QApplication created")
        
        # Test 1: Import the class
        print("\n🧪 Test 1: Import ScoopTab class")
        try:
            from main_window import ScoopTab
            print("✅ ScoopTab imported successfully")
        except Exception as e:
            print(f"❌ Failed to import ScoopTab: {e}")
            return False
        
        # Test 2: Create instance
        print("\n🧪 Test 2: Create ScoopTab instance")
        try:
            scoop_tab = ScoopTab()
            print("✅ ScoopTab instance created")
        except Exception as e:
            print(f"❌ Failed to create ScoopTab instance: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test 3: Check properties
        print("\n🧪 Test 3: Check ScoopTab properties")
        print(f"   Type: {type(scoop_tab)}")
        print(f"   Is QWidget: {isinstance(scoop_tab, QWidget)}")
        print(f"   Has layout: {scoop_tab.layout() is not None}")
        if scoop_tab.layout():
            print(f"   Layout item count: {scoop_tab.layout().count()}")
            if scoop_tab.layout().count() > 0:
                first_item = scoop_tab.layout().itemAt(0)
                if first_item.widget():
                    print(f"   First widget: {first_item.widget().text()}")
        
        # Test 4: Show the tab
        print("\n🧪 Test 4: Display ScoopTab")
        scoop_tab.show()
        print("✅ ScoopTab displayed")
        
        # Display results
        print(f"\n📊 Test Results:")
        print(f"   ScoopTab created: ✅")
        print(f"   ScoopTab displayed: ✅")
        
        print("\n🎉 ScoopTab test completed!")
        print("You should see a window with 'Scoop Tab (Demo Mode)' text.")
        print("Press Ctrl+C to exit...")
        
        # Keep the application running
        app.exec()
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = test_scoop_tab()
    
    if success:
        print("\n✅ ScoopTab test passed!")
    else:
        print("\n❌ ScoopTab test failed!")
        sys.exit(1)
