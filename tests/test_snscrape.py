#!/usr/bin/env python3
"""
Test script for snscrape integration in SoapBoxx
Demonstrates how to use the social media scraper
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path("backend")))


def test_snscrape():
    """Test snscrape functionality"""
    print("🧪 Testing snscrape integration...")

    try:
        from social_media_scraper import SocialMediaScraper

        scraper = SocialMediaScraper()

        if not scraper.is_available():
            print(
                "❌ snscrape not available. Please install with: pip install snscrape"
            )
            return False

        print("✅ snscrape is available!")

        # Test Twitter trends
        print("\n🐦 Testing Twitter trends...")
        twitter_trends = scraper.get_twitter_trends("podcast", limit=3)

        if "error" in twitter_trends:
            print(f"❌ Twitter test failed: {twitter_trends['error']}")
        else:
            print(
                f"✅ Twitter test successful! Found {twitter_trends.get('count', 0)} tweets"
            )
            for i, tweet in enumerate(twitter_trends.get("tweets", [])[:2], 1):
                print(f"  {i}. @{tweet['username']}: {tweet['content'][:50]}...")

        # Test Reddit trends
        print("\n🤖 Testing Reddit trends...")
        reddit_trends = scraper.get_reddit_trends("podcasts", limit=3)

        if "error" in reddit_trends:
            print(f"❌ Reddit test failed: {reddit_trends['error']}")
        else:
            print(
                f"✅ Reddit test successful! Found {reddit_trends.get('count', 0)} posts"
            )
            for i, post in enumerate(reddit_trends.get("posts", [])[:2], 1):
                print(f"  {i}. {post['title'][:50]}...")

        # Test trending topics
        print("\n📊 Testing trending topics...")
        trending = scraper.get_trending_topics()

        if "error" in trending:
            print(f"❌ Trending topics test failed: {trending['error']}")
        else:
            print("✅ Trending topics test successful!")
            if trending.get("twitter"):
                print(f"  Twitter: {len(trending['twitter'])} trends")
            if trending.get("reddit"):
                print(f"  Reddit: {len(trending['reddit'])} trends")

        print("\n🎉 All snscrape tests completed!")
        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False


if __name__ == "__main__":
    success = test_snscrape()
    sys.exit(0 if success else 1)
