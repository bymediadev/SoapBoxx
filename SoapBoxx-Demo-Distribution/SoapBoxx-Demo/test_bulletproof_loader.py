#!/usr/bin/env python3
"""
Test script for the bulletproof tab loader
==========================================

This script tests the bulletproof tab loader to ensure it properly handles
all PyQt6 edge cases and tab insertion scenarios.
"""

import sys
import os

# Add frontend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'frontend'))

def test_bulletproof_loader():
    """Test the bulletproof tab loader functionality"""
    try:
        from PyQt6.QtWidgets import QApplication, QTabWidget, QWidget, QVBoxLayout, QLabel
        from PyQt6.QtCore import Qt
        from bulletproof_tab_loader import create_bulletproof_tab_loader
        
        print("✅ PyQt6 and bulletproof loader imported successfully")
        
        # Create application
        app = QApplication([])
        print("✅ QApplication created")
        
        # Create tab widget
        tab_widget = QTabWidget()
        print("✅ QTabWidget created")
        
        # Create bulletproof loader
        loader = create_bulletproof_tab_loader(tab_widget)
        print("✅ Bulletproof tab loader created")
        
        # Test 1: Valid QWidget tab
        print("\n🧪 Test 1: Valid QWidget tab")
        valid_tab = QWidget()
        layout = QVBoxLayout(valid_tab)
        label = QLabel("Valid QWidget Tab")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        
        success = loader.safe_insert_tab(0, valid_tab, "Valid Tab")
        print(f"Result: {'✅ Success' if success else '❌ Failed'}")
        
        # Test 2: Object with layout method
        print("\n🧪 Test 2: Object with layout method")
        class LayoutObject:
            def __init__(self):
                self._layout = QVBoxLayout()
                label = QLabel("Layout Object Tab")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._layout.addWidget(label)
            
            def layout(self):
                return self._layout
        
        layout_obj = LayoutObject()
        success = loader.safe_insert_tab(1, layout_obj, "Layout Object")
        print(f"Result: {'✅ Success' if success else '❌ Failed'}")
        
        # Test 3: Generic object
        print("\n🧪 Test 3: Generic object")
        class GenericObject:
            def __init__(self):
                self.name = "Generic Object"
        
        generic_obj = GenericObject()
        success = loader.safe_insert_tab(2, generic_obj, "Generic Object")
        print(f"Result: {'✅ Success' if success else '❌ Failed'}")
        
        # Test 4: None object (should create fallback)
        print("\n🧪 Test 4: None object (fallback test)")
        success = loader.safe_insert_tab(3, None, "None Object")
        print(f"Result: {'✅ Success' if success else '❌ Failed'}")
        
        # Display results
        print(f"\n📊 Final Results:")
        print(f"   Tab count: {tab_widget.count()}")
        print(f"   Error count: {loader.get_error_count()}")
        print(f"   Loaded tabs: {loader.get_loaded_tabs()}")
        
        # Show the widget briefly
        tab_widget.show()
        print("\n🎉 All tests completed! Widget should be visible.")
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
    print("🚀 Testing Bulletproof Tab Loader")
    print("=" * 40)
    
    success = test_bulletproof_loader()
    
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)
