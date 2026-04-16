#!/usr/bin/env python3
"""
Test script for the enhanced FeedbackEngine
Demonstrates new precision features and quantitative analysis
"""

import json
import os
import sys
import time as time_module  # Added for caching test fix
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

try:
    from feedback_engine import ContentMetrics, FeedbackEngine, FeedbackScore

    _FEEDBACK_IMPORT_OK = True
    _FEEDBACK_IMPORT_ERROR = ""
except ImportError as e:
    ContentMetrics = FeedbackEngine = FeedbackScore = None  # type: ignore
    _FEEDBACK_IMPORT_OK = False
    _FEEDBACK_IMPORT_ERROR = str(e)


def dataclass_to_dict(obj):
    """Convert dataclass objects to dictionaries for JSON serialization"""
    if hasattr(obj, "__dict__"):
        return {k: dataclass_to_dict(v) for k, v in obj.__dict__.items()}
    elif isinstance(obj, (list, tuple)):
        return [dataclass_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: dataclass_to_dict(v) for k, v in obj.items()}
    else:
        return obj


def test_basic_functionality():
    """Test basic functionality with different analysis depths"""
    print("\nTesting Basic Functionality")
    print("=" * 50)

    fe = FeedbackEngine()
    sample_transcript = "Hello world. This is a test."

    # Test different analysis depths
    depths = ["basic", "standard", "comprehensive"]

    for depth in depths:
        print(f"\n{depth.title()} Analysis Result:")
        result = fe.analyze(transcript=sample_transcript, analysis_depth=depth)
        # Convert dataclass objects to dictionaries for JSON serialization
        serializable_result = dataclass_to_dict(result)
        print(json.dumps(serializable_result, indent=2))


def test_quantitative_metrics():
    """Test quantitative metrics calculation"""
    print("\nTesting Quantitative Metrics")
    print("=" * 50)

    fe = FeedbackEngine()

    # Test with different transcript lengths
    transcripts = [
        "Short content.",
        "This is a medium length transcript with some content to analyze. It has multiple sentences and varied vocabulary.",
        """This is a comprehensive transcript designed to test the enhanced feedback engine. 
        It contains multiple sentences with varying complexity, technical terminology, and engaging elements. 
        The content covers multiple topics while maintaining coherence and structure. 
        We'll analyze clarity, engagement, structure, energy, and professionalism aspects.""",
    ]

    for i, transcript in enumerate(transcripts, 1):
        print(f"\nTranscript {i} ({len(transcript.split())} words):")
        metrics = fe._calculate_content_metrics(transcript)
        print(f"  Word count: {metrics.word_count}")
        print(f"  Sentence count: {metrics.sentence_count}")
        print(f"  Avg sentence length: {metrics.avg_sentence_length:.1f}")
        print(f"  Vocabulary diversity: {metrics.vocabulary_diversity:.3f}")
        print(f"  Reading level: {metrics.reading_level}")
        print(f"  Speaking pace: {metrics.speaking_pace:.1f} words/minute")
        print(f"  Topic coherence: {metrics.topic_coherence:.2f}")
        print(f"  Engagement signals: {metrics.engagement_signals}")

        # Test scoring
        scores = fe._calculate_quantitative_scores(transcript, metrics)
        print(
            f"  Scores - Clarity: {scores.clarity}, Engagement: {scores.engagement}, Overall: {scores.overall}"
        )


def test_focus_specific_feedback():
    """Test focus-specific feedback capabilities"""
    print("\n🎯 Testing Focus-Specific Feedback")
    print("=" * 50)

    fe = FeedbackEngine()
    sample_transcript = """Welcome to our podcast about artificial intelligence! 
    Today we're diving deep into machine learning algorithms and their applications. 
    This is going to be fascinating! Have you ever wondered how AI makes decisions? 
    Let me tell you about neural networks and deep learning techniques."""

    focus_areas = ["clarity", "engagement", "structure", "energy", "professionalism"]

    for focus_area in focus_areas:
        print(f"\nFocus Area: {focus_area.upper()}")
        result = fe.get_specific_feedback(sample_transcript, focus_area, "standard")

        print(
            f"  Focus-specific suggestions: {result.get('focus_specific_suggestions', [])}"
        )

        # Handle both dict and dataclass score objects
        scores = result.get("scores", {})
        if hasattr(scores, "overall"):
            overall_score = scores.overall
        else:
            overall_score = scores.get("overall", "N/A")
        print(f"  Overall score: {overall_score}")


