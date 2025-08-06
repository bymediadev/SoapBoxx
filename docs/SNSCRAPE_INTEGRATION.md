# 🐦 snscrape Integration for SoapBoxx

## 📋 Overview

SoapBoxx now includes **snscrape** integration for social media trend analysis and content discovery. This feature allows you to scrape Twitter and Reddit for podcast-related trends, discussions, and content without requiring API keys.

## ✨ Features

### 🐦 **Twitter Integration**
- **Trending tweets** - Get latest podcast-related tweets
- **Hashtag tracking** - Monitor specific hashtags like #podcast, #podcasting
- **Content discovery** - Find trending topics and discussions
- **No API keys required** - Uses web scraping instead of official APIs

### 🤖 **Reddit Integration**
- **Subreddit monitoring** - Track r/podcasts and other podcast-related subreddits
- **Trending posts** - Get popular discussions and questions
- **Community insights** - Understand what podcasters are talking about
- **No API keys required** - Uses web scraping instead of official APIs

### 📊 **Social Media Analytics**
- **Cross-platform trends** - Compare trends across Twitter and Reddit
- **Content analysis** - Identify popular topics and discussions
- **Engagement metrics** - Track likes, upvotes, and interactions
- **Real-time data** - Get current trends and discussions

## 🚀 Quick Start

### 1. **Installation**

```bash
# Install snscrape
pip install snscrape

# Or install all SoapBoxx dependencies
pip install -r requirements.txt
```

### 2. **Usage in SoapBoxx**

1. **Launch SoapBoxx**:
   ```bash
   python frontend/main_window.py
   ```

2. **Navigate to Scoop Tab**:
   - Click on the "Scoop" tab in the main interface

3. **Use Social Media Features**:
   - **🐦 Social Media Trends (snscrape)** - Get trends from multiple platforms
   - **🐦 Twitter Trends** - Get Twitter-specific trends
   - **🤖 Reddit Trends** - Get Reddit-specific trends

### 3. **Programmatic Usage**

```python
from backend.social_media_scraper import SocialMediaScraper

# Initialize scraper
scraper = SocialMediaScraper()

# Check availability
if scraper.is_available():
    # Get Twitter trends
    twitter_trends = scraper.get_twitter_trends("podcast", limit=10)
    
    # Get Reddit trends
    reddit_trends = scraper.get_reddit_trends("podcasts", limit=10)
    
    # Get trending topics
    trending = scraper.get_trending_topics()
    
    print(f"Found {twitter_trends.get('count', 0)} Twitter trends")
    print(f"Found {reddit_trends.get('count', 0)} Reddit trends")
else:
    print("snscrape not available")
```

## 🎯 Use Cases

### **For Podcast Creators**

1. **Content Research**
   - Find trending topics to discuss on your podcast
   - Discover what your audience is talking about
   - Identify popular hashtags and discussions

2. **Audience Engagement**
   - Monitor conversations about your podcast
   - Track mentions and discussions
   - Engage with your community

3. **Competitive Analysis**
   - See what other podcasters are discussing
   - Identify gaps in content coverage
   - Understand industry trends

### **For Content Planning**

1. **Episode Ideas**
   - Use trending topics as episode themes
   - Address popular questions and discussions
   - Stay current with industry trends

2. **Guest Research**
   - Find potential guests based on trending discussions
   - Identify thought leaders in your niche
   - Research guest backgrounds and interests

3. **Marketing Insights**
   - Identify popular hashtags for promotion
   - Understand what content resonates
   - Track industry conversations

## 🔧 Configuration

### **Environment Variables**

No API keys are required for snscrape functionality. However, you can configure:

```bash
# Optional: Configure SSL settings (if needed)
export PYTHONHTTPSVERIFY=0  # Disable SSL verification (use with caution)
```

### **Error Handling**

The system includes robust error handling:

- **SSL Issues**: Automatically handles SSL certificate issues
- **Network Errors**: Graceful fallback to mock data
- **Rate Limiting**: Built-in delays and retry logic
- **Data Validation**: Ensures data integrity

