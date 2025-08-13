#!/usr/bin/env python3
"""
Simple Demo - Basic tab functionality test
=========================================

This script creates a minimal demo with just the essential tab functionality
to isolate any issues.
"""

import sys
import os

# Add frontend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'frontend'))

def simple_demo():
    """Simple demo with basic tabs"""
    try:
        from PyQt6.QtWidgets import QApplication, QTabWidget, QWidget, QVBoxLayout, QLabel
        from PyQt6.QtCore import Qt
        from main_window import SoapBoxxTab, ScoopTab, ReverbTab
        
        print("🚀 Starting Simple Demo")
        print("=" * 40)
        
        # Create application
        app = QApplication([])
        print("✅ QApplication created")
        
        # Create main window
        main_widget = QWidget()
        main_widget.setWindowTitle("SoapBoxx Demo - Simple Version")
        main_widget.resize(800, 600)
        
        # Create layout
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        
        # Create tab widget
        tab_widget = QTabWidget()
        print("✅ QTabWidget created")
        
        # Create and add tabs directly (no lazy loading)
        print("\n📱 Creating tabs...")
        
        # Tab 1: SoapBoxx
        print("   Creating SoapBoxx tab...")
        soapboxx_tab = SoapBoxxTab()
        tab_widget.addTab(soapboxx_tab, "SoapBoxx")
        print("   ✅ SoapBoxx tab added")
        
        # Tab 2: Scoop
        print("   Creating Scoop tab...")
        scoop_tab = ScoopTab()
        tab_widget.addTab(scoop_tab, "Scoop")
        print("   ✅ Scoop tab added")
        
        # Tab 3: Reverb
        print("   Creating Reverb tab...")
        reverb_tab = ReverbTab()
        tab_widget.addTab(reverb_tab, "Reverb")
        print("   ✅ Reverb tab added")
        
        # Add tab widget to main layout
        layout.addWidget(tab_widget)
        
        # Display results
        print(f"\n📊 Demo Results:")
        print(f"   Tab count: {tab_widget.count()}")
        print(f"   Current tab index: {tab_widget.currentIndex()}")
        
        # Show the main window
        main_widget.show()
        print("\n🎉 Demo is now running!")
        print("You should see:")
        print("   - A window titled 'SoapBoxx Demo - Simple Version'")
        print("   - 3 tabs: SoapBoxx, Scoop, Reverb")
        print("   - Each tab should show a label with the tab name")
        print("   - Click between tabs to switch")
        print("\nPress Ctrl+C to exit...")
        
        # Keep the application running
        app.exec()
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = simple_demo()
    
    if success:
        print("\n✅ Demo completed successfully!")
    else:
        print("\n❌ Demo failed!")
        sys.exit(1)
