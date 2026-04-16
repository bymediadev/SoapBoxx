#!/usr/bin/env python3
"""
Test script for SoapBoxx tab with local Whisper integration
"""

import os
import sys
from pathlib import Path

import pytest

# Add backend to path
sys.path.insert(0, str(Path("backend")))


def test_soapboxx_local():
    """Test SoapBoxx tab with local Whisper"""
    print("🎤 Testing SoapBoxx tab with local Whisper...")

    try:
        from transcriber import Transcriber

        # Test local transcriber
        print("🔧 Testing local transcriber...")
        transcriber = Transcriber(service="local")

        model_info = transcriber.get_local_model_info()
        if model_info.get("available"):
            print(
                f"✅ Local Whisper available: {model_info.get('model_size', 'unknown')}"
            )
        else:
            print(
                f"❌ Local Whisper not available: {model_info.get('error', 'Unknown error')}"
            )
            pytest.skip(
                f"local Whisper not available: {model_info.get('error', 'unknown')}"
            )

        # Test service selection
        print("\n🔧 Testing service selection...")
        services = ["openai", "local", "assemblyai", "azure"]

        for service in services:
            try:
                test_transcriber = Transcriber(service=service)
                if service == "local":
                    info = test_transcriber.get_local_model_info()
                    if info.get("available"):
                        print(f"✅ {service}: Available")
                    else:
                        print(f"⚠️ {service}: {info.get('error', 'Not available')}")
                else:
                    print(f"✅ {service}: Configured")
            except Exception as e:
                print(f"❌ {service}: {str(e)}")

        print("\n🎯 Local Whisper integration test completed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        pytest.fail(str(e))


if __name__ == "__main__":
    success = test_soapboxx_local()
    print(f"\n🎯 Test {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)
