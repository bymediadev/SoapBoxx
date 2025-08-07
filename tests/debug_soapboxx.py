#!/usr/bin/env python3
"""
SoapBoxx Debug Script
Comprehensive debugging and testing for all components
"""

import os
import sys
import traceback
from pathlib import Path

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
sys.path.append(os.path.join(os.path.dirname(__file__), "frontend"))


def test_imports():
    """Test all imports"""
    print("🔍 Testing imports...")

    try:
        # Test backend imports
        from soapboxx_core import SoapBoxxCore

        print("✅ SoapBoxxCore imported successfully")
    except Exception as e:
        print(f"❌ SoapBoxxCore import failed: {e}")
        traceback.print_exc()

    try:
        from transcriber import Transcriber

        print("✅ Transcriber imported successfully")
    except Exception as e:
        print(f"❌ Transcriber import failed: {e}")
        traceback.print_exc()

    try:
        from feedback_engine import FeedbackEngine

        print("✅ FeedbackEngine imported successfully")
    except Exception as e:
        print(f"❌ FeedbackEngine import failed: {e}")
        traceback.print_exc()

    try:
        from guest_research import GuestResearch

        print("✅ GuestResearch imported successfully")
    except Exception as e:
        print(f"❌ GuestResearch import failed: {e}")
        traceback.print_exc()

    try:
        from config import Config

        print("✅ Config imported successfully")
    except Exception as e:
        print(f"❌ Config import failed: {e}")
        traceback.print_exc()


def test_openai_compatibility():
    """Test OpenAI API compatibility"""
    print("\n🤖 Testing OpenAI API compatibility...")

    try:
        import openai

        print(f"✅ OpenAI package version: {openai.__version__}")

        # Test new API
        try:
            from openai import OpenAI

            print("✅ New OpenAI API (v1.0.0+) available")
        except ImportError:
            print("⚠️ New OpenAI API not available, using legacy API")

    except ImportError:
        print("❌ OpenAI package not installed")
        return False

    return True


def test_audio_devices():
    """Test audio device detection"""
    print("\n🎤 Testing audio devices...")

    try:
        import sounddevice as sd

        devices = sd.query_devices()
        input_devices = []

        for i, device in enumerate(devices):
            max_inputs = device.get("max_inputs", 0)
            if max_inputs > 0:
                device_name = device.get("name", f"Device {i}")
                input_devices.append(f"{device_name} (ID: {i})")

        print(f"✅ Found {len(input_devices)} input devices:")
        for device in input_devices:
            print(f"  - {device}")

        return len(input_devices) > 0

    except ImportError:
        print("❌ sounddevice not installed")
        return False
    except Exception as e:
        print(f"❌ Audio device detection failed: {e}")
        return False


def test_transcription_services():
    """Test transcription services"""
    print("\n🎙️ Testing transcription services...")

    try:
        from transcriber import Transcriber

        # Test local service
        print("Testing local Whisper...")
        local_transcriber = Transcriber(service="local")
        model_info = local_transcriber.get_local_model_info()
        if model_info.get("available"):
            print("✅ Local Whisper available")
        else:
            print("⚠️ Local Whisper not available")

        # Test OpenAI service
        print("Testing OpenAI service...")
        openai_transcriber = Transcriber(service="openai")
        if openai_transcriber.api_key:
            print("✅ OpenAI API key configured")
        else:
            print("⚠️ OpenAI API key not configured")

    except Exception as e:
        print(f"❌ Transcription service test failed: {e}")
        traceback.print_exc()


def test_configuration():
    """Test configuration"""
    print("\n⚙️ Testing configuration...")

    try:
        from config import Config

        config = Config()

        # Test API keys
        openai_key = config.get_openai_api_key()
        if openai_key:
            print(f"✅ OpenAI API key configured: {openai_key[:8]}...")
        else:
            print("⚠️ OpenAI API key not configured")

        google_cse_id = config.get_google_cse_id()
        if google_cse_id:
            print(f"✅ Google CSE ID configured: {google_cse_id[:8]}...")
        else:
            print("⚠️ Google CSE ID not configured")

    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        traceback.print_exc()


def test_backend_components():
    """Test backend components"""
    print("\n🔧 Testing backend components...")

    try:
        from soapboxx_core import SoapBoxxCore

        # Test core initialization
        print("Testing SoapBoxxCore initialization...")
        core = SoapBoxxCore(transcription_service="local")
        print("✅ SoapBoxxCore initialized successfully")

        # Test service switching
        print("Testing service switching...")
        core.set_transcription_service("openai")
        print("✅ Service switching works")

    except Exception as e:
        print(f"❌ Backend component test failed: {e}")
        traceback.print_exc()


def test_frontend_components():
    """Test frontend components"""
    print("\n🖥️ Testing frontend components...")

    try:
        # Test tab imports
        from soapboxx_tab import SoapBoxxTab

        print("✅ SoapBoxxTab imported successfully")

        from reverb_tab import ReverbTab

        print("✅ ReverbTab imported successfully")

        from scoop_tab import ScoopTab

        print("✅ ScoopTab imported successfully")

    except Exception as e:
        print(f"❌ Frontend component test failed: {e}")
        traceback.print_exc()


def test_dependencies():
    """Test required dependencies"""
    print("\n📦 Testing dependencies...")

    dependencies = [
        ("PyQt6", "PyQt6"),
        ("numpy", "numpy"),
        ("requests", "requests"),
        ("sounddevice", "sounddevice"),
        ("openai", "openai"),
        ("whisper", "whisper"),  # Changed from "openai-whisper" to "whisper"
        ("pydub", "pydub"),
        ("python-dotenv", "dotenv"),
    ]

    for package_name, import_name in dependencies:
        try:
            __import__(import_name)
            print(f"✅ {package_name} available")
        except ImportError:
            print(f"❌ {package_name} not available")


def main():
    """Main debug function"""
    print("🔍 SoapBoxx Debug Script")
    print("=" * 50)

    # Test imports
    test_imports()

    # Test OpenAI compatibility
    test_openai_compatibility()

    # Test audio devices
    test_audio_devices()

    # Test transcription services
    test_transcription_services()

    # Test configuration
    test_configuration()

    # Test backend components
    test_backend_components()

    # Test frontend components
    test_frontend_components()

    # Test dependencies
    test_dependencies()

    print("\n" + "=" * 50)
    print("🎯 Debug Summary:")
    print("1. Check the output above for any ❌ errors")
    print("2. Install missing dependencies with: pip install <package>")
    print("3. Configure API keys in .env file or config")
    print("4. Test audio devices if microphone issues occur")
    print("5. Run the application with: python frontend/main_window.py")


if __name__ == "__main__":
    main()
