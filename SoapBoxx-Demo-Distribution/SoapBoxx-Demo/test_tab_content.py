#!/usr/bin/env python3
"""
Test script to verify tab content is working
===========================================

This script tests the individual tab classes to ensure they display content properly.
"""

import sys
import os

# Add frontend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'frontend'))

def test_tab_content():
    """Test individual tab content"""
    try:
        from PyQt6.QtWidgets import QApplication, QTabWidget, QWidget, QVBoxLayout, QLabel
        from PyQt6.QtCore import Qt
        from main_window import SoapBoxxTab, ScoopTab, ReverbTab
        
        print("✅ PyQt6 and tab classes imported successfully")
        
        # Create application
        app = QApplication([])
        print("✅ QApplication created")
        
        # Create tab widget
        tab_widget = QTabWidget()
        print("✅ QTabWidget created")
        
        # Test 1: SoapBoxx Tab
        print("\n🧪 Test 1: SoapBoxx Tab")
        soapboxx_tab = SoapBoxxTab()
        print(f"   Type: {type(soapboxx_tab)}")
        print(f"   Is QWidget: {isinstance(soapboxx_tab, QWidget)}")
        print(f"   Has layout: {soapboxx_tab.layout() is not None}")
        if soapboxx_tab.layout():
            print(f"   Layout item count: {soapboxx_tab.layout().count()}")
        
        tab_widget.addTab(soapboxx_tab, "SoapBoxx")
        print("   ✅ SoapBoxx tab added")
        
        # Test 2: Scoop Tab
        print("\n🧪 Test 2: Scoop Tab")
        scoop_tab = ScoopTab()
        print(f"   Type: {type(scoop_tab)}")
        print(f"   Is QWidget: {isinstance(scoop_tab, QWidget)}")
        print(f"   Has layout: {scoop_tab.layout() is not None}")
        if scoop_tab.layout():
            print(f"   Layout item count: {scoop_tab.layout().count()}")
        
        tab_widget.addTab(scoop_tab, "Scoop")
        print("   ✅ Scoop tab added")
        
        # Test 3: Reverb Tab
        print("\n🧪 Test 3: Reverb Tab")
        reverb_tab = ReverbTab()
        print(f"   Type: {type(reverb_tab)}")
        print(f"   Is QWidget: {isinstance(reverb_tab, QWidget)}")
        print(f"   Has layout: {reverb_tab.layout() is not None}")
        if reverb_tab.layout():
            print(f"   Layout item count: {reverb_tab.layout().count()}")
        
        tab_widget.addTab(reverb_tab, "Reverb")
        print("   ✅ Reverb tab added")
        
        # Display results
        print(f"\n📊 Final Results:")
        print(f"   Tab count: {tab_widget.count()}")
        
        # Show the widget
        tab_widget.show()
        print("\n🎉 All tests completed! Widget should be visible with 3 tabs.")
        print("Each tab should show a label with the tab name.")
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
    print("🚀 Testing Tab Content")
    print("=" * 30)
    
    success = test_tab_content()
    
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)
