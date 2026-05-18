# frontend/reverb_tab.py
"""
Reverb Tab - Podcast Feedback and Coaching Tools
Provides AI-powered feedback and coaching for podcast creators
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add backend to path - handle separate frontend/backend folder structure
current_dir = os.path.dirname(os.path.abspath(__file__))  # frontend/
parent_dir = os.path.dirname(current_dir)  # root/
backend_dir = os.path.join(parent_dir, "backend")  # root/backend/
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Avoid Windows cp1252 crashes when printing unicode symbols.
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def _reverb_ollama_model_configured() -> bool:
    try:
        from ollama_resolve import resolved_ollama_model
    except ImportError:
        return bool((os.getenv("SOAPBOXX_OLLAMA_MODEL") or "").strip())
    return bool(resolved_ollama_model())


def _config_soapbox_stt_service() -> str:
    """STT from persisted SoapBoxx Settings (same keys MainWindow saves)."""
    try:
        from config import Config
    except ImportError:
        try:
            from backend.config import Config  # type: ignore
        except ImportError:
            return ""
    try:
        cfg = Config()
        for key in (
            "ui_settings.soapbox.transcription_service",
            "ui_settings.soapbox.stt_service",
        ):
            v = str(cfg.get(key, "") or "").strip().lower()
            if v in ("openai", "local", "assemblyai", "azure"):
                return v
    except Exception:
        pass
    return ""


def _episode_analysis_stt_service() -> str:
    """Transcription backend for Reverb episode upload analysis (env-overridable).

    If ``SOAPBOXX_TRANSCRIPTION_SERVICE`` / ``SOAPBOXX_EPISODE_ANALYSIS_STT`` are unset,
    prefer **local** Whisper when an Ollama model is available (same local demo stack as
    the rest of the app); otherwise fall back to OpenAI Whisper API.
    """
    raw = (
        os.getenv("SOAPBOXX_TRANSCRIPTION_SERVICE")
        or os.getenv("SOAPBOXX_EPISODE_ANALYSIS_STT")
        or _config_soapbox_stt_service()
        or ""
    ).strip().lower()
    if raw in ("openai", "local", "assemblyai", "azure"):
        return raw
    if _reverb_ollama_model_configured():
        return "local"
    return "openai"


def _episode_analysis_stt_max_file_mb() -> float:
    """Upload size guard (MB). OpenAI Whisper API caps near 25 MB; other backends stay relaxed."""
    return 25.0 if _episode_analysis_stt_service() == "openai" else 2048.0


def _episode_upload_size_hint() -> str:
    svc = _episode_analysis_stt_service()
    if svc == "openai":
        return (
            "💡 Transcription uses the OpenAI API (Whisper). Maximum file size is 25 MB; "
            "compress larger episodes first."
        )
    return (
        f"💡 Transcription uses «{svc}» (not the OpenAI 25 MB cap). "
        "Very large files may still be slow or memory-heavy with local Whisper."
    )


def _reverb_clip_corpus(text: str, limit: int = 14000) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[:limit] + "\n…(truncated for LLM context)"


def _reverb_summarize_search_hits(heading: str, corpus: str) -> Optional[str]:
    """
    Turn API search hits (YouTube / Podchaser) into producer-facing bullets using the same
    stack as workflow LLM calls: ``call_llm`` → Ollama when ``SOAPBOXX_OLLAMA_MODEL`` is set
    (or Groq when ``SOAPBOXX_WORKFLOW_LLM_BACKEND=groq`` and a Groq key is present).
    """
    if not _reverb_ollama_model_configured():
        return None
    if (os.getenv("SOAPBOXX_REVERB_SEARCH_LLM") or "1").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return None
    corpus = _reverb_clip_corpus(corpus)
    if not corpus:
        return None
    try:
        from soapboxx_v3_workflow import call_llm
    except ImportError:
        return None
    prompt = (
        f"{heading}\n\n"
        "Below are structured search hits (titles, channels, ratings, snippets). "
        "Write 6–10 bullet points for a podcast producer. Be specific to these results; "
        "avoid generic podcast platitudes. Use plain lines starting with '- '.\n\n"
        f"{corpus}"
    )
    try:
        env = call_llm(
            prompt,
            max_tokens=900,
            temperature=0.25,
            system=(
                "You interpret podcast discovery search results into concise, actionable producer notes. "
                "Do not invent shows or metrics not present in the input."
            ),
            client=None,
            json_format=False,
            stage="reverb.search_summary",
        )
        text = (env.get("text") or "").strip()
        return text or None
    except Exception:
        return None


def _append_reverb_llm_block(lines: List[str], heading: str, corpus: str) -> None:
    """Append an LLM summary block, or a short hint when no model is configured."""
    blob = _reverb_summarize_search_hits(heading, corpus)
    lines.append("")
    if blob:
        lines.append("Producer insights (LLM):")
        lines.append(blob)
    elif _reverb_ollama_model_configured():
        lines.append(
            "Producer insights (LLM): (call failed — check Ollama/Groq logs and SOAPBOXX_OLLAMA_DEBUG.)"
        )
    else:
        lines.append(
            "Producer insights (LLM): set SOAPBOXX_OLLAMA_MODEL in .env and run Ollama "
            "to replace generic bullets with summaries here. "
            "Optional: SOAPBOXX_WORKFLOW_LLM_BACKEND=ollama to force Ollama when a Groq key exists."
        )


from PyQt6.QtCore import Qt, QThread, pyqtSignal
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
            stt = _episode_analysis_stt_service()
            limit_mb = _episode_analysis_stt_max_file_mb()

            # Try multiple import paths
            try:
                from feedback_engine import FeedbackEngine
                from transcriber import Transcriber

                feedback_engine = FeedbackEngine()
                transcriber = Transcriber(service=stt)
            except ImportError:
                try:
                    # Try with backend path
                    sys.path.insert(0, backend_dir)
                    from feedback_engine import FeedbackEngine
                    from transcriber import Transcriber

                    feedback_engine = FeedbackEngine()
                    transcriber = Transcriber(service=stt)
                except ImportError:
                    try:
                        # Try with relative path
                        sys.path.insert(
                            0, os.path.join(os.path.dirname(__file__), "..", "backend")
                        )
                        from feedback_engine import FeedbackEngine
                        from transcriber import Transcriber

                        feedback_engine = FeedbackEngine()
                        transcriber = Transcriber(service=stt)
                    except ImportError as e:
                        self.error_occurred.emit(
                            f"Failed to import backend modules: {e}"
                        )
                        return

            if feedback_engine is None or transcriber is None:
                self.error_occurred.emit("Failed to initialize backend modules")
                return

            self.progress_updated.emit(20)

            # Check file size again in case it was modified (25 MB cap only for OpenAI STT)
            file_size = os.path.getsize(self.file_path) / (1024 * 1024)  # MB
            if file_size > limit_mb:
                if stt == "openai":
                    self.error_occurred.emit(
                        f"File size ({file_size:.1f}MB) exceeds OpenAI's 25MB limit. "
                        "Compress the audio, use a smaller file, or set SOAPBOXX_EPISODE_ANALYSIS_STT=local "
                        "with local Whisper + an Ollama model configured."
                    )
                else:
                    self.error_occurred.emit(
                        f"File size ({file_size:.1f}MB) exceeds the configured limit ({limit_mb:.0f} MB) for "
                        f"transcription backend «{stt}»."
                    )
                return

            # Transcribe audio
            try:
                with open(self.file_path, "rb") as f:
                    audio_data = f.read()
            except Exception as e:
                self.error_occurred.emit(f"Failed to read audio file: {e}")
                return

            self.progress_updated.emit(40)

            max_bytes = int(limit_mb * 1024 * 1024)
            if len(audio_data) > max_bytes:
                if stt == "openai":
                    self.error_occurred.emit(
                        f"Audio file is too large ({len(audio_data) / (1024*1024):.1f}MB). "
                        "OpenAI's limit is 25MB — compress the audio or switch to local STT."
                    )
                else:
                    self.error_occurred.emit(
                        f"Audio file is too large ({len(audio_data) / (1024*1024):.1f}MB) for the "
                        f"«{stt}» backend (limit {limit_mb:.0f} MB)."
                    )
                return

            transcript = transcriber.transcribe(audio_data)
            if not transcript or transcript.startswith("Error"):
                # Check for specific OpenAI errors
                if stt == "openai" and (
                    "413" in str(transcript)
                    or "Maximum content size limit" in str(transcript)
                ):
                    self.error_occurred.emit(
                        "File too large for OpenAI API. Compress to under 25MB or use local transcription "
                        "(Ollama model + SOAPBOXX_EPISODE_ANALYSIS_STT=local)."
                    )
                else:
                    self.error_occurred.emit(f"Transcription failed: {transcript}")
                return

            self.progress_updated.emit(60)

            # Analyze content or episode report / network brief
            network_brief_md = None
            network_brief_payload = None
            if self.analysis_type == "Episode Report (v3 — primary)":
                if not hasattr(feedback_engine, "generate_network_brief_v3"):
                    self.error_occurred.emit(
                        "Episode Report (v3) requires FeedbackEngine.generate_network_brief_v3."
                    )
                    return
                base = os.path.splitext(os.path.basename(self.file_path))[0]
                nb = feedback_engine.generate_network_brief_v3(
                    transcript,
                    title=base,
                    creator="",
                    genre="",
                )
                # Prefer unified export (v3 + workflow sections); coach-only markdown_v3 omits a lot.
                network_brief_md = (
                    nb.get("markdown_export")
                    or nb.get("markdown_v3")
                    or nb.get("markdown")
                    or ""
                )
                try:
                    from episode_report_v3 import finalize_unified_markdown_export

                    network_brief_md = finalize_unified_markdown_export(
                        str(network_brief_md or "")
                    )
                except Exception:
                    pass
                network_brief_payload = nb
                analysis = {
                    "listener_feedback": "Primary v3 Episode Report generated (see below).",
                    "coaching_suggestions": nb.get("warnings") or [],
                    "benchmark": f"Model: {nb.get('model', 'unknown')}",
                    "confidence": 1.0,
                }
            elif self.analysis_type == "Network Brief (v2 — compact)":
                if not hasattr(feedback_engine, "generate_network_brief"):
                    self.error_occurred.emit(
                        "Network Brief requires an updated FeedbackEngine with generate_network_brief."
                    )
                    return
                base = os.path.splitext(os.path.basename(self.file_path))[0]
                nb = feedback_engine.generate_network_brief(
                    transcript,
                    title=base,
                    creator="",
                    genre="",
                )
                network_brief_md = nb.get("markdown", "")
                network_brief_payload = nb
                analysis = {
                    "listener_feedback": "Compact v2 network brief generated (see below).",
                    "coaching_suggestions": nb.get("warnings") or [],
                    "benchmark": f"Model: {nb.get('model', 'unknown')}",
                    "confidence": 1.0,
                }
            else:
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
                "network_brief_markdown": network_brief_md,
                "network_brief": network_brief_payload,
            }

            self.progress_updated.emit(100)
            self.analysis_complete.emit(results)

        except Exception as e:
            self.error_occurred.emit(f"Analysis failed: {str(e)}")
            import traceback

            traceback.print_exc()


def _format_session_feedback_block(analysis: dict) -> str:
    """Human-readable block for FeedbackEngine.analyze() results."""
    lines = ["🎯 AI feedback (SoapBoxx recording)", "─" * 44, ""]
    if not isinstance(analysis, dict):
        return str(analysis)
    lf = analysis.get("listener_feedback")
    if lf:
        lines.append("Listener feedback")
        lines.append(str(lf).strip())
        lines.append("")
    cs = analysis.get("coaching_suggestions")
    if isinstance(cs, (list, tuple)) and cs:
        lines.append("Coaching suggestions")
        for i, s in enumerate(cs, 1):
            lines.append(f"  {i}. {s}")
        lines.append("")
    bm = analysis.get("benchmark")
    if bm:
        lines.append(f"Benchmark: {bm}")
    conf = analysis.get("confidence")
    if conf is not None:
        try:
            lines.append(f"Confidence: {float(conf):.2f}")
        except (TypeError, ValueError):
            lines.append(f"Confidence: {conf}")
    return "\n".join(lines).strip()


class SessionFeedbackThread(QThread):
    """Run FeedbackEngine.analyze in the background (SoapBoxx → Reverb path)."""

    feedback_complete = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, transcript: str, analysis_depth: str = "standard"):
        super().__init__()
        self.transcript = transcript
        self.analysis_depth = analysis_depth

    def run(self):
        try:
            feedback_engine = None
            try:
                from feedback_engine import FeedbackEngine

                feedback_engine = FeedbackEngine()
            except ImportError:
                try:
                    sys.path.insert(0, backend_dir)
                    from feedback_engine import FeedbackEngine

                    feedback_engine = FeedbackEngine()
                except ImportError:
                    try:
                        sys.path.insert(
                            0, os.path.join(os.path.dirname(__file__), "..", "backend")
                        )
                        from feedback_engine import FeedbackEngine

                        feedback_engine = FeedbackEngine()
                    except ImportError as e:
                        self.error_occurred.emit(
                            f"Could not import FeedbackEngine: {e}"
                        )
                        return

            if feedback_engine is None:
                self.error_occurred.emit("FeedbackEngine failed to initialize")
                return

            out = feedback_engine.analyze(
                transcript=self.transcript,
                analysis_depth=self.analysis_depth,
            )
            if isinstance(out, dict):
                self.feedback_complete.emit(out)
            else:
                self.error_occurred.emit("Unexpected response from feedback engine")
        except Exception as e:
            self.error_occurred.emit(str(e))


class ReverbTab(QWidget):
    """Reverb tab for podcast feedback and coaching tools"""

    def __init__(self):
        super().__init__()
        self.uploaded_episodes = []
        self.analysis_thread = None
        self._session_feedback_thread = None
        # Defer UI setup until widget is shown
        self._ui_initialized = False

        # Connect show event to initialize UI
        self.showEvent = self._on_show_event

    def _on_show_event(self, event):
        """Initialize UI when widget is first shown"""
        if not self._ui_initialized:
            print("🎨 ReverbTab: Initializing UI...")
            self.init_ui()
            self._ui_initialized = True
            print("✅ ReverbTab: UI initialized")

        # Call the original showEvent if it exists
        super().showEvent(event)

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

        # File size / STT backend hint (OpenAI Whisper API = 25 MB cap; local = relaxed)
        size_info = QLabel(_episode_upload_size_hint())
        size_info.setStyleSheet("color: #666; font-size: 11px; margin: 5px;")
        upload_layout.addWidget(size_info)

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
                "Episode Report (v3 — primary)",
                "Network Brief (v2 — compact)",
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
            "Ollama model (SOAPBOXX_OLLAMA_MODEL)": os.environ.get(
                "SOAPBOXX_OLLAMA_MODEL", "Not set"
            ),
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
        _has_openai = bool(
            api_keys.get("OpenAI API Key")
            and api_keys.get("OpenAI API Key") != "Not set"
        )
        _llm_ready = _has_openai or _reverb_ollama_model_configured()
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
        content_btn.setEnabled(_llm_ready)
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
        coaching_btn.setEnabled(_llm_ready)
        feedback_layout.addWidget(coaching_btn)

        # Engagement Analysis
        engagement_btn = QPushButton("📈 Engagement Analysis")
        engagement_btn.clicked.connect(self.engagement_analysis)
        engagement_btn.setEnabled(_llm_ready)
        feedback_layout.addWidget(engagement_btn)

        # Storytelling Feedback
        storytelling_btn = QPushButton("📖 Storytelling Feedback")
        storytelling_btn.clicked.connect(self.storytelling_feedback)
        storytelling_btn.setEnabled(_llm_ready)
        feedback_layout.addWidget(storytelling_btn)

        feedback_group.setLayout(feedback_layout)
        layout.addWidget(feedback_group)

        # SoapBoxx live recording → AI feedback (moved from SoapBoxx tab)
        session_fb_group = QGroupBox("🎙️ SoapBoxx recording — AI feedback")
        session_fb_layout = QVBoxLayout()
        session_hint = QLabel(
            "When you stop recording on the SoapBoxx tab, the live transcript is sent here for "
            "listener feedback and coaching. Uses Ollama when SOAPBOXX_OLLAMA_MODEL is set, "
            "otherwise your OpenAI API key (same stack as FeedbackEngine)."
        )
        session_hint.setWordWrap(True)
        session_hint.setStyleSheet("color: #666; font-size: 11px;")
        session_fb_layout.addWidget(session_hint)
        self.session_feedback_status = QLabel(
            "Waiting for a finished SoapBoxx recording…"
        )
        self.session_feedback_status.setWordWrap(True)
        self.session_feedback_status.setStyleSheet("color: #6C757D;")
        session_fb_layout.addWidget(self.session_feedback_status)
        self.session_feedback_output = QTextEdit()
        self.session_feedback_output.setReadOnly(True)
        self.session_feedback_output.setPlaceholderText(
            "Listener feedback and coaching suggestions appear here after each session."
        )
        self.session_feedback_output.setMinimumHeight(200)
        session_fb_layout.addWidget(self.session_feedback_output)
        session_fb_group.setLayout(session_fb_layout)
        layout.addWidget(session_fb_group)

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

    def run_session_feedback_from_transcript(self, transcript: str):
        """Called from MainWindow when SoapBoxx recording stops (non-empty transcript)."""
        if not getattr(self, "_ui_initialized", False):
            self.init_ui()
            self._ui_initialized = True
        t = (transcript or "").strip()
        if not t:
            self.session_feedback_status.setText("No transcript text to analyze.")
            return
        if self._session_feedback_thread and self._session_feedback_thread.isRunning():
            self._session_feedback_thread.wait(2000)
        self.session_feedback_status.setText("Generating AI feedback…")
        self.session_feedback_output.clear()
        self._session_feedback_thread = SessionFeedbackThread(t, "standard")
        self._session_feedback_thread.feedback_complete.connect(
            self._on_session_feedback_complete,
            Qt.ConnectionType.QueuedConnection,
        )
        self._session_feedback_thread.error_occurred.connect(
            self._on_session_feedback_error,
            Qt.ConnectionType.QueuedConnection,
        )
        self._session_feedback_thread.start()

    def _on_session_feedback_complete(self, analysis: dict):
        self.session_feedback_status.setText("Feedback ready.")
        self.session_feedback_output.setPlainText(
            _format_session_feedback_block(analysis)
        )

    def _on_session_feedback_error(self, err: str):
        self.session_feedback_status.setText("Feedback failed.")
        tip = (
            "Tips: set SOAPBOXX_OLLAMA_MODEL and run Ollama for local feedback, "
            "or set OPENAI_API_KEY for cloud-only use."
            if _reverb_ollama_model_configured()
            else "Tips: set OPENAI_API_KEY, or run Ollama with SOAPBOXX_OLLAMA_MODEL in your environment."
        )
        self.session_feedback_output.setPlainText(
            f"Could not generate feedback.\n\n{err}\n\n{tip}"
        )

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

        limit_mb = _episode_analysis_stt_max_file_mb()
        stt = _episode_analysis_stt_service()
        file_size = os.path.getsize(self.selected_file_path) / (1024 * 1024)  # MB
        if file_size > limit_mb:
            if stt == "openai":
                extra = (
                    "\n\nTips:\n"
                    "• Convert to MP3 with lower bitrate (128kbps)\n"
                    "• Use audio compression tools\n"
                    "• Split large files into smaller segments\n"
                    "• Or use local transcription: configure Ollama + leave "
                    "SOAPBOXX_EPISODE_ANALYSIS_STT unset (defaults to local when Ollama is available)"
                )
            else:
                extra = (
                    f"\n\nThis backend («{stt}») allows up to about {limit_mb:.0f} MB. "
                    "Try a shorter file or a more compressed format."
                )
            QMessageBox.warning(
                self,
                "File Too Large",
                f"File size ({file_size:.1f} MB) exceeds the limit ({limit_mb:.0f} MB) for "
                f"transcription backend «{stt}»."
                + extra,
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
            transcript = results.get("transcript", "")
            if transcript and not transcript.startswith("Error"):
                transcript_preview = (
                    transcript[:500] + "..." if len(transcript) > 500 else transcript
                )
                output += f"📝 Transcript Preview:\n{transcript_preview}\n\n"
            else:
                output += (
                    f"📝 Transcript Preview:\n❌ Transcription failed: {transcript}\n\n"
                )
                output += f"💡 Suggestions:\n"
                output += f"• Check if the audio file is corrupted\n"
                if _episode_analysis_stt_service() == "openai":
                    output += f"• Ensure the file is under 25MB when using OpenAI transcription\n"
                else:
                    output += (
                        f"• Transcription uses «{_episode_analysis_stt_service()}» — "
                        "check local Whisper (openai-whisper) and available RAM\n"
                    )
                output += f"• Try converting to a different audio format\n"
                output += f"• Check if the audio contains speech\n\n"

            # Add analysis results
            analysis = results.get("analysis", {})
            if isinstance(analysis, dict):
                if results.get("network_brief_markdown"):
                    if results.get("analysis_type") == "Episode Report (v3 — primary)":
                        output += "📋 EPISODE REPORT (v3 — primary)\n"
                    else:
                        output += "📋 NETWORK BRIEF (v2 — compact)\n"
                    output += "─" * 50 + "\n"
                    output += results["network_brief_markdown"]
                    output += "\n\n"
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
            import traceback

            traceback.print_exc()

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
                        sys.path.insert(
                            0, os.path.join(os.path.dirname(__file__), "..", "backend")
                        )
                        from feedback_engine import FeedbackEngine

                        feedback_engine = FeedbackEngine()
                    except ImportError as e:
                        self.results_text.setText(
                            f"❌ Error: Could not import FeedbackEngine module. Please check backend installation. Error: {e}"
                        )
                        return

            if feedback_engine is None:
                self.results_text.setText(
                    "❌ Error: Could not import FeedbackEngine module. Please check backend installation."
                )
                return

            # This would analyze the current transcript or uploaded content
            self.results_text.setText(
                "📊 Content Analysis\n\nThis feature analyzes your podcast content for:\n• Clarity and coherence\n• Engagement factors\n• Topic relevance\n• Audience appeal\n• Content structure\n\nUse the buttons above with a transcript, or finish a recording on SoapBoxx — feedback is generated automatically on this tab under “SoapBoxx recording — AI feedback”."
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
                        sys.path.insert(
                            0, os.path.join(os.path.dirname(__file__), "..", "backend")
                        )
                        from google_apis import GoogleAPIs

                        google_apis = GoogleAPIs()
                    except ImportError as e:
                        self.results_text.setText(
                            f"❌ Error: Could not import GoogleAPIs module. Please check backend installation. Error: {e}"
                        )
                        return

            if google_apis is None:
                self.results_text.setText(
                    "❌ Error: Could not import GoogleAPIs module. Please check backend installation."
                )
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

            corpus_lines: List[str] = []
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
                corpus_lines.append(
                    f"- Hit {i}: title={title!r} channel={channel!r} views={view_count} desc={description!r}"
                )

            _append_reverb_llm_block(
                analysis_results,
                "YouTube trending (US): summarize these video hits for a podcast producer.",
                "\n".join(corpus_lines),
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
                        sys.path.insert(
                            0, os.path.join(os.path.dirname(__file__), "..", "backend")
                        )
                        from google_apis import GoogleAPIs

                        google_apis = GoogleAPIs()
                    except ImportError as e:
                        self.results_text.setText(
                            f"❌ Error: Could not import GoogleAPIs module. Please check backend installation. Error: {e}"
                        )
                        return

            if google_apis is None:
                self.results_text.setText(
                    "❌ Error: Could not import GoogleAPIs module. Please check backend installation."
                )
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

            corpus_lines: List[str] = []
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
                corpus_lines.append(
                    f"- Hit {i}: title={title!r} channel={channel!r} url={url!r} desc={description!r}"
                )

            _append_reverb_llm_block(
                research_results,
                'YouTube search query: "video podcast". Interpret these results for a producer.',
                "\n".join(corpus_lines),
            )

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
                        sys.path.insert(
                            0, os.path.join(os.path.dirname(__file__), "..", "backend")
                        )
                        from podcast_apis import PodcastAPIs

                        podcast_apis = PodcastAPIs()
                    except ImportError as e:
                        self.results_text.setText(
                            f"❌ Error: Could not import PodcastAPIs module. Please check backend installation. Error: {e}"
                        )
                        return

            if podcast_apis is None:
                self.results_text.setText(
                    "❌ Error: Could not import PodcastAPIs module. Please check backend installation."
                )
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
                        sys.path.insert(
                            0, os.path.join(os.path.dirname(__file__), "..", "backend")
                        )
                        from podcast_apis import PodcastAPIs

                        podcast_apis = PodcastAPIs()
                    except ImportError as e:
                        self.results_text.setText(
                            f"❌ Error: Could not import PodcastAPIs module. Please check backend installation. Error: {e}"
                        )
                        return

            if podcast_apis is None:
                self.results_text.setText(
                    "❌ Error: Could not import PodcastAPIs module. Please check backend installation."
                )
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

            corpus_lines: List[str] = []
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
                corpus_lines.append(
                    f"- Hit {i}: title={title!r} rating={rating} reviews={review_count} "
                    f"categories={categories!r} desc={description!r}"
                )

            _append_reverb_llm_block(
                analytics_results,
                'Podchaser search: query "podcast". Summarize positioning and takeaways.',
                "\n".join(corpus_lines),
            )

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
                        sys.path.insert(
                            0, os.path.join(os.path.dirname(__file__), "..", "backend")
                        )
                        from podcast_apis import PodcastAPIs

                        podcast_apis = PodcastAPIs()
                    except ImportError as e:
                        self.results_text.setText(
                            f"❌ Error: Could not import PodcastAPIs module. Please check backend installation. Error: {e}"
                        )
                        return

            if podcast_apis is None:
                self.results_text.setText(
                    "❌ Error: Could not import PodcastAPIs module. Please check backend installation."
                )
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

            corpus_lines: List[str] = []
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
                corpus_lines.append(
                    f"- Trend {i}: title={title!r} rating={rating} reviews={review_count} desc={description!r}"
                )

            _append_reverb_llm_block(
                trending_data,
                "Podchaser trending list: what should a producer notice or try next?",
                "\n".join(corpus_lines),
            )

            self.results_text.setText("\n".join(trending_data))

        except Exception as e:
            self.results_text.setText(f"❌ Error in Podchaser trending: {str(e)}")
            import traceback

            traceback.print_exc()
