#!/usr/bin/env python3
"""
Test script for Podchaser API integration
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path("backend")))


def test_podchaser():
    """Test Podchaser API functionality"""
    print("🎯 Testing Podchaser API integration...")

    try:
        from podcast_apis import PodcastAPIs

        apis = PodcastAPIs()

        if not apis.podchaser_key:
            print("❌ Podchaser API key not configured")
            return False

        print("✅ Podchaser API key found!")

        # Test trending podcasts
        print("\n📈 Testing Podchaser trending podcasts...")
        trending_result = apis.get_trending_podcasts("podchaser")

        if "error" in trending_result:
            print(f"❌ Trending test failed: {trending_result['error']}")
        else:
            trending_data = trending_result.get("trending", [])
            print(
                f"✅ Trending test successful! Found {len(trending_data)} trending podcasts"
            )
            if trending_data:
                print("   Sample trending podcast:")
                first_podcast = trending_data[0].get("node", {})
                print(f"   - Title: {first_podcast.get('title', 'N/A')}")
                print(f"   - Rating: {first_podcast.get('rating', 'N/A')}")
            else:
                print("   No trending podcasts found (this might be normal)")

        # Test podcast search
        print("\n🔍 Testing Podchaser podcast search...")
        search_result = apis.search_podcasts("podcast", service="podchaser")

        if "error" in search_result:
            print(f"❌ Search test failed: {search_result['error']}")
        else:
            search_data = search_result.get("results", [])
            print(f"✅ Search test successful! Found {len(search_data)} podcasts")
            if search_data:
                print("   Sample search result:")
                first_result = search_data[0].get("node", {})
                print(f"   - Title: {first_result.get('title', 'N/A')}")
                print(f"   - Rating: {first_result.get('rating', 'N/A')}")
            else:
                print("   No search results found (this might be normal)")

        print("\n🎉 Podchaser API tests completed!")
        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False


if __name__ == "__main__":
    success = test_podchaser()
    sys.exit(0 if success else 1)
