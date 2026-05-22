# frontend/reverb_tab.py
"""
Coach tab (ReverbTab) — post-episode Episode Coach Report (sections A–F).
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
    try:
        from backend.coach_stt import resolve_stt_for_coach
    except ImportError:
        try:
            from coach_stt import resolve_stt_for_coach  # type: ignore
        except ImportError:
            resolve_stt_for_coach = None  # type: ignore
    if resolve_stt_for_coach is not None:
        effective, _ = resolve_stt_for_coach(raw)
        return effective
    if raw in ("openai", "local", "assemblyai"):
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
        "Coach supports openai, local, or assemblyai only. "
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
    stack as workflow LLM calls: ``llm_service.call_llm`` → Ollama when ``SOAPBOXX_OLLAMA_MODEL`` is set
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
        try:
            from backend.llm_service import call_llm
        except ImportError:
            from llm_service import call_llm  # type: ignore
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
                             QProgressBar, QPushButton, QTextEdit, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout, QWidget)


class EpisodeAnalysisThread(QThread):
    """Thread for analyzing uploaded episodes"""

    analysis_complete = pyqtSignal(dict)
    progress_updated = pyqtSignal(int)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        file_path: str,
        analysis_type: str,
        *,
        category: str = "general",
        title: str = "",
    ):
        super().__init__()
        self.file_path = file_path
        self.analysis_type = analysis_type
        self.category = category
        self.episode_title = title

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

            base = os.path.splitext(os.path.basename(self.file_path))[0]
            title = (self.episode_title or base).strip()
            if hasattr(feedback_engine, "generate_episode_coach_report"):
                coach = feedback_engine.generate_episode_coach_report(
                    transcript,
                    title=title,
                    creator="",
                )
                intelligence: dict = {}
                try:
                    from backend.intelligence_v1.pipeline import process_transcript_only
                except ImportError:
                    from intelligence_v1.pipeline import process_transcript_only  # type: ignore

                self.progress_updated.emit(85)
                intelligence = process_transcript_only(
                    transcript, self.category, title=title
                )
                self.progress_updated.emit(100)
                self.analysis_complete.emit(
                    {
                        "file_path": self.file_path,
                        "file_name": base,
                        "transcript": transcript,
                        "coach_report": coach,
                        "markdown": coach.get("markdown") or "",
                        "intelligence": intelligence,
                        "intelligence_markdown": intelligence.get("markdown") or "",
                        "analysis_type": "Episode Coach Report",
                    }
                )
                return

            # Legacy path (should not run in focused coach UI)
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


def _coach_category_choices():
    try:
        from backend.intelligence_v1.categories import category_labels
    except ImportError:
        try:
            from intelligence_v1.categories import category_labels  # type: ignore
        except ImportError:
            return [("general", "General / mixed")]
    return category_labels()


def _load_saved_intelligence_category() -> str:
    try:
        from config import Config
    except ImportError:
        try:
            from backend.config import Config  # type: ignore
        except ImportError:
            return "general"
    try:
        return str(
            Config().get("ui_settings.soapbox.intelligence_category", "general")
            or "general"
        ).strip()
    except Exception:
        return "general"


def _format_coach_report_payload(payload: dict) -> str:
    """Display Episode Coach Report markdown from generate_episode_coach_report."""
    if not isinstance(payload, dict):
        return str(payload)
    md = str(payload.get("markdown") or "").strip()
    if md:
        return md
    return "(No coach report generated.)"


class EpisodeIngestThread(QThread):
    """Pull transcript from YouTube, file, or audio."""

    ingest_complete = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, mode: str, payload: str):
        super().__init__()
        self.mode = mode
        self.payload = payload

    def run(self):
        try:
            try:
                from backend.episode_ingest import (
                    ingest_from_audio_file,
                    ingest_from_transcript_file,
                    ingest_from_youtube_url,
                )
            except ImportError:
                from episode_ingest import (  # type: ignore
                    ingest_from_audio_file,
                    ingest_from_transcript_file,
                    ingest_from_youtube_url,
                )

            if self.mode == "youtube":
                r = ingest_from_youtube_url(self.payload)
            elif self.mode == "transcript_file":
                r = ingest_from_transcript_file(self.payload)
            elif self.mode == "audio_file":
                r = ingest_from_audio_file(self.payload)
            else:
                self.error_occurred.emit(f"Unknown ingest mode: {self.mode}")
                return
            self.ingest_complete.emit(r.to_dict())
        except Exception as e:
            self.error_occurred.emit(str(e))


class FullEpisodeAnalysisThread(QThread):
    """Episode Coach Report (A–F) + intelligence metrics/tier report."""

    analysis_complete = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        transcript: str,
        *,
        title: str = "",
        category: str = "general",
        creator: str = "",
    ):
        super().__init__()
        self.transcript = transcript
        self.title = title
        self.category = category
        self.creator = creator

    def run(self):
        try:
            feedback_engine = None
            try:
                from feedback_engine import FeedbackEngine

                feedback_engine = FeedbackEngine()
            except ImportError:
                sys.path.insert(0, backend_dir)
                from feedback_engine import FeedbackEngine

                feedback_engine = FeedbackEngine()
            if feedback_engine is None:
                self.error_occurred.emit("FeedbackEngine not available")
                return

            coach: dict = {}
            if hasattr(feedback_engine, "generate_episode_coach_report"):
                coach = feedback_engine.generate_episode_coach_report(
                    self.transcript,
                    title=self.title,
                    creator=self.creator,
                )
            else:
                coach = feedback_engine.analyze(transcript=self.transcript)

            intelligence: dict = {}
            try:
                from backend.intelligence_v1.pipeline import process_transcript_only
            except ImportError:
                from intelligence_v1.pipeline import process_transcript_only  # type: ignore

            intelligence = process_transcript_only(
                self.transcript,
                self.category,
                title=self.title or "Episode",
            )

            self.analysis_complete.emit(
                {
                    "coach": coach if isinstance(coach, dict) else {},
                    "intelligence": intelligence,
                }
            )
        except Exception as e:
            self.error_occurred.emit(str(e))


class WeeklyBatchThread(QThread):
    """Process pending library queue (measurement-first)."""

    batch_complete = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            from backend.library import run_weekly_batch

            summary = run_weekly_batch()
            self.batch_complete.emit(summary)
        except Exception as e:
            self.error_occurred.emit(str(e))


class ReverbTab(QWidget):
    """Reverb tab for podcast feedback and coaching tools"""

    def __init__(self):
        super().__init__()
        self.uploaded_episodes = []
        self.analysis_thread = None
        self._session_feedback_thread = None
        self._coach_report_thread = None
        self._last_episode_session = None
        self._last_ingest_source: Optional[Dict[str, str]] = None
        self._batch_thread: Optional[WeeklyBatchThread] = None
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
        """Focused post-episode coach UI (transcript → Episode Coach Report)."""
        layout = QVBoxLayout()

        title = QLabel("Episode Coach")
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin: 8px 0;")
        layout.addWidget(title)

        description = QLabel(
            "Import from where you already publish (YouTube, transcript, or audio). "
            "SoapBoxx adds an insights library on top — producer coaching and structure metrics "
            "for your next episode, in 2–3 minutes."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #555; margin-bottom: 8px;")
        layout.addWidget(description)

        input_group = QGroupBox("1. Import episode")
        input_layout = QVBoxLayout()

        import_row = QHBoxLayout()
        import_row.addWidget(QLabel("YouTube URL:"))
        self.youtube_url_input = QLineEdit()
        self.youtube_url_input.setPlaceholderText("https://www.youtube.com/watch?v=…")
        import_row.addWidget(self.youtube_url_input, 1)
        self.import_youtube_btn = QPushButton("Import URL")
        self.import_youtube_btn.clicked.connect(self.import_from_youtube_url)
        import_row.addWidget(self.import_youtube_btn)
        input_layout.addLayout(import_row)

        file_row = QHBoxLayout()
        self.import_transcript_btn = QPushButton("Import transcript file…")
        self.import_transcript_btn.clicked.connect(self.import_transcript_file)
        file_row.addWidget(self.import_transcript_btn)
        self.import_audio_btn = QPushButton("Import audio file…")
        self.import_audio_btn.clicked.connect(self.import_audio_file)
        file_row.addWidget(self.import_audio_btn)
        file_row.addStretch()
        input_layout.addLayout(file_row)

        paste_hint = QLabel(
            "Or paste a transcript below (e.g. from Tactiq). Then choose category and generate."
        )
        paste_hint.setWordWrap(True)
        paste_hint.setStyleSheet("color: #666; font-size: 11px;")
        input_layout.addWidget(paste_hint)

        self.transcript_input = QTextEdit()
        self.transcript_input.setPlaceholderText(
            "Paste your episode transcript here…"
        )
        self.transcript_input.setMinimumHeight(120)
        input_layout.addWidget(self.transcript_input)

        meta_row = QHBoxLayout()
        meta_row.addWidget(QLabel("Episode title:"))
        self.episode_title_input = QLineEdit()
        self.episode_title_input.setPlaceholderText("Optional — used in reports")
        meta_row.addWidget(self.episode_title_input, 1)
        input_layout.addLayout(meta_row)

        shelf_row = QHBoxLayout()
        shelf_row.addWidget(QLabel("Show:"))
        self.show_title_input = QLineEdit()
        self.show_title_input.setPlaceholderText("Podcast / series name")
        shelf_row.addWidget(self.show_title_input, 1)
        shelf_row.addWidget(QLabel("Author:"))
        self.author_input = QLineEdit()
        self.author_input.setPlaceholderText("Host / creator")
        shelf_row.addWidget(self.author_input, 1)
        input_layout.addLayout(shelf_row)

        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        for cid, label in _coach_category_choices():
            self.category_combo.addItem(label, cid)
        saved_cat = _load_saved_intelligence_category()
        idx = self.category_combo.findData(saved_cat)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        cat_row.addWidget(self.category_combo, 1)
        cat_hint = QLabel("Benchmarks compare against this show type.")
        cat_hint.setStyleSheet("color: #888; font-size: 10px;")
        cat_row.addWidget(cat_hint)
        input_layout.addLayout(cat_row)

        btn_row = QHBoxLayout()
        self.generate_coach_btn = QPushButton("Generate Episode Coach Report")
        self.generate_coach_btn.clicked.connect(self.generate_coach_from_transcript)
        btn_row.addWidget(self.generate_coach_btn)
        self.coach_progress = QProgressBar()
        self.coach_progress.setVisible(False)
        btn_row.addWidget(self.coach_progress, 1)
        input_layout.addLayout(btn_row)

        self.session_feedback_status = QLabel("Waiting for transcript…")
        self.session_feedback_status.setWordWrap(True)
        self.session_feedback_status.setStyleSheet("color: #6C757D; font-size: 11px;")
        input_layout.addWidget(self.session_feedback_status)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        library_group = QGroupBox("Insights library — weekly batch")
        library_layout = QVBoxLayout()
        lib_hint = QLabel(
            "Spotify, YouTube, and other hosts are the catalog — SoapBoxx builds your "
            "insights shelf here (category → author → show → episodes). "
            "Queue episodes from imports, run weekly batch for measurements; coach stays on demand."
        )
        lib_hint.setWordWrap(True)
        lib_hint.setStyleSheet("color: #666; font-size: 11px;")
        library_layout.addWidget(lib_hint)

        queue_row = QHBoxLayout()
        self.add_to_queue_btn = QPushButton("Add to weekly queue")
        self.add_to_queue_btn.clicked.connect(self.add_episode_to_weekly_queue)
        queue_row.addWidget(self.add_to_queue_btn)
        self.run_batch_btn = QPushButton("Run weekly batch")
        self.run_batch_btn.clicked.connect(self.run_weekly_batch)
        queue_row.addWidget(self.run_batch_btn)
        self.batch_progress = QProgressBar()
        self.batch_progress.setVisible(False)
        queue_row.addWidget(self.batch_progress, 1)
        library_layout.addLayout(queue_row)

        self.library_status = QLabel("")
        self.library_status.setWordWrap(True)
        self.library_status.setStyleSheet("color: #6C757D; font-size: 11px;")
        library_layout.addWidget(self.library_status)

        self.library_tree = QTreeWidget()
        self.library_tree.setHeaderLabels(["Shelf", ""])
        self.library_tree.setMinimumHeight(140)
        library_layout.addWidget(self.library_tree)

        library_group.setLayout(library_layout)
        layout.addWidget(library_group)

        report_group = QGroupBox("2. Episode Coach Report")
        report_layout = QVBoxLayout()
        self.coach_report_output = QTextEdit()
        self.coach_report_output.setReadOnly(True)
        self.coach_report_output.setPlaceholderText(
            "Sections A–F will appear here: summary, strong/weak moments, missed follow-ups, "
            "host patterns, and next-episode improvements."
        )
        self.coach_report_output.setMinimumHeight(220)
        report_layout.addWidget(self.coach_report_output)

        intel_label = QLabel("3. Intelligence (metrics, tier, actions)")
        intel_label.setStyleSheet("font-weight: 600; margin-top: 8px;")
        report_layout.addWidget(intel_label)
        self.intelligence_report_output = QTextEdit()
        self.intelligence_report_output.setReadOnly(True)
        self.intelligence_report_output.setPlaceholderText(
            "Category comparison, predicted tier (A/B/C), and metric-driven actions appear here."
        )
        self.intelligence_report_output.setMinimumHeight(200)
        report_layout.addWidget(self.intelligence_report_output)

        report_group.setLayout(report_layout)
        layout.addWidget(report_group, 1)
        self.results_text = self.coach_report_output  # legacy helper methods

        # Optional: audio upload → transcribe → same coach report
        upload_group = QGroupBox("Optional: upload audio (transcribe → coach)")
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

        self.analyze_btn = QPushButton("Transcribe & generate coach report")
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

        self.setLayout(layout)
        self._coach_report_thread = None
        self._full_analysis_thread = None
        self._ingest_thread = None
        self._ensure_button_labels_visible()
        self.refresh_library_tree()

    def _ensure_button_labels_visible(self):
        """Black readable labels on standard QPushButton (Coach tab)."""
        style = """
            QPushButton {
                color: #000000;
                background-color: #F5F5F5;
                border: 1px solid #BDBDBD;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 13px;
                font-weight: 500;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: #E8E8E8;
                border: 1px solid #999999;
            }
            QPushButton:disabled {
                color: #666666;
                background-color: #EEEEEE;
            }
        """
        for btn in self.findChildren(QPushButton):
            btn.setStyleSheet(style)

    def _current_category_id(self) -> str:
        if hasattr(self, "category_combo"):
            data = self.category_combo.currentData()
            if data:
                return str(data)
        return _load_saved_intelligence_category()

    def _current_episode_title(self) -> str:
        if hasattr(self, "episode_title_input"):
            t = (self.episode_title_input.text() or "").strip()
            if t:
                return t
        return "Studio recording"

    def _current_show_title(self) -> str:
        if hasattr(self, "show_title_input"):
            return (self.show_title_input.text() or "").strip()
        return ""

    def _current_author(self) -> str:
        if hasattr(self, "author_input"):
            return (self.author_input.text() or "").strip()
        return ""

    def refresh_library_tree(self):
        if not hasattr(self, "library_tree"):
            return
        try:
            from backend.library import get_library_tree, list_pending_queue
        except ImportError:
            return
        tree = get_library_tree()
        pending = list_pending_queue()
        self.library_tree.clear()
        for cat_node in tree:
            cat_item = QTreeWidgetItem([str(cat_node.get("category", ""))])
            for auth in cat_node.get("authors") or []:
                auth_item = QTreeWidgetItem([str(auth.get("author", ""))])
                cat_item.addChild(auth_item)
                for show in auth.get("shows") or []:
                    n = show.get("episode_count", 0)
                    show_item = QTreeWidgetItem(
                        [str(show.get("title", "")), f"{n} episode(s)"]
                    )
                    auth_item.addChild(show_item)
                    for ep in show.get("episodes") or []:
                        title = str(ep.get("title") or "Episode")
                        when = str(ep.get("created_at") or "")[:10]
                        show_item.addChild(QTreeWidgetItem([title, when]))
            self.library_tree.addTopLevelItem(cat_item)
        self.library_tree.expandAll()
        if hasattr(self, "library_status"):
            self.library_status.setText(
                f"Library: {sum(len(a.get('shows') or []) for c in tree for a in c.get('authors') or [])} show(s). "
                f"Weekly queue: {len(pending)} pending."
            )

    def add_episode_to_weekly_queue(self):
        try:
            from backend.library import enqueue_episode
        except ImportError as e:
            QMessageBox.warning(self, "Library", f"Library module unavailable: {e}")
            return

        category = self._current_category_id()
        show_title = self._current_show_title() or "Untitled show"
        author = self._current_author() or "Unknown"
        episode_title = self._current_episode_title()

        source_type = ""
        source_ref = ""
        if self._last_ingest_source:
            source_type = self._last_ingest_source.get("source_type", "")
            source_ref = self._last_ingest_source.get("source_ref", "")
        url = (self.youtube_url_input.text() or "").strip() if hasattr(
            self, "youtube_url_input"
        ) else ""
        if not source_ref and url:
            source_type, source_ref = "youtube", url
        if not source_ref:
            paste = self.transcript_input.toPlainText().strip()
            if len(paste) >= 80:
                source_type, source_ref = "paste", paste
        if not source_ref:
            QMessageBox.warning(
                self,
                "Weekly queue",
                "Import a YouTube URL / file, or paste a transcript, then add to queue.",
            )
            return

        try:
            result = enqueue_episode(
                source_type=source_type,
                source_ref=source_ref,
                category=category,
                show_title=show_title,
                author=author,
                episode_title=episode_title,
            )
        except Exception as e:
            QMessageBox.warning(self, "Weekly queue", str(e))
            return

        dup = result.get("duplicate")
        self.library_status.setText(
            f"{'Already queued' if dup else 'Added to weekly queue'} "
            f"(#{result.get('queue_id')}). Run batch when ready."
        )
        self.refresh_library_tree()

    def run_weekly_batch(self):
        if self._batch_thread and self._batch_thread.isRunning():
            return
        self.run_batch_btn.setEnabled(False)
        self.add_to_queue_btn.setEnabled(False)
        self.batch_progress.setVisible(True)
        self.batch_progress.setRange(0, 0)
        self.library_status.setText("Running weekly batch…")
        self._batch_thread = WeeklyBatchThread()
        self._batch_thread.batch_complete.connect(
            self._on_weekly_batch_complete, Qt.ConnectionType.QueuedConnection
        )
        self._batch_thread.error_occurred.connect(
            self._on_weekly_batch_error, Qt.ConnectionType.QueuedConnection
        )
        self._batch_thread.start()

    def _on_weekly_batch_complete(self, summary: dict):
        self.run_batch_btn.setEnabled(True)
        self.add_to_queue_btn.setEnabled(True)
        self.batch_progress.setVisible(False)
        ok = summary.get("processed", 0)
        fail = summary.get("failed", 0)
        self.library_status.setText(
            f"Batch {summary.get('label', '')}: {ok} processed, {fail} failed."
        )
        self.refresh_library_tree()
        if fail:
            QMessageBox.warning(
                self,
                "Weekly batch",
                f"Finished with {fail} failure(s). See library status.",
            )

    def _on_weekly_batch_error(self, err: str):
        self.run_batch_btn.setEnabled(True)
        self.add_to_queue_btn.setEnabled(True)
        self.batch_progress.setVisible(False)
        self.library_status.setText("Weekly batch failed.")
        QMessageBox.warning(self, "Weekly batch", err)

    def _start_full_analysis(self, transcript: str):
        category = self._current_category_id()
        title = self._current_episode_title()
        thread = FullEpisodeAnalysisThread(
            transcript,
            title=title,
            category=category,
        )
        thread.analysis_complete.connect(
            self._on_full_analysis_complete,
            Qt.ConnectionType.QueuedConnection,
        )
        thread.error_occurred.connect(
            self._on_full_analysis_error,
            Qt.ConnectionType.QueuedConnection,
        )
        self._full_analysis_thread = thread
        thread.start()

    def run_session_feedback_from_transcript(self, transcript: str):
        """Legacy hook if Studio tab is enabled — same as paste + analyze."""
        if hasattr(self, "transcript_input"):
            self.transcript_input.setPlainText((transcript or "").strip())
        self.generate_coach_from_transcript()

    def import_from_youtube_url(self):
        url = (self.youtube_url_input.text() or "").strip()
        if not url:
            QMessageBox.warning(self, "Import", "Paste a YouTube URL first.")
            return
        self._run_ingest("youtube", url)

    def import_transcript_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import transcript",
            "",
            "Text (*.txt *.md);;All files (*.*)",
        )
        if path:
            self._run_ingest("transcript_file", path)

    def import_audio_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import audio",
            "",
            "Audio (*.mp3 *.wav *.m4a *.flac *.ogg);;All files (*.*)",
        )
        if path:
            self._run_ingest("audio_file", path)

    def _run_ingest(self, mode: str, payload: str):
        if self._ingest_thread and self._ingest_thread.isRunning():
            self._ingest_thread.wait(3000)
        self.session_feedback_status.setText("Importing episode…")
        self.import_youtube_btn.setEnabled(False)
        self.import_transcript_btn.setEnabled(False)
        self.import_audio_btn.setEnabled(False)
        self._ingest_thread = EpisodeIngestThread(mode, payload)
        self._ingest_thread.ingest_complete.connect(
            self._on_ingest_complete, Qt.ConnectionType.QueuedConnection
        )
        self._ingest_thread.error_occurred.connect(
            self._on_ingest_error, Qt.ConnectionType.QueuedConnection
        )
        self._ingest_thread.start()

    def _on_ingest_complete(self, result: dict):
        self.import_youtube_btn.setEnabled(True)
        self.import_transcript_btn.setEnabled(True)
        self.import_audio_btn.setEnabled(True)
        tx = str(result.get("transcript") or "").strip()
        self.transcript_input.setPlainText(tx)
        if result.get("title") and hasattr(self, "episode_title_input"):
            self.episode_title_input.setText(str(result["title"]))
        st = str(result.get("source_type") or "")
        ref = str(result.get("source_ref") or "")
        if st and ref:
            self._last_ingest_source = {"source_type": st, "source_ref": ref}
        creator = str(result.get("creator") or "").strip()
        if creator and hasattr(self, "author_input") and not self.author_input.text().strip():
            self.author_input.setText(creator)
        warns = result.get("warnings") or []
        msg = f"Imported ({result.get('source_type', 'unknown')})."
        if warns:
            msg += " " + "; ".join(str(w) for w in warns[:2])
        self.session_feedback_status.setText(msg)

    def _on_ingest_error(self, err: str):
        self.import_youtube_btn.setEnabled(True)
        self.import_transcript_btn.setEnabled(True)
        self.import_audio_btn.setEnabled(True)
        self.session_feedback_status.setText("Import failed.")
        QMessageBox.warning(
            self,
            "Import failed",
            f"{err}\n\nFor YouTube: install yt-dlp (`pip install yt-dlp`). "
            "For ASR fallback: ffmpeg on PATH + OpenAI or local Whisper.",
        )

    def _on_full_analysis_complete(self, payload: dict):
        self.generate_coach_btn.setEnabled(True)
        self.coach_progress.setVisible(False)
        self.session_feedback_status.setText("Coach + intelligence ready.")
        coach = payload.get("coach") or {}
        intel = payload.get("intelligence") or {}
        episode_id = intel.get("episode_id")
        if episode_id:
            try:
                from backend.library.db import LibraryDB

                db = LibraryDB()
                db.init_schema()
                md = str(coach.get("markdown") or "").strip()
                if not md:
                    md = _format_coach_report_payload(coach)
                db.save_coach_report(
                    int(episode_id),
                    markdown=md,
                    report=coach if isinstance(coach, dict) else None,
                )
            except Exception:
                pass
        self.coach_report_output.setPlainText(_format_coach_report_payload(coach))
        intel_md = str(intel.get("markdown") or "").strip()
        if hasattr(self, "intelligence_report_output"):
            self.intelligence_report_output.setPlainText(
                intel_md or "(Intelligence report not generated.)"
            )

    def _on_full_analysis_error(self, err: str):
        self._on_session_feedback_error(err)

    def _on_session_feedback_error(self, err: str):
        self.generate_coach_btn.setEnabled(True)
        self.coach_progress.setVisible(False)
        self.session_feedback_status.setText("Analysis failed.")
        tip = (
            "Set OPENAI_API_KEY or SOAPBOXX_OLLAMA_MODEL in Settings, then try again."
        )
        msg = f"Could not complete analysis.\n\n{err}\n\n{tip}"
        self.coach_report_output.setPlainText(msg)
        if hasattr(self, "intelligence_report_output"):
            self.intelligence_report_output.setPlainText("")

    def generate_coach_from_transcript(self):
        """Generate coach report from text in transcript_input."""
        if not getattr(self, "_ui_initialized", False):
            self.init_ui()
            self._ui_initialized = True
        t = self.transcript_input.toPlainText().strip()
        if len(t) < 80:
            QMessageBox.warning(
                self,
                "Transcript too short",
                "Paste at least a few sentences of dialogue for meaningful coaching.",
            )
            return
        if self._coach_report_thread and self._coach_report_thread.isRunning():
            self._coach_report_thread.wait(2000)
        self.generate_coach_btn.setEnabled(False)
        self.coach_progress.setVisible(True)
        self.coach_progress.setRange(0, 0)
        if hasattr(self, "intelligence_report_output"):
            self.intelligence_report_output.clear()
        self.session_feedback_status.setText(
            "Generating coach report and intelligence analysis…"
        )
        self.coach_report_output.clear()
        if self._full_analysis_thread and self._full_analysis_thread.isRunning():
            self._full_analysis_thread.wait(2000)
        self._start_full_analysis(t)

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

        self.analysis_thread = EpisodeAnalysisThread(
            self.selected_file_path,
            "Episode Coach Report",
            category=self._current_category_id(),
            title=self._current_episode_title(),
        )
        self.analysis_thread.analysis_complete.connect(self.on_analysis_complete)
        self.analysis_thread.progress_updated.connect(self.analysis_progress.setValue)
        self.analysis_thread.error_occurred.connect(self.on_analysis_error)
        self.analysis_thread.start()

    def on_analysis_complete(self, results):
        """Handle transcribe + coach report completion."""
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Transcribe & generate coach report")
        self.analysis_progress.setVisible(False)

        md = results.get("markdown") or ""
        if not md and results.get("coach_report"):
            md = _format_coach_report_payload(results["coach_report"])
        transcript = results.get("transcript", "")
        if transcript and hasattr(self, "transcript_input"):
            self.transcript_input.setPlainText(transcript)
        self.coach_report_output.setPlainText(md or "(No coach report generated.)")
        intel_md = results.get("intelligence_markdown") or ""
        if not intel_md and results.get("intelligence"):
            intel_md = str(results["intelligence"].get("markdown") or "")
        if hasattr(self, "intelligence_report_output"):
            self.intelligence_report_output.setPlainText(
                intel_md or "(Intelligence report not generated.)"
            )
        self.session_feedback_status.setText("Coach + intelligence ready (from audio).")

        fname = results.get("file_name") or os.path.basename(
            results.get("file_path", "episode")
        )
        episode_item = QListWidgetItem(f"📁 {fname}")
        episode_item.setData(1, results)
        self.episodes_list.addItem(episode_item)

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
        """Show stored coach report (episode list click)."""
        md = results.get("markdown") or ""
        if not md and results.get("coach_report"):
            md = _format_coach_report_payload(results["coach_report"])
        if md:
            self.coach_report_output.setPlainText(md)
        transcript = results.get("transcript", "")
        if transcript and hasattr(self, "transcript_input"):
            self.transcript_input.setPlainText(transcript)

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
