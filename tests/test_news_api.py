#!/usr/bin/env python3
"""
Test script for News API integration
"""

import os
import requests
from dotenv import load_dotenv

def test_news_api():
    """Test News API functionality"""
    print("📰 Testing News API integration...")
    
    # Load environment variables
    load_dotenv()
    
    # Get API key
    news_api_key = os.getenv("NEWS_API_KEY")
    if not news_api_key:
        print("❌ News API key not configured")
        return False
    
    print(f"✅ News API key found: {news_api_key[:8]}...")
    
    try:
        # News API endpoint
        url = "https://newsapi.org/v2/top-headlines"
        
        # Parameters for technology news
        params = {
            "apiKey": news_api_key,
            "country": "us",
            "category": "technology",
            "pageSize": 3,
            "language": "en"
        }
        
        print("🔍 Fetching latest technology news...")
        
        # Make the request
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            articles = data.get("articles", [])
            
            if articles:
                print(f"✅ Success! Found {len(articles)} articles")
                print("\n📰 Sample Articles:")
                for i, article in enumerate(articles[:2], 1):
                    title = article.get("title", "No title")
                    source = article.get("source", {}).get("name", "Unknown source")
                    print(f"  {i}. {title}")
                    print(f"     📰 Source: {source}")
                print("\n🎉 News API integration is working!")
                return True
            else:
                print("⚠️ No articles found")
                return False
        else:
            print(f"❌ News API Error: {response.status_code}")
            if response.status_code == 401:
                print("   - Invalid API key")
            elif response.status_code == 429:
                print("   - Rate limit exceeded")
            else:
                try:
                    error_data = response.json()
                    print(f"   - {error_data.get('message', 'Unknown error')}")
                except:
                    print(f"   - {response.text[:100]}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ News API request timed out")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_news_api()
    exit(0 if success else 1) 