# frontend/reverb_tab.py
"""
Reverb Tab - Podcast Feedback and Coaching Tools
Provides AI-powered feedback and coaching for podcast creators
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Add backend to path - handle separate frontend/backend folder structure
current_dir = os.path.dirname(os.path.abspath(__file__))  # frontend/
parent_dir = os.path.dirname(current_dir)  # root/
backend_dir = os.path.join(parent_dir, "backend")  # root/backend/
sys.path.insert(0, backend_dir)

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (QButtonGroup, QComboBox, QFileDialog, QGridLayout,
                             QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                             QListWidget, QListWidgetItem, QMessageBox,
                             QProgressBar, QPushButton, QTextEdit, QVBoxLayout,
                             QWidget)


class EpisodeAnalysisThread(QThread):
    """Thread for analyzing uploaded episodes"""

    analysis_complete = pyqtSignal(dict)
    progress_updated = pyqtSignal(int)
    error_occurred = pyqtSignal(str)

    def __init__(self, file_path: str, analysis_type: str):
        super().__init__()
        self.file_path = file_path
        self.analysis_type = analysis_type

    def run(self):
        """Run episode analysis"""
        try:
            self.progress_updated.emit(10)

            # Import analysis modules with robust error handling
            feedback_engine = None
            transcriber = None
            
            # Try multiple import paths
            try:
                from feedback_engine import FeedbackEngine
                from transcriber import Transcriber
                feedback_engine = FeedbackEngine()
                transcriber = Transcriber(service="openai")
            except ImportError:
                try:
                    # Try with backend path
                    sys.path.insert(0, backend_dir)
                    from feedback_engine import FeedbackEngine
                    from transcriber import Transcriber
                    feedback_engine = FeedbackEngine()
                    transcriber = Transcriber(service="openai")
                except ImportError:
                    try:
                        # Try with relative path
                        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
                        from feedback_engine import FeedbackEngine
                        from transcriber import Transcriber
                        feedback_engine = FeedbackEngine()
                        transcriber = Transcriber(service="openai")
                    except ImportError as e:
                        self.error_occurred.emit(f"Failed to import backend modules: {e}")
                        return

            if feedback_engine is None or transcriber is None:
                self.error_occurred.emit("Failed to initialize backend modules")
                return

            self.progress_updated.emit(20)

            # Transcribe audio
            with open(self.file_path, "rb") as f:
                audio_data = f.read()

            self.progress_updated.emit(40)

            transcript = transcriber.transcribe(audio_data)
            if not transcript or transcript.startswith("Error"):
                self.error_occurred.emit(f"Transcription failed: {transcript}")
                return

            self.progress_updated.emit(60)

            # Analyze content
            analysis = feedback_engine.analyze(transcript=transcript)

            self.progress_updated.emit(80)

            # Prepare results
            results = {
                "file_path": self.file_path,
                "file_name": os.path.basename(self.file_path),
                "transcript": transcript,
                "analysis": analysis,
                "analysis_type": self.analysis_type,
                "word_count": len(transcript.split()),
                "duration_estimate": len(transcript.split())
                / 150,  # Rough estimate: 150 words per minute
            }

            self.progress_updated.emit(100)
            self.analysis_complete.emit(results)

        except Exception as e:
            self.error_occurred.emit(f"Analysis failed: {str(e)}")
            import traceback
            traceback.print_exc()


class ReverbTab(QWidget):
    """Reverb tab for podcast feedback and coaching tools"""

    def __init__(self):
        super().__init__()
        self.uploaded_episodes = []
        self.analysis_thread = None
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout()

        # Title
        title = QLabel("🎙️ Reverb - Podcast Feedback & Coaching")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)

        # Description
        description = QLabel(
            "AI-powered feedback and coaching tools to help you create better podcasts"
        )
        description.setStyleSheet("color: #666; margin: 5px;")
        layout.addWidget(description)

        # Past Episodes Upload Section
        upload_group = QGroupBox("📁 Past Episodes Upload")
        upload_layout = QVBoxLayout()

        # File selection
        file_layout = QHBoxLayout()
        self.file_path_label = QLabel("No file selected")
        self.file_path_label.setStyleSheet(
            "color: #666; padding: 5px; border: 1px solid #ccc; border-radius: 3px;"
        )

        select_file_btn = QPushButton("📁 Select Episode File")
        select_file_btn.clicked.connect(self.select_episode_file)
        file_layout.addWidget(select_file_btn)
        file_layout.addWidget(self.file_path_label, 1)

        upload_layout.addLayout(file_layout)

        # Analysis type selection
        analysis_layout = QHBoxLayout()
        analysis_label = QLabel("Analysis Type:")
        self.analysis_combo = QComboBox()
        self.analysis_combo.addItems(
            [
                "Content Analysis",
                "Performance Coaching",
                "Engagement Analysis",
                "Storytelling Feedback",
                "Guest Interview Coaching",
            ]
        )
        analysis_layout.addWidget(analysis_label)
        analysis_layout.addWidget(self.analysis_combo)
        analysis_layout.addStretch()

        upload_layout.addLayout(analysis_layout)

        # Upload and analyze button
        self.analyze_btn = QPushButton("🔍 Analyze Episode")
        self.analyze_btn.clicked.connect(self.analyze_episode)
        self.analyze_btn.setEnabled(False)
        upload_layout.addWidget(self.analyze_btn)

        # Progress bar
        self.analysis_progress = QProgressBar()
        self.analysis_progress.setVisible(False)
        upload_layout.addWidget(self.analysis_progress)

        # Uploaded episodes list
        episodes_label = QLabel("📋 Uploaded Episodes:")
        upload_layout.addWidget(episodes_label)

        self.episodes_list = QListWidget()
        self.episodes_list.setMaximumHeight(150)
        self.episodes_list.itemClicked.connect(self.on_episode_selected)
        upload_layout.addWidget(self.episodes_list)

        upload_group.setLayout(upload_layout)
        layout.addWidget(upload_group)

        # API Status
        api_status_group = QGroupBox("🔑 API Key Status")
        api_status_layout = QGridLayout()

        api_keys = {
            "OpenAI API Key": os.environ.get("OPENAI_API_KEY", "Not set"),
            "YouTube API Key": os.environ.get("YOUTUBE_API_KEY", "Not set"),
            "AssemblyAI API Key": os.environ.get("ASSEMBLYAI_API_KEY", "Not set"),
            "ElevenLabs API Key": os.environ.get("ELEVENLABS_API_KEY", "Not set"),
            "Azure Speech Key": os.environ.get("AZURE_SPEECH_KEY", "Not set"),
            "Spotify Client ID": os.environ.get("SPOTIFY_CLIENT_ID", "Not set"),
            "PODCHASER_API_KEY": os.environ.get("PODCHASER_API_KEY", "Not set"),
            "LISTEN_NOTES_API_KEY": os.environ.get("LISTEN_NOTES_API_KEY", "Not set"),
            "APPLE_PODCASTS_API_KEY": os.environ.get(
                "APPLE_PODCASTS_API_KEY", "Not set"
            ),
            "GOOGLE_PODCASTS_API_KEY": os.environ.get(
                "GOOGLE_PODCASTS_API_KEY", "Not set"
            ),
        }

        row = 0
        for key_name, value in api_keys.items():
            status = "✅ Configured" if value and value != "Not set" else "❌ Not set"
            status_label = QLabel(f"{key_name}: {status}")
            api_status_layout.addWidget(status_label, row, 0)
            row += 1

        api_status_group.setLayout(api_status_layout)
        layout.addWidget(api_status_group)

        # Feedback Tools
        feedback_group = QGroupBox("🎯 Feedback & Coaching Tools")
        feedback_layout = QVBoxLayout()

        # Content Analysis
        content_btn = QPushButton("📊 Content Analysis")
        content_btn.clicked.connect(self.content_analysis)
        content_btn.setEnabled(
            api_keys.get("OpenAI API Key")
            and api_keys.get("OpenAI API Key") != "Not set"
        )
        feedback_layout.addWidget(content_btn)

        # Video Content Analysis (NEW - YouTube Integration)
        video_analysis_btn = QPushButton("🎥 Video Content Analysis")
        video_analysis_btn.clicked.connect(self.video_content_analysis)
        video_analysis_btn.setEnabled(
            api_keys.get("YouTube API Key")
            and api_keys.get("YouTube API Key") != "Not set"
        )
        feedback_layout.addWidget(video_analysis_btn)

        # Video Podcast Research (NEW - YouTube Integration)
        video_research_btn = QPushButton("🔍 Video Podcast Research")
        video_research_btn.clicked.connect(self.video_podcast_research)
        video_research_btn.setEnabled(
            api_keys.get("YouTube API Key")
            and api_keys.get("YouTube API Key") != "Not set"
        )
        feedback_layout.addWidget(video_research_btn)

        # Performance Coaching
        coaching_btn = QPushButton("🎓 Performance Coaching")
        coaching_btn.clicked.connect(self.performance_coaching)
        coaching_btn.setEnabled(
            api_keys.get("OpenAI API Key")
            and api_keys.get("OpenAI API Key") != "Not set"
        )
        feedback_layout.addWidget(coaching_btn)

        # Engagement Analysis
        engagement_btn = QPushButton("📈 Engagement Analysis")
        engagement_btn.clicked.connect(self.engagement_analysis)
        engagement_btn.setEnabled(
            api_keys.get("OpenAI API Key")
            and api_keys.get("OpenAI API Key") != "Not set"
        )
        feedback_layout.addWidget(engagement_btn)

        # Storytelling Feedback
        storytelling_btn = QPushButton("📖 Storytelling Feedback")
        storytelling_btn.clicked.connect(self.storytelling_feedback)
        storytelling_btn.setEnabled(
            api_keys.get("OpenAI API Key")
            and api_keys.get("OpenAI API Key") != "Not set"
        )
        feedback_layout.addWidget(storytelling_btn)

        feedback_group.setLayout(feedback_layout)
        layout.addWidget(feedback_group)

        # Results section
        results_group = QGroupBox("📊 Analysis Results")
        results_layout = QVBoxLayout()

        self.results_text = QTextEdit()
        self.results_text.setPlaceholderText(
            "Episode analysis results will appear here..."
        )
        self.results_text.setMaximumHeight(300)
        results_layout.addWidget(self.results_text)

        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        self.setLayout(layout)

    def select_episode_file(self):
        """Select an episode file for upload"""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self,
            "Select Episode File",
            "",
            "Audio Files (*.mp3 *.wav *.m4a *.flac *.ogg);;All Files (*.*)",
        )

        if file_path:
            self.file_path_label.setText(os.path.basename(file_path))
            self.file_path_label.setStyleSheet(
                "color: #333; padding: 5px; border: 1px solid #4CAF50; border-radius: 3px; background-color: #E8F5E8;"
            )
            self.analyze_btn.setEnabled(True)
            self.selected_file_path = file_path

    def analyze_episode(self):
        """Analyze the selected episode"""
        if not hasattr(self, "selected_file_path"):
            QMessageBox.warning(self, "Error", "Please select an episode file first.")
            return

        # Check file size
        file_size = os.path.getsize(self.selected_file_path) / (1024 * 1024)  # MB
        if file_size > 100:  # 100MB limit
            QMessageBox.warning(
                self,
                "File Too Large",
                f"File size ({file_size:.1f}MB) exceeds the 100MB limit. Please use a smaller file.",
            )
            return

        # Start analysis
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("🔍 Analyzing...")
        self.analysis_progress.setVisible(True)
        self.analysis_progress.setValue(0)

        # Create analysis thread
        analysis_type = self.analysis_combo.currentText()
        self.analysis_thread = EpisodeAnalysisThread(
            self.selected_file_path, analysis_type
        )
        self.analysis_thread.analysis_complete.connect(self.on_analysis_complete)
        self.analysis_thread.progress_updated.connect(self.analysis_progress.setValue)
        self.analysis_thread.error_occurred.connect(self.on_analysis_error)
        self.analysis_thread.start()

    def on_analysis_complete(self, results):
        """Handle analysis completion"""
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("🔍 Analyze Episode")
        self.analysis_progress.setVisible(False)

        # Add to episodes list
        episode_item = QListWidgetItem(
            f"📁 {results['file_name']} - {results['analysis_type']}"
        )
        episode_item.setData(1, results)  # Store results data
        self.episodes_list.addItem(episode_item)

        # Display results
        self.display_analysis_results(results)

        QMessageBox.information(
            self,
            "Analysis Complete",
            f"Episode analysis completed successfully!\n\n"
            f"File: {results['file_name']}\n"
            f"Analysis Type: {results['analysis_type']}\n"
            f"Word Count: {results['word_count']}\n"
            f"Estimated Duration: {results['duration_estimate']:.1f} minutes",
        )

    def on_analysis_error(self, error):
        """Handle analysis error"""
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("🔍 Analyze Episode")
        self.analysis_progress.setVisible(False)
        QMessageBox.critical(
            self, "Analysis Error", f"Episode analysis failed: {error}"
        )

    def on_episode_selected(self, item):
        """Handle episode selection from list"""
        results = item.data(1)
        if results:
            self.display_analysis_results(results)

    def display_analysis_results(self, results):
        """Display analysis results in the results text area"""
        try:
            # Format results
            output = f"📊 Episode Analysis Results\n"
            output += f"─" * 50 + "\n"
            output += f"📁 File: {results['file_name']}\n"
            output += f"🔍 Analysis Type: {results['analysis_type']}\n"
            output += f"📝 Word Count: {results['word_count']}\n"
            output += (
                f"⏱️ Estimated Duration: {results['duration_estimate']:.1f} minutes\n"
            )
            output += (
                f"📅 Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            )

            # Add transcript preview
            transcript_preview = (
                results["transcript"][:500] + "..."
                if len(results["transcript"]) > 500
                else results["transcript"]
            )
            output += f"📝 Transcript Preview:\n{transcript_preview}\n\n"

            # Add analysis results
            analysis = results["analysis"]
            if isinstance(analysis, dict):
                if "listener_feedback" in analysis:
                    output += (
                        f"🎯 Listener Feedback:\n{analysis['listener_feedback']}\n\n"
                    )

                if "coaching_suggestions" in analysis:
                    output += f"💡 Coaching Suggestions:\n"
                    for i, suggestion in enumerate(analysis["coaching_suggestions"], 1):
                        output += f"  {i}. {suggestion}\n"
                    output += "\n"

                if "benchmark" in analysis:
                    output += f"📊 Benchmark: {analysis['benchmark']}\n\n"

                if "confidence" in analysis:
                    output += f"🎯 Confidence Score: {analysis['confidence']:.2f}\n\n"
            else:
                output += f"📊 Analysis Results:\n{str(analysis)}\n\n"

            self.results_text.setText(output)

        except Exception as e:
            self.results_text.setText(f"Error displaying results: {str(e)}")

    def content_analysis(self):
        """Analyze podcast content for quality and engagement"""
        try:
            # Import backend components with robust error handling
            feedback_engine = None
            
            try:
                from feedback_engine import FeedbackEngine
                feedback_engine = FeedbackEngine()
            except ImportError:
                try:
                    # Try with backend path
                    sys.path.insert(0, backend_dir)
                    from feedback_engine import FeedbackEngine
                    feedback_engine = FeedbackEngine()
                except ImportError:
                    try:
                        # Try with relative path
                        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
                        from feedback_engine import FeedbackEngine
                        feedback_engine = FeedbackEngine()
                    except ImportError as e:
                        self.results_text.setText(f"❌ Error: Could not import FeedbackEngine module. Please check backend installation. Error: {e}")
                        return

            if feedback_engine is None:
                self.results_text.setText("❌ Error: Could not import FeedbackEngine module. Please check backend installation.")
                return

            # This would analyze the current transcript or uploaded content
            self.results_text.setText(
                "📊 Content Analysis\n\nThis feature analyzes your podcast content for:\n• Clarity and coherence\n• Engagement factors\n• Topic relevance\n• Audience appeal\n• Content structure\n\nUpload a transcript or use the recording from the SoapBoxx tab to get detailed feedback."
            )

        except Exception as e:
            self.results_text.setText(f"❌ Error in content analysis: {str(e)}")
            import traceback
            traceback.print_exc()

    def video_content_analysis(self):
        """Analyze video podcast content using YouTube API"""
        try:
            # Import YouTube API components with robust error handling
            google_apis = None
            
            try:
                from google_apis import GoogleAPIs
                google_apis = GoogleAPIs()
            except ImportError:
                try:
                    # Try with backend path
                    sys.path.insert(0, backend_dir)
                    from google_apis import GoogleAPIs
                    google_apis = GoogleAPIs()
                except ImportError:
                    try:
                        # Try with relative path
                        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
                        from google_apis import GoogleAPIs
                        google_apis = GoogleAPIs()
                    except ImportError as e:
                        self.results_text.setText(f"❌ Error: Could not import GoogleAPIs module. Please check backend installation. Error: {e}")
                        return

            if google_apis is None:
                self.results_text.setText("❌ Error: Could not import GoogleAPIs module. Please check backend installation.")
                return

            if not google_apis.is_available():
                self.results_text.setText(
                    "❌ YouTube API not configured. Please set YOUTUBE_API_KEY in your .env file"
                )
                return

            # Search for video podcast content for analysis
            self.results_text.setText(
                "🎥 Video Content Analysis\n\nSearching for video podcast content to analyze..."
            )

            # Get trending video podcasts
            trending_results = google_apis.get_youtube_trends("US", max_results=5)

            if "error" in trending_results:
                self.results_text.setText(
                    f"❌ Error fetching video content: {trending_results['error']}"
                )
                return

            analysis_results = ["🎥 Video Content Analysis\n"]
            analysis_results.append("📊 Trending Video Content Analysis:")
            analysis_results.append("=" * 50)

            for i, video in enumerate(trending_results.get("videos", [])[:3], 1):
                title = video.get("title", "Unknown")
                channel = video.get("channel_title", "Unknown")
                view_count = video.get("view_count", "N/A")
                description = (
                    video.get("description", "")[:100] + "..."
                    if len(video.get("description", "")) > 100
                    else video.get("description", "")
                )

                analysis_results.append(f"\n{i}. {title}")
                analysis_results.append(f"   Channel: {channel}")
                analysis_results.append(f"   Views: {view_count}")
                analysis_results.append(f"   Description: {description}")

                # Add analysis insights
                analysis_results.append(f"   📈 Analysis:")
                analysis_results.append(f"   • High engagement potential (trending)")
                analysis_results.append(f"   • Popular channel format")
                analysis_results.append(f"   • Strong audience appeal")

            analysis_results.append(f"\n🎯 Key Insights:")
            analysis_results.append(
                f"• Trending content shows current audience interests"
            )
            analysis_results.append(f"• Video format increases engagement potential")
            analysis_results.append(f"• Popular channels provide format examples")
            analysis_results.append(
                f"• High view counts indicate successful content strategies"
            )

            self.results_text.setText("\n".join(analysis_results))

        except Exception as e:
            self.results_text.setText(f"❌ Error in video content analysis: {str(e)}")
            import traceback
            traceback.print_exc()

    def video_podcast_research(self):
        """Research video podcast trends and content"""
        try:
            # Import YouTube API components with robust error handling
            google_apis = None
            
            try:
                from google_apis import GoogleAPIs
                google_apis = GoogleAPIs()
            except ImportError:
                try:
                    # Try with backend path
                    sys.path.insert(0, backend_dir)
                    from google_apis import GoogleAPIs
                    google_apis = GoogleAPIs()
                except ImportError:
                    try:
                        # Try with relative path
                        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
                        from google_apis import GoogleAPIs
                        google_apis = GoogleAPIs()
                    except ImportError as e:
                        self.results_text.setText(f"❌ Error: Could not import GoogleAPIs module. Please check backend installation. Error: {e}")
                        return

            if google_apis is None:
                self.results_text.setText("❌ Error: Could not import GoogleAPIs module. Please check backend installation.")
                return

            if not google_apis.is_available():
                self.results_text.setText(
                    "❌ YouTube API not configured. Please set YOUTUBE_API_KEY in your .env file"
                )
                return

            self.results_text.setText(
                "🔍 Video Podcast Research\n\nResearching video podcast trends and content..."
            )

            # Search for video podcast content
            search_results = google_apis.search_youtube_simple(
                "video podcast", max_results=5
            )

            if "error" in search_results:
                self.results_text.setText(
                    f"❌ Error searching video podcasts: {search_results['error']}"
                )
                return

            research_results = ["🔍 Video Podcast Research\n"]
            research_results.append("📊 Video Podcast Content Research:")
            research_results.append("=" * 50)

            for i, video in enumerate(search_results.get("videos", [])[:3], 1):
                title = video.get("title", "Unknown")
                channel = video.get("channel_title", "Unknown")
                description = (
                    video.get("description", "")[:150] + "..."
                    if len(video.get("description", "")) > 150
                    else video.get("description", "")
                )
                url = video.get("url", "")

                research_results.append(f"\n{i}. {title}")
                research_results.append(f"   Channel: {channel}")
                research_results.append(f"   Description: {description}")
                research_results.append(f"   URL: {url}")

                # Add research insights
                research_results.append(f"   🔍 Research Insights:")
                research_results.append(f"   • Content format analysis")
                research_results.append(f"   • Audience engagement patterns")
                research_results.append(f"   • Production quality indicators")

            research_results.append(f"\n🎯 Research Summary:")
            research_results.append(f"• Video podcasts are gaining popularity")
            research_results.append(f"• Visual content enhances audience engagement")
            research_results.append(
                f"• Multiple formats available (interviews, discussions, etc.)"
            )
            research_results.append(
                f"• High-quality production increases viewer retention"
            )
            research_results.append(f"• Regular uploads maintain audience interest")

            self.results_text.setText("\n".join(research_results))

        except Exception as e:
            self.results_text.setText(f"❌ Error in video podcast research: {str(e)}")
            import traceback
            traceback.print_exc()

    def performance_coaching(self):
        """Provide performance coaching for podcast hosts"""
        try:
            self.results_text.setText(
                "🎓 Performance Coaching\n\nThis feature provides personalized coaching for:\n• Speaking pace and clarity\n• Voice modulation and tone\n• Interview techniques\n• Audience engagement\n• Professional presentation\n\nUse this tool to improve your podcast hosting skills and delivery."
            )

        except Exception as e:
            self.results_text.setText(f"❌ Error in performance coaching: {str(e)}")

    def engagement_analysis(self):
        """Analyze audience engagement potential"""
        try:
            self.results_text.setText(
                "📈 Engagement Analysis\n\nThis feature analyzes your content for:\n• Audience retention factors\n• Hook effectiveness\n• Call-to-action strength\n• Emotional resonance\n• Shareability potential\n\nGet insights on how to keep your audience engaged throughout your episodes."
            )

        except Exception as e:
            self.results_text.setText(f"❌ Error in engagement analysis: {str(e)}")

    def storytelling_feedback(self):
        """Provide feedback on storytelling techniques"""
        try:
            self.results_text.setText(
                "📖 Storytelling Feedback\n\nThis feature evaluates your storytelling for:\n• Narrative structure\n• Character development\n• Plot progression\n• Emotional arcs\n• Pacing and timing\n\nImprove your storytelling skills to create more compelling podcast episodes."
            )

        except Exception as e:
            self.results_text.setText(f"❌ Error in storytelling feedback: {str(e)}")

    def guest_interview_coaching(self):
        """Provide coaching for guest interviews"""
        try:
            self.results_text.setText(
                "🎤 Guest Interview Coaching\n\nThis feature provides coaching for:\n• Interview preparation\n• Question formulation\n• Active listening\n• Guest engagement\n• Conversation flow\n\nEnhance your interview skills to create more engaging guest episodes."
            )

        except Exception as e:
            self.results_text.setText(f"❌ Error in guest interview coaching: {str(e)}")

    def podcast_analytics(self):
        """Analyze podcast performance and trends"""
        try:
            # Import podcast APIs with robust error handling
            podcast_apis = None
            
            try:
                from podcast_apis import PodcastAPIs
                podcast_apis = PodcastAPIs()
            except ImportError:
                try:
                    # Try with backend path
                    sys.path.insert(0, backend_dir)
                    from podcast_apis import PodcastAPIs
                    podcast_apis = PodcastAPIs()
                except ImportError:
                    try:
                        # Try with relative path
                        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
                        from podcast_apis import PodcastAPIs
                        podcast_apis = PodcastAPIs()
                    except ImportError as e:
                        self.results_text.setText(f"❌ Error: Could not import PodcastAPIs module. Please check backend installation. Error: {e}")
                        return

            if podcast_apis is None:
                self.results_text.setText("❌ Error: Could not import PodcastAPIs module. Please check backend installation.")
                return

            available_apis = podcast_apis.get_available_apis()

            if not any(available_apis.values()):
                self.results_text.setText(
                    "❌ No podcast APIs configured. Please add one of the following to your .env file:\n\n• PODCHASER_API_KEY - For podcast database and analytics\n• LISTEN_NOTES_API_KEY - For podcast search and discovery\n• APPLE_PODCASTS_API_KEY - For Apple Podcasts integration\n• GOOGLE_PODCASTS_API_KEY - For Google Podcasts integration"
                )
                return

            # Show available APIs
            api_status = []
            for api, available in available_apis.items():
                status = "✅" if available else "❌"
                api_status.append(f"{status} {api.replace('_', ' ').title()}")

            self.results_text.setText(
                f"📊 Podcast Analytics Available\n\nAvailable APIs:\n"
                + "\n".join(api_status)
                + "\n\nThis feature provides:\n• Performance metrics\n• Audience insights\n• Trend analysis\n• Competitive analysis\n• Growth recommendations\n\nUse podcast analytics to understand your audience and improve your show."
            )

        except Exception as e:
            self.results_text.setText(f"❌ Error in podcast analytics: {str(e)}")
            import traceback
            traceback.print_exc()

    def podchaser_analytics(self):
        """Get detailed analytics from Podchaser"""
        try:
            # Import podcast APIs with robust error handling
            podcast_apis = None
            
            try:
                from podcast_apis import PodcastAPIs
                podcast_apis = PodcastAPIs()
            except ImportError:
                try:
                    # Try with backend path
                    sys.path.insert(0, backend_dir)
                    from podcast_apis import PodcastAPIs
                    podcast_apis = PodcastAPIs()
                except ImportError:
                    try:
                        # Try with relative path
                        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
                        from podcast_apis import PodcastAPIs
                        podcast_apis = PodcastAPIs()
                    except ImportError as e:
                        self.results_text.setText(f"❌ Error: Could not import PodcastAPIs module. Please check backend installation. Error: {e}")
                        return

            if podcast_apis is None:
                self.results_text.setText("❌ Error: Could not import PodcastAPIs module. Please check backend installation.")
                return

            if not podcast_apis.podchaser_key:
                self.results_text.setText(
                    "❌ Podchaser API key not configured. Please add PODCHASER_API_KEY to your .env file"
                )
                return

            self.results_text.setText(
                "🎯 Podchaser Analytics\n\nFetching podcast analytics from Podchaser..."
            )

            # Search for popular podcasts to analyze
            search_results = podcast_apis.search_podcasts(
                "podcast", service="podchaser"
            )

            if "error" in search_results:
                self.results_text.setText(
                    f"❌ Error fetching Podchaser data: {search_results['error']}"
                )
                return

            analytics_results = ["🎯 Podchaser Analytics\n"]
            analytics_results.append("📊 Podcast Analytics from Podchaser:")
            analytics_results.append("=" * 50)

            # Analyze the first few results
            for i, edge in enumerate(search_results.get("results", [])[:3], 1):
                node = edge.get("node", {})
                title = node.get("title", "Unknown")
                description = (
                    node.get("description", "")[:100] + "..."
                    if len(node.get("description", "")) > 100
                    else node.get("description", "")
                )
                rating = node.get("rating", "N/A")
                review_count = node.get("reviewCount", "N/A")
                categories = [cat.get("name", "") for cat in node.get("categories", [])]

                analytics_results.append(f"\n{i}. {title}")
                analytics_results.append(
                    f"   Rating: {rating}/5 ({review_count} reviews)"
                )
                analytics_results.append(
                    f"   Categories: {', '.join(categories) if categories else 'N/A'}"
                )
                analytics_results.append(f"   Description: {description}")

                # Add analytics insights
                analytics_results.append(f"   📈 Analytics Insights:")
                analytics_results.append(f"   • Audience engagement potential")
                analytics_results.append(f"   • Content quality indicators")
                analytics_results.append(f"   • Market positioning")

            analytics_results.append(f"\n🎯 Key Analytics Insights:")
            analytics_results.append(
                f"• High-rated podcasts show strong audience engagement"
            )
            analytics_results.append(f"• Review counts indicate community involvement")
            analytics_results.append(f"• Category analysis reveals content positioning")
            analytics_results.append(f"• Description quality impacts discoverability")
            analytics_results.append(f"• Rating trends show content performance")

            self.results_text.setText("\n".join(analytics_results))

        except Exception as e:
            self.results_text.setText(f"❌ Error in Podchaser analytics: {str(e)}")
            import traceback
            traceback.print_exc()

    def podchaser_trending(self):
        """Get trending podcasts from Podchaser"""
        try:
            # Import podcast APIs with robust error handling
            podcast_apis = None
            
            try:
                from podcast_apis import PodcastAPIs
                podcast_apis = PodcastAPIs()
            except ImportError:
                try:
                    # Try with backend path
                    sys.path.insert(0, backend_dir)
                    from podcast_apis import PodcastAPIs
                    podcast_apis = PodcastAPIs()
                except ImportError:
                    try:
                        # Try with relative path
                        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
                        from podcast_apis import PodcastAPIs
                        podcast_apis = PodcastAPIs()
                    except ImportError as e:
                        self.results_text.setText(f"❌ Error: Could not import PodcastAPIs module. Please check backend installation. Error: {e}")
                        return

            if podcast_apis is None:
                self.results_text.setText("❌ Error: Could not import PodcastAPIs module. Please check backend installation.")
                return

            if not podcast_apis.podchaser_key:
                self.results_text.setText(
                    "❌ Podchaser API key not configured. Please add PODCHASER_API_KEY to your .env file"
                )
                return

            self.results_text.setText(
                "📈 Podchaser Trending\n\nFetching trending podcasts from Podchaser..."
            )

            # Get trending podcasts
            trending_results = podcast_apis.get_trending_podcasts(service="podchaser")

            if "error" in trending_results:
                self.results_text.setText(
                    f"❌ Error fetching trending podcasts: {trending_results['error']}"
                )
                return

            trending_data = ["📈 Podchaser Trending Podcasts\n"]
            trending_data.append("🔥 Currently Trending on Podchaser:")
            trending_data.append("=" * 50)

            # Display trending podcasts
            for i, edge in enumerate(trending_results.get("trending", [])[:5], 1):
                node = edge.get("node", {})
                title = node.get("title", "Unknown")
                description = (
                    node.get("description", "")[:150] + "..."
                    if len(node.get("description", "")) > 150
                    else node.get("description", "")
                )
                rating = node.get("rating", "N/A")
                review_count = node.get("reviewCount", "N/A")

                trending_data.append(f"\n{i}. {title}")
                trending_data.append(f"   Rating: {rating}/5 ({review_count} reviews)")
                trending_data.append(f"   Description: {description}")

                # Add trending insights
                trending_data.append(f"   🔥 Trending Insights:")
                trending_data.append(f"   • High audience engagement")
                trending_data.append(f"   • Strong community feedback")
                trending_data.append(f"   • Current market relevance")

            trending_data.append(f"\n🎯 Trending Analysis:")
            trending_data.append(f"• Trending podcasts show current audience interests")
            trending_data.append(f"• High ratings indicate quality content")
            trending_data.append(f"• Review counts show community engagement")
            trending_data.append(f"• Trending status reflects market demand")
            trending_data.append(f"• Content themes reveal audience preferences")

            self.results_text.setText("\n".join(trending_data))

        except Exception as e:
            self.results_text.setText(f"❌ Error in Podchaser trending: {str(e)}")
            import traceback
            traceback.print_exc()
