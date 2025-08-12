# 🔍 Google API Integration for SoapBoxx

## 📋 Overview

SoapBoxx now includes **Google API** integration for web search, YouTube content discovery, and research capabilities. This feature provides access to Google's powerful search and content APIs to enhance your podcast research and content discovery.

## ✨ Features

### 🔍 **Google Custom Search API**
- **Web search** - Search the web for podcast-related content
- **Content discovery** - Find relevant articles, blogs, and resources
- **Research capabilities** - Comprehensive topic research
- **Custom search engine** - Tailored search results

### 📺 **YouTube Data API**
- **Video search** - Find YouTube videos related to your topics
- **Trending videos** - Get current trending content
- **Video analytics** - View counts, likes, comments
- **Content discovery** - Discover relevant video content

### 🎯 **Podcast-Specific Features**
- **Podcast research** - Find podcast-related content and discussions
- **Topic analysis** - Research trending topics for episodes
- **Content planning** - Discover content ideas and trends
- **Competitive analysis** - Research other podcasts and content

## 🚀 Quick Start

### 1. **Installation**

```bash
# Install Google API client
pip install google-api-python-client

# Or install all SoapBoxx dependencies
pip install -r requirements.txt
```

### 2. **Configuration**

#### **Required Environment Variables**

Add these to your `.env` file:

```bash
# Google Custom Search API
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_CSE_ID=your_custom_search_engine_id_here

# YouTube Data API
YOUTUBE_API_KEY=your_youtube_api_key_here
```

#### **Setting Up Google APIs**