## 📊 Data Format

### **Twitter Data Structure**

```json
{
  "platform": "twitter",
  "query": "podcast",
  "count": 10,
  "tweets": [
    {
      "id": "123456789",
      "username": "podcaster_pro",
      "display_name": "Podcast Pro",
      "content": "Just launched my new podcast! 🎙️",
      "date": "2024-01-01T12:00:00",
      "likes": 42,
      "retweets": 5,
      "replies": 3,
      "url": "https://twitter.com/podcaster_pro/status/123456789"
    }
  ],
  "timestamp": "2024-01-01T12:00:00"
}
```

### **Reddit Data Structure**

```json
{
  "platform": "reddit",
  "subreddit": "podcasts",
  "count": 10,
  "posts": [
    {
      "id": "abc123",
      "title": "What's your favorite podcast editing software?",
      "author": "podcast_editor",
      "content": "Looking for recommendations...",
      "date": "2024-01-01T12:00:00",
      "upvotes": 156,
      "downvotes": 5,
      "comments": 23,
      "url": "https://reddit.com/r/podcasts/comments/abc123",
      "subreddit": "podcasts"
    }
  ],
  "timestamp": "2024-01-01T12:00:00"
}
```

## 🛠️ Advanced Usage

### **Custom Queries**

```python
# Search for specific topics
scraper.get_twitter_trends("podcast marketing", limit=20)
scraper.get_reddit_trends("podcasting", limit=15)

# Search with hashtags
scraper.get_twitter_hashtags("podcast", limit=10)
```

### **Trend Analysis**

```python
# Get comprehensive trend analysis
trends = scraper.get_social_trends_summary(["twitter", "reddit"])

# Analyze trending topics
topics = scraper.get_trending_topics()
```

### **Error Handling**

```python
# Check for errors
twitter_data = scraper.get_twitter_trends("podcast")
if "error" in twitter_data:
    print(f"Error: {twitter_data['error']}")
    # Use mock data as fallback
    mock_data = scraper.get_mock_trends()
else:
    print(f"Found {twitter_data['count']} tweets")
```

## 🔍 Troubleshooting

### **Common Issues**

1. **SSL Certificate Errors**
   ```bash
   # Solution: Disable SSL verification (use with caution)
   export PYTHONHTTPSVERIFY=0
   ```

2. **Network Connectivity**
   - Check internet connection
   - Verify firewall settings
   - Try different network

3. **Rate Limiting**
   - Reduce request frequency
   - Use smaller limits
   - Implement delays between requests

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

1. **Additional Platforms**
   - Instagram scraping
   - LinkedIn monitoring
   - YouTube comments

2. **Advanced Analytics**
   - Sentiment analysis
   - Trend prediction
   - Content scoring

3. **Integration Features**
   - Automated posting
   - Content scheduling
   - Engagement tracking

## 🎉 Benefits

### **For SoapBoxx Users**

- **No API Keys Required** - Free social media data
- **Real-time Insights** - Current trends and discussions
- **Content Discovery** - Find relevant topics and guests
- **Community Engagement** - Monitor and engage with audience
- **Competitive Intelligence** - Track industry trends

### **For Podcast Creators**

- **Content Ideas** - Discover trending topics
- **Audience Research** - Understand what listeners want
- **Guest Discovery** - Find potential guests
- **Marketing Insights** - Identify promotion opportunities
- **Industry Trends** - Stay current with podcasting

## 🔗 Resources

- **snscrape Documentation**: [GitHub Repository](https://github.com/JustAnotherArchivist/snscrape)
- **Twitter Scraping**: [Twitter Search Scraper](https://github.com/JustAnotherArchivist/snscrape#twitter)
- **Reddit Scraping**: [Reddit Search Scraper](https://github.com/JustAnotherArchivist/snscrape#reddit)
- **SoapBoxx Documentation**: [README.md](README.md)

---

**🎯 snscrape integration provides powerful social media insights without requiring API keys!** 