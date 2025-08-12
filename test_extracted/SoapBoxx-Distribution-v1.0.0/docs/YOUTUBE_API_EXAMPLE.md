# 🎥 YouTube API Example for SoapBoxx

## 📋 Overview

This document shows how to use the YouTube API with SoapBoxx, based on the exact code pattern you provided.

## 🚀 Quick Start Example

### **Basic YouTube Search (Your Example)**

```python
from googleapiclient.discovery import build
import os

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

def search_youtube(query, max_results=5):
    request = youtube.search().list(
        q=query,
        part="snippet",
        maxResults=max_results,
        type="video"
    )
    response = request.execute()
    return response["items"]

# Example usage
videos = search_youtube("Joe Rogan Jordan Peterson podcast")
for video in videos:
    print(video["snippet"]["title"], video["id"]["videoId"])
```

## 🔧 Setup Instructions

### **1. Install Dependencies**

```bash
pip install google-api-python-client
```

### **2. Configure YouTube API**

1. **Go to Google Cloud Console**:
   - Visit [https://console.cloud.google.com/](https://console.cloud.google.com/)
   - Create a new project or select existing one

2. **Enable YouTube Data API**:
   - Go to "APIs & Services" > "Library"
   - Search for "YouTube Data API v3"
   - Click "Enable"

3. **Create API Key**:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "API Key"
   - Copy your API key

4. **Add to Environment**:
   ```bash
   # Add to your .env file
   YOUTUBE_API_KEY=your_actual_api_key_here
   ```

## 🎯 Usage Examples

### **Example 1: Basic Search**

```python
from googleapiclient.discovery import build
import os

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

def search_youtube(query, max_results=5):
    request = youtube.search().list(
        q=query,
        part="snippet",
        maxResults=max_results,
        type="video"
    )
    response = request.execute()
    return response["items"]

# Search for podcast content
videos = search_youtube("Joe Rogan Jordan Peterson podcast", max_results=3)
for video in videos:
    title = video["snippet"]["title"]
    video_id = video["id"]["videoId"]
    channel = video["snippet"]["channelTitle"]
    print(f"Title: {title}")
    print(f"Channel: {channel}")
    print(f"URL: https://www.youtube.com/watch?v={video_id}")
    print()
```

### **Example 2: Advanced Search with Statistics**

```python
def search_youtube_with_stats(query, max_results=5):
    # First, get search results
    search_request = youtube.search().list(
        q=query,
        part="id",
        maxResults=max_results,
        type="video"
    )
    search_response = search_request.execute()
    
    # Get video IDs
    video_ids = [item["id"]["videoId"] for item in search_response["items"]]
    
    if video_ids:
        # Get detailed video information
        videos_request = youtube.videos().list(
            part="snippet,statistics",
            id=",".join(video_ids)
        )
        videos_response = videos_request.execute()
        
        return videos_response["items"]
    
    return []

# Usage
videos = search_youtube_with_stats("podcast equipment setup", max_results=3)
for video in videos:
    title = video["snippet"]["title"]
    channel = video["snippet"]["channelTitle"]
    view_count = video["statistics"].get("viewCount", "N/A")
    like_count = video["statistics"].get("likeCount", "N/A")
    
    print(f"Title: {title}")
    print(f"Channel: {channel}")
    print(f"Views: {view_count} | Likes: {like_count}")
    print()
```

### **Example 3: Trending Videos**

```python
def get_trending_videos(region_code="US", max_results=10):
    request = youtube.videos().list(
        part="snippet,statistics",
        chart="mostPopular",
        regionCode=region_code,
        maxResults=max_results
    )
    response = request.execute()
    return response["items"]

# Usage
trending = get_trending_videos("US", max_results=5)
for video in trending:
    title = video["snippet"]["title"]
    channel = video["snippet"]["channelTitle"]
    view_count = video["statistics"].get("viewCount", "N/A")
    
    print(f"Trending: {title}")
    print(f"Channel: {channel} | Views: {view_count}")
    print()
```

## 🔗 SoapBoxx Integration

### **Using the GoogleAPIs Class**

```python
from backend.google_apis import GoogleAPIs

# Initialize Google APIs
google_apis = GoogleAPIs()

# Check availability
if google_apis.is_available():
    # Simple search (matches your example)
    results = google_apis.search_youtube_simple("podcast tips", max_results=5)
    
    if "error" not in results:
        for video in results["videos"]:
            print(f"Title: {video['title']}")
            print(f"Channel: {video['channel_title']}")
            print(f"URL: {video['url']}")
            print()
    else:
        print(f"Error: {results['error']}")
else:
    print("YouTube API not configured")
```

### **Integration with Scoop Tab**

The YouTube API is already integrated into your SoapBoxx Scoop tab:

1. **Launch SoapBoxx**: `python frontend/main_window.py`
2. **Go to Scoop Tab**: Click the "Scoop" tab
3. **Use YouTube Features**:
   - **📺 YouTube Trends** - Get trending videos
   - **🔍 Research Topic** - Search for content (includes YouTube)

## 📊 Data Format

### **Search Response Structure**

```json
{
  "query": "Joe Rogan Jordan Peterson podcast",
  "total_results": 3,
  "videos": [
    {
      "id": "video_id_123",
      "title": "Joe Rogan Experience #1234 - Jordan Peterson",
      "description": "Jordan Peterson discusses...",
      "channel_title": "Joe Rogan Experience",
      "published_at": "2024-01-01T00:00:00Z",
      "thumbnails": {
        "default": {"url": "https://...", "width": 120, "height": 90},
        "medium": {"url": "https://...", "width": 320, "height": 180},
        "high": {"url": "https://...", "width": 480, "height": 360}
      },
      "url": "https://www.youtube.com/watch?v=video_id_123"
    }
  ],
  "timestamp": "2024-01-01T12:00:00"
}
```

## 🛠️ Advanced Features

### **Search Filters**

```python
def search_youtube_advanced(query, max_results=10, order="relevance", published_after=None):
    request_params = {
        "q": query,
        "part": "snippet",
        "maxResults": max_results,
        "type": "video",
        "order": order  # relevance, date, rating, viewCount, title
    }
    
    if published_after:
        request_params["publishedAfter"] = published_after
    
    request = youtube.search().list(**request_params)
    response = request.execute()
    return response["items"]
```

### **Channel Search**

```python
def search_channels(query, max_results=5):
    request = youtube.search().list(
        q=query,
        part="snippet",
        maxResults=max_results,
        type="channel"
    )
    response = request.execute()
    return response["items"]
```

### **Playlist Search**

```python
def search_playlists(query, max_results=5):
    request = youtube.search().list(
        q=query,
        part="snippet",
        maxResults=max_results,
        type="playlist"
    )
    response = request.execute()
    return response["items"]
```

## 🔍 Error Handling

### **Robust Search Function**

```python
def search_youtube_robust(query, max_results=5):
    try:
        request = youtube.search().list(
            q=query,
            part="snippet",
            maxResults=max_results,
            type="video"
        )
        response = request.execute()
        return response["items"]
    except HttpError as e:
        print(f"YouTube API error: {e}")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return []

# Usage with error handling
videos = search_youtube_robust("podcast tips")
if videos:
    for video in videos:
        print(video["snippet"]["title"])
else:
    print("No videos found or error occurred")
```

## 📈 Performance Tips

### **1. Batch Requests**

```python
def get_video_details_batch(video_ids, max_batch_size=50):
    """Get details for multiple videos efficiently"""
    all_videos = []
    
    # Process in batches
    for i in range(0, len(video_ids), max_batch_size):
        batch_ids = video_ids[i:i + max_batch_size]
        
        request = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(batch_ids)
        )
        response = request.execute()
        all_videos.extend(response["items"])
    
    return all_videos
```

### **2. Caching Results**

```python
import json
from datetime import datetime, timedelta

def search_youtube_cached(query, max_results=5, cache_duration_hours=1):
    """Search with caching to avoid repeated API calls"""
    cache_file = f"youtube_cache_{query.replace(' ', '_')}.json"
    
    # Check if cache exists and is fresh
    try:
        with open(cache_file, 'r') as f:
            cached_data = json.load(f)
            cached_time = datetime.fromisoformat(cached_data["timestamp"])
            
            if datetime.now() - cached_time < timedelta(hours=cache_duration_hours):
                return cached_data["videos"]
    except (FileNotFoundError, KeyError, ValueError):
        pass
    
    # Perform search
    videos = search_youtube(query, max_results)
    
    # Cache results
    cache_data = {
        "timestamp": datetime.now().isoformat(),
        "videos": videos
    }
    
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f)
    
    return videos
```

## 🎯 Use Cases for Podcasters

### **1. Content Research**

```python
# Find podcast-related content
podcast_videos = search_youtube("podcast interview techniques", max_results=10)
for video in podcast_videos:
    print(f"Research: {video['snippet']['title']}")
```

### **2. Guest Research**

```python
# Research potential guests
guest_videos = search_youtube("Jordan Peterson interview", max_results=5)
for video in guest_videos:
    print(f"Guest content: {video['snippet']['title']}")
```

### **3. Equipment Reviews**

```python
# Find equipment reviews
equipment_videos = search_youtube("podcast microphone review", max_results=5)
for video in equipment_videos:
    print(f"Equipment: {video['snippet']['title']}")
```

### **4. Trending Topics**

```python
# Stay current with trends
trending = get_trending_videos("US", max_results=10)
for video in trending:
    print(f"Trending: {video['snippet']['title']}")
```

## 🔗 Resources

- **YouTube Data API Documentation**: [https://developers.google.com/youtube/v3](https://developers.google.com/youtube/v3)
- **Google Cloud Console**: [https://console.cloud.google.com/](https://console.cloud.google.com/)
- **API Quotas**: [https://developers.google.com/youtube/v3/getting-started#quota](https://developers.google.com/youtube/v3/getting-started#quota)
- **SoapBoxx Documentation**: [README.md](README.md)

---

**🎯 YouTube API integration provides powerful video content discovery for your podcast research!** 