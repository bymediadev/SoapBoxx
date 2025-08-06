#!/usr/bin/env python3
"""
Test script for YouTube API functionality
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
    print("Warning: python-dotenv not available. Make sure environment variables are set manually.")

# Add backend to path
sys.path.insert(0, str(Path("backend")))

def test_youtube_api():
    """Test YouTube API functionality"""
    print("🧪 Testing YouTube API integration...")
    
    try:
        from googleapiclient.discovery import build
        
        # Get API key from environment
        YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
        
        if not YOUTUBE_API_KEY:
            print("❌ YouTube API key not configured. Please set YOUTUBE_API_KEY in your .env file")
            return False
        
        print("✅ YouTube API key found!")
        
        # Build YouTube service
        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        print("✅ YouTube service built successfully!")
        
        def search_youtube(query, max_results=5):
            """Search YouTube videos"""
            try:
                request = youtube.search().list(
                    q=query,
                    part="snippet",
                    maxResults=max_results,
                    type="video"
                )
                response = request.execute()
                return response["items"]
            except Exception as e:
                print(f"❌ Search failed: {e}")
                return []
        
        # Test search
        print("\n🔍 Testing YouTube search...")
        query = "Joe Rogan Jordan Peterson podcast"
        videos = search_youtube(query, max_results=3)
        
        if videos:
            print(f"✅ Found {len(videos)} videos for query: '{query}'")
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
        
        # Test trending videos
        print("📈 Testing YouTube trending videos...")
        try:
            trending_request = youtube.videos().list(
                part="snippet,statistics",
                chart="mostPopular",
                regionCode="US",
                maxResults=3
            )
            trending_response = trending_request.execute()
            trending_videos = trending_response["items"]
            
            if trending_videos:
                print(f"✅ Found {len(trending_videos)} trending videos")
                for i, video in enumerate(trending_videos, 1):
                    title = video["snippet"]["title"]
                    channel = video["snippet"]["channelTitle"]
                    view_count = video["statistics"].get("viewCount", "N/A")
                    print(f"  {i}. {title}")
                    print(f"     Channel: {channel} | Views: {view_count}")
                    print()
            else:
                print("❌ No trending videos found")
                
        except Exception as e:
            print(f"❌ Trending videos test failed: {e}")
        
        print("🎉 YouTube API tests completed!")
        return True
        
    except ImportError:
        print("❌ Google API client not available. Please install with: pip install google-api-python-client")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = test_youtube_api()
    sys.exit(0 if success else 1) 