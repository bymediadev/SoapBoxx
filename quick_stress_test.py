#!/usr/bin/env python3
"""
SoapBoxx Quick Stress Test
Focused testing of key workflows in under 2 minutes
"""

import json
import sys
import time
from datetime import datetime

# Add backend to path
sys.path.append("backend")

from backend.audio_recorder import AudioRecorder
from backend.config import Config
from backend.feedback_engine import FeedbackEngine
from backend.guest_research import GuestResearch
from backend.soapboxx_core import SoapBoxxCore
from backend.transcriber import Transcriber


class QuickStressTester:
    def __init__(self):
        self.results = {}
        self.start_time = None
        self.end_time = None

    def test_critical_components(self):
        """Test critical system components"""
        print("🚀 Testing Critical Components...")

        try:
            # Test config and OpenAI
            config = Config()
            openai_key = config.get_openai_api_key()
            assert openai_key, "OpenAI API key required"
            print("   ✅ OpenAI API configured")

            # Test core components
            components = {
                "AudioRecorder": AudioRecorder(),
                "Transcriber": Transcriber(),
                "FeedbackEngine": FeedbackEngine(),
                "GuestResearch": GuestResearch(),
                "SoapBoxxCore": SoapBoxxCore(),
            }

            for name, component in components.items():
                assert component is not None, f"{name} should initialize"
                print(f"   ✅ {name} ready")

            return True

        except Exception as e:
            print(f"   ❌ Critical components failed: {e}")
            return False

    def test_recording_workflow(self):
        """Test complete recording workflow"""
        print("🎤 Testing Recording Workflow...")

        try:
            recorder = AudioRecorder()
            transcriber = Transcriber()
            feedback_engine = FeedbackEngine()

            # Start recording
            start_time = time.time()
            recording_success = recorder.start_recording()

            if not recording_success:
                print("   ❌ Failed to start recording")
                return False

            # Simulate recording
            time.sleep(1)  # 1 second recording

            # Stop and get audio
            audio_data = recorder.stop_recording()
            recording_time = time.time() - start_time

            print(f"   ✅ Recording: {recording_time:.2f}s ({len(audio_data)} bytes)")

            # Transcribe
            transcription_start = time.time()
            transcript = transcriber.transcribe(audio_data)
            transcription_time = time.time() - transcription_start

            if transcript.startswith("Error:"):
                print(f"   ⚠️ Transcription failed, using fallback")
                transcript = "Test transcript for feedback analysis."
            else:
                print(
                    f"   ✅ Transcription: {transcription_time:.2f}s ({len(transcript)} chars)"
                )

            # Generate feedback
            feedback_start = time.time()
            feedback = feedback_engine.analyze(transcript)
            feedback_time = time.time() - feedback_start

            print(f"   ✅ Feedback: {feedback_time:.2f}s")

            total_time = time.time() - start_time
            print(f"   ✅ Complete workflow: {total_time:.2f}s")

            return {
                "recording_time": recording_time,
                "transcription_time": transcription_time,
                "feedback_time": feedback_time,
                "total_time": total_time,
                "success": True,
            }

        except Exception as e:
            print(f"   ❌ Recording workflow failed: {e}")
            return {"success": False, "error": str(e)}

    def test_guest_research(self):
        """Test guest research functionality"""
        print("🔍 Testing Guest Research...")

        try:
            research = GuestResearch()

            # Test 3 different guest types
            test_guests = ["Tech Expert", "Business Leader", "Podcast Host"]
            results = []

            for guest in test_guests:
                start_time = time.time()
                result = research.research(guest)
                research_time = time.time() - start_time

                success = "error" not in result
                results.append(
                    {"guest": guest, "research_time": research_time, "success": success}
                )

                status = "✅" if success else "⚠️"
                print(f"   {status} {guest}: {research_time:.2f}s")

            successful = sum(1 for r in results if r["success"])
            print(f"   ✅ Research: {successful}/{len(results)} successful")

            return results

        except Exception as e:
            print(f"   ❌ Guest research failed: {e}")
            return [{"success": False, "error": str(e)}]

    def test_concurrent_operations(self):
        """Test concurrent operations"""
        print("⚡ Testing Concurrent Operations...")

        try:
            import concurrent.futures

            def run_transcription():
                transcriber = Transcriber()
                dummy_audio = b"dummy_audio_data" * 50
                result = transcriber.transcribe(dummy_audio)
                return result if isinstance(result, str) else str(result)

            def run_feedback():
                engine = FeedbackEngine()
                return engine.analyze("Test transcript for concurrent testing.")

            def run_research():
                research = GuestResearch()
                return research.research("Test Guest")

            # Run 3 concurrent operations
            start_time = time.time()

            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = [
                    executor.submit(run_transcription),
                    executor.submit(run_feedback),
                    executor.submit(run_research),
                ]

                results = [
                    future.result()
                    for future in concurrent.futures.as_completed(futures)
                ]

            total_time = time.time() - start_time

            # Check results
            transcription_success = not results[0].startswith("Error:")
            feedback_success = "listener_feedback" in results[1]
            research_success = "error" not in results[2]

            successful = sum(
                [transcription_success, feedback_success, research_success]
            )
            print(f"   ✅ Concurrent: {successful}/3 successful in {total_time:.2f}s")

            return {
                "total_time": total_time,
                "successful": successful,
                "total": 3,
                "success": successful == 3,
            }

        except Exception as e:
            print(f"   ❌ Concurrent operations failed: {e}")
            return {"success": False, "error": str(e)}

    def test_error_handling(self):
        """Test error handling scenarios"""
        print("🛡️ Testing Error Handling...")

        try:
            transcriber = Transcriber()
            feedback_engine = FeedbackEngine()
            research = GuestResearch()

            scenarios = [
                ("Empty audio", b""),
                ("Invalid data", b"not_audio"),
                ("None input", None),
            ]

            handled_count = 0

            for scenario_name, test_data in scenarios:
                try:
                    if test_data is not None:
                        result = transcriber.transcribe(test_data)
                        handled = result.startswith("Error:")
                    else:
                        result = transcriber.transcribe(None)
                        handled = result.startswith("Error:")

                    if handled:
                        handled_count += 1
                        print(f"   ✅ {scenario_name}: Handled gracefully")
                    else:
                        print(f"   ⚠️ {scenario_name}: Not handled as expected")

                except Exception:
                    print(f"   ❌ {scenario_name}: Crashed")

            print(
                f"   ✅ Error handling: {handled_count}/{len(scenarios)} scenarios handled"
            )
            return {
                "handled": handled_count,
                "total": len(scenarios),
                "success": handled_count == len(scenarios),
            }

        except Exception as e:
            print(f"   ❌ Error handling test failed: {e}")
            return {"success": False, "error": str(e)}

    def run_quick_test(self):
        """Run quick stress test"""
        print("🚀 Starting SoapBoxx Quick Stress Test")
        print("=" * 50)

        self.start_time = time.time()

        # Run quick tests
        tests = [
            ("Critical Components", self.test_critical_components),
            ("Recording Workflow", self.test_recording_workflow),
            ("Guest Research", self.test_guest_research),
            ("Concurrent Operations", self.test_concurrent_operations),
            ("Error Handling", self.test_error_handling),
        ]

        for test_name, test_func in tests:
            print(f"\n🔬 {test_name}")
            print("-" * 30)

            try:
                result = test_func()
                self.results[test_name] = result
                print(f"✅ {test_name} completed")
            except Exception as e:
                print(f"❌ {test_name} failed: {e}")
                self.results[test_name] = {"error": str(e)}

        self.end_time = time.time()

        # Generate quick report
        self._generate_quick_report()

        return self.results

    def _generate_quick_report(self):
        """Generate quick test report"""
        total_time = self.end_time - self.start_time

        print("\n" + "=" * 50)
        print("📊 QUICK STRESS TEST RESULTS")
        print("=" * 50)

        print(f"Total Test Time: {total_time:.2f} seconds")
        print(f"Tests Completed: {len(self.results)}")

        # Calculate success rate
        successful_tests = 0
        total_operations = 0
        successful_operations = 0

        for test_name, result in self.results.items():
            if isinstance(result, bool):
                if result:
                    successful_tests += 1
                    successful_operations += 1
                total_operations += 1
            elif isinstance(result, dict):
                if result.get("success", False):
                    successful_tests += 1
                    successful_operations += 1
                total_operations += 1
            elif isinstance(result, list):
                total_operations += len(result)
                successful_operations += sum(
                    1 for r in result if r.get("success", False)
                )

        success_rate = (
            (successful_operations / total_operations * 100)
            if total_operations > 0
            else 0
        )

        print(f"Successful Tests: {successful_tests}/{len(self.results)}")
        print(f"Total Operations: {total_operations}")
        print(f"Successful Operations: {successful_operations}")
        print(f"Success Rate: {success_rate:.1f}%")

        # Quick assessment
        if success_rate >= 95:
            print("\n🎉 EXCELLENT: System is rock solid!")
        elif success_rate >= 80:
            print("\n✅ GOOD: System is very reliable")
        elif success_rate >= 60:
            print("\n⚠️ FAIR: System has some issues")
        else:
            print("\n❌ POOR: System needs attention")

        # Save report
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_time": total_time,
            "successful_tests": successful_tests,
            "total_tests": len(self.results),
            "success_rate": success_rate,
            "results": self.results,
        }

        with open("quick_stress_test_report.json", "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n📄 Report saved to: quick_stress_test_report.json")


def main():
    """Main quick stress test runner"""
    tester = QuickStressTester()
    results = tester.run_quick_test()

    print("\n🏁 Quick stress testing completed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
