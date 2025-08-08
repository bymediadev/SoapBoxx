#!/usr/bin/env python3
"""
Test script for OpenAI API integration across SoapBoxx platform
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path("backend")))


def test_openai_integration():
    """Test OpenAI API integration across all components"""
    print("🔑 Testing OpenAI API integration across SoapBoxx platform...")

    try:
        # Test 1: Environment variable loading
        print("\n1️⃣ Testing environment variable loading...")
        from dotenv import load_dotenv

        load_dotenv()

        env_key = os.getenv("OPENAI_API_KEY")
        if env_key:
            print(f"   ✅ Environment variable loaded: {env_key[:8]}...")
        else:
            print("   ❌ Environment variable not found")
            return False

        # Test 2: Config class integration
        print("\n2️⃣ Testing config class integration...")
        from config import config

        config_key = config.get_openai_api_key()
        if config_key:
            print(f"   ✅ Config class integration: {config_key[:8]}...")
        else:
            print("   ❌ Config class integration failed")
            return False

        # Test 3: Transcriber component
        print("\n3️⃣ Testing Transcriber component...")
        from transcriber import Transcriber

        transcriber = Transcriber(api_key=config_key)
        if transcriber.api_key:
            print(f"   ✅ Transcriber component: [HIDDEN]")
        else:
            print("   ❌ Transcriber component failed")
            return False

        # Test 4: Feedback Engine component
        print("\n4️⃣ Testing Feedback Engine component...")
        from feedback_engine import FeedbackEngine

        feedback_engine = FeedbackEngine(api_key=config_key)
        if feedback_engine.api_key:
            print(f"   ✅ Feedback Engine component: [HIDDEN]")
        else:
            print("   ❌ Feedback Engine component failed")
            return False

        # Test 5: Guest Research component
        print("\n5️⃣ Testing Guest Research component...")
        from guest_research import GuestResearch

        guest_research = GuestResearch(openai_api_key=config_key)
        if guest_research.api_key:
            print(f"   ✅ Guest Research component: [HIDDEN]")
        else:
            print("   ❌ Guest Research component failed")
            return False

        # Test 6: SoapBoxx Core integration
        print("\n6️⃣ Testing SoapBoxx Core integration...")
        from soapboxx_core import SoapBoxxCore

        core = SoapBoxxCore(api_key=config_key)
        if hasattr(core, "transcriber") and core.transcriber.api_key:
            print(f"   ✅ SoapBoxx Core integration: [HIDDEN]")
        else:
            print("   ❌ SoapBoxx Core integration failed")
            return False

        print("\n🎉 All OpenAI API integration tests passed!")
        print("\n📊 Integration Summary:")
        print("   ✅ Environment variable loading")
        print("   ✅ Config class integration")
        print("   ✅ Transcriber component")
        print("   ✅ Feedback Engine component")
        print("   ✅ Guest Research component")
        print("   ✅ SoapBoxx Core integration")

        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False


if __name__ == "__main__":
    success = test_openai_integration()
    sys.exit(0 if success else 1)
