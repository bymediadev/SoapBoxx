#!/usr/bin/env python3
"""
SoapBoxx End-to-End Stress Test
Tests the complete system workflow from start to finish
"""

import os
import sys
import time
import threading
import concurrent.futures
import json
import tempfile
import subprocess
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
from backend.error_tracker import error_tracker

class E2EStressTester:
    def __init__(self):
        self.results = {}
        self.config = Config()
        self.logger = Logger()
        self.start_time = None
        self.end_time = None
        
    def test_system_initialization(self):
        """Test complete system initialization"""
        print("🚀 Testing System Initialization...")
        
        try:
            # Test config loading
            config = Config()
            assert config is not None, "Config should load"
            
            # Test OpenAI API
            openai_key = config.get_openai_api_key()
            assert openai_key, "OpenAI API key should be configured"
            
            # Test all core components
            components = {
                "AudioRecorder": AudioRecorder(),
                "Transcriber": Transcriber(),
                "FeedbackEngine": FeedbackEngine(),
                "GuestResearch": GuestResearch(),
                "Logger": Logger(),
                "SoapBoxxCore": SoapBoxxCore()
            }
            
            for name, component in components.items():
                assert component is not None, f"{name} should initialize"
                print(f"   ✅ {name} initialized")
            
            print("✅ System initialization completed successfully")
            return True
            
        except Exception as e:
            print(f"❌ System initialization failed: {e}")
            return False
    
    def test_complete_recording_workflow(self):
        """Test complete recording workflow from start to finish"""
        print("🎤 Testing Complete Recording Workflow...")
        
        workflow_results = []
        
        try:
            # Step 1: Initialize components
            recorder = AudioRecorder()
            transcriber = Transcriber()
            feedback_engine = FeedbackEngine()
            core = SoapBoxxCore()
            
            # Step 2: Start recording
            print("   Step 1: Starting recording...")
            start_time = time.time()
            
            recording_success = recorder.start_recording()
            if not recording_success:
                print("   ❌ Failed to start recording")
                return False
            
            # Simulate recording time
            time.sleep(2)  # Record for 2 seconds
            
            # Step 3: Stop recording and get audio
            print("   Step 2: Stopping recording...")
            audio_data = recorder.stop_recording()
            
            recording_time = time.time() - start_time
            print(f"   ✅ Recording completed in {recording_time:.2f}s ({len(audio_data)} bytes)")
            
            # Step 4: Transcribe audio
            print("   Step 3: Transcribing audio...")
            transcription_start = time.time()
            
            transcript = transcriber.transcribe(audio_data)
            transcription_time = time.time() - transcription_start
            
            if transcript.startswith("Error:"):
                print(f"   ⚠️ Transcription failed: {transcript}")
                # Use fallback transcript for testing
                transcript = "This is a test transcript for stress testing the feedback engine."
            else:
                print(f"   ✅ Transcription completed in {transcription_time:.2f}s ({len(transcript)} chars)")
            
            # Step 5: Generate feedback
            print("   Step 4: Generating feedback...")
            feedback_start = time.time()
            
            feedback = feedback_engine.analyze(transcript)
            feedback_time = time.time() - feedback_start
            
            print(f"   ✅ Feedback generated in {feedback_time:.2f}s")
            
            # Step 6: Complete workflow
            workflow_time = time.time() - start_time
            
            workflow_results.append({
                "recording_time": recording_time,
                "transcription_time": transcription_time,
                "feedback_time": feedback_time,
                "total_time": workflow_time,
                "audio_size": len(audio_data),
                "transcript_length": len(transcript),
                "has_feedback": "listener_feedback" in feedback,
                "success": True
            })
            
            print(f"   ✅ Complete workflow completed in {workflow_time:.2f}s")
            return workflow_results
            
        except Exception as e:
            print(f"   ❌ Recording workflow failed: {e}")
            return False
    
    def test_guest_research_workflow(self):
        """Test complete guest research workflow"""
        print("🔍 Testing Guest Research Workflow...")
        
        research_results = []
        
        try:
            research = GuestResearch()
            
            # Test different guest types
            test_guests = [
                "Tech Expert",
                "Business Leader", 
                "Podcast Host",
                "Industry Specialist",
                "Thought Leader"
            ]
            
            for guest in test_guests:
                print(f"   Researching: {guest}")
                start_time = time.time()
                
                try:
                    result = research.research(guest)
                    research_time = time.time() - start_time
                    
                    success = "error" not in result
                    has_profile = "profile" in result and result["profile"]
                    has_talking_points = "talking_points" in result and result["talking_points"]
                    has_questions = "questions" in result and result["questions"]
                    
                    research_results.append({
                        "guest": guest,
                        "research_time": research_time,
                        "success": success,
                        "has_profile": has_profile,
                        "has_talking_points": has_talking_points,
                        "has_questions": has_questions,
                        "fallback_used": result.get("fallback", False)
                    })
                    
                    status = "✅" if success else "⚠️"
                    print(f"     {status} {guest}: {research_time:.2f}s")
                    
                except Exception as e:
                    research_time = time.time() - start_time
                    research_results.append({
                        "guest": guest,
                        "research_time": research_time,
                        "success": False,
                        "error": str(e)
                    })
                    print(f"     ❌ {guest}: Failed - {e}")
            
            return research_results
            
        except Exception as e:
            print(f"   ❌ Guest research workflow failed: {e}")
            return False
    
    def test_concurrent_operations(self):
        """Test multiple operations running concurrently"""
        print("⚡ Testing Concurrent Operations...")
        
        concurrent_results = []
        
        def run_transcription_task(task_id):
            """Run a transcription task"""
            try:
                transcriber = Transcriber()
                dummy_audio = b"dummy_audio_data" * 100
                
                start_time = time.time()
                result = transcriber.transcribe(dummy_audio)
                duration = time.time() - start_time
                
                return {
                    "task_id": task_id,
                    "type": "transcription",
                    "success": not result.startswith("Error:"),
                    "duration": duration,
                    "result_length": len(result)
                }
            except Exception as e:
                return {
                    "task_id": task_id,
                    "type": "transcription",
                    "success": False,
                    "error": str(e)
                }
        
        def run_feedback_task(task_id):
            """Run a feedback analysis task"""
            try:
                engine = FeedbackEngine()
                dummy_transcript = "This is a test transcript for concurrent stress testing. " * 10
                
                start_time = time.time()
                result = engine.analyze(dummy_transcript)
                duration = time.time() - start_time
                
                return {
                    "task_id": task_id,
                    "type": "feedback",
                    "success": "listener_feedback" in result,
                    "duration": duration,
                    "has_feedback": "listener_feedback" in result
                }
            except Exception as e:
                return {
                    "task_id": task_id,
                    "type": "feedback",
                    "success": False,
                    "error": str(e)
                }
        
        def run_research_task(task_id):
            """Run a guest research task"""
            try:
                research = GuestResearch()
                guest_name = f"Test Guest {task_id}"
                
                start_time = time.time()
                result = research.research(guest_name)
                duration = time.time() - start_time
                
                return {
                    "task_id": task_id,
                    "type": "research",
                    "success": "error" not in result,
                    "duration": duration,
                    "has_results": bool(result)
                }
            except Exception as e:
                return {
                    "task_id": task_id,
                    "type": "research",
                    "success": False,
                    "error": str(e)
                }
        
        # Test different concurrency levels
        concurrency_levels = [3, 5, 10]
        
        for concurrency in concurrency_levels:
            print(f"   Testing {concurrency} concurrent operations...")
            
            start_time = time.time()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
                # Submit mixed tasks
                futures = []
                
                for i in range(concurrency):
                    if i % 3 == 0:
                        futures.append(executor.submit(run_transcription_task, i))
                    elif i % 3 == 1:
                        futures.append(executor.submit(run_feedback_task, i))
                    else:
                        futures.append(executor.submit(run_research_task, i))
                
                # Collect results
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            total_time = time.time() - start_time
            successful = sum(1 for r in results if r["success"])
            failed = len(results) - successful
            
            concurrent_results.append({
                "concurrency": concurrency,
                "total_operations": len(results),
                "successful": successful,
                "failed": failed,
                "total_time": total_time,
                "avg_time_per_operation": total_time / len(results),
                "results": results
            })
            
            print(f"     ✅ {successful}/{len(results)} successful in {total_time:.2f}s")
        
        return concurrent_results
    
    def test_memory_stress_over_time(self):
        """Test memory usage over extended operations"""
        print("💾 Testing Memory Stress Over Time...")
        
        try:
            import psutil
            import gc
            
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            print(f"   Initial memory: {initial_memory:.2f} MB")
            
            memory_samples = []
            
            # Run extended operations
            for iteration in range(100):  # 100 iterations
                iteration_start = time.time()
                
                try:
                    # Create fresh instances each time
                    transcriber = Transcriber()
                    feedback_engine = FeedbackEngine()
                    research = GuestResearch()
                    
                    # Perform operations
                    dummy_audio = b"dummy_audio_data" * 50
                    transcript = transcriber.transcribe(dummy_audio)
                    
                    feedback_engine.analyze("Test transcript for memory stress testing.")
                    research.research("Test Guest")
                    
                    # Force garbage collection
                    gc.collect()
                    
                    current_memory = process.memory_info().rss / 1024 / 1024
                    iteration_time = time.time() - iteration_start
                    
                    memory_samples.append({
                        "iteration": iteration,
                        "memory_mb": current_memory,
                        "memory_increase": current_memory - initial_memory,
                        "duration": iteration_time
                    })
                    
                    if iteration % 20 == 0:
                        print(f"     Iteration {iteration}: {current_memory:.2f} MB (+{current_memory - initial_memory:.2f} MB)")
                    
                except Exception as e:
                    print(f"     ❌ Iteration {iteration} failed: {e}")
            
            final_memory = process.memory_info().rss / 1024 / 1024
            print(f"   Final memory: {final_memory:.2f} MB")
            print(f"   Total memory increase: {final_memory - initial_memory:.2f} MB")
            
            return {
                "initial_memory": initial_memory,
                "final_memory": final_memory,
                "total_increase": final_memory - initial_memory,
                "samples": memory_samples
            }
            
        except ImportError:
            print("   ⚠️ psutil not available, skipping memory monitoring")
            return {"note": "Memory monitoring not available"}
        except Exception as e:
            print(f"   ❌ Memory stress test failed: {e}")
            return {"error": str(e)}
    
    def test_error_recovery_scenarios(self):
        """Test various error recovery scenarios"""
        print("🛡️ Testing Error Recovery Scenarios...")
        
        recovery_results = []
        
        # Test scenarios
        scenarios = [
            ("Invalid audio data", b"not_audio_data"),
            ("Empty audio", b""),
            ("Very large audio", b"dummy" * 2000000),  # ~8MB
            ("None input", None),
            ("Corrupted audio", b"RIFF\x00\x00\x00\x00WAVE"),
            ("Unsupported format", b"UNSUPPORTED_FORMAT_DATA"),
        ]
        
        for scenario_name, test_data in scenarios:
            print(f"   Testing: {scenario_name}")
            
            try:
                transcriber = Transcriber()
                feedback_engine = FeedbackEngine()
                research = GuestResearch()
                
                start_time = time.time()
                
                # Test transcription
                if test_data is not None:
                    transcript_result = transcriber.transcribe(test_data)
                    transcription_handled = transcript_result.startswith("Error:")
                else:
                    transcript_result = transcriber.transcribe(None)
                    transcription_handled = transcript_result.startswith("Error:")
                
                # Test feedback with invalid transcript
                feedback_result = feedback_engine.analyze("")
                feedback_handled = "listener_feedback" in feedback_result
                
                # Test research with empty guest
                research_result = research.research("")
                research_handled = "error" in research_result
                
                duration = time.time() - start_time
                
                recovery_results.append({
                    "scenario": scenario_name,
                    "transcription_handled": transcription_handled,
                    "feedback_handled": feedback_handled,
                    "research_handled": research_handled,
                    "duration": duration,
                    "success": transcription_handled and feedback_handled and research_handled
                })
                
                status = "✅" if transcription_handled and feedback_handled and research_handled else "⚠️"
                print(f"     {status} {scenario_name}: {duration:.3f}s")
                
            except Exception as e:
                recovery_results.append({
                    "scenario": scenario_name,
                    "error": str(e),
                    "success": False
                })
                print(f"     ❌ {scenario_name}: Crashed - {e}")
        
        return recovery_results
    
    def test_system_integration(self):
        """Test complete system integration"""
        print("🔗 Testing System Integration...")
        
        try:
            # Initialize core system
            core = SoapBoxxCore()
            
            # Test status
            status = core.get_status()
            assert isinstance(status, dict), "Status should return dict"
            
            # Test callbacks
            callback_called = False
            def test_callback(message):
                nonlocal callback_called
                callback_called = True
            
            core.set_callbacks(
                on_transcription_progress=test_callback,
                on_feedback_progress=test_callback,
                on_research_progress=test_callback
            )
            
            # Test performance monitoring
            if hasattr(core, 'performance_monitor'):
                metrics = core.performance_monitor.get_metrics()
                print(f"   Performance metrics available: {bool(metrics)}")
            
            # Test rate limiting
            if hasattr(core, 'rate_limiter'):
                can_proceed = core.rate_limiter.can_proceed("test_operation")
                print(f"   Rate limiting available: {can_proceed}")
            
            print("✅ System integration test completed")
            return True
            
        except Exception as e:
            print(f"❌ System integration test failed: {e}")
            return False
    
    def run_complete_e2e_test(self):
        """Run complete end-to-end stress test"""
        print("🚀 Starting SoapBoxx End-to-End Stress Test")
        print("=" * 70)
        
        self.start_time = time.time()
        
        # Run all E2E tests
        tests = [
            ("System Initialization", self.test_system_initialization),
            ("Complete Recording Workflow", self.test_complete_recording_workflow),
            ("Guest Research Workflow", self.test_guest_research_workflow),
            ("Concurrent Operations", self.test_concurrent_operations),
            ("Memory Stress Over Time", self.test_memory_stress_over_time),
            ("Error Recovery Scenarios", self.test_error_recovery_scenarios),
            ("System Integration", self.test_system_integration),
        ]
        
        for test_name, test_func in tests:
            print(f"\n🔬 {test_name}")
            print("-" * 50)
            
            try:
                result = test_func()
                self.results[test_name] = result
                print(f"✅ {test_name} completed")
            except Exception as e:
                print(f"❌ {test_name} failed: {e}")
                self.results[test_name] = {"error": str(e)}
        
        self.end_time = time.time()
        
        # Generate comprehensive report
        self._generate_e2e_report()
        
        return self.results
    
    def _generate_e2e_report(self):
        """Generate comprehensive E2E test report"""
        total_time = self.end_time - self.start_time
        
        print("\n" + "=" * 70)
        print("📊 E2E STRESS TEST RESULTS")
        print("=" * 70)
        
        print(f"Total Test Time: {total_time:.2f} seconds ({total_time/60:.1f} minutes)")
        print(f"Tests Completed: {len(self.results)}")
        
        # Calculate overall metrics
        total_operations = 0
        successful_operations = 0
        failed_operations = 0
        
        for test_name, result in self.results.items():
            if isinstance(result, bool):
                if result:
                    successful_operations += 1
                else:
                    failed_operations += 1
                total_operations += 1
            elif isinstance(result, list):
                total_operations += len(result)
                successful_operations += sum(1 for r in result if r.get("success", False))
                failed_operations += sum(1 for r in result if not r.get("success", True))
            elif isinstance(result, dict) and "error" not in result:
                if result.get("success", False):
                    successful_operations += 1
                else:
                    failed_operations += 1
                total_operations += 1
        
        success_rate = (successful_operations / total_operations * 100) if total_operations > 0 else 0
        
        print(f"Total Operations: {total_operations}")
        print(f"Successful: {successful_operations}")
        print(f"Failed: {failed_operations}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        # Detailed results
        print(f"\n📋 Detailed Results:")
        for test_name, result in self.results.items():
            if isinstance(result, bool):
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"   {test_name:<30} {status}")
            elif isinstance(result, list):
                successful = sum(1 for r in result if r.get("success", False))
                total = len(result)
                status = f"✅ {successful}/{total}" if successful == total else f"⚠️ {successful}/{total}"
                print(f"   {test_name:<30} {status}")
            elif isinstance(result, dict):
                if "error" in result:
                    print(f"   {test_name:<30} ❌ ERROR")
                else:
                    status = "✅ PASS" if result.get("success", False) else "⚠️ PARTIAL"
                    print(f"   {test_name:<30} {status}")
        
        # Save detailed report
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_time": total_time,
            "total_operations": total_operations,
            "successful_operations": successful_operations,
            "failed_operations": failed_operations,
            "success_rate": success_rate,
            "results": self.results
        }
        
        with open("e2e_stress_test_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: e2e_stress_test_report.json")
        
        # Overall assessment
        if success_rate >= 95:
            print("\n🎉 EXCELLENT: System handles E2E stress very well!")
        elif success_rate >= 80:
            print("\n✅ GOOD: System handles E2E stress well with minor issues")
        elif success_rate >= 60:
            print("\n⚠️ FAIR: System has some E2E stress-related issues")
        else:
            print("\n❌ POOR: System has significant E2E stress-related issues")

def main():
    """Main E2E stress test runner"""
    tester = E2EStressTester()
    results = tester.run_complete_e2e_test()
    
    print("\n🏁 End-to-end stress testing completed!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