1. **Google Custom Search API**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable "Custom Search API"
   - Create credentials (API key)
   - Create a Custom Search Engine at [Google Programmable Search Engine](https://programmablesearchengine.google.com/)
   - Get your Search Engine ID

2. **YouTube Data API**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Enable "YouTube Data API v3"
   - Create credentials (API key)

### 3. **Usage in SoapBoxx**

1. **Launch SoapBoxx**:
   ```bash
   python frontend/main_window.py
   ```

2. **Navigate to Scoop Tab**:
   - Click on the "Scoop" tab in the main interface

3. **Use Google API Features**:
   - **🔍 Research Topic** - Search for podcast-related content
   - **📺 YouTube Trends** - Get trending YouTube videos

### 4. **Programmatic Usage**

```python
from backend.google_apis import GoogleAPIs

# Initialize Google APIs
google_apis = GoogleAPIs()

# Check availability
if google_apis.is_available():
    # Search for podcast content
    search_results = google_apis.search_podcast_content("podcast trends", num_results=10)
    
    # Search YouTube
    youtube_results = google_apis.search_youtube("podcast", max_results=10)
    
    # Get YouTube trends
    youtube_trends = google_apis.get_youtube_trends("US", max_results=10)
    
    print(f"Found {search_results.get('total_results', 0)} search results")
    print(f"Found {youtube_results.get('total_results', 0)} YouTube videos")
else:
    print("Google APIs not configured")
```

## 🎯 Use Cases

### **For Podcast Creators**

1. **Content Research**
   - Find trending topics to discuss on your podcast
   - Research guest backgrounds and expertise
   - Discover relevant articles and resources
   - Stay current with industry trends

2. **Content Discovery**
   - Find YouTube videos for inspiration
   - Discover trending content in your niche
   - Research competitor content
   - Identify content gaps

3. **Episode Planning**
   - Research episode topics thoroughly
   - Find supporting content and resources
   - Discover guest interview questions
   - Plan content calendar

### **For Content Planning**

1. **Topic Research**
   - Comprehensive topic analysis
   - Find related discussions and debates
   - Identify trending conversations
   - Research audience interests

2. **Guest Research**
   - Research potential guests
   - Find their recent content and interviews
   - Understand their expertise areas
   - Prepare interview questions

3. **Competitive Analysis**
   - Research other podcasts in your niche
   - Analyze their content and approach
   - Identify opportunities and gaps
   - Stay ahead of trends

## 🔧 Configuration

### **Environment Variables**

```bash
# Google Custom Search API
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_CSE_ID=your_custom_search_engine_id_here

# YouTube Data API
YOUTUBE_API_KEY=your_youtube_api_key_here
```

### **API Limits and Quotas**

- **Google Custom Search API**: 100 free queries per day
- **YouTube Data API**: 10,000 units per day (free tier)
- **Rate Limiting**: Built-in delays and retry logic
- **Error Handling**: Graceful fallback to mock data

## 📊 Data Format

### **Web Search Results**

```json
{
  "query": "podcast trends",
  "total_results": 1000,
  "results": [
    {
      "title": "Top Podcast Trends for 2024",
      "link": "https://example.com/podcast-trends-2024",
      "snippet": "Discover the latest podcast trends...",
      "display_link": "example.com",
      "image": "https://example.com/image.jpg"
    }
  ],
  "timestamp": "2024-01-01T12:00:00"
}
```

### **YouTube Search Results**

```json
{
  "query": "podcast",
  "total_results": 10,
  "videos": [
    {
      "id": "video_id",
      "title": "How to Start a Podcast",
      "description": "Step-by-step guide...",
      "channel_title": "Podcast Academy",
      "published_at": "2024-01-01T00:00:00Z",
      "view_count": "15000",
      "like_count": "1200",
      "comment_count": "89",
      "duration": "PT15M30S",
      "url": "https://www.youtube.com/watch?v=video_id"
    }
  ],
  "timestamp": "2024-01-01T12:00:00"
}
```

## 🛠️ Advanced Usage

### **Custom Queries**

```python
# Search for specific topics
search_results = google_apis.search_web("podcast marketing strategies", num_results=20)
youtube_results = google_apis.search_youtube("podcast equipment", max_results=15)

# Search podcast-specific content
podcast_results = google_apis.search_podcast_content("interview techniques", num_results=10)
```

### **Trend Analysis**

```python
# Get YouTube trends for different regions
us_trends = google_apis.get_youtube_trends("US", max_results=10)
uk_trends = google_apis.get_youtube_trends("GB", max_results=10)

# Analyze trending content
for video in us_trends.get("videos", []):
    print(f"Trending: {video['title']} - {video['view_count']} views")
```

### **Error Handling**

```python
# Check for errors
search_results = google_apis.search_podcast_content("podcast trends")
if "error" in search_results:
    print(f"Error: {search_results['error']}")
    # Use mock data as fallback
    mock_results = google_apis.get_mock_search_results("podcast trends")
else:
    print(f"Found {search_results['total_results']} results")
```

## 🔍 Troubleshooting

### **Common Issues**

1. **API Key Not Configured**
   ```bash
   # Solution: Add to .env file
   GOOGLE_API_KEY=your_actual_api_key
   GOOGLE_CSE_ID=your_actual_search_engine_id
   YOUTUBE_API_KEY=your_actual_youtube_api_key
   ```

2. **API Quota Exceeded**
   - Check your Google Cloud Console quotas
   - Implement rate limiting
   - Use mock data as fallback

3. **Import Errors**
   ```bash
   # Solution: Install Google API client
   pip install google-api-python-client
   ```

### **Performance Tips**

1. **Optimize Queries**
   - Use specific search terms
   - Limit result counts
   - Cache results when possible

2. **Error Recovery**
   - Implement retry logic
   - Use mock data as fallback
   - Log errors for debugging

3. **Data Management**
   - Store results locally
   - Implement data validation
   - Clean and format data

## 📈 Future Enhancements

### **Planned Features**

1. **Advanced Search**
   - Filter by date range
   - Search specific domains
   - Advanced query operators

2. **Content Analysis**
   - Sentiment analysis
   - Content categorization
   - Trend prediction

3. **Integration Features**
   - Automated content discovery
   - Content scheduling
   - Analytics dashboard

## 🎉 Benefits

### **For SoapBoxx Users**

- **Comprehensive Research** - Access to Google's vast content database
- **Content Discovery** - Find relevant articles, videos, and resources
- **Trend Analysis** - Stay current with industry trends
- **Competitive Intelligence** - Research competitor content
- **Guest Research** - Find and research potential guests

### **For Podcast Creators**

- **Content Ideas** - Discover trending topics and discussions
- **Research Efficiency** - Quick and comprehensive topic research
- **Content Quality** - Find supporting content and resources
- **Audience Insights** - Understand what content resonates
- **Industry Trends** - Stay ahead of podcasting trends

## 🔗 Resources

- **Google API Documentation**: [Google APIs](https://developers.google.com/apis)
- **Custom Search API**: [Custom Search API](https://developers.google.com/custom-search)
- **YouTube Data API**: [YouTube Data API](https://developers.google.com/youtube/v3)
- **Google Cloud Console**: [Cloud Console](https://console.cloud.google.com/)
- **SoapBoxx Documentation**: [README.md](README.md)

---

**🎯 Google API integration provides powerful research and content discovery capabilities!** 