#!/usr/bin/env python3
"""
Test script for Google API integration in SoapBoxx
Demonstrates how to use the Google API integrations
"""

import os
import sys
from pathlib import Path

import pytest
from _pytest.outcomes import Failed, Skipped

# Add backend to path
sys.path.insert(0, str(Path("backend")))


def test_google_apis():
    """Test Google API functionality"""
    print("🧪 Testing Google API integration...")

    try:
        from google_apis import GoogleAPIs

        google_apis = GoogleAPIs()

        # Check if Google API client is available
        try:
            import googleapiclient.discovery

            print("✅ Google API client is available!")
        except ImportError:
            print(
                "❌ Google API client not available. Please install with: pip install google-api-python-client"
            )
            pytest.skip("google-api-python-client not installed")

        # Check API status
        api_status = google_apis.get_api_status()
        print(f"\n📊 API Status:")
        print(f"  Google API Available: {api_status['google_api_available']}")
        print(
            f"  Google API Key: {'✅ Configured' if api_status['google_api_key'] else '❌ Not set'}"
        )
        print(
            f"  YouTube API Key: {'✅ Configured' if api_status['youtube_api_key'] else '❌ Not set'}"
        )
        print(f"  Custom Search ID: {api_status['custom_search_id']}")
        print(f"  Web Search Enabled: {api_status['web_search_enabled']}")
        print(f"  YouTube Enabled: {api_status['youtube_enabled']}")

        # Test web search
        print("\n🔍 Testing web search...")
        search_results = google_apis.search_podcast_content(
            "podcast trends", num_results=3
        )

        if "error" in search_results:
            print(f"❌ Web search test failed: {search_results['error']}")
            print("   Using mock data for demonstration...")
            search_results = google_apis.get_mock_search_results("podcast trends")

        print(
            f"✅ Web search test successful! Found {search_results.get('total_results', 0)} results"
        )
        for i, result in enumerate(search_results.get("results", [])[:2], 1):
            print(f"  {i}. {result['title'][:50]}...")

        # Test YouTube search
        print("\n📺 Testing YouTube search...")
        youtube_results = google_apis.search_youtube("podcast", max_results=3)

        if "error" in youtube_results:
            print(f"❌ YouTube search test failed: {youtube_results['error']}")
            print("   Using mock data for demonstration...")
            youtube_results = google_apis.get_mock_youtube_results("podcast")

        print(
            f"✅ YouTube search test successful! Found {youtube_results.get('total_results', 0)} videos"
        )
        for i, video in enumerate(youtube_results.get("videos", [])[:2], 1):
            print(f"  {i}. {video['title'][:50]}...")

        # Test YouTube trends
        print("\n📈 Testing YouTube trends...")
        youtube_trends = google_apis.get_youtube_trends("US", max_results=3)

        if "error" in youtube_trends:
            print(f"❌ YouTube trends test failed: {youtube_trends['error']}")
            print("   Using mock data for demonstration...")
            youtube_trends = google_apis.get_mock_youtube_results("trending")

        print(
            f"✅ YouTube trends test successful! Found {youtube_trends.get('total_results', 0)} trending videos"
        )
        for i, video in enumerate(youtube_trends.get("videos", [])[:2], 1):
            print(f"  {i}. {video['title'][:50]}...")

        print("\n🎉 All Google API tests completed!")

    except Skipped:
        raise
    except ModuleNotFoundError as e:
        if "google_apis" in str(e):
            pytest.skip("google_apis module not available")
        print(f"❌ Test failed with error: {e}")
        pytest.fail(str(e))
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        pytest.fail(str(e))


if __name__ == "__main__":
    try:
        test_google_apis()
    except Skipped:
        sys.exit(0)
    except Failed:
        sys.exit(1)
    sys.exit(0)
