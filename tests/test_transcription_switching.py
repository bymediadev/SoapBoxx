#!/usr/bin/env python3
"""
Test script to verify transcription service switching functionality
"""

import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

try:
    from soapboxx_core import SoapBoxxCore
    from transcriber import Transcriber

    print("✅ Backend imports successful")
except ImportError as e:
    print(f"❌ Backend import failed: {e}")
    sys.exit(1)


def test_transcription_services():
    """Test different transcription services"""
    print("\n🔧 Testing Transcription Services...")

    # Test local service
    print("\n1. Testing Local Whisper:")
    try:
        local_transcriber = Transcriber(service="local")
        model_info = local_transcriber.get_local_model_info()
        if model_info.get("available"):
            print(
                f"   ✅ Local Whisper available: {model_info.get('model_size', 'unknown')}"
            )
        else:
            print(
                f"   ❌ Local Whisper not available: {model_info.get('error', 'Unknown error')}"
            )
    except Exception as e:
        print(f"   ❌ Local Whisper test failed: {e}")

    # Test OpenAI service
    print("\n2. Testing OpenAI:")
    try:
        openai_transcriber = Transcriber(service="openai")
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            print(f"   ✅ OpenAI API key configured: [HIDDEN]")
        else:
            print("   ⚠️ OpenAI API key not configured")
    except Exception as e:
        print(f"   ❌ OpenAI test failed: {e}")

    # Test AssemblyAI service
    print("\n3. Testing AssemblyAI:")
    try:
        assemblyai_transcriber = Transcriber(service="assemblyai")
        api_key = os.getenv("ASSEMBLYAI_API_KEY")
        if api_key:
            print(f"   ✅ AssemblyAI API key configured: [HIDDEN]")
        else:
            print("   ⚠️ AssemblyAI API key not configured")
    except Exception as e:
        print(f"   ❌ AssemblyAI test failed: {e}")

    # Test Azure service
    print("\n4. Testing Azure Speech:")
    try:
        azure_transcriber = Transcriber(service="azure")
        api_key = os.getenv("AZURE_SPEECH_KEY")
        if api_key:
            print(f"   ✅ Azure Speech key configured: [HIDDEN]")
        else:
            print("   ⚠️ Azure Speech key not configured")
    except Exception as e:
        print(f"   ❌ Azure test failed: {e}")


def test_core_service_switching():
    """Test SoapBoxxCore service switching"""
    print("\n🎤 Testing SoapBoxxCore Service Switching...")

    try:
        # Initialize core with default service
        core = SoapBoxxCore(transcription_service="openai")
        print(f"   ✅ Core initialized with service: {core.transcription_service}")

        # Test switching to local
        print("\n   Switching to local service...")
        core.set_transcription_service("local")
        print(f"   ✅ Switched to: {core.transcription_service}")

        # Test switching to OpenAI
        print("\n   Switching to OpenAI service...")
        core.set_transcription_service("openai")
        print(f"   ✅ Switched to: {core.transcription_service}")

        # Test switching to AssemblyAI
        print("\n   Switching to AssemblyAI service...")
        core.set_transcription_service("assemblyai")
        print(f"   ✅ Switched to: {core.transcription_service}")

        # Test switching to Azure
        print("\n   Switching to Azure service...")
        core.set_transcription_service("azure")
        print(f"   ✅ Switched to: {core.transcription_service}")

    except Exception as e:
        print(f"   ❌ Core service switching test failed: {e}")


def main():
    """Main test function"""
    print("🚀 Testing Transcription Service Switching Functionality")
    print("=" * 60)

    test_transcription_services()
    test_core_service_switching()

    print("\n" + "=" * 60)
    print("✅ Testing completed!")
    print("\nTo use the transcription service switching in the UI:")
    print("1. Open the SoapBoxx application")
    print("2. Go to the SoapBoxx tab")
    print("3. Use the 'Service' dropdown to switch between:")
    print("   - OpenAI (requires API key)")
    print("   - Local (requires Whisper installation)")
    print("   - AssemblyAI (requires API key)")
    print("   - Azure Speech (requires API key)")
    print("4. The service status will update automatically")
    print("5. Start recording to use the selected service")


if __name__ == "__main__":
    main()
