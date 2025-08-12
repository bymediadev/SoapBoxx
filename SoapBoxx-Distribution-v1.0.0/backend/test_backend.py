#!/usr/bin/env python3
"""
Comprehensive test suite for SoapBoxx backend
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from audio_recorder import AudioRecorder
from config import Config
from error_tracker import error_tracker
from feedback_engine import FeedbackEngine
from guest_research import GuestResearch
from logger import Logger
from soapboxx_core import SoapBoxxCore
from transcriber import Transcriber


class BackendTester:
    def __init__(self):
        self.results = {}
        self.config = Config()
        self.logger = Logger()

    def test_openai_critical(self):
        """Test OpenAI API - CRITICAL SYSTEM COMPONENT"""
        print("🔑 CRITICAL: Testing OpenAI API configuration...")
        try:
            from config import config

            # Check if OpenAI is configured
            if not config.is_openai_configured():
                print("❌ CRITICAL ERROR: OpenAI API is NOT configured!")
                print("   This will severely limit system functionality")
                print("   - Transcription will fail")
                print("   - AI feedback will be unavailable")
                print("   - Guest research will be limited")
                print("   - Most core features will not work")
                return False

            # Get detailed OpenAI status
            openai_status = config.get_openai_status()

            if openai_status["configured"]:
                print("✅ CRITICAL SUCCESS: OpenAI API is properly configured!")
                print("   Enabled features:")
                for feature in openai_status["features_enabled"]:
                    print(f"   ✅ {feature}")
                print("   Recommendations:")
                for rec in openai_status["recommendations"]:
                    print(f"   💡 {rec}")
                return True
            else:
                print("❌ CRITICAL ERROR: OpenAI API configuration failed!")
                print("   Disabled features:")
                for feature in openai_status["features_disabled"]:
                    print(f"   ❌ {feature}")
                print("   Recommendations:")
                for rec in openai_status["recommendations"]:
                    print(f"   💡 {rec}")
                return False

        except Exception as e:
            print(f"❌ CRITICAL ERROR: OpenAI test failed: {e}")
            return False

    def test_configuration(self):
        """Test configuration system"""
        print("🔧 Testing Configuration...")
        try:
            # Test config loading
            config = Config()
            assert config is not None, "Config should load"

            # CRITICAL: Test OpenAI API key setup
            api_key = config.get_openai_api_key()
            if not api_key:
                print("⚠️  CRITICAL WARNING: No OpenAI API key configured")
                print("   This will severely limit system functionality")
                return False
            else:
                print(f"✅ CRITICAL SUCCESS: OpenAI API key found: [HIDDEN]")

            # Test config validation
            validation = config.validate_config()
            if validation["valid"]:
                print("✅ Configuration is valid")
                return True
            else:
                print(f"❌ Configuration issues: {validation['issues']}")
                return False

        except Exception as e:
            print(f"❌ Configuration test failed: {e}")
            return False

    def test_audio_recorder(self):
        """Test audio recording system"""
        print("🎤 Testing Audio Recorder...")
        try:
            recorder = AudioRecorder()
            assert recorder is not None, "AudioRecorder should initialize"

            # Test recorder properties
            assert recorder.samplerate == 16000, "Default sample rate should be 16000"
            assert recorder.channels == 1, "Default channels should be 1"

            print("✅ Audio Recorder initialized successfully")
            return True

        except Exception as e:
            print(f"❌ Audio Recorder test failed: {e}")
            return False

    def test_transcriber(self):
        """Test transcription system"""
        print("📝 Testing Transcriber...")
        try:
            transcriber = Transcriber()
            assert transcriber is not None, "Transcriber should initialize"

            # Test with empty audio (should handle gracefully)
            result = transcriber.transcribe(b"")
            assert isinstance(result, str), "Transcription should return string"

            print("✅ Transcriber initialized successfully")
            return True

        except Exception as e:
            print(f"❌ Transcriber test failed: {e}")
            return False

    def test_feedback_engine(self):
        """Test feedback analysis system"""
        print("🤖 Testing Feedback Engine...")
        try:
            engine = FeedbackEngine()
            assert engine is not None, "FeedbackEngine should initialize"

            # Test with empty transcript
            result = engine.analyze("")
            assert isinstance(result, dict), "Feedback should return dict"
            assert (
                "listener_feedback" in result
            ), "Feedback should have listener_feedback"

            print("✅ Feedback Engine initialized successfully")
            return True

        except Exception as e:
            print(f"❌ Feedback Engine test failed: {e}")
            return False

    def test_guest_research(self):
        """Test guest research system"""
        print("🔍 Testing Guest Research...")
        try:
            research = GuestResearch()
            assert research is not None, "GuestResearch should initialize"

            # Test with empty guest name (should handle gracefully)
            result = research.research("")
            assert isinstance(result, dict), "Research should return dict"

            print("✅ Guest Research initialized successfully")
            return True

        except Exception as e:
            print(f"❌ Guest Research test failed: {e}")
            return False

    def test_logger(self):
        """Test logging system"""
        print("📋 Testing Logger...")
        try:
            logger = Logger()
            assert logger is not None, "Logger should initialize"

            # Test logging methods
            logger.log_error("Test error message")
            logger.log_ui_bug("Test UI bug message")
            logger.log_audio_issue("Test audio issue message")

            print("✅ Logger initialized and working")
            return True

        except Exception as e:
            print(f"❌ Logger test failed: {e}")
            return False

    def test_full_integration(self):
        """Test full system integration"""
        print("🔗 Testing Full Integration...")
        try:
            core = SoapBoxxCore()
            assert core is not None, "SoapBoxxCore should initialize"

            # Test status
            status = core.get_status()
            assert isinstance(status, dict), "Status should return dict"

            print("✅ Full integration test passed")
            return True

        except Exception as e:
            print(f"❌ Full integration test failed: {e}")
            return False

    def run_all_tests(self):
        """Run all tests and generate report"""
        print("🚀 Starting SoapBoxx Backend Test Suite")
        print("=" * 50)

        tests = [
            ("OpenAI API (CRITICAL)", self.test_openai_critical),
            ("Configuration", self.test_configuration),
            ("Audio Recorder", self.test_audio_recorder),
            ("Transcriber", self.test_transcriber),
            ("Feedback Engine", self.test_feedback_engine),
            ("Guest Research", self.test_guest_research),
            ("Logger", self.test_logger),
            ("Full Integration", self.test_full_integration),
        ]

        passed = 0
        failed = 0

        for test_name, test_func in tests:
            try:
                result = test_func()
                self.results[test_name] = result
                if result:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"❌ {test_name} test crashed: {e}")
                self.results[test_name] = False
                failed += 1

        # Generate report
        self._generate_report(passed, failed)

        return passed, failed

    def _generate_report(self, passed, failed):
        """Generate test report"""
        print("\n" + "=" * 50)
        print("📊 TEST RESULTS")
        print("=" * 50)

        for test_name, result in self.results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test_name:<20} {status}")

        print(f"\nTotal Tests: {passed + failed}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")

        # Save report
        report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_tests": passed + failed,
            "passed_tests": passed,
            "failed_tests": failed,
            "results": self.results,
            "config_status": {
                "valid": self.results.get("Configuration", False),
                "issues": (
                    []
                    if self.results.get("Configuration", False)
                    else ["OpenAI API key not configured"]
                ),
                "configured": bool(self.config.get_openai_api_key()),
            },
        }

        with open("backend_test_report.json", "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n📄 Report saved to: backend_test_report.json")


def main():
    """Main test runner"""
    tester = BackendTester()
    passed, failed = tester.run_all_tests()

    if failed == 0:
        print("\n🎉 All tests passed! Backend is ready to use.")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please check the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
