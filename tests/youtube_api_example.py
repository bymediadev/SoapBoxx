#!/usr/bin/env python3
"""
YouTube API Example for SoapBoxx
Based on user's example code
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    print(
        "Warning: python-dotenv not available. Make sure environment variables are set manually."
    )

# Add backend to path
sys.path.insert(0, str(Path("backend")))


def youtube_api_example():
    """Example of YouTube API usage"""
    print("🎥 YouTube API Example for SoapBoxx")
    print("=" * 50)

    # Check if Google API client is available
    try:
        from googleapiclient.discovery import build

        print("✅ Google API client is available!")
    except ImportError:
        print(
            "❌ Google API client not available. Install with: pip install google-api-python-client"
        )
        return False

    # Get API key from environment
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

    if not YOUTUBE_API_KEY:
        print("❌ YouTube API key not configured.")
        print("\n📝 To configure YouTube API:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project or select existing one")
        print("3. Enable 'YouTube Data API v3'")
        print("4. Create credentials (API key)")
        print("5. Add to your .env file: YOUTUBE_API_KEY=your_api_key_here")
        print("\n🔍 For now, showing mock data...")

        # Show mock data
        mock_videos = [
            {
                "title": "Joe Rogan Experience #1234 - Jordan Peterson",
                "channel": "Joe Rogan Experience",
                "video_id": "mock_video_1",
                "url": "https://www.youtube.com/watch?v=mock_video_1",
            },
            {
                "title": "Jordan Peterson on Podcasting and Free Speech",
                "channel": "Jordan B Peterson",
                "video_id": "mock_video_2",
                "url": "https://www.youtube.com/watch?v=mock_video_2",
            },
            {
                "title": "The Psychology of Podcasting - Jordan Peterson Interview",
                "channel": "Podcast Insights",
                "video_id": "mock_video_3",
                "url": "https://www.youtube.com/watch?v=mock_video_3",
            },
        ]

        print(f"\n🎯 Mock search results for 'Joe Rogan Jordan Peterson podcast':")
        for i, video in enumerate(mock_videos, 1):
            print(f"  {i}. {video['title']}")
            print(f"     Channel: {video['channel']}")
            print(f"     URL: {video['url']}")
            print()

        return True

    print("✅ YouTube API key found!")

    try:
        # Build YouTube service
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        print("✅ YouTube service built successfully!")

        def search_youtube(query, max_results=5):
            """Search YouTube videos using the exact pattern from user's example"""
            try:
                request = youtube.search().list(
                    q=query, part="snippet", maxResults=max_results, type="video"
                )
                response = request.execute()
                return response["items"]
            except Exception as e:
                print(f"❌ Search failed: {e}")
                return []

        # Example usage - exactly as provided by user
        print("\n🔍 Searching for 'Joe Rogan Jordan Peterson podcast'...")
        videos = search_youtube("Joe Rogan Jordan Peterson podcast", max_results=3)

        if videos:
            print(f"✅ Found {len(videos)} videos:")
            for i, video in enumerate(videos, 1):
                title = video["snippet"]["title"]
                video_id = video["id"]["videoId"]
                channel = video["snippet"]["channelTitle"]
                print(f"  {i}. {title}")
                print(f"     Channel: {channel}")
                print(f"     URL: https://www.youtube.com/watch?v={video_id}")
                print()
        else:
            print("❌ No videos found")

        # Additional example - search for podcast-related content
        print("\n🎙️ Searching for 'podcast equipment setup'...")
        equipment_videos = search_youtube("podcast equipment setup", max_results=2)

        if equipment_videos:
            print(f"✅ Found {len(equipment_videos)} equipment videos:")
            for i, video in enumerate(equipment_videos, 1):
                title = video["snippet"]["title"]
                video_id = video["id"]["videoId"]
                channel = video["snippet"]["channelTitle"]
                print(f"  {i}. {title}")
                print(f"     Channel: {channel}")
                print(f"     URL: https://www.youtube.com/watch?v={video_id}")
                print()

        print("🎉 YouTube API example completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def show_integration_example():
    """Show how to integrate with SoapBoxx"""
    print("\n🔗 SoapBoxx Integration Example")
    print("=" * 40)

    try:
        from google_apis import GoogleAPIs

        google_apis = GoogleAPIs()

        if google_apis.is_available():
            print("✅ Google APIs module is available!")

            # Test the simple search method
            print("\n🔍 Testing SoapBoxx YouTube integration...")
            results = google_apis.search_youtube_simple("podcast tips", max_results=2)

            if "error" in results:
                print(f"❌ Error: {results['error']}")
            else:
                print(f"✅ Found {results['total_results']} videos:")
                for i, video in enumerate(results["videos"], 1):
                    print(f"  {i}. {video['title']}")
                    print(f"     Channel: {video['channel_title']}")
                    print(f"     URL: {video['url']}")
                    print()
        else:
            print("❌ Google APIs module not available")

    except ImportError:
        print("❌ Google APIs module not found")
    except Exception as e:
        print(f"❌ Integration test failed: {e}")


if __name__ == "__main__":
    print("🚀 YouTube API Example for SoapBoxx")
    print("=" * 50)

    # Run the main example
    success = youtube_api_example()

    # Show integration example
    show_integration_example()

    print("\n📚 Usage Instructions:")
    print("1. Set YOUTUBE_API_KEY in your .env file")
    print("2. Use the search_youtube() function for simple searches")
    print("3. Use GoogleAPIs class for advanced features")
    print("4. Integrate with SoapBoxx Scoop tab for UI access")

    sys.exit(0 if success else 1)
