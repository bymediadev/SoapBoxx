#!/usr/bin/env python3
"""
SoapBoxx Stress Test Suite
Tests the entire system under various load conditions
"""

import os
import sys
import time
import threading
import concurrent.futures
import json
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.append("backend")

from backend.config import Config
from backend.audio_recorder import AudioRecorder
from backend.transcriber import Transcriber
from backend.feedback_engine import FeedbackEngine
from backend.guest_research import GuestResearch
from backend.logger import Logger
from backend.soapboxx_core import SoapBoxxCore
from backend.error_tracker import error_tracker, track_error

class StressTester:
    def __init__(self):
        self.results = {}
        self.config = Config()
        self.logger = Logger()
        self.start_time = None
        self.end_time = None
        
    def log_stress_event(self, event_type: str, details: dict):
        """Log stress test events"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "details": details
        }
        error_tracker.track_error(f"STRESS_TEST_{event_type}", details)
        
    def test_openai_api_stress(self):
        """Stress test OpenAI API with multiple concurrent requests"""
        print("🔑 STRESS TEST: OpenAI API Concurrent Requests...")
        
        def make_openai_request(request_id: int):
            try:
                start_time = time.time()
                
                # Simulate OpenAI API call
                transcriber = Transcriber()
                
                # Create dummy audio data (1KB)
                dummy_audio = b"dummy_audio_data" * 64
                
                # Attempt transcription
                result = transcriber.transcribe(dummy_audio)
                
                duration = time.time() - start_time
                
                self.log_stress_event("openai_request", {
                    "request_id": request_id,
                    "duration": duration,
                    "success": True,
                    "result_length": len(result) if result else 0
                })
                
                return {
                    "request_id": request_id,
                    "success": True,
                    "duration": duration,
                    "result_length": len(result) if result else 0
                }
                
            except Exception as e:
                duration = time.time() - start_time
                self.log_stress_event("openai_request_failed", {
                    "request_id": request_id,
                    "duration": duration,
                    "error": str(e)
                })
                
                return {
                    "request_id": request_id,
                    "success": False,
                    "duration": duration,
                    "error": str(e)
                }
        
        # Test with different concurrency levels
        concurrency_levels = [1, 3, 5, 10]
        results = {}
        
        for concurrency in concurrency_levels:
            print(f"   Testing {concurrency} concurrent requests...")
            
            start_time = time.time()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(make_openai_request, i) for i in range(concurrency)]
                responses = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            total_time = time.time() - start_time
            successful = sum(1 for r in responses if r["success"])
            failed = len(responses) - successful
            
            results[concurrency] = {
                "total_requests": concurrency,
                "successful": successful,
                "failed": failed,
                "total_time": total_time,
                "avg_response_time": total_time / concurrency,
                "responses": responses
            }
            
            print(f"     ✅ {successful}/{concurrency} successful in {total_time:.2f}s")
        
        return results
    
    def test_audio_recording_stress(self):
        """Stress test audio recording with rapid start/stop cycles"""
        print("🎤 STRESS TEST: Audio Recording Rapid Cycles...")
        
        results = []
        
        try:
            recorder = AudioRecorder()
            
            # Test rapid start/stop cycles
            for cycle in range(10):
                start_time = time.time()
                
                try:
                    # Start recording
                    recorder.start_recording()
                    time.sleep(0.1)  # Record for 100ms
                    
                    # Stop recording
                    audio_data = recorder.stop_recording()
                    
                    cycle_time = time.time() - start_time
                    
                    results.append({
                        "cycle": cycle,
                        "success": True,
                        "duration": cycle_time,
                        "audio_size": len(audio_data) if audio_data else 0
                    })
                    
                    print(f"     ✅ Cycle {cycle}: {cycle_time:.3f}s ({len(audio_data) if audio_data else 0} bytes)")
                    
                except Exception as e:
                    cycle_time = time.time() - start_time
                    results.append({
                        "cycle": cycle,
                        "success": False,
                        "duration": cycle_time,
                        "error": str(e)
                    })
                    
                    print(f"     ❌ Cycle {cycle}: Failed - {e}")
                    
        except Exception as e:
            print(f"     ❌ Audio recorder stress test failed: {e}")
        
        return results
    
    def test_transcription_stress(self):
        """Stress test transcription with various audio sizes"""
        print("📝 STRESS TEST: Transcription Various Audio Sizes...")
        
        results = []
        
        try:
            transcriber = Transcriber()
            
            # Test different audio sizes
            audio_sizes = [100, 1000, 10000, 100000]  # bytes
            
            for size in audio_sizes:
                start_time = time.time()
                
                try:
                    # Create dummy audio of specified size
                    dummy_audio = b"dummy_audio_data" * (size // 16)
                    
                    # Attempt transcription
                    result = transcriber.transcribe(dummy_audio)
                    
                    duration = time.time() - start_time
                    
                    results.append({
                        "audio_size": size,
                        "success": True,
                        "duration": duration,
                        "result_length": len(result) if result else 0
                    })
                    
                    print(f"     ✅ {size} bytes: {duration:.3f}s ({len(result) if result else 0} chars)")
                    
                except Exception as e:
                    duration = time.time() - start_time
                    results.append({
                        "audio_size": size,
                        "success": False,
                        "duration": duration,
                        "error": str(e)
                    })
                    
                    print(f"     ❌ {size} bytes: Failed - {e}")
                    
        except Exception as e:
            print(f"     ❌ Transcription stress test failed: {e}")
        
        return results
    
    def test_feedback_engine_stress(self):
        """Stress test feedback engine with various transcript lengths"""
        print("🤖 STRESS TEST: Feedback Engine Various Transcripts...")
        
        results = []
        
        try:
            engine = FeedbackEngine()
            
            # Test different transcript lengths
            transcript_lengths = [10, 100, 1000, 5000]  # words
            
            for length in transcript_lengths:
                start_time = time.time()
                
                try:
                    # Create dummy transcript
                    dummy_transcript = "This is a test transcript. " * length
                    
                    # Attempt feedback analysis
                    result = engine.analyze(dummy_transcript)
                    
                    duration = time.time() - start_time
                    
                    results.append({
                        "transcript_length": length,
                        "success": True,
                        "duration": duration,
                        "has_feedback": "listener_feedback" in result
                    })
                    
                    print(f"     ✅ {length} words: {duration:.3f}s")
                    
                except Exception as e:
                    duration = time.time() - start_time
                    results.append({
                        "transcript_length": length,
                        "success": False,
                        "duration": duration,
                        "error": str(e)
                    })
                    
                    print(f"     ❌ {length} words: Failed - {e}")
                    
        except Exception as e:
            print(f"     ❌ Feedback engine stress test failed: {e}")
        
        return results
    
    def test_guest_research_stress(self):
        """Stress test guest research with various guest names"""
        print("🔍 STRESS TEST: Guest Research Various Names...")
        
        results = []
        
        try:
            research = GuestResearch()
            
            # Test different guest names
            guest_names = ["John Doe", "Jane Smith", "Tech Expert", "Business Leader", "Podcast Host"]
            
            for name in guest_names:
                start_time = time.time()
                
                try:
                    # Attempt guest research
                    result = research.research(name)
                    
                    duration = time.time() - start_time
                    
                    results.append({
                        "guest_name": name,
                        "success": True,
                        "duration": duration,
                        "has_results": bool(result)
                    })
                    
                    print(f"     ✅ '{name}': {duration:.3f}s")
                    
                except Exception as e:
                    duration = time.time() - start_time
                    results.append({
                        "guest_name": name,
                        "success": False,
                        "duration": duration,
                        "error": str(e)
                    })
                    
                    print(f"     ❌ '{name}': Failed - {e}")
                    
        except Exception as e:
            print(f"     ❌ Guest research stress test failed: {e}")
        
        return results
    
    def test_memory_stress(self):
        """Stress test memory usage with repeated operations"""
        print("💾 STRESS TEST: Memory Usage Repeated Operations...")
        
        results = []
        
        try:
            import psutil
            import gc
            
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            print(f"     Initial memory: {initial_memory:.2f} MB")
            
            # Perform repeated operations
            for iteration in range(50):
                start_time = time.time()
                
                try:
                    # Create and destroy objects
                    transcriber = Transcriber()
                    feedback_engine = FeedbackEngine()
                    research = GuestResearch()
                    
                    # Simulate some work
                    dummy_audio = b"dummy_audio_data" * 100
                    transcriber.transcribe(dummy_audio)
                    
                    feedback_engine.analyze("Test transcript for memory stress test.")
                    research.research("Test Guest")
                    
                    # Force garbage collection
                    gc.collect()
                    
                    current_memory = process.memory_info().rss / 1024 / 1024
                    duration = time.time() - start_time
                    
                    results.append({
                        "iteration": iteration,
                        "success": True,
                        "duration": duration,
                        "memory_mb": current_memory,
                        "memory_increase": current_memory - initial_memory
                    })
                    
                    if iteration % 10 == 0:
                        print(f"     ✅ Iteration {iteration}: {duration:.3f}s, {current_memory:.2f} MB")
                    
                except Exception as e:
                    duration = time.time() - start_time
                    results.append({
                        "iteration": iteration,
                        "success": False,
                        "duration": duration,
                        "error": str(e)
                    })
                    
                    print(f"     ❌ Iteration {iteration}: Failed - {e}")
            
            final_memory = process.memory_info().rss / 1024 / 1024
            print(f"     Final memory: {final_memory:.2f} MB")
            print(f"     Memory increase: {final_memory - initial_memory:.2f} MB")
            
        except ImportError:
            print("     ⚠️ psutil not available, skipping memory monitoring")
            results = [{"note": "Memory monitoring not available"}]
        except Exception as e:
            print(f"     ❌ Memory stress test failed: {e}")
        
        return results
    
    def test_error_recovery_stress(self):
        """Stress test error recovery mechanisms"""
        print("🛡️ STRESS TEST: Error Recovery Mechanisms...")
        
        results = []
        
        # Test various error conditions
        error_scenarios = [
            ("Empty audio", b""),
            ("Invalid audio format", b"not_audio_data"),
            ("Very large audio", b"dummy" * 1000000),  # ~4MB
            ("None input", None),
        ]
        
        for scenario_name, test_data in error_scenarios:
            start_time = time.time()
            
            try:
                transcriber = Transcriber()
                
                if test_data is None:
                    result = transcriber.transcribe(None)
                else:
                    result = transcriber.transcribe(test_data)
                
                duration = time.time() - start_time
                
                # Check if error was handled gracefully
                handled_gracefully = result.startswith("Error:") if result else True
                
                results.append({
                    "scenario": scenario_name,
                    "success": handled_gracefully,
                    "duration": duration,
                    "graceful_handling": handled_gracefully
                })
                
                status = "✅" if handled_gracefully else "❌"
                print(f"     {status} {scenario_name}: {duration:.3f}s")
                
            except Exception as e:
                duration = time.time() - start_time
                results.append({
                    "scenario": scenario_name,
                    "success": False,
                    "duration": duration,
                    "error": str(e)
                })
                
                print(f"     ❌ {scenario_name}: Crashed - {e}")
        
        return results
    
    def run_all_stress_tests(self):
        """Run all stress tests and generate comprehensive report"""
        print("🚀 Starting SoapBoxx Stress Test Suite")
        print("=" * 60)
        
        self.start_time = time.time()
        
        # Run all stress tests
        tests = [
            ("OpenAI API Concurrent Requests", self.test_openai_api_stress),
            ("Audio Recording Rapid Cycles", self.test_audio_recording_stress),
            ("Transcription Various Sizes", self.test_transcription_stress),
            ("Feedback Engine Various Transcripts", self.test_feedback_engine_stress),
            ("Guest Research Various Names", self.test_guest_research_stress),
            ("Memory Usage Repeated Operations", self.test_memory_stress),
            ("Error Recovery Mechanisms", self.test_error_recovery_stress),
        ]
        
        for test_name, test_func in tests:
            print(f"\n🔬 {test_name}")
            print("-" * 40)
            
            try:
                result = test_func()
                self.results[test_name] = result
                print(f"✅ {test_name} completed")
            except Exception as e:
                print(f"❌ {test_name} failed: {e}")
                self.results[test_name] = {"error": str(e)}
        
        self.end_time = time.time()
        
        # Generate comprehensive report
        self._generate_stress_report()
        
        return self.results
    
    def _generate_stress_report(self):
        """Generate comprehensive stress test report"""
        total_time = self.end_time - self.start_time
        
        print("\n" + "=" * 60)
        print("📊 STRESS TEST RESULTS")
        print("=" * 60)
        
        print(f"Total Test Time: {total_time:.2f} seconds")
        print(f"Tests Completed: {len(self.results)}")
        
        # Calculate overall metrics
        total_requests = 0
        successful_requests = 0
        failed_requests = 0
        
        for test_name, result in self.results.items():
            if isinstance(result, dict) and "error" not in result:
                if test_name == "OpenAI API Concurrent Requests":
                    for concurrency, data in result.items():
                        total_requests += data["total_requests"]
                        successful_requests += data["successful"]
                        failed_requests += data["failed"]
                elif isinstance(result, list):
                    total_requests += len(result)
                    successful_requests += sum(1 for r in result if r.get("success", False))
                    failed_requests += sum(1 for r in result if not r.get("success", True))
        
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
        
        print(f"Total Requests: {total_requests}")
        print(f"Successful: {successful_requests}")
        print(f"Failed: {failed_requests}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        # Save detailed report
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_time": total_time,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": success_rate,
            "results": self.results
        }
        
        with open("stress_test_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: stress_test_report.json")
        
        # Overall assessment
        if success_rate >= 95:
            print("\n🎉 EXCELLENT: System handles stress very well!")
        elif success_rate >= 80:
            print("\n✅ GOOD: System handles stress well with minor issues")
        elif success_rate >= 60:
            print("\n⚠️ FAIR: System has some stress-related issues")
        else:
            print("\n❌ POOR: System has significant stress-related issues")

def main():
    """Main stress test runner"""
    tester = StressTester()
    results = tester.run_all_stress_tests()
    
    print("\n🏁 Stress testing completed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
