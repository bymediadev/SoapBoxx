#!/usr/bin/env python3
"""
Minimal test script to test SoapBoxxTab creation
"""

import sys
import os

# Add backend to path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

try:
    print("Testing SoapBoxxTab creation...")
    
    # Try to create the tab without PyQt6
    print("1. Testing import...")
    from frontend.soapboxx_tab import SoapBoxxTab
    print("✅ SoapBoxxTab imported successfully")
    
    print("2. Testing basic initialization...")
    # Create a mock core object
    class MockCore:
        def __init__(self):
            self.transcription_service = "openai"
        
        def set_transcription_service(self, service):
            self.transcription_service = service
    
    mock_core = MockCore()
    print("✅ Mock core created")
    
    print("3. Testing tab creation...")
    # This will fail without PyQt6, but let's see where it fails
    try:
        tab = SoapBoxxTab()
        print("✅ SoapBoxxTab created successfully")
    except Exception as e:
        print(f"⚠️ SoapBoxxTab creation failed (expected without PyQt6): {e}")
    
    print("✅ Basic SoapBoxxTab test completed")
    
except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
