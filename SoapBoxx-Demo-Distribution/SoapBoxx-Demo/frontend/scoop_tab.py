#!/usr/bin/env python3
"""
Scoop Tab - Demo Version
========================

This is a demo version that shows what the real Scoop tab looks like
without requiring complex backend dependencies.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QComboBox, QLineEdit,
                             QGroupBox, QGridLayout, QScrollArea, QFrame)

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

class ScoopTab(QWidget):
    """Demo version of the Scoop tab with realistic UI"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
        # Demo timer for fake updates
        self.demo_timer = QTimer()
        self.demo_timer.timeout.connect(self.update_demo_status)
        self.demo_timer.start(3000)  # Update every 3 seconds
    
    def setup_ui(self):
        """Set up the tab UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Header
        header = QLabel("🔍 Scoop - Content Discovery & Research")
        header.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2C3E50;
                padding: 20px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #E8F4FD, stop:1 #B3D9F2);
                border-radius: 12px;
                margin: 10px;
            }
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Search section
        search_card = ModernCard()
        search_layout = QVBoxLayout()
        search_card.setLayout(search_layout)
        
        search_group = QGroupBox("🔎 Content Search")
        search_group_layout = QGridLayout()
        
        # Search input
        search_group_layout.addWidget(QLabel("Search for:"), 0, 0)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter keywords, topics, or questions...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border: 2px solid #BDC3C7;
                border-radius: 8px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #3498DB;
            }
        """)
        search_group_layout.addWidget(self.search_input, 0, 1)
        
        # Search button
        self.search_button = ModernButton("🔍 Search", style="primary")
        self.search_button.clicked.connect(self.perform_search)
        search_group_layout.addWidget(self.search_button, 0, 2)
        
        # Search filters
        search_group_layout.addWidget(QLabel("Content Type:"), 1, 0)
        self.content_type_combo = QComboBox()
        self.content_type_combo.addItems(["All", "Articles", "Videos", "Podcasts", "Social Media"])
        search_group_layout.addWidget(self.content_type_combo, 1, 1)
        
        # Date range
        search_group_layout.addWidget(QLabel("Date Range:"), 2, 0)
        self.date_range_combo = QComboBox()
        self.date_range_combo.addItems(["Any time", "Past 24 hours", "Past week", "Past month", "Past year"])
        search_group_layout.addWidget(self.date_range_combo, 2, 1)
        
        search_group.setLayout(search_group_layout)
        search_layout.addWidget(search_group)
        
        layout.addWidget(search_card)
        
        # Results section
        results_card = ModernCard()
        results_layout = QVBoxLayout()
        results_card.setLayout(results_layout)
        
        results_header = QLabel("📊 Search Results")
        results_header.setStyleSheet("font-size: 18px; font-weight: bold; color: #2C3E50;")
        results_layout.addWidget(results_header)
        
        # Demo results
        self.results_area = QScrollArea()
        self.results_area.setWidgetResizable(True)
        self.results_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #BDC3C7;
                border-radius: 8px;
                background-color: #F8F9FA;
            }
        """)
        
        results_widget = QWidget()
        results_widget_layout = QVBoxLayout()
        
        # Demo result items
        demo_results = [
            ("📰 AI in Podcasting: The Future is Here", "TechCrunch", "2 hours ago", "95% relevance"),
            ("🎙️ How to Start a Successful Podcast", "Medium", "1 day ago", "87% relevance"),
            ("📱 Social Media Trends for Content Creators", "Forbes", "3 days ago", "82% relevance"),
            ("🎬 Video Content Strategy for 2024", "YouTube Creator Blog", "1 week ago", "78% relevance"),
            ("🔊 Audio Quality Tips for Podcasters", "Sound Engineering Weekly", "2 weeks ago", "75% relevance")
        ]
        
        for title, source, time, relevance in demo_results:
            result_item = self.create_result_item(title, source, time, relevance)
            results_widget_layout.addWidget(result_item)
        
        results_widget.setLayout(results_widget_layout)
        self.results_area.setWidget(results_widget)
        results_layout.addWidget(self.results_area)
        
        layout.addWidget(results_card)
        
        # Trending topics
        trending_card = ModernCard()
        trending_layout = QVBoxLayout()
        trending_card.setLayout(trending_layout)
        
        trending_header = QLabel("🔥 Trending Topics")
        trending_header.setStyleSheet("font-size: 18px; font-weight: bold; color: #2C3E50;")
        trending_layout.addWidget(trending_header)
        
        trending_topics = ["AI Content Creation", "Podcast Monetization", "Social Media Marketing", 
                          "Video Production", "Audio Engineering", "Content Strategy"]
        
        topics_layout = QHBoxLayout()
        for topic in trending_topics:
            topic_button = ModernButton(topic, style="secondary")
            topic_button.setMaximumWidth(150)
            topics_layout.addWidget(topic_button)
        
        trending_layout.addLayout(topics_layout)
        layout.addWidget(trending_card)
        
        # Demo info
        demo_info = QLabel("🎭 This is a demo version. The real Scoop includes:\n"
                          "• AI-powered content discovery\n"
                          "• Real-time trend analysis\n"
                          "• Content relevance scoring\n"
                          "• Multi-platform search integration")
        demo_info.setStyleSheet("""
            QLabel {
                color: #7F8C8D;
                font-style: italic;
                padding: 15px;
                background-color: #F8F9FA;
                border: 1px solid #E9ECEF;
                border-radius: 8px;
                margin: 10px;
            }
        """)
        demo_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(demo_info)
        
        # Status bar
        self.status_bar = QLabel("🔍 Scoop Demo - Discover trending content and insights!")
        self.status_bar.setStyleSheet("""
            QLabel {
                color: #2C3E50;
                font-weight: bold;
                padding: 10px;
                background-color: #E8F4FD;
                border: 1px solid #B3D9F2;
                border-radius: 6px;
                margin: 10px;
            }
        """)
        self.status_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_bar)
    
    def create_result_item(self, title, source, time, relevance):
        """Create a demo result item"""
        item = QFrame()
        item.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E9ECEF;
                border-radius: 8px;
                padding: 12px;
                margin: 5px;
            }
            QFrame:hover {
                border: 1px solid #3498DB;
                background-color: #F8F9FA;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: bold; color: #2C3E50; font-size: 14px;")
        layout.addWidget(title_label)
        
        # Meta info
        meta_layout = QHBoxLayout()
        meta_layout.addWidget(QLabel(f"📰 {source}"))
        meta_layout.addWidget(QLabel(f"⏰ {time}"))
        meta_layout.addWidget(QLabel(f"🎯 {relevance}"))
        meta_layout.addStretch()
        
        # Action buttons
        meta_layout.addWidget(ModernButton("📖 Read", style="secondary"))
        meta_layout.addWidget(ModernButton("💾 Save", style="secondary"))
        
        layout.addLayout(meta_layout)
        item.setLayout(layout)
        
        return item
    
    def perform_search(self):
        """Perform demo search"""
        query = self.search_input.text() or "podcast content"
        self.status_bar.setText(f"🔍 Searching for: {query}...")
        
        # Simulate search delay
        QTimer.singleShot(1500, lambda: self.status_bar.setText(f"✅ Found 5 results for: {query}"))
    
    def update_demo_status(self):
        """Update demo status periodically"""
        import random
        
        statuses = [
            "🔍 Scoop Demo - Discover trending content and insights!",
            "📊 Analyzing content trends...",
            "🔥 New trending topics detected!",
            "📈 Content relevance scores updated"
        ]
        
        self.status_bar.setText(random.choice(statuses))
