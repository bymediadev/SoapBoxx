import os
import sys
from typing import Dict, Optional
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from dotenv import load_dotenv
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QTextEdit, 
                             QVBoxLayout, QWidget, QGroupBox, QGridLayout,
                             QLineEdit, QComboBox, QMessageBox, QSplitter)

# Load environment variables from .env if not already loaded
load_dotenv()


class ScoopTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("📰 Scoop - News & Research")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Search Engine Section
        search_group = QGroupBox("🔍 Search Engine")
        search_layout = QGridLayout()
        
        # Search type selector
        search_type_label = QLabel("Search Type:")
        self.search_type_combo = QComboBox()
        self.search_type_combo.addItems(["Guest Research", "Topic Research", "News Search", "Social Media Search"])
        self.search_type_combo.currentTextChanged.connect(self.on_search_type_changed)
        search_layout.addWidget(search_type_label, 0, 0)
        search_layout.addWidget(self.search_type_combo, 0, 1)
        
        # Search query input
        query_label = QLabel("Search Query:")
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Enter guest name, topic, or keywords...")
        self.query_input.returnPressed.connect(self.perform_search)
        search_layout.addWidget(query_label, 1, 0)
        search_layout.addWidget(self.query_input, 1, 1)
        
        # Additional info input (for guest research)
        self.additional_info_label = QLabel("Additional Info:")
        self.additional_info_input = QLineEdit()
        self.additional_info_input.setPlaceholderText("Website, social media, or additional context...")
        self.additional_info_input.setVisible(False)
        search_layout.addWidget(self.additional_info_label, 2, 0)
        search_layout.addWidget(self.additional_info_input, 2, 1)
        
        # Search button
        self.search_button = QPushButton("🔍 Search")
        self.search_button.clicked.connect(self.perform_search)
        self.search_button.setStyleSheet("font-weight: bold; padding: 8px;")
        search_layout.addWidget(self.search_button, 3, 0, 1, 2)
        
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # API Keys Status Section
        api_group = QGroupBox("🔑 API Keys Status")
        api_layout = QGridLayout()
        
        # Get API keys from environment
        api_keys = self.get_api_keys()
        
        # Display API key status
        row = 0
        for key_name, key_value in api_keys.items():
            status_label = QLabel(f"{key_name}:")
            status_label.setStyleSheet("font-weight: bold;")
            
            if key_value and key_value != "Not set":
                status = f"✅ {key_value[:8]}..." if len(key_value) > 8 else f"✅ {key_value}"
                status_color = "color: green;"
            else:
                status = "❌ Not configured"
                status_color = "color: red;"
            
            status_value = QLabel(status)
            status_value.setStyleSheet(status_color)
            
            api_layout.addWidget(status_label, row, 0)
            api_layout.addWidget(status_value, row, 1)
            row += 1
        
        api_group.setLayout(api_layout)
        layout.addWidget(api_group)
        
        # Features Section
        features_group = QGroupBox("🎯 Quick Actions")
        features_layout = QVBoxLayout()
        
        # News Integration
        news_btn = QPushButton("📰 Get Latest News")
        news_btn.clicked.connect(self.get_latest_news)
        news_btn.setEnabled(bool(api_keys.get("NEWS_API_KEY") and api_keys.get("NEWS_API_KEY") != "Not set"))
        features_layout.addWidget(news_btn)
        
        # Social Media Integration (Enhanced with snscrape)
        social_btn = QPushButton("🐦 Social Media Trends (snscrape)")
        social_btn.clicked.connect(self.get_social_trends)
        social_btn.setEnabled(True)  # snscrape doesn't require API keys
        features_layout.addWidget(social_btn)
        
        # Twitter Trends
        twitter_btn = QPushButton("🐦 Twitter Trends")
        twitter_btn.clicked.connect(self.get_twitter_trends)
        twitter_btn.setEnabled(True)  # snscrape doesn't require API keys
        features_layout.addWidget(twitter_btn)
        
        # Reddit Trends
        reddit_btn = QPushButton("🤖 Reddit Trends")
        reddit_btn.clicked.connect(self.get_reddit_trends)
        reddit_btn.setEnabled(True)  # snscrape doesn't require API keys
        features_layout.addWidget(reddit_btn)
        
        # YouTube Integration
        youtube_btn = QPushButton("📺 YouTube Trends")
        youtube_btn.clicked.connect(self.get_youtube_trends)
        youtube_btn.setEnabled(bool(api_keys.get("YOUTUBE_API_KEY") and api_keys.get("YOUTUBE_API_KEY") != "Not set"))
        features_layout.addWidget(youtube_btn)
        
        # Podcast Search
        podcast_btn = QPushButton("🎙️ Podcast Search")
        podcast_btn.clicked.connect(self.podcast_search)
        podcast_btn.setEnabled(bool(any(api_keys.get(k) and api_keys.get(k) != "Not set" for k in ["PODCHASER_API_KEY", "LISTEN_NOTES_API_KEY", "APPLE_PODCASTS_API_KEY", "GOOGLE_PODCASTS_API_KEY"])))
        features_layout.addWidget(podcast_btn)
        
        features_group.setLayout(features_layout)
        layout.addWidget(features_group)
        
        # Results Section
        results_group = QGroupBox("📊 Search Results")
        results_layout = QVBoxLayout()
        
        self.results_text = QTextEdit()
        self.results_text.setPlaceholderText("Search results, news, social media trends, and research results will appear here...")
        self.results_text.setMaximumHeight(400)
        results_layout.addWidget(self.results_text)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        self.setLayout(layout)
    
    def on_search_type_changed(self, search_type: str):
        """Handle search type change"""
        if search_type == "Guest Research":
            self.additional_info_label.setVisible(True)
            self.additional_info_input.setVisible(True)
            self.query_input.setPlaceholderText("Enter guest name...")
            self.additional_info_input.setPlaceholderText("Website, social media, or additional context...")
        else:
            self.additional_info_label.setVisible(False)
            self.additional_info_input.setVisible(False)
            if search_type == "Topic Research":
                self.query_input.setPlaceholderText("Enter topic or keywords...")
            elif search_type == "News Search":
                self.query_input.setPlaceholderText("Enter news topic or keywords...")
            elif search_type == "Social Media Search":
                self.query_input.setPlaceholderText("Enter social media topic or hashtag...")
    
    def perform_search(self):
        """Perform search based on selected type and query"""
        search_type = self.search_type_combo.currentText()
        query = self.query_input.text().strip()
        
        if not query:
            QMessageBox.warning(self, "Search Error", "Please enter a search query.")
            return
        
        try:
            if search_type == "Guest Research":
                self.search_guest(query)
            elif search_type == "Topic Research":
                self.search_topic(query)
            elif search_type == "News Search":
                self.search_news(query)
            elif search_type == "Social Media Search":
                self.search_social_media(query)
        except Exception as e:
            self.results_text.setText(f"❌ Search error: {str(e)}")
    
    def search_guest(self, guest_name: str):
        """Search for guest information"""
        try:
            # Import guest research
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path("backend")))
            from guest_research import GuestResearch
            
            self.results_text.setText(f"🔍 Researching guest: {guest_name}...\n\nThis may take a moment...")
            
            # Get additional info if provided
            additional_info = self.additional_info_input.text().strip() if self.additional_info_input.isVisible() else None
            
            # Initialize guest research
            guest_research = GuestResearch()
            
            # Perform research
            research_results = guest_research.research(guest_name, additional_info=additional_info)
            
            if "error" in research_results:
                self.results_text.setText(f"❌ Guest research error: {research_results['error']}")
                return
            
            # Format results
            results = [f"🔍 Guest Research Results\n"]
            results.append(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            results.append(f"👤 Guest: {guest_name}")
            if additional_info:
                results.append(f"📝 Additional Info: {additional_info}")
            results.append("─" * 50 + "\n")
            
            # Profile
            if research_results.get("profile"):
                results.append("📋 Profile:")
                results.append(research_results["profile"])
                results.append("")
            
            # Talking points
            if research_results.get("talking_points"):
                results.append("💬 Talking Points:")
                for i, point in enumerate(research_results["talking_points"], 1):
                    results.append(f"  {i}. {point}")
                results.append("")
            
            # Questions
            if research_results.get("questions"):
                results.append("❓ Suggested Questions:")
                for i, question in enumerate(research_results["questions"], 1):
                    results.append(f"  {i}. {question}")
                results.append("")
            
            # Recent work
            if research_results.get("recent_work"):
                results.append("📈 Recent Work:")
                results.append(research_results["recent_work"])
                results.append("")
            
            # Controversies
            if research_results.get("controversies"):
                results.append("⚠️ Controversies/Sensitive Topics:")
                results.append(research_results["controversies"])
                results.append("")
            
            # Interests
            if research_results.get("interests"):
                results.append("🎯 Interests/Hobbies:")
                results.append(research_results["interests"])
                results.append("")
            
            results.append("✨ Powered by AI-powered guest research!")
            
            self.results_text.setText("\n".join(results))
            
        except Exception as e:
            self.results_text.setText(f"❌ Error researching guest: {str(e)}")
    
    def search_topic(self, topic: str):
        """Search for topic information"""
        try:
            # Import guest research for web search functionality
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path("backend")))
            from guest_research import GuestResearch
            
            self.results_text.setText(f"🔍 Researching topic: {topic}...\n\nThis may take a moment...")
            
            # Initialize guest research for web search
            guest_research = GuestResearch()
            
            # Use the web search functionality from guest research
            web_results = guest_research._search_web(topic)
            
            if not web_results:
                # If web search fails, provide mock data
                self.results_text.setText("⚠️ Real-time search failed. Showing sample data...")
                web_results = [
                    {
                        "title": f"Sample result for {topic}",
                        "snippet": f"This is a sample search result for the topic '{topic}'. In a real implementation, this would show actual web search results from Google Custom Search API.",
                        "link": "https://example.com",
                        "displayLink": "example.com"
                    },
                    {
                        "title": f"Another result for {topic}",
                        "snippet": f"Additional information about {topic} would appear here. This helps users understand the topic better for podcast content planning.",
                        "link": "https://example2.com",
                        "displayLink": "example2.com"
                    }
                ]
            
            # Format results
            results = [f"🔍 Topic Research Results\n"]
            results.append(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            results.append(f"🔍 Topic: {topic}")
            results.append(f"📊 Found {len(web_results)} results")
            results.append("─" * 50 + "\n")
            
            for i, result in enumerate(web_results[:5], 1):
                results.append(f"{i}. {result['title']}")
                results.append(f"   {result['snippet'][:200]}{'...' if len(result['snippet']) > 200 else ''}")
                results.append(f"   🔗 {result['link']}")
                results.append("")
            
            results.append("✨ Powered by Google Custom Search API!")
            
            self.results_text.setText("\n".join(results))
            
        except Exception as e:
            self.results_text.setText(f"❌ Error researching topic: {str(e)}")
    
    def search_news(self, query: str):
        """Search for news articles"""
        try:
            import requests
            
            self.results_text.setText(f"📰 Searching news for: {query}...\n\nThis may take a moment...")
            
            news_api_key = os.environ.get("NEWS_API_KEY")
            if not news_api_key or news_api_key == "Not set":
                self.results_text.setText("❌ News API key not configured. Please add NEWS_API_KEY to your .env file.")
                return
            
            # News API endpoint
            url = "https://newsapi.org/v2/everything"
            
            # Parameters for news search
            params = {
                "apiKey": news_api_key,
                "q": query,
                "pageSize": 10,
                "language": "en",
                "sortBy": "relevancy"
            }
            
            # Make the request
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get("articles", [])
                
                if articles:
                    results = [f"📰 News Search Results\n"]
                    results.append(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    results.append(f"🔍 Query: {query}")
                    results.append(f"📊 Found {len(articles)} articles")
                    results.append("─" * 50 + "\n")
                    
                    for i, article in enumerate(articles[:5], 1):
                        title = article.get("title", "No title")
                        source = article.get("source", {}).get("name", "Unknown source")
                        description = article.get("description", "No description available")
                        url = article.get("url", "#")
                        published_at = article.get("publishedAt", "Unknown date")
                        
                        # Format the date
                        try:
                            date_obj = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                            formatted_date = date_obj.strftime("%Y-%m-%d %H:%M")
                        except:
                            formatted_date = published_at
                        
                        results.append(f"{i}. {title}")
                        results.append(f"   📰 Source: {source}")
                        results.append(f"   📅 Published: {formatted_date}")
                        results.append(f"   📝 {description[:150]}{'...' if len(description) > 150 else ''}")
                        results.append(f"   🔗 {url}")
                        results.append("")
                    
                    results.append("✨ Powered by News API!")
                    
                    self.results_text.setText("\n".join(results))
                else:
                    self.results_text.setText(f"📰 No news articles found for: {query}")
            else:
                error_msg = f"❌ News API Error: {response.status_code}"
                if response.status_code == 401:
                    error_msg += " - Invalid API key"
                elif response.status_code == 429:
                    error_msg += " - Rate limit exceeded"
                else:
                    try:
                        error_data = response.json()
                        error_msg += f" - {error_data.get('message', 'Unknown error')}"
                    except:
                        error_msg += f" - {response.text[:100]}"
                
                self.results_text.setText(error_msg)
                
        except Exception as e:
            self.results_text.setText(f"❌ Error searching news: {str(e)}")
    
    def search_social_media(self, query: str):
        """Search for social media content"""
        try:
            # Import social media scraper
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path("backend")))
            from social_media_scraper import SocialMediaScraper
            
            self.results_text.setText(f"🐦 Searching social media for: {query}...\n\nThis may take a moment...")
            
            scraper = SocialMediaScraper()
            
            if not scraper.is_available():
                self.results_text.setText("❌ snscrape not available. Please install with: pip install snscrape")
                return
            
            # Get social media content from both Twitter and Reddit
            twitter_results = scraper.search_social_media(query, platform="twitter", limit=5)
            reddit_results = scraper.search_social_media(query, platform="reddit", limit=5)
            
            # Format results
            results = [f"🐦 Social Media Search Results\n"]
            results.append(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            results.append(f"🔍 Query: {query}")
            results.append("─" * 50 + "\n")
            
            # Twitter results
            if "error" not in twitter_results and twitter_results.get("tweets"):
                results.append("🐦 Twitter Results:")
                for i, tweet in enumerate(twitter_results["tweets"][:3], 1):
                    results.append(f"  {i}. @{tweet['username']}: {tweet['content'][:150]}{'...' if len(tweet['content']) > 150 else ''}")
                    results.append(f"     ❤️ {tweet['likes']} likes | 🔗 {tweet['url']}")
                results.append("")
            elif "error" in twitter_results:
                results.append("🐦 Twitter Results: Error - " + twitter_results["error"])
                results.append("")
            
            # Reddit results
            if "error" not in reddit_results and reddit_results.get("posts"):
                results.append("🤖 Reddit Results:")
                for i, post in enumerate(reddit_results["posts"][:3], 1):
                    results.append(f"  {i}. {post['title']}")
                    results.append(f"     👤 u/{post['author']} | ⬆️ {post['upvotes']} upvotes")
                    results.append(f"     🔗 {post['url']}")
                results.append("")
            elif "error" in reddit_results:
                results.append("🤖 Reddit Results: Error - " + reddit_results["error"])
                results.append("")
            
            # If both failed, try mock data
            if ("error" in twitter_results and "error" in reddit_results):
                self.results_text.setText("⚠️ Real-time social media search failed. Showing sample data...")
                mock_data = scraper.get_mock_trends()
                
                results = [f"🐦 Social Media Search Results (Sample Data)\n"]
                results.append(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                results.append(f"🔍 Query: {query}")
                results.append("─" * 50 + "\n")
                
                if mock_data.get("twitter"):
                    results.append("🐦 Twitter Results:")
                    for i, tweet in enumerate(mock_data["twitter"][:3], 1):
                        results.append(f"  {i}. @{tweet['username']}: {tweet['content']}")
                        results.append(f"     ❤️ {tweet['likes']} likes | 🔗 {tweet['url']}")
                    results.append("")
                
                if mock_data.get("reddit"):
                    results.append("🤖 Reddit Results:")
                    for i, post in enumerate(mock_data["reddit"][:3], 1):
                        results.append(f"  {i}. {post['title']}")
                        results.append(f"     👤 u/{post['author']} | ⬆️ {post['upvotes']} upvotes")
                        results.append(f"     🔗 {post['url']}")
                    results.append("")
            
            results.append("✨ Powered by snscrape - No API keys required!")
            
            self.results_text.setText("\n".join(results))
            
        except Exception as e:
            self.results_text.setText(f"❌ Error searching social media: {str(e)}")
    
    def get_api_keys(self) -> Dict[str, str]:
        """Get all relevant API keys from environment variables"""
        return {
            "OpenAI API Key": os.environ.get("OPENAI_API_KEY", "Not set"),
            "News API Key": os.environ.get("NEWS_API_KEY", "Not set"),
            "Twitter API Key": os.environ.get("TWITTER_API_KEY", "Not set"),
            "Google API Key": os.environ.get("GOOGLE_API_KEY", "Not set"),
            "Google CSE ID": os.environ.get("GOOGLE_CSE_ID", "Not set"),
            "YouTube API Key": os.environ.get("YOUTUBE_API_KEY", "Not set"),
            "PODCHASER_API_KEY": os.environ.get("PODCHASER_API_KEY", "Not set"),
            "LISTEN_NOTES_API_KEY": os.environ.get("LISTEN_NOTES_API_KEY", "Not set"),
            "APPLE_PODCASTS_API_KEY": os.environ.get("APPLE_PODCASTS_API_KEY", "Not set"),
            "GOOGLE_PODCASTS_API_KEY": os.environ.get("GOOGLE_PODCASTS_API_KEY", "Not set"),
        }
    
    def get_latest_news(self):
        """Get latest news using News API"""
        news_api_key = os.environ.get("NEWS_API_KEY")
        if not news_api_key or news_api_key == "Not set":
            self.results_text.setText("❌ News API key not configured. Please add NEWS_API_KEY to your .env file.")
            return
        
        try:
            import requests
            
            self.results_text.setText("📰 Fetching latest news...\n\nThis may take a moment...")
            
            # News API endpoint
            url = "https://newsapi.org/v2/top-headlines"
            
            # Parameters for podcast and technology related news
            params = {
                "apiKey": news_api_key,
                "country": "us",
                "category": "technology",
                "pageSize": 10,
                "language": "en"
            }
            
            # Make the request
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                articles = data.get("articles", [])
                
                if articles:
                    results = ["📰 Latest News (News API)\n"]
                    results.append(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    results.append(f"📊 Total Articles: {len(articles)}\n")
                    results.append("─" * 50 + "\n")
                    
                    for i, article in enumerate(articles[:5], 1):
                        title = article.get("title", "No title")
                        source = article.get("source", {}).get("name", "Unknown source")
                        description = article.get("description", "No description available")
                        url = article.get("url", "#")
                        published_at = article.get("publishedAt", "Unknown date")
                        
                        # Format the date
                        try:
                            date_obj = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                            formatted_date = date_obj.strftime("%Y-%m-%d %H:%M")
                        except:
                            formatted_date = published_at
                        
                        results.append(f"{i}. {title}")
                        results.append(f"   📰 Source: {source}")
                        results.append(f"   📅 Published: {formatted_date}")
                        results.append(f"   📝 {description[:150]}{'...' if len(description) > 150 else ''}")
                        results.append(f"   🔗 {url}")
                        results.append("")
                    
                    results.append("✨ Powered by News API")
                    
                    self.results_text.setText("\n".join(results))
                else:
                    self.results_text.setText("📰 No news articles found. Try again later.")
            else:
                error_msg = f"❌ News API Error: {response.status_code}"
                if response.status_code == 401:
                    error_msg += " - Invalid API key"
                elif response.status_code == 429:
                    error_msg += " - Rate limit exceeded"
                else:
                    try:
                        error_data = response.json()
                        error_msg += f" - {error_data.get('message', 'Unknown error')}"
                    except:
                        error_msg += f" - {response.text[:100]}"
                
                self.results_text.setText(error_msg)
                
        except requests.exceptions.Timeout:
            self.results_text.setText("❌ News API request timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            self.results_text.setText(f"❌ Error fetching news: {str(e)}")
        except Exception as e:
            self.results_text.setText(f"❌ Unexpected error: {str(e)}")
    
    def get_social_trends(self):
        """Get social media trends using snscrape"""
        try:
            # Import social media scraper
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path("backend")))
            from social_media_scraper import SocialMediaScraper
            
            scraper = SocialMediaScraper()
            
            if not scraper.is_available():
                self.results_text.setText("❌ snscrape not available. Please install with: pip install snscrape")
                return
            
            self.results_text.setText("🐦 Fetching social media trends with snscrape...\n\nThis may take a moment...")
            
            # Get trending topics from multiple platforms
            trends = scraper.get_trending_topics()
            
            if "error" in trends:
                # If real scraping fails, use mock data
                self.results_text.setText("⚠️ Real-time scraping failed. Showing sample data...")
                trends = scraper.get_mock_trends()
            
            # Format results
            results = ["🐦 Social Media Trends (snscrape)\n"]
            results.append(f"📅 Timestamp: {trends.get('timestamp', 'N/A')}\n")
            
            # Twitter trends
            if trends.get("twitter"):
                results.append("🐦 Twitter Trends:")
                for i, tweet in enumerate(trends["twitter"][:3], 1):
                    results.append(f"  {i}. @{tweet['username']}: {tweet['content']}")
                    results.append(f"     ❤️ {tweet['likes']} likes | 🔗 {tweet['url']}")
                results.append("")
            
            # Reddit trends
            if trends.get("reddit"):
                results.append("🤖 Reddit Trends (r/podcasts):")
                for i, post in enumerate(trends["reddit"][:3], 1):
                    results.append(f"  {i}. {post['title']}")
                    results.append(f"     👤 u/{post['author']} | ⬆️ {post['upvotes']} upvotes")
                    results.append(f"     🔗 {post['url']}")
                results.append("")
            
            results.append("✨ Powered by snscrape - No API keys required!")
            
            self.results_text.setText("\n".join(results))
            
        except Exception as e:
            self.results_text.setText(f"❌ Error fetching social trends: {str(e)}")
    
    def get_twitter_trends(self):
        """Get Twitter trends using snscrape"""
        try:
            # Import social media scraper
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path("backend")))
            from social_media_scraper import SocialMediaScraper
            
            scraper = SocialMediaScraper()
            
            if not scraper.is_available():
                self.results_text.setText("❌ snscrape not available. Please install with: pip install snscrape")
                return
            
            self.results_text.setText("🐦 Fetching Twitter trends with snscrape...\n\nThis may take a moment...")
            
            # Get Twitter trends
            twitter_trends = scraper.get_twitter_trends("podcast", limit=8)
            
            if "error" in twitter_trends:
                # If real scraping fails, use mock data
                self.results_text.setText("⚠️ Real-time Twitter scraping failed. Showing sample data...")
                mock_data = scraper.get_mock_trends()
                twitter_trends = {
                    "platform": "twitter",
                    "query": "podcast",
                    "count": len(mock_data.get("twitter", [])),
                    "tweets": mock_data.get("twitter", []),
                    "timestamp": mock_data.get("timestamp", datetime.now().isoformat())
                }
            
            # Format results
            results = ["🐦 Twitter Trends (snscrape)\n"]
            results.append(f"📅 Timestamp: {twitter_trends.get('timestamp', 'N/A')}")
            results.append(f"🔍 Query: {twitter_trends.get('query', 'podcast')}")
            results.append(f"📊 Found {twitter_trends.get('count', 0)} tweets\n")
            
            for i, tweet in enumerate(twitter_trends.get("tweets", [])[:5], 1):
                results.append(f"{i}. @{tweet['username']}:")
                results.append(f"   {tweet['content'][:150]}{'...' if len(tweet['content']) > 150 else ''}")
                results.append(f"   ❤️ {tweet['likes']} likes | 🔗 {tweet['url']}")
                results.append("")
            
            results.append("✨ Powered by snscrape - No API keys required!")
            
            self.results_text.setText("\n".join(results))
            
        except Exception as e:
            self.results_text.setText(f"❌ Error fetching Twitter trends: {str(e)}")
    
    def get_reddit_trends(self):
        """Get Reddit trends using snscrape"""
        try:
            # Import social media scraper
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path("backend")))
            from social_media_scraper import SocialMediaScraper
            
            scraper = SocialMediaScraper()
            
            if not scraper.is_available():
                self.results_text.setText("❌ snscrape not available. Please install with: pip install snscrape")
                return
            
            self.results_text.setText("🤖 Fetching Reddit trends with snscrape...\n\nThis may take a moment...")
            
            # Get Reddit trends
            reddit_trends = scraper.get_reddit_trends("podcasts", limit=8)
            
            if "error" in reddit_trends:
                # If real scraping fails, use mock data
                self.results_text.setText("⚠️ Real-time Reddit scraping failed. Showing sample data...")
                mock_data = scraper.get_mock_trends()
                reddit_trends = {
                    "platform": "reddit",
                    "subreddit": "podcasts",
                    "count": len(mock_data.get("reddit", [])),
                    "posts": mock_data.get("reddit", []),
                    "timestamp": mock_data.get("timestamp", datetime.now().isoformat())
                }
            
            # Format results
            results = ["🤖 Reddit Trends (r/podcasts)\n"]
            results.append(f"📅 Timestamp: {reddit_trends.get('timestamp', 'N/A')}")
            results.append(f"📊 Found {reddit_trends.get('count', 0)} posts\n")
            
            for i, post in enumerate(reddit_trends.get("posts", [])[:5], 1):
                results.append(f"{i}. {post['title']}")
                results.append(f"   👤 u/{post['author']}")
                results.append(f"   ⬆️ {post['upvotes']} upvotes")
                results.append(f"   🔗 {post['url']}")
                results.append("")
            
            results.append("✨ Powered by snscrape - No API keys required!")
            
            self.results_text.setText("\n".join(results))
            
        except Exception as e:
            self.results_text.setText(f"❌ Error fetching Reddit trends: {str(e)}")
    
    def research_topic(self):
        """Research a topic using Google API"""
        try:
            # Import Google APIs
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path("backend")))
            from google_apis import GoogleAPIs
            
            google_apis = GoogleAPIs()
            
            if not google_apis.is_available():
                self.results_text.setText("❌ Google API not configured. Please add GOOGLE_API_KEY and GOOGLE_CSE_ID to your .env file.")
                return
            
            # For now, use a sample query - in a real implementation, you'd get this from user input
            query = "podcast trends 2024"
            
            self.results_text.setText("🔍 Researching topic with Google API...\n\nThis may take a moment...")
            
            # Search for podcast-related content
            search_results = google_apis.search_podcast_content(query, num_results=5)
            
            if "error" in search_results:
                # If real search fails, use mock data
                self.results_text.setText("⚠️ Real-time search failed. Showing sample data...")
                search_results = google_apis.get_mock_search_results(query)
            
            # Format results
            results = ["🔍 Topic Research (Google API)\n"]
            results.append(f"📅 Timestamp: {search_results.get('timestamp', 'N/A')}")
            results.append(f"🔍 Query: {search_results.get('query', query)}")
            results.append(f"📊 Found {search_results.get('total_results', 0)} results\n")
            
            for i, result in enumerate(search_results.get("results", [])[:3], 1):
                results.append(f"{i}. {result['title']}")
                results.append(f"   {result['snippet'][:150]}{'...' if len(result['snippet']) > 150 else ''}")
                results.append(f"   🔗 {result['link']}")
                results.append("")
            
            results.append("✨ Powered by Google Custom Search API!")
            
            self.results_text.setText("\n".join(results))
            
        except Exception as e:
            self.results_text.setText(f"❌ Error researching topic: {str(e)}")
    
    def get_youtube_trends(self):
        """Get YouTube trends using YouTube API"""
        try:
            # Import Google APIs
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path("backend")))
            from google_apis import GoogleAPIs
            
            google_apis = GoogleAPIs()
            
            if not google_apis.is_available():
                self.results_text.setText("❌ YouTube API not configured. Please add YOUTUBE_API_KEY to your .env file.")
                return
            
            self.results_text.setText("📺 Fetching YouTube trends with YouTube API...\n\nThis may take a moment...")
            
            # Get YouTube trends
            youtube_trends = google_apis.get_youtube_trends("US", max_results=5)
            
            if "error" in youtube_trends:
                # If real trends fail, use mock data
                self.results_text.setText("⚠️ Real-time YouTube trends failed. Showing sample data...")
                youtube_trends = google_apis.get_mock_youtube_results("podcast")
            
            # Format results
            results = ["📺 YouTube Trends (YouTube API)\n"]
            results.append(f"📅 Timestamp: {youtube_trends.get('timestamp', 'N/A')}")
            results.append(f"🌍 Region: {youtube_trends.get('region', 'US')}")
            results.append(f"📊 Found {youtube_trends.get('total_results', 0)} videos\n")
            
            for i, video in enumerate(youtube_trends.get("videos", [])[:3], 1):
                results.append(f"{i}. {video['title']}")
                results.append(f"   📺 {video['channel_title']}")
                results.append(f"   👁️ {video['view_count']} views | ❤️ {video['like_count']} likes")
                results.append(f"   🔗 {video['url']}")
                results.append("")
            
            results.append("✨ Powered by YouTube Data API!")
            
            self.results_text.setText("\n".join(results))
            
        except Exception as e:
            self.results_text.setText(f"❌ Error fetching YouTube trends: {str(e)}")

    def podcast_search(self):
        """Search for podcasts using podcast-specific APIs"""
        try:
            # Import podcast APIs
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path("backend")))
            from podcast_apis import PodcastAPIs
            
            podcast_apis = PodcastAPIs()
            available_apis = podcast_apis.get_available_apis()
            
            if not any(available_apis.values()):
                self.results_text.setText("❌ No podcast APIs configured. Please add one of the following to your .env file:\n\n• PODCHASER_API_KEY - For podcast database and analytics\n• LISTEN_NOTES_API_KEY - For podcast search and discovery\n• APPLE_PODCASTS_API_KEY - For Apple Podcasts integration\n• GOOGLE_PODCASTS_API_KEY - For Google Podcasts integration")
                return
            
            # Search for trending podcasts
            trending_results = []
            for api, available in available_apis.items():
                if available:
                    try:
                        if api == "podchaser":
                            result = podcast_apis.get_trending_podcasts("podchaser")
                        elif api == "listen_notes":
                            result = podcast_apis.get_trending_podcasts("listen_notes")
                        else:
                            continue
                            
                        if "error" not in result:
                            trending_results.append(f"📊 {api.replace('_', ' ').title()} Trending:")
                            if api == "podchaser":
                                for edge in result.get("trending", [])[:5]:
                                    podcast = edge.get("node", {})
                                    trending_results.append(f"  • {podcast.get('title', 'N/A')} (Rating: {podcast.get('rating', 'N/A')})")
                            elif api == "listen_notes":
                                for podcast in result.get("trending", [])[:5]:
                                    trending_results.append(f"  • {podcast.get('title', 'N/A')} (Score: {podcast.get('listen_score', 'N/A')})")
                    except Exception as e:
                        trending_results.append(f"  ❌ {api} error: {str(e)}")
            
            if trending_results:
                self.results_text.setText("🎙️ Podcast Search Results\n\n" + "\n".join(trending_results) + "\n\nThis feature provides:\n• Podcast discovery and search\n• Trending podcasts\n• Podcast analytics\n• Episode information\n• Category browsing\n\nNote: This replaces Spotify's limited podcast functionality with dedicated podcast APIs.")
            else:
                self.results_text.setText("❌ No podcast search results available. Please check your API configurations.")
                
        except Exception as e:
            self.results_text.setText(f"❌ Error in podcast search: {str(e)}")
