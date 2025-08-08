import os
import sys
from datetime import datetime
from typing import Dict, Optional

# Add backend to path - handle separate frontend/backend folder structure
current_dir = os.path.dirname(os.path.abspath(__file__))  # frontend/
parent_dir = os.path.dirname(current_dir)  # root/
backend_dir = os.path.join(parent_dir, "backend")  # root/backend/
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
from PyQt6.QtWidgets import (QComboBox, QGridLayout, QGroupBox, QHBoxLayout,
                             QLabel, QLineEdit, QMessageBox, QPushButton,
                             QSplitter, QTextEdit, QVBoxLayout, QWidget,
                             QScrollArea, QScrollBar, QAbstractScrollArea,
                             QFrame) # Added QFrame
from PyQt6.QtCore import Qt

# Load environment variables from .env if not already loaded
load_dotenv()


class ModernCard(QFrame):
    """Modern card widget with shadow and rounded corners"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            ModernCard {
                background-color: white;
                border: 1px solid #E0E0E0;
                border-radius: 12px;
                padding: 16px;
                margin: 8px;
            }
            ModernCard:hover {
                border: 1px solid #BDBDBD;
            }
        """)


class ModernButton(QPushButton):
    """Modern button with gradient and hover effects"""
    
    def __init__(self, text="", parent=None, style="primary"):
        super().__init__(text, parent)
        self.style_type = style
        self.update_style()
    
    def update_style(self):
        if self.style_type == "primary":
            self.setStyleSheet("""
                ModernButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #3498DB, stop:1 #2980B9);
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 14px;
                }
                ModernButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2980B9, stop:1 #1F5F8B);
                }
                ModernButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1F5F8B, stop:1 #154360);
                }
            """)
        elif self.style_type == "secondary":
            self.setStyleSheet("""
                ModernButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #6C757D, stop:1 #495057);
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 14px;
                }
                ModernButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #495057, stop:1 #343A40);
                }
            """)
        elif self.style_type == "success":
            self.setStyleSheet("""
                ModernButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #28A745, stop:1 #1E7E34);
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 14px;
                }
                ModernButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #1E7E34, stop:1 #155724);
                }
            """)


class ScoopTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        """Setup the user interface with modern design"""
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title with modern styling
        title = QLabel("📰 Scoop - News & Research")
        title.setStyleSheet("""
            font-size: 24px; 
            font-weight: bold; 
            color: #2C3E50;
            margin: 20px 0;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Create a scroll area for better content management
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #F8F9FA;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #DEE2E6;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #ADB5BD;
            }
        """)
        
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(20)

        # Search Engine Section - Modern Card Design
        search_card = ModernCard()
        search_layout = QVBoxLayout(search_card)
        
        # Card header
        search_header = QLabel("🔍 Search Engine")
        search_header.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold; 
            color: #2C3E50;
            margin-bottom: 15px;
        """)
        search_layout.addWidget(search_header)

        # Search type selector with modern styling
        search_type_layout = QHBoxLayout()
        search_type_label = QLabel("Search Type:")
        search_type_label.setStyleSheet("font-weight: bold; color: #495057;")
        self.search_type_combo = QComboBox()
        self.search_type_combo.addItems(
            ["Guest Research", "Topic Research", "News Search", "Social Media Search", "Business Search", "LinkedIn Search", "Executive Search", "Company News"]
        )
        self.search_type_combo.currentTextChanged.connect(self.on_search_type_changed)
        self.search_type_combo.setStyleSheet("""
            QComboBox {
                padding: 10px;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                font-size: 14px;
                background: white;
            }
            QComboBox:focus {
                border: 2px solid #3498DB;
            }
        """)
        search_type_layout.addWidget(search_type_label)
        search_type_layout.addWidget(self.search_type_combo)
        search_type_layout.addStretch()
        search_layout.addLayout(search_type_layout)

        # Search query input with modern styling
        query_layout = QHBoxLayout()
        query_label = QLabel("Search Query:")
        query_label.setStyleSheet("font-weight: bold; color: #495057;")
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Enter guest name, topic, or keywords...")
        self.query_input.returnPressed.connect(self.perform_search)
        self.query_input.setStyleSheet("""
            QLineEdit {
                padding: 12px;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                font-size: 14px;
                background: white;
            }
            QLineEdit:focus {
                border: 2px solid #3498DB;
            }
        """)
        query_layout.addWidget(query_label)
        query_layout.addWidget(self.query_input)
        search_layout.addLayout(query_layout)

        # Additional info input (for guest research)
        self.additional_info_label = QLabel("Additional Info:")
        self.additional_info_label.setStyleSheet("font-weight: bold; color: #495057;")
        self.additional_info_input = QLineEdit()
        self.additional_info_input.setPlaceholderText(
            "Website, social media, or additional context..."
        )
        self.additional_info_input.setVisible(False)
        self.additional_info_input.setStyleSheet("""
            QLineEdit {
                padding: 12px;
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                font-size: 14px;
                background: white;
            }
            QLineEdit:focus {
                border: 2px solid #3498DB;
            }
        """)
        search_layout.addWidget(self.additional_info_label)
        search_layout.addWidget(self.additional_info_input)

        # Search button with modern styling
        self.search_button = ModernButton("🔍 Search", style="primary")
        self.search_button.clicked.connect(self.perform_search)
        search_layout.addWidget(self.search_button)

        scroll_layout.addWidget(search_card)

        # API Keys Status Section - Modern Card Design
        api_card = ModernCard()
        api_layout = QVBoxLayout(api_card)
        
        # Card header
        api_header = QLabel("🔑 API Keys Status")
        api_header.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold; 
            color: #2C3E50;
            margin-bottom: 15px;
        """)
        api_layout.addWidget(api_header)

        # Get API keys from environment
        api_keys = self.get_api_keys()

        # Display API key status in a grid
        api_grid = QGridLayout()
        row = 0
        for key_name, key_value in api_keys.items():
            status_label = QLabel(f"{key_name}:")
            status_label.setStyleSheet("font-weight: bold; color: #495057;")

            if key_value and key_value != "Not set":
                status = (
                    f"✅ {key_value[:8]}..."
                    if len(key_value) > 8
                    else f"✅ {key_value}"
                )
                status_color = "color: #28A745; background: #D4EDDA; padding: 5px 10px; border-radius: 4px;"
            else:
                status = "❌ Not configured"
                status_color = "color: #DC3545; background: #F8D7DA; padding: 5px 10px; border-radius: 4px;"

            status_value = QLabel(status)
            status_value.setStyleSheet(status_color)

            api_grid.addWidget(status_label, row, 0)
            api_grid.addWidget(status_value, row, 1)
            row += 1

        api_layout.addLayout(api_grid)
        scroll_layout.addWidget(api_card)

        # Results Section - Modern Card Design
        results_card = ModernCard()
        results_layout = QVBoxLayout(results_card)
        
        # Card header
        results_header = QLabel("📊 Search Results")
        results_header.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold; 
            color: #2C3E50;
            margin-bottom: 15px;
        """)
        results_layout.addWidget(results_header)

        # Results text area with modern styling
        self.results_text = QTextEdit()
        self.results_text.setPlaceholderText("Search results will appear here...")
        self.results_text.setStyleSheet("""
            QTextEdit {
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
                background: white;
                line-height: 1.5;
            }
            QTextEdit:focus {
                border: 2px solid #3498DB;
            }
        """)
        self.results_text.setMinimumHeight(300)
        results_layout.addWidget(self.results_text)

        scroll_layout.addWidget(results_card)

        # Set up scroll area
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        self.setLayout(layout)

    def on_search_type_changed(self, search_type: str):
        """Handle search type changes"""
        if search_type == "Guest Research":
            self.query_input.setPlaceholderText("Enter guest name...")
            self.additional_info_input.setVisible(True)
            self.additional_info_label.setVisible(True)
        elif search_type == "Topic Research":
            self.query_input.setPlaceholderText("Enter topic or keywords...")
            self.additional_info_input.setVisible(False)
            self.additional_info_label.setVisible(False)
        elif search_type == "News Search":
            self.query_input.setPlaceholderText("Enter news topic or keywords...")
            self.additional_info_input.setVisible(False)
            self.additional_info_label.setVisible(False)
        elif search_type == "Social Media Search":
            self.query_input.setPlaceholderText("Enter social media topic or hashtag...")
            self.additional_info_input.setVisible(False)
            self.additional_info_label.setVisible(False)
        elif search_type == "Business Search":
            self.query_input.setPlaceholderText("Enter company name...")
            self.additional_info_input.setVisible(False)
            self.additional_info_label.setVisible(False)
        elif search_type == "LinkedIn Search":
            self.query_input.setPlaceholderText("Enter company name or person name...")
            self.additional_info_input.setVisible(False)
            self.additional_info_label.setVisible(False)
        elif search_type == "Executive Search":
            self.query_input.setPlaceholderText("Enter company name for executive search...")
            self.additional_info_input.setVisible(False)
            self.additional_info_label.setVisible(False)
        elif search_type == "Company News":
            self.query_input.setPlaceholderText("Enter company name for recent news...")
            self.additional_info_input.setVisible(False)
            self.additional_info_label.setVisible(False)

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
            elif search_type == "Business Search":
                self.search_business(query, "all")
            elif search_type == "LinkedIn Search":
                self.search_business(query, "linkedin")
            elif search_type == "Executive Search":
                self.search_business(query, "executive")
            elif search_type == "Company News":
                self.search_business(query, "news")
        except Exception as e:
            self.results_text.setText(f"❌ Search error: {str(e)}")

    def search_guest(self, guest_name: str):
        """Search for guest information"""
        try:
            # Import guest research with robust error handling
            guest_research = None
            
            # Try multiple import paths for separate frontend/backend structure
            try:
                from guest_research import GuestResearch
                guest_research = GuestResearch()
            except ImportError:
                try:
                    # Try with backend path (already added to sys.path)
                    from guest_research import GuestResearch
                    guest_research = GuestResearch()
                except ImportError:
                    try:
                        # Try with explicit backend path
                        backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend")
                        sys.path.insert(0, backend_path)
                        from guest_research import GuestResearch
                        guest_research = GuestResearch()
                    except ImportError as e:
                        self.results_text.setText(f"❌ Error: Could not import GuestResearch module. Please check backend installation. Error: {e}")
                        return
            
            if guest_research is None:
                self.results_text.setText("❌ Error: Could not import GuestResearch module. Please check backend installation.")
                return

            self.results_text.setText(
                f"🔍 Researching guest: {guest_name}...\n\nThis may take a moment..."
            )

            # Get additional info if provided
            additional_info = (
                self.additional_info_input.text().strip()
                if self.additional_info_input.isVisible()
                else None
            )

            # Perform research
            research_results = guest_research.research(
                guest_name, additional_info=additional_info
            )

            if "error" in research_results:
                self.results_text.setText(
                    f"❌ Guest research error: {research_results['error']}"
                )
                return

            # Format results
            results = [f"🔍 Guest Research Results\n"]
            results.append(
                f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
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

            # If no results found, provide fallback
            if not any([research_results.get("profile"), 
                       research_results.get("talking_points"),
                       research_results.get("questions"),
                       research_results.get("recent_work"),
                       research_results.get("controversies"),
                       research_results.get("interests")]):
                results.append("📋 Basic Profile:")
                results.append(f"{guest_name} is a notable guest with expertise in their field.")
                results.append("")
                results.append("💬 Suggested Talking Points:")
                results.append("  • Professional background and experience")
                results.append("  • Current projects and interests")
                results.append("  • Industry insights and trends")
                results.append("")
                results.append("❓ Suggested Questions:")
                results.append("  • What inspired your career path?")
                results.append("  • Can you tell us about your current projects?")
                results.append("  • What advice would you give to someone starting out?")
                results.append("")

            results.append("✨ Powered by AI-powered guest research!")

            self.results_text.setText("\n".join(results))

        except Exception as e:
            self.results_text.setText(f"❌ Error researching guest: {str(e)}")
            print(f"Guest research error: {e}")
            import traceback
            traceback.print_exc()

    def search_topic(self, topic: str):
        """Search for topic information"""
        try:
            # Import guest research for web search functionality with robust error handling
            guest_research = None
            
            # Try multiple import paths for separate frontend/backend structure
            try:
                from guest_research import GuestResearch
                guest_research = GuestResearch()
            except ImportError:
                try:
                    # Try with backend path (already added to sys.path)
                    from guest_research import GuestResearch
                    guest_research = GuestResearch()
                except ImportError:
                    try:
                        # Try with explicit backend path
                        backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend")
                        sys.path.insert(0, backend_path)
                        from guest_research import GuestResearch
                        guest_research = GuestResearch()
                    except ImportError as e:
                        self.results_text.setText(f"❌ Error: Could not import GuestResearch module. Please check backend installation. Error: {e}")
                        return
            
            if guest_research is None:
                self.results_text.setText("❌ Error: Could not import GuestResearch module. Please check backend installation.")
                return

            self.results_text.setText(
                f"🔍 Researching topic: {topic}...\n\nThis may take a moment..."
            )

            # Use the public web search functionality from guest research
            web_results = guest_research.search_web(topic)

            if not web_results:
                # If web search fails, provide mock data
                self.results_text.setText(
                    "⚠️ Real-time search failed. Showing sample data..."
                )
                web_results = [
                    {
                        "title": f"Sample result for {topic}",
                        "snippet": f"This is a sample search result for the topic '{topic}'. In a real implementation, this would show actual web search results from Google Custom Search API.",
                        "link": "https://example.com",
                        "displayLink": "example.com",
                    },
                    {
                        "title": f"Another result for {topic}",
                        "snippet": f"Additional information about {topic} would appear here. This helps users understand the topic better for podcast content planning.",
                        "link": "https://example2.com",
                        "displayLink": "example2.com",
                    },
                ]

            # Format results
            results = [f"🔍 Topic Research Results\n"]
            results.append(
                f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            results.append(f"🔍 Topic: {topic}")
            results.append(f"📊 Found {len(web_results)} results")
            results.append("─" * 50 + "\n")

            for i, result in enumerate(web_results[:5], 1):
                results.append(f"{i}. {result.get('title', 'No title')}")
                snippet = result.get('snippet', 'No description available')
                results.append(
                    f"   {snippet[:200]}{'...' if len(snippet) > 200 else ''}"
                )
                results.append(f"   🔗 {result.get('link', 'No link')}")
                results.append("")

            results.append("✨ Powered by Google Custom Search API!")

            self.results_text.setText("\n".join(results))

        except Exception as e:
            self.results_text.setText(f"❌ Error researching topic: {str(e)}")
            print(f"Topic research error: {e}")
            import traceback
            traceback.print_exc()

    def search_news(self, query: str):
        """Search for news articles"""
        try:
            import requests

            self.results_text.setText(
                f"📰 Searching news for: {query}...\n\nThis may take a moment..."
            )

            news_api_key = os.environ.get("NEWS_API_KEY")
            if not news_api_key or news_api_key == "Not set":
                self.results_text.setText(
                    "❌ News API key not configured. Please add NEWS_API_KEY to your .env file."
                )
                return

            # News API endpoint
            url = "https://newsapi.org/v2/everything"

            # Parameters for news search
            params = {
                "apiKey": news_api_key,
                "q": query,
                "pageSize": 10,
                "language": "en",
                "sortBy": "relevancy",
            }

            # Make the request
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                articles = data.get("articles", [])

                if articles:
                    results = [f"📰 News Search Results\n"]
                    results.append(
                        f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    results.append(f"🔍 Query: {query}")
                    results.append(f"📊 Found {len(articles)} articles")
                    results.append("─" * 50 + "\n")

                    for i, article in enumerate(articles[:5], 1):
                        title = article.get("title", "No title")
                        source = article.get("source", {}).get("name", "Unknown source")
                        description = article.get(
                            "description", "No description available"
                        )
                        url = article.get("url", "#")
                        published_at = article.get("publishedAt", "Unknown date")

                        # Format the date
                        try:
                            date_obj = datetime.fromisoformat(
                                published_at.replace("Z", "+00:00")
                            )
                            formatted_date = date_obj.strftime("%Y-%m-%d %H:%M")
                        except:
                            formatted_date = published_at

                        results.append(f"{i}. {title}")
                        results.append(f"   📰 Source: {source}")
                        results.append(f"   📅 Published: {formatted_date}")
                        results.append(
                            f"   📝 {description[:150]}{'...' if len(description) > 150 else ''}"
                        )
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
            print(f"News search error: {e}")

    def search_social_media(self, query: str):
        """Search for social media content"""
        try:
            # Import social media scraper with robust error handling
            scraper = None
            
            # Try multiple import paths
            try:
                from social_media_scraper import SocialMediaScraper
                scraper = SocialMediaScraper()
            except ImportError:
                try:
                    # Try with backend path
                    sys.path.insert(0, backend_dir)
                    from social_media_scraper import SocialMediaScraper
                    scraper = SocialMediaScraper()
                except ImportError:
                    try:
                        # Try with relative path
                        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
                        from social_media_scraper import SocialMediaScraper
                        scraper = SocialMediaScraper()
                    except ImportError as e:
                        self.results_text.setText(f"❌ Error: Could not import SocialMediaScraper module. Please check backend installation. Error: {e}")
                        return
            
            if scraper is None:
                self.results_text.setText("❌ Error: Could not import SocialMediaScraper module. Please check backend installation.")
                return

            self.results_text.setText(
                f"🐦 Searching social media for: {query}...\n\nThis may take a moment..."
            )

            if not scraper.is_available():
                self.results_text.setText(
                    "❌ snscrape not available. Please install with: pip install snscrape"
                )
                return

            # Get social media content from both Twitter and Reddit
            twitter_results = scraper.search_social_media(
                query, platform="twitter", limit=5
            )
            reddit_results = scraper.search_social_media(
                query, platform="reddit", limit=5
            )

            # Format results
            results = [f"🐦 Social Media Search Results\n"]
            results.append(
                f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            results.append(f"🔍 Query: {query}")
            results.append("─" * 50 + "\n")

            # Twitter results
            if "error" not in twitter_results and twitter_results.get("tweets"):
                results.append("🐦 Twitter Results:")
                for i, tweet in enumerate(twitter_results["tweets"][:3], 1):
                    results.append(
                        f"  {i}. @{tweet.get('username', 'unknown')}: {tweet.get('content', '')[:150]}{'...' if len(tweet.get('content', '')) > 150 else ''}"
                    )
                    results.append(f"     ❤️ {tweet.get('likes', 0)} likes | 🔗 {tweet.get('url', 'N/A')}")
                results.append("")
            elif "error" in twitter_results:
                results.append(
                    "🐦 Twitter Results: Error - " + twitter_results["error"]
                )
                results.append("")

            # Reddit results
            if "error" not in reddit_results and reddit_results.get("posts"):
                results.append("🤖 Reddit Results:")
                for i, post in enumerate(reddit_results["posts"][:3], 1):
                    results.append(f"  {i}. {post.get('title', 'N/A')}")
                    results.append(
                        f"     👤 u/{post.get('author', 'unknown')} | ⬆️ {post.get('upvotes', 0)} upvotes"
                    )
                    results.append(f"     🔗 {post.get('url', 'N/A')}")
                results.append("")
            elif "error" in reddit_results:
                results.append("🤖 Reddit Results: Error - " + reddit_results["error"])
                results.append("")

            # If both failed, try mock data
            if "error" in twitter_results and "error" in reddit_results:
                self.results_text.setText(
                    "⚠️ Real-time social media search failed. Showing sample data..."
                )
                mock_data = scraper.get_mock_trends()

                results = [f"🐦 Social Media Search Results (Sample Data)\n"]
                results.append(
                    f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                results.append(f"🔍 Query: {query}")
                results.append("─" * 50 + "\n")

                if mock_data.get("twitter"):
                    results.append("🐦 Twitter Results:")
                    for i, tweet in enumerate(mock_data["twitter"][:3], 1):
                        results.append(
                            f"  {i}. @{tweet.get('username', 'unknown')}: {tweet.get('content', 'N/A')}"
                        )
                        results.append(
                            f"     ❤️ {tweet.get('likes', 0)} likes | 🔗 {tweet.get('url', 'N/A')}"
                        )
                    results.append("")

                if mock_data.get("reddit"):
                    results.append("🤖 Reddit Results:")
                    for i, post in enumerate(mock_data["reddit"][:3], 1):
                        results.append(f"  {i}. {post.get('title', 'N/A')}")
                        results.append(
                            f"     👤 u/{post.get('author', 'unknown')} | ⬆️ {post.get('upvotes', 0)} upvotes"
                        )
                        results.append(f"     🔗 {post.get('url', 'N/A')}")
                    results.append("")

            results.append("✨ Powered by snscrape - No API keys required!")

            self.results_text.setText("\n".join(results))

        except Exception as e:
            self.results_text.setText(f"❌ Error searching social media: {str(e)}")
            print(f"Social media search error: {e}")
            import traceback
            traceback.print_exc()

    def search_business(self, company_name: str, search_type: str = "all"):
        """Search for business and company information"""
        try:
            # Import guest research with robust error handling
            guest_research = None
            
            # Try multiple import paths
            try:
                from guest_research import GuestResearch
                guest_research = GuestResearch()
            except ImportError:
                try:
                    # Try with backend path
                    sys.path.insert(0, backend_dir)
                    from guest_research import GuestResearch
                    guest_research = GuestResearch()
                except ImportError:
                    try:
                        # Try with relative path
                        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
                        from guest_research import GuestResearch
                        guest_research = GuestResearch()
                    except ImportError as e:
                        self.results_text.setText(f"❌ Error: Could not import GuestResearch module. Please check backend installation. Error: {e}")
                        return
            
            if guest_research is None:
                self.results_text.setText("❌ Error: Could not import GuestResearch module. Please check backend installation.")
                return

            self.results_text.setText(
                f"🔍 Searching for business information: {company_name}...\n\nThis may take a moment..."
            )

            # Perform business search
            search_results = guest_research.search_business(company_name, search_type)

            if "error" in search_results:
                self.results_text.setText(
                    f"❌ Business search error: {search_results['error']}"
                )
                return

            # Format results
            results = [f"🏢 Business Search Results\n"]
            results.append(
                f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            results.append(f"🏢 Company: {company_name}")
            results.append(f"🔍 Search Type: {search_type.title()}")
            results.append("─" * 50 + "\n")

            # Summary
            if search_results.get("summary"):
                results.append("📋 Business Summary:")
                results.append(search_results["summary"])
                results.append("")

            # Company Information
            if search_results.get("company_info", {}).get("web_results"):
                results.append("🏢 Company Information:")
                for i, result in enumerate(search_results["company_info"]["web_results"][:5], 1):
                    results.append(f"  {i}. {result.get('title', 'N/A')}")
                    results.append(f"     {result.get('snippet', 'N/A')}")
                    results.append(f"     🔗 {result.get('link', 'N/A')}")
                    results.append("")
                results.append("")

            # LinkedIn Profiles
            if search_results.get("linkedin_profiles"):
                results.append("💼 LinkedIn Profiles:")
                for i, profile in enumerate(search_results["linkedin_profiles"][:5], 1):
                    results.append(f"  {i}. {profile.get('title', 'N/A')}")
                    results.append(f"     {profile.get('snippet', 'N/A')}")
                    results.append(f"     🔗 {profile.get('link', 'N/A')}")
                    results.append("")
                results.append("")

            # News
            if search_results.get("news"):
                results.append("📰 Recent News:")
                for i, news in enumerate(search_results["news"][:5], 1):
                    results.append(f"  {i}. {news.get('title', 'N/A')}")
                    results.append(f"     {news.get('snippet', 'N/A')}")
                    results.append(f"     🔗 {news.get('link', 'N/A')}")
                    results.append("")
                results.append("")

            # Executive Information
            if search_results.get("results"):
                executive_results = [r for r in search_results["results"] if r.get("type") == "executive_info"]
                if executive_results:
                    results.append("👔 Executive Information:")
                    for i, exec_info in enumerate(executive_results[:5], 1):
                        results.append(f"  {i}. {exec_info.get('title', 'N/A')}")
                        results.append(f"     {exec_info.get('snippet', 'N/A')}")
                        results.append(f"     🔗 {exec_info.get('link', 'N/A')}")
                        results.append("")
                    results.append("")

            # If no specific results found, show general results
            if not any([search_results.get("summary"), 
                       search_results.get("company_info", {}).get("web_results"),
                       search_results.get("linkedin_profiles"),
                       search_results.get("news"),
                       search_results.get("results")]):
                results.append("📊 General Search Results:")
                for i, result in enumerate(search_results.get("results", [])[:5], 1):
                    results.append(f"  {i}. {result.get('title', 'N/A')}")
                    results.append(f"     {result.get('snippet', 'N/A')}")
                    results.append(f"     🔗 {result.get('link', 'N/A')}")
                    results.append("")
                results.append("")

            results.append("✨ Powered by AI-powered business research!")

            self.results_text.setText("\n".join(results))

        except Exception as e:
            self.results_text.setText(f"❌ Error searching business: {str(e)}")
            print(f"Business search error: {e}")
            import traceback
            traceback.print_exc()

    def get_api_keys(self) -> Dict[str, str]:
        """Get all relevant API keys from environment variables"""
        return {
            "OpenAI API Key": "✅ Configured" if os.environ.get("OPENAI_API_KEY") else "❌ Not set",
            "News API Key": "✅ Configured" if os.environ.get("NEWS_API_KEY") else "❌ Not set",
            "Twitter API Key": "✅ Configured" if os.environ.get("TWITTER_API_KEY") else "❌ Not set",
            "Google API Key": "✅ Configured" if os.environ.get("GOOGLE_API_KEY") else "❌ Not set",
            "Google CSE ID": "✅ Configured" if os.environ.get("GOOGLE_CSE_ID") else "❌ Not set",
            "YouTube API Key": "✅ Configured" if os.environ.get("YOUTUBE_API_KEY") else "❌ Not set",
            "PODCHASER_API_KEY": "✅ Configured" if os.environ.get("PODCHASER_API_KEY") else "❌ Not set",
            "LISTEN_NOTES_API_KEY": "✅ Configured" if os.environ.get("LISTEN_NOTES_API_KEY") else "❌ Not set",
            "APPLE_PODCASTS_API_KEY": "✅ Configured" if os.environ.get("APPLE_PODCASTS_API_KEY") else "❌ Not set",
            "GOOGLE_PODCASTS_API_KEY": "✅ Configured" if os.environ.get("GOOGLE_PODCASTS_API_KEY") else "❌ Not set",
        }

    def get_latest_news(self):
        """Get latest news using News API"""
        news_api_key = os.environ.get("NEWS_API_KEY")
        if not news_api_key or news_api_key == "Not set":
            self.results_text.setText(
                "❌ News API key not configured. Please add NEWS_API_KEY to your .env file."
            )
            return

        try:
            import requests

            self.results_text.setText(
                "📰 Fetching latest news...\n\nThis may take a moment..."
            )

            # News API endpoint
            url = "https://newsapi.org/v2/top-headlines"

            # Parameters for podcast and technology related news
            params = {
                "apiKey": news_api_key,
                "country": "us",
                "category": "technology",
                "pageSize": 10,
                "language": "en",
            }

            # Make the request
            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                articles = data.get("articles", [])

                if articles:
                    results = ["📰 Latest News (News API)\n"]
                    results.append(
                        f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                    )
                    results.append(f"📊 Total Articles: {len(articles)}\n")
                    results.append("─" * 50 + "\n")

                    for i, article in enumerate(articles[:5], 1):
                        title = article.get("title", "No title")
                        source = article.get("source", {}).get("name", "Unknown source")
                        description = article.get(
                            "description", "No description available"
                        )
                        url = article.get("url", "#")
                        published_at = article.get("publishedAt", "Unknown date")

                        # Format the date
                        try:
                            date_obj = datetime.fromisoformat(
                                published_at.replace("Z", "+00:00")
                            )
                            formatted_date = date_obj.strftime("%Y-%m-%d %H:%M")
                        except:
                            formatted_date = published_at

                        results.append(f"{i}. {title}")
                        results.append(f"   📰 Source: {source}")
                        results.append(f"   📅 Published: {formatted_date}")
                        results.append(
                            f"   📝 {description[:150]}{'...' if len(description) > 150 else ''}"
                        )
                        results.append(f"   🔗 {url}")
                        results.append("")

                    results.append("✨ Powered by News API")

                    self.results_text.setText("\n".join(results))
                else:
                    self.results_text.setText(
                        "📰 No news articles found. Try again later."
                    )
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
            self.results_text.setText(
                "❌ News API request timed out. Please try again."
            )
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
                self.results_text.setText(
                    "❌ snscrape not available. Please install with: pip install snscrape"
                )
                return

            self.results_text.setText(
                "🐦 Fetching social media trends with snscrape...\n\nThis may take a moment..."
            )

            # Get trending topics from multiple platforms
            trends = scraper.get_trending_topics()

            if "error" in trends:
                # If real scraping fails, use mock data
                self.results_text.setText(
                    "⚠️ Real-time scraping failed. Showing sample data..."
                )
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
                    results.append(
                        f"     👤 u/{post['author']} | ⬆️ {post['upvotes']} upvotes"
                    )
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
                self.results_text.setText(
                    "❌ snscrape not available. Please install with: pip install snscrape"
                )
                return

            self.results_text.setText(
                "🐦 Fetching Twitter trends with snscrape...\n\nThis may take a moment..."
            )

            # Get Twitter trends
            twitter_trends = scraper.get_twitter_trends("podcast", limit=8)

            if "error" in twitter_trends:
                # If real scraping fails, use mock data
                self.results_text.setText(
                    "⚠️ Real-time Twitter scraping failed. Showing sample data..."
                )
                mock_data = scraper.get_mock_trends()
                twitter_trends = {
                    "platform": "twitter",
                    "query": "podcast",
                    "count": len(mock_data.get("twitter", [])),
                    "tweets": mock_data.get("twitter", []),
                    "timestamp": mock_data.get("timestamp", datetime.now().isoformat()),
                }

            # Format results
            results = ["🐦 Twitter Trends (snscrape)\n"]
            results.append(f"📅 Timestamp: {twitter_trends.get('timestamp', 'N/A')}")
            results.append(f"🔍 Query: {twitter_trends.get('query', 'podcast')}")
            results.append(f"📊 Found {twitter_trends.get('count', 0)} tweets\n")

            for i, tweet in enumerate(twitter_trends.get("tweets", [])[:5], 1):
                results.append(f"{i}. @{tweet['username']}:")
                results.append(
                    f"   {tweet['content'][:150]}{'...' if len(tweet['content']) > 150 else ''}"
                )
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
                self.results_text.setText(
                    "❌ snscrape not available. Please install with: pip install snscrape"
                )
                return

            self.results_text.setText(
                "🤖 Fetching Reddit trends with snscrape...\n\nThis may take a moment..."
            )

            # Get Reddit trends
            reddit_trends = scraper.get_reddit_trends("podcasts", limit=8)

            if "error" in reddit_trends:
                # If real scraping fails, use mock data
                self.results_text.setText(
                    "⚠️ Real-time Reddit scraping failed. Showing sample data..."
                )
                mock_data = scraper.get_mock_trends()
                reddit_trends = {
                    "platform": "reddit",
                    "subreddit": "podcasts",
                    "count": len(mock_data.get("reddit", [])),
                    "posts": mock_data.get("reddit", []),
                    "timestamp": mock_data.get("timestamp", datetime.now().isoformat()),
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
                self.results_text.setText(
                    "❌ Google API not configured. Please add GOOGLE_API_KEY and GOOGLE_CSE_ID to your .env file."
                )
                return

            # For now, use a sample query - in a real implementation, you'd get this from user input
            query = "podcast trends 2024"

            self.results_text.setText(
                "🔍 Researching topic with Google API...\n\nThis may take a moment..."
            )

            # Search for podcast-related content
            search_results = google_apis.search_podcast_content(query, num_results=5)

            if "error" in search_results:
                # If real search fails, use mock data
                self.results_text.setText(
                    "⚠️ Real-time search failed. Showing sample data..."
                )
                search_results = google_apis.get_mock_search_results(query)

            # Format results
            results = ["🔍 Topic Research (Google API)\n"]
            results.append(f"📅 Timestamp: {search_results.get('timestamp', 'N/A')}")
            results.append(f"🔍 Query: {search_results.get('query', query)}")
            results.append(
                f"📊 Found {search_results.get('total_results', 0)} results\n"
            )

            for i, result in enumerate(search_results.get("results", [])[:3], 1):
                results.append(f"{i}. {result['title']}")
                results.append(
                    f"   {result['snippet'][:150]}{'...' if len(result['snippet']) > 150 else ''}"
                )
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
                self.results_text.setText(
                    "❌ YouTube API not configured. Please add YOUTUBE_API_KEY to your .env file."
                )
                return

            self.results_text.setText(
                "📺 Fetching YouTube trends with YouTube API...\n\nThis may take a moment..."
            )

            # Get YouTube trends
            youtube_trends = google_apis.get_youtube_trends("US", max_results=5)

            if "error" in youtube_trends:
                # If real trends fail, use mock data
                self.results_text.setText(
                    "⚠️ Real-time YouTube trends failed. Showing sample data..."
                )
                youtube_trends = google_apis.get_mock_youtube_results("podcast")

            # Format results
            results = ["📺 YouTube Trends (YouTube API)\n"]
            results.append(f"📅 Timestamp: {youtube_trends.get('timestamp', 'N/A')}")
            results.append(f"🌍 Region: {youtube_trends.get('region', 'US')}")
            results.append(
                f"📊 Found {youtube_trends.get('total_results', 0)} videos\n"
            )

            for i, video in enumerate(youtube_trends.get("videos", [])[:3], 1):
                results.append(f"{i}. {video['title']}")
                results.append(f"   📺 {video['channel_title']}")
                results.append(
                    f"   👁️ {video['view_count']} views | ❤️ {video['like_count']} likes"
                )
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
                self.results_text.setText(
                    "❌ No podcast APIs configured. Please add one of the following to your .env file:\n\n• PODCHASER_API_KEY - For podcast database and analytics\n• LISTEN_NOTES_API_KEY - For podcast search and discovery\n• APPLE_PODCASTS_API_KEY - For Apple Podcasts integration\n• GOOGLE_PODCASTS_API_KEY - For Google Podcasts integration"
                )
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
                            trending_results.append(
                                f"📊 {api.replace('_', ' ').title()} Trending:"
                            )
                            if api == "podchaser":
                                for edge in result.get("trending", [])[:5]:
                                    podcast = edge.get("node", {})
                                    trending_results.append(
                                        f"  • {podcast.get('title', 'N/A')} (Rating: {podcast.get('rating', 'N/A')})"
                                    )
                            elif api == "listen_notes":
                                for podcast in result.get("trending", [])[:5]:
                                    trending_results.append(
                                        f"  • {podcast.get('title', 'N/A')} (Score: {podcast.get('listen_score', 'N/A')})"
                                    )
                    except Exception as e:
                        trending_results.append(f"  ❌ {api} error: {str(e)}")

            if trending_results:
                self.results_text.setText(
                    "🎙️ Podcast Search Results\n\n"
                    + "\n".join(trending_results)
                    + "\n\nThis feature provides:\n• Podcast discovery and search\n• Trending podcasts\n• Podcast analytics\n• Episode information\n• Category browsing\n\nNote: This replaces Spotify's limited podcast functionality with dedicated podcast APIs."
                )
            else:
                self.results_text.setText(
                    "❌ No podcast search results available. Please check your API configurations."
                )

        except Exception as e:
            self.results_text.setText(f"❌ Error in podcast search: {str(e)}")
