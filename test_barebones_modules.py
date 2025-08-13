#!/usr/bin/env python3
"""
Test Script for SoapBoxx Demo Barebones Modules
Tests each module individually to ensure they work correctly
"""

import sys
import traceback
from pathlib import Path

def test_module(module_name, test_function):
    """Test a module and report results"""
    print(f"🧪 Testing {module_name}...")
    try:
        result = test_function()
        print(f"✅ {module_name}: PASSED")
        return True
    except Exception as e:
        print(f"❌ {module_name}: FAILED")
        print(f"   Error: {e}")
        traceback.print_exc()
        return False

def test_feedback_engine():
    """Test the barebones feedback engine"""
    from backend.feedback_engine_barebones import BarebonesFeedbackEngine
    
    engine = BarebonesFeedbackEngine()
    
    # Test basic analysis
    test_text = "Welcome to our podcast about artificial intelligence and machine learning."
    result = engine.analyze(test_text, analysis_depth="comprehensive")
    
    # Verify result structure
    assert "metrics" in result, "Missing metrics in result"
    assert "feedback" in result, "Missing feedback in result"
    assert "scores" in result, "Missing scores in result"
    
    # Verify metrics
    metrics = result["metrics"]
    assert metrics.word_count > 0, "Word count should be positive"
    assert metrics.sentence_count > 0, "Sentence count should be positive"
    
    # Verify scores
    scores = result["scores"]
    # Check individual scores
    assert 0 <= scores.clarity <= 10, "Clarity score should be 0-10"
    assert 0 <= scores.engagement <= 10, "Engagement score should be 0-10"
    assert 0 <= scores.structure <= 10, "Structure score should be 0-10"
    assert 0 <= scores.energy <= 10, "Energy score should be 0-10"
    assert 0 <= scores.professionalism <= 10, "Professionalism score should be 0-10"
    assert 0 <= scores.overall_score <= 10, "Overall score should be 0-10"
    
    print(f"   📊 Analyzed text: {metrics.word_count} words, {metrics.sentence_count} sentences")
    print(f"   ⭐ Overall score: {scores.overall_score}")
    
    return True

def test_guest_research():
    """Test the barebones guest research"""
    from backend.guest_research_barebones import BarebonesGuestResearch
    
    research = BarebonesGuestResearch()
    
    # Test guest search
    result = research.research_guest("John Doe")
    
    # Verify result structure
    assert "guest_info" in result, "Missing guest info in result"
    
    # Verify guest info
    guest_info = result["guest_info"]
    assert guest_info["name"], "Guest name should be present"
    assert guest_info["expertise"], "Expertise should be present"
    
    print(f"   👤 Found guest: {guest_info['name']}")
    print(f"   🏢 Company: {guest_info['company']}")
    
    return True

def test_transcriber():
    """Test the barebones transcriber"""
    from backend.transcriber_barebones import BarebonesTranscriber
    
    transcriber = BarebonesTranscriber()
    
    # Test mock transcription
    result = transcriber.transcribe_audio(b"mock_audio_data")
    
    # Verify result structure
    assert "transcript" in result, "Missing transcript in result"
    assert "confidence" in result, "Missing confidence in result"
    assert "metrics" in result, "Missing metrics in result"
    
    # Verify transcript content
    assert result["transcript"], "Transcript should not be empty"
    assert result["confidence"] > 0, "Confidence should be positive"
    
    metrics = result["metrics"]
    assert "word_count" in metrics, "Missing word count in metrics"
    
    print(f"   📝 Transcript: {metrics['word_count']} words")
    print(f"   🎯 Confidence: {result['confidence']}%")
    
    return True

def test_tts_generator():
    """Test the barebones TTS generator"""
    from backend.tts_generator_barebones import BarebonesTTSGenerator
    
    tts = BarebonesTTSGenerator()
    
    # Test TTS generation
    test_text = "Hello, this is a test of the text-to-speech system."
    result = tts.generate_speech(test_text, voice_id="en-US-1", speed=1.0)
    
    # Verify result structure
    assert "audio_file_path" in result, "Missing audio file path in result"
    assert "metrics" in result, "Missing metrics in result"
    
    # Verify content
    assert result["audio_file_path"], "Audio file path should be present"
    
    metrics = result["metrics"]
    assert "estimated_duration_seconds" in metrics, "Missing duration in metrics"
    assert metrics["estimated_duration_seconds"] > 0, "Duration should be positive"
    
    print(f"   🎵 Generated audio: {metrics['estimated_duration_seconds']:.1f}s")
    print(f"   📁 File: {result['audio_file_path']}")
    
    return True

def test_soapboxx_core():
    """Test the barebones SoapBoxx core"""
    from backend.soapboxx_core_barebones import BarebonesSoapBoxxCore
    
    core = BarebonesSoapBoxxCore()
    
    # Test session management
    session_result = core.start_session("Test Session")
    
    # Verify session started
    assert "session_id" in session_result, "Missing session ID"
    assert "success" in session_result, "Missing success flag"
    
    # Test system status
    status_result = core.get_system_status()
    
    # Verify status structure
    assert "modules" in status_result, "Missing modules in status"
    assert "status" in status_result, "Missing status in result"
    
    # Test session info
    info_result = core.get_session_info()
    assert "session_id" in info_result, "Missing session ID in info"
    
    # End session
    end_result = core.end_session()
    assert "success" in end_result, "Missing success flag in end result"
    
    print(f"   🆔 Session ID: {session_result['session_id']}")
    print(f"   🔧 Modules: {len(status_result['modules'])} active")
    
    return True

def main():
    """Main test function"""
    print("🚀 SoapBoxx Demo - Barebones Module Testing")
    print("=" * 50)
    print()
    
    # Check if we're in the right directory
    if not Path("backend").exists():
        print("❌ Error: 'backend' directory not found")
        print("   Please run this script from the SoapBoxx root directory")
        sys.exit(1)
    
    # Check if barebones modules exist
    required_modules = [
        "backend/feedback_engine_barebones.py",
        "backend/guest_research_barebones.py", 
        "backend/transcriber_barebones.py",
        "backend/tts_generator_barebones.py",
        "backend/soapboxx_core_barebones.py"
    ]
    
    missing_modules = []
    for module in required_modules:
        if not Path(module).exists():
            missing_modules.append(module)
    
    if missing_modules:
        print("❌ Missing required modules:")
        for module in missing_modules:
            print(f"   - {module}")
        print("\n   Please ensure you're on the demo branch:")
        print("   git checkout demo/soapboxx-barebones")
        sys.exit(1)
    
    print("✅ All required modules found")
    print()
    
    # Run tests
    tests = [
        ("Feedback Engine", test_feedback_engine),
        ("Guest Research", test_guest_research),
        ("Transcriber", test_transcriber),
        ("TTS Generator", test_tts_generator),
        ("SoapBoxx Core", test_soapboxx_core)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        if test_module(test_name, test_func):
            passed += 1
        print()
    
    # Summary
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} modules passed")
    
    if passed == total:
        print("🎉 All modules working correctly!")
        print("   Ready to run SoapBoxx Demo!")
    else:
        print("⚠️  Some modules have issues")
        print("   Check the error messages above")
    
    return passed == total

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)