def test_comparative_analysis():
    """Test comparative analysis between two transcripts"""
    print("\n📈 Testing Comparative Analysis")
    print("=" * 50)

    fe = FeedbackEngine()

    # Two different transcripts for comparison
    transcript1 = "Hello, this is a basic introduction. We'll talk about topics."
    transcript2 = """Welcome to our comprehensive podcast! Today we're exploring fascinating subjects 
    with detailed explanations, engaging questions, and professional insights. 
    This content demonstrates improved structure, clarity, and engagement techniques."""

    comparison = fe.get_comparative_analysis(transcript1, transcript2)

    print("Comparative Analysis Result:")
    # Convert dataclass objects to dictionaries for JSON serialization
    serializable_comparison = dataclass_to_dict(comparison)
    print(json.dumps(serializable_comparison, indent=2))


def test_caching_functionality():
    """Test caching capabilities"""
    print("\n💾 Testing Caching Functionality")
    print("=" * 50)

    fe = FeedbackEngine()
    sample_transcript = "Testing cache functionality with repeated analysis."

    # First analysis (should cache)
    print("First analysis (should cache)...")
    start_time = time_module.time()
    result1 = fe.analyze(transcript=sample_transcript, analysis_depth="basic")
    time1 = time_module.time() - start_time

    # Second analysis (should use cache)
    print("Second analysis (should use cache)...")
    start_time = time_module.time()
    result2 = fe.analyze(transcript=sample_transcript, analysis_depth="basic")
    time2 = time_module.time() - start_time

    print(f"First analysis time: {time1:.4f}s")
    print(f"Second analysis time: {time2:.4f}s")

    # Avoid division by zero
    if time2 > 0:
        print(f"Cache hit speedup: {time1/time2:.1f}x")
    else:
        print("Cache hit speedup: N/A (instant response)")

    # Test cache stats
    cache_stats = fe.get_cache_stats()
    print(f"Cache stats: {cache_stats}")

    # Clear cache
    fe.clear_cache()
    print("Cache cleared")

    cache_stats_after = fe.get_cache_stats()
    print(f"Cache stats after clearing: {cache_stats_after}")


def test_error_handling():
    """Test error handling and edge cases"""
    print("\n[WARN] Testing Error Handling")
    print("=" * 50)

    fe = FeedbackEngine()

    # Test empty transcript
    print("Testing empty transcript...")
    result = fe.analyze(transcript="")
    print(f"Empty transcript result: {result}")

    # Test very short transcript
    print("\nTesting very short transcript...")
    result = fe.analyze(transcript="Hi.")
    print(f"Short transcript result: {result}")

    # Test very long transcript
    print("\nTesting very long transcript...")
    long_transcript = "This is a test. " * 1000
    result = fe.analyze(transcript=long_transcript, analysis_depth="basic")
    print(
        f"Long transcript word count: {result.get('metrics', {}).get('word_count', 'N/A')}"
    )


def test_advanced_features():
    """Test advanced features and configurations"""
    print("\nTesting Advanced Features")
    print("=" * 50)

    fe = FeedbackEngine()
    sample_transcript = """Advanced podcast content with technical terminology, 
    structured arguments, and professional delivery. This demonstrates multiple 
    improvement areas and strengths across different dimensions."""

    # Test different analysis depths
    depths = ["basic", "standard", "comprehensive", "expert"]

    for depth in depths:
        print(f"\nTesting {depth} analysis depth...")
        try:
            result = fe.analyze(transcript=sample_transcript, analysis_depth=depth)
            print(f"  Success: {depth} analysis completed")
            print(f"  Confidence: {result.get('confidence', 'N/A')}")
            print(f"  Suggestions count: {len(result.get('coaching_suggestions', []))}")
        except Exception as e:
            print(f"  Error in {depth} analysis: {e}")


def main():
    """Run all tests"""
    if not _FEEDBACK_IMPORT_OK:
        print(f"[FAIL] Enhanced FeedbackEngine import failed: {_FEEDBACK_IMPORT_ERROR}")
        sys.exit(1)
    print("Enhanced FeedbackEngine Test Suite")
    print("=" * 60)

    tests = [
        test_basic_functionality,
        test_quantitative_metrics,
        test_focus_specific_feedback,
        test_comparative_analysis,
        test_caching_functionality,
        test_error_handling,
        test_advanced_features,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
                print(f"[OK] {test.__name__} passed")
            else:
                print(f"[FAIL] {test.__name__} failed")
        except Exception as e:
            print(f"[FAIL] {test.__name__} failed with error: {e}")

    print(f"\nTest Results: {passed}/{total} tests passed")

    if passed == total:
        print("All tests passed. Enhanced FeedbackEngine is working correctly.")
    else:
        print("[WARN] Some tests failed. Please review the output above.")


if __name__ == "__main__":
    main()
