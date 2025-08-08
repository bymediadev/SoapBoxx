import json
import os
import sys
import threading
import time
import traceback
from datetime import datetime

# Add backend to path - handle separate frontend/backend folder structure
current_dir = os.path.dirname(os.path.abspath(__file__))  # frontend/
parent_dir = os.path.dirname(current_dir)  # root/
backend_dir = os.path.join(parent_dir, "backend")  # root/backend/
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
from PyQt6.QtCore import QThread, QTimer, pyqtSignal, Qt
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox,
                             QHBoxLayout, QLabel, QMessageBox, QProgressBar,
                             QPushButton, QSlider, QTextEdit, QVBoxLayout,
                             QWidget, QScrollArea)

# Load environment variables from .env if not already loaded
load_dotenv()

# Try to import OBS WebSocket
try:
    import websocket
    OBS_AVAILABLE = True
except ImportError:
    OBS_AVAILABLE = False
    print("OBS WebSocket not available. Install with: pip install websocket-client")

# Try to import backend modules
try:
    # Import using the package structure
    from backend.config import Config
    from backend.soapboxx_core import SoapBoxxCore
    from backend.transcriber import Transcriber
    from backend.tts_generator import TTSGenerator
    BACKEND_AVAILABLE = True
except ImportError as e:
    print(f"Backend not available: {e}")
    print(f"Backend directory: {backend_dir}")
    print(f"Current sys.path: {sys.path}")
    # Try alternative import method
    try:
        from config import Config
        from soapboxx_core import SoapBoxxCore
        from transcriber import Transcriber
        from tts_generator import TTSGenerator
        BACKEND_AVAILABLE = True
        print("✅ Backend imported using alternative method")
    except ImportError as e2:
        print(f"Alternative import also failed: {e2}")
        # Try one more time with explicit path
        try:
            sys.path.insert(0, backend_dir)
            from config import Config
            from soapboxx_core import SoapBoxxCore
            from transcriber import Transcriber
            from tts_generator import TTSGenerator
            BACKEND_AVAILABLE = True
            print("✅ Backend imported using explicit path method")
        except ImportError as e3:
            print(f"Explicit path import also failed: {e3}")
            BACKEND_AVAILABLE = False


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
                ModernButton:disabled {
                    background: #E9ECEF;
                    color: #6C757D;
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
                ModernButton:disabled {
                    background: #E9ECEF;
                    color: #6C757D;
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
                ModernButton:disabled {
                    background: #E9ECEF;
                    color: #6C757D;
                }
            """)


class AudioLevelThread(QThread):
    """Thread for monitoring audio levels with robust error handling"""

    level_updated = pyqtSignal(float)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.is_monitoring = False
        self.last_update_time = 0
        self.update_interval = 0.1  # Update every 100ms to prevent overflow
        self.audio_stream = None
        self.device_id = None

    def set_device(self, device_id):
        """Set the device ID to use for monitoring"""
        self.device_id = device_id

    def run(self):
        """Monitor audio levels"""
        try:
            import time as time_module
            import numpy as np
            import sounddevice as sd

            def audio_callback(indata, frames, time, status):
                if status:
                    if "input overflow" in str(status):
                        # Ignore input overflow warnings - they're common and not critical
                        return
                    elif "output underflow" in str(status):
                        # Ignore output underflow warnings
                        return
                    else:
                        print(f"Audio callback status: {status}")
                
                if self.is_monitoring:
                    current_time = time_module.time()
                    # Only update if enough time has passed to prevent overflow
                    if current_time - self.last_update_time >= self.update_interval:
                        try:
                            # Calculate RMS level with proper error handling
                            if indata is not None and len(indata) > 0:
                                level = np.sqrt(np.mean(indata**2))
                                self.level_updated.emit(float(level))
                                self.last_update_time = current_time
                        except Exception as e:
                            print(f"Error calculating audio level: {e}")

            # Use larger buffer size and lower sample rate to prevent overflow
            stream_params = {
                'callback': audio_callback, 
                'channels': 1, 
                'samplerate': 16000,
                'blocksize': 1024,  # Larger block size
                'latency': 'high'   # Higher latency for stability
            }
            
            # Add device selection if specified
            if self.device_id is not None:
                stream_params['device'] = self.device_id

            with sd.InputStream(**stream_params):
                while self.is_monitoring:
                    time_module.sleep(0.05)  # Shorter sleep time for responsiveness

        except ImportError as import_error:
            self.error_occurred.emit(f"Required audio libraries not available: {str(import_error)}")
        except Exception as e:
            self.error_occurred.emit(f"Audio monitoring failed: {str(e)}")
            import traceback
            traceback.print_exc()

    def start_monitoring(self):
        """Start audio level monitoring"""
        self.is_monitoring = True
        self.last_update_time = 0
        if not self.isRunning():
            self.start()

    def stop_monitoring(self):
        """Stop audio level monitoring and cleanup resources"""
        self.is_monitoring = False
        
        # Close audio stream if it exists
        if hasattr(self, 'audio_stream') and self.audio_stream:
            try:
                self.audio_stream.stop()
                self.audio_stream.close()
            except Exception as e:
                print(f"Error closing audio stream: {e}")
            finally:
                self.audio_stream = None
        
        # Wait for thread to finish
        if self.isRunning():
            self.wait(2000)  # Wait max 2 seconds




class RecordingThread(QThread):
    """Thread for handling continuous recording with live transcription"""

    transcript_updated = pyqtSignal(str)
    feedback_updated = pyqtSignal(dict)
    status_updated = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    audio_chunk_ready = pyqtSignal(bytes)  # Signal for audio chunks

    def __init__(self, core, transcription_service="openai"):
        super().__init__()
        self.core = core
        self.transcription_service = transcription_service
        self.is_recording = False
        self.audio_recorder = None
        self.transcription_buffer = ""
        self.last_transcription_time = 0
        self.transcription_interval = 2.0  # Transcribe every 2 seconds for more responsive experience
        self.audio_buffer = []  # Buffer for accumulating audio data
        self.min_audio_length = 1.0  # Minimum audio length in seconds before transcribing

    def run(self):
        """Start continuous recording with live transcription"""
        try:
            self.is_recording = True
            self.status_updated.emit("Initializing live recording...")

            # Import audio recorder
            try:
                from backend.audio_recorder import AudioRecorder
                self.audio_recorder = AudioRecorder()
            except ImportError as e:
                self.error_occurred.emit(f"Audio recorder not available: {e}")
                return

            # Start recording
            self.status_updated.emit("Starting live recording...")
            if not self.audio_recorder.start_recording():
                self.error_occurred.emit("Failed to start audio recording")
                return

            self.status_updated.emit("Live recording in progress... Speak now!")
            
            # Continuous recording loop
            start_time = time.time()
            last_chunk_time = start_time
            
            while self.is_recording:
                try:
                    # Get audio chunk
                    chunk = self.audio_recorder.get_chunk()
                    if chunk is not None:
                        current_time = time.time()
                        
                        # Add chunk to buffer with timestamp
                        self.audio_buffer.append((chunk, current_time))
                        
                        # Emit chunk for real-time processing
                        self.audio_chunk_ready.emit(chunk.tobytes())
                        
                        # Debug: Print chunk info occasionally
                        if len(self.audio_buffer) % 10 == 0:  # Every 10 chunks
                            print(f"🎵 Audio buffer: {len(self.audio_buffer)} chunks, latest: {chunk.shape}")
                        
                        # Check if we have enough audio to transcribe
                        if current_time - self.last_transcription_time >= self.transcription_interval:
                            # Get audio chunks from the last interval
                            recent_chunks = [chunk for chunk, timestamp in self.audio_buffer 
                                           if timestamp >= self.last_transcription_time]
                            
                            print(f"⏰ Transcription interval reached: {len(recent_chunks)} chunks ready")
                            
                            if recent_chunks and len(recent_chunks) > 0:
                                # Transcribe the recent audio
                                self._transcribe_accumulated_audio(recent_chunks)
                                self.last_transcription_time = current_time
                                
                                # Keep only recent chunks to prevent memory buildup
                                cutoff_time = current_time - 10.0  # Keep last 10 seconds
                                self.audio_buffer = [(chunk, timestamp) for chunk, timestamp in self.audio_buffer 
                                                   if timestamp >= cutoff_time]
                                print(f"🧹 Cleaned buffer: {len(self.audio_buffer)} chunks remaining")
                    else:
                        # No chunk available
                        if len(self.audio_buffer) % 50 == 0:  # Every 50 empty checks
                            print(f"⏳ Waiting for audio chunks... (buffer: {len(self.audio_buffer)} chunks)")
                    
                    time.sleep(0.05)  # Smaller delay for more responsive transcription
                    
                except Exception as chunk_error:
                    print(f"❌ Audio chunk error: {chunk_error}")
                    import traceback
                    traceback.print_exc()
                    continue

        except Exception as e:
            self.error_occurred.emit(f"Live recording error: {str(e)}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_recording = False
            if self.audio_recorder:
                self.audio_recorder.stop_recording()
                self.audio_recorder.cleanup()
            self.status_updated.emit("Live recording session ended")

    def _transcribe_accumulated_audio(self, audio_chunks):
        """Transcribe accumulated audio chunks"""
        try:
            if not audio_chunks:
                print("⚠️ No audio chunks to transcribe")
                return
                
            print(f"🎵 Transcribing {len(audio_chunks)} audio chunks...")
                
            # Combine audio chunks properly
            combined_audio = self._combine_audio_chunks(audio_chunks)
            if not combined_audio:
                print("⚠️ Failed to combine audio chunks")
                return
                
            print(f"🎵 Combined audio: {len(combined_audio)} bytes")
                
            # Create transcription thread
            self.transcription_thread = TranscriptionThread(
                combined_audio, 
                self.transcription_service, 
                "Live Recording"
            )
            self.transcription_thread.transcription_completed.connect(
                self._on_live_transcription_completed
            )
            self.transcription_thread.transcription_failed.connect(
                self._on_live_transcription_failed
            )
            self.transcription_thread.start()
            
        except Exception as e:
            print(f"❌ Live transcription error: {e}")
            import traceback
            traceback.print_exc()

    def _on_live_transcription_completed(self, transcript):
        """Handle completed live transcription"""
        if transcript and transcript.strip():
            # Append to existing transcript
            if self.transcription_buffer:
                self.transcription_buffer += " " + transcript
            else:
                self.transcription_buffer = transcript
            
            # Emit updated transcript
            self.transcript_updated.emit(self.transcription_buffer)
            self.status_updated.emit("Live transcription updated")

    def _on_live_transcription_failed(self, error):
        """Handle failed live transcription"""
        print(f"Live transcription failed: {error}")
        self.status_updated.emit(f"Transcription error: {error}")

    def stop_recording(self):
        """Stop continuous recording"""
        try:
            self.is_recording = False
            self.status_updated.emit("Stopping live recording...")
        except Exception as e:
            self.error_occurred.emit(f"Failed to stop recording: {str(e)}")

    def _combine_audio_chunks(self, chunks):
        """Combine audio chunks into a single audio data"""
        try:
            if not chunks:
                print("⚠️ No chunks to combine")
                return b""
            
            print(f"🔧 Combining {len(chunks)} audio chunks...")
            
            # Convert numpy arrays to bytes and concatenate
            combined_bytes = []
            total_samples = 0
            
            for i, chunk in enumerate(chunks):
                if chunk is not None:
                    # Convert numpy array to bytes
                    chunk_bytes = chunk.tobytes()
                    combined_bytes.append(chunk_bytes)
                    total_samples += len(chunk)
                    print(f"  Chunk {i}: {chunk.shape} -> {len(chunk_bytes)} bytes")
                else:
                    print(f"  Chunk {i}: None (skipped)")
            
            if combined_bytes:
                result = b"".join(combined_bytes)
                print(f"✅ Combined {len(combined_bytes)} chunks: {total_samples} samples -> {len(result)} bytes")
                return result
            else:
                print("⚠️ No valid chunks to combine")
                return b""
            
        except Exception as e:
            print(f"❌ Error combining audio chunks: {e}")
            import traceback
            traceback.print_exc()
            return b""


class SoapBoxxTab(QWidget):
    def __init__(self):
        super().__init__()
        self.core = None
        self.transcriber = None
        self.audio_level_thread = None
        self.recording_thread = None
        self.transcription_thread = None  # Add transcription thread
        self.obs_websocket = None
        self.last_audio_update = 0
        self.audio_update_interval = 0.1  # Update UI every 100ms
        # Guest questions state
        self.questions = []  # list of dicts: {"text": str, "status": "pending|approved|denied"}
        self._known_questions = set()
        # Defer timer creation until widget is shown
        self._questions_timer = None
        
        # Defer UI setup until widget is shown
        self._ui_initialized = False
        self._backend_initialized = False
        
        # Connect show event to initialize UI
        self.showEvent = self._on_show_event

    def _on_show_event(self, event):
        """Initialize UI when widget is first shown"""
        if not self._ui_initialized:
            print("🎨 SoapBoxxTab: Initializing UI...")
            self.setup_ui()
            self._ui_initialized = True
            print("✅ SoapBoxxTab: UI initialized")
        
        if not self._backend_initialized:
            print("🔧 SoapBoxxTab: Initializing backend...")
            self.setup_backend()
            self._backend_initialized = True
            print("✅ SoapBoxxTab: Backend initialized")
            
            # Initialize timer after backend is ready
            if self._questions_timer is None:
                self._questions_timer = QTimer(self)
                self._questions_timer.setInterval(2000)  # 2s
                self._questions_timer.timeout.connect(self._scan_transcript_for_questions)
                print("✅ SoapBoxxTab: Timer initialized")
            
            # Refresh devices after a short delay to ensure UI is fully loaded
            QTimer.singleShot(500, self.refresh_devices)
        
        # Call the original showEvent if it exists
        super().showEvent(event)

    def setup_ui(self):
        """Setup the user interface with modern design"""
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title with modern styling
        title = QLabel("🎤 SoapBoxx - Recording & Transcription")
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

        # Microphone Input Section - Modern Card Design
        mic_card = ModernCard()
        mic_layout = QVBoxLayout(mic_card)
        
        # Card header
        mic_header = QLabel("🎤 Microphone Input")
        mic_header.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold; 
            color: #2C3E50;
            margin-bottom: 15px;
        """)
        mic_layout.addWidget(mic_header)

        # Device selection with modern styling
        device_layout = QHBoxLayout()
        device_label = QLabel("Input Device:")
        device_label.setStyleSheet("font-weight: bold; color: #495057;")
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(300)
        self.device_combo.addItem("Loading devices...")
        self.device_combo.currentTextChanged.connect(self.on_device_changed)
        self.device_combo.setStyleSheet("""
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
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #6C757D;
            }
        """)
        device_layout.addWidget(device_label)
        device_layout.addWidget(self.device_combo)

        # Refresh devices button
        refresh_btn = ModernButton("🔄 Refresh", style="secondary")
        refresh_btn.clicked.connect(self.refresh_devices)
        refresh_btn.setMaximumWidth(120)
        device_layout.addWidget(refresh_btn)
        device_layout.addStretch()
        mic_layout.addLayout(device_layout)

        # Audio level meter with modern styling
        level_layout = QHBoxLayout()
        level_label = QLabel("Audio Level:")
        level_label.setStyleSheet("font-weight: bold; color: #495057;")
        self.audio_level_bar = QProgressBar()
        self.audio_level_bar.setRange(0, 100)
        self.audio_level_bar.setValue(0)
        self.audio_level_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
                background-color: #F8F9FA;
                height: 20px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00ff00, stop:0.5 #ffff00, stop:1 #ff0000);
                border-radius: 6px;
            }
        """)
        level_layout.addWidget(level_label)
        level_layout.addWidget(self.audio_level_bar)
        mic_layout.addLayout(level_layout)

        # Test microphone button
        self.test_mic_btn = ModernButton("🎤 Test Microphone", style="primary")
        self.test_mic_btn.clicked.connect(self.test_microphone)
        mic_layout.addWidget(self.test_mic_btn)

        scroll_layout.addWidget(mic_card)

        # OBS Integration Section - Modern Card Design
        obs_card = ModernCard()
        obs_layout = QVBoxLayout(obs_card)
        
        # Card header
        obs_header = QLabel("🎬 OBS Integration")
        obs_header.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold; 
            color: #2C3E50;
            margin-bottom: 15px;
        """)
        obs_layout.addWidget(obs_header)

        # OBS Status with modern styling
        obs_status_layout = QHBoxLayout()
        obs_status_label = QLabel("OBS Status:")
        obs_status_label.setStyleSheet("font-weight: bold; color: #495057;")
        self.obs_status = QLabel("Not Connected")
        self.obs_status.setStyleSheet("color: #DC3545; font-weight: bold; padding: 5px 10px; background: #F8D7DA; border-radius: 4px;")
        obs_status_layout.addWidget(obs_status_label)
        obs_status_layout.addWidget(self.obs_status)
        obs_status_layout.addStretch()
        obs_layout.addLayout(obs_status_layout)

        # OBS Connection button
        self.obs_connect_btn = ModernButton("🔗 Connect to OBS", style="primary")
        self.obs_connect_btn.clicked.connect(self.connect_to_obs)
        obs_layout.addWidget(self.obs_connect_btn)

        # OBS Controls
        obs_controls_layout = QHBoxLayout()
        self.obs_start_stream_btn = ModernButton("▶️ Start Stream", style="success")
        self.obs_start_stream_btn.clicked.connect(self.obs_start_stream)
        self.obs_start_stream_btn.setEnabled(False)
        obs_controls_layout.addWidget(self.obs_start_stream_btn)

        self.obs_stop_stream_btn = ModernButton("⏹️ Stop Stream", style="secondary")
        self.obs_stop_stream_btn.clicked.connect(self.obs_stop_stream)
        self.obs_stop_stream_btn.setEnabled(False)
        obs_controls_layout.addWidget(self.obs_stop_stream_btn)

        self.obs_start_recording_btn = ModernButton("🔴 Start Recording", style="success")
        self.obs_start_recording_btn.clicked.connect(self.obs_start_recording)
        self.obs_start_recording_btn.setEnabled(False)
        obs_controls_layout.addWidget(self.obs_start_recording_btn)

        self.obs_stop_recording_btn = ModernButton("⏹️ Stop Recording", style="secondary")
        self.obs_stop_recording_btn.clicked.connect(self.obs_stop_recording)
        self.obs_stop_recording_btn.setEnabled(False)
        obs_controls_layout.addWidget(self.obs_stop_recording_btn)

        obs_layout.addLayout(obs_controls_layout)
        scroll_layout.addWidget(obs_card)

        # Transcription Service Selection - Modern Card Design
        service_card = ModernCard()
        service_layout = QVBoxLayout(service_card)
        
        # Card header
        service_header = QLabel("🔧 Transcription Service")
        service_header.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold; 
            color: #2C3E50;
            margin-bottom: 15px;
        """)
        service_layout.addWidget(service_header)

        # Service selector with modern styling
        service_selector_layout = QHBoxLayout()
        service_label = QLabel("Service:")
        service_label.setStyleSheet("font-weight: bold; color: #495057;")
        self.service_combo = QComboBox()
        self.service_combo.addItems(["openai", "local", "assemblyai", "azure"])
        self.service_combo.currentTextChanged.connect(self.on_service_changed)
        self.service_combo.setStyleSheet("""
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
        service_selector_layout.addWidget(service_label)
        service_selector_layout.addWidget(self.service_combo)
        service_selector_layout.addStretch()
        service_layout.addLayout(service_selector_layout)

        # Service status with modern styling
        self.service_status = QLabel("Checking service...")
        self.service_status.setStyleSheet("color: #6C757D; padding: 5px 10px; background: #F8F9FA; border-radius: 4px;")
        service_layout.addWidget(self.service_status)

        scroll_layout.addWidget(service_card)

        # Recording Controls - Modern Card Design
        recording_card = ModernCard()
        recording_layout = QVBoxLayout(recording_card)
        
        # Card header
        recording_header = QLabel("🎙️ Recording Controls")
        recording_header.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold; 
            color: #2C3E50;
            margin-bottom: 15px;
        """)
        recording_layout.addWidget(recording_header)

        # Status indicators
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #28A745; font-weight: bold; padding: 5px 10px; background: #D4EDDA; border-radius: 4px;")
        status_layout.addWidget(self.status_label)

        # Configuration status
        self.config_status = QLabel("Checking configuration...")
        self.config_status.setStyleSheet("color: #6C757D; padding: 5px 10px; background: #F8F9FA; border-radius: 4px;")
        status_layout.addWidget(self.config_status)
        status_layout.addStretch()
        recording_layout.addLayout(status_layout)

        # Recording controls
        controls_layout = QHBoxLayout()
        self.record_button = ModernButton("🎙️ Start Recording", style="success")
        self.record_button.clicked.connect(self.toggle_recording)
        self.record_button.setEnabled(False)
        controls_layout.addWidget(self.record_button)

        self.stop_button = ModernButton("⏹️ Stop Recording", style="secondary")
        self.stop_button.clicked.connect(self.stop_recording)
        self.stop_button.setEnabled(False)
        controls_layout.addWidget(self.stop_button)

        controls_layout.addStretch()
        recording_layout.addLayout(controls_layout)

        scroll_layout.addWidget(recording_card)

        # Transcript Display - Modern Card Design
        transcript_card = ModernCard()
        transcript_layout = QVBoxLayout(transcript_card)
        
        # Card header
        transcript_header = QLabel("📝 Live Transcript & Speech-to-Text")
        transcript_header.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold;
            color: #2C3E50;
            margin-bottom: 15px;
        """)
        transcript_layout.addWidget(transcript_header)

        # STT Service Selection (integrated into transcript section)
        stt_service_layout = QHBoxLayout()
        stt_service_label = QLabel("STT Service:")
        stt_service_label.setStyleSheet("font-weight: bold; color: #495057;")
        self.stt_service_combo = QComboBox()
        self.stt_service_combo.addItems(["openai", "local", "azure", "assemblyai"])
        self.stt_service_combo.setCurrentText("openai")
        self.stt_service_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                font-size: 14px;
                background: white;
            }
            QComboBox:focus {
                border: 2px solid #3498DB;
            }
        """)
        stt_service_layout.addWidget(stt_service_label)
        stt_service_layout.addWidget(self.stt_service_combo)

        # STT Status
        self.stt_status_label = QLabel("Ready to transcribe speech")
        self.stt_status_label.setStyleSheet("color: #6C757D; font-style: italic; padding: 5px;")
        stt_service_layout.addWidget(self.stt_status_label)
        stt_service_layout.addStretch()
        transcript_layout.addLayout(stt_service_layout)

        # STT Controls (integrated into transcript section)
        stt_controls_layout = QHBoxLayout()
        
        # Upload Audio button
        self.upload_audio_btn = ModernButton("📁 Upload Audio", style="primary")
        self.upload_audio_btn.clicked.connect(self.upload_audio_for_transcription)
        self.upload_audio_btn.setMaximumWidth(200)
        stt_controls_layout.addWidget(self.upload_audio_btn)
        
        # Transcribe Recording button
        self.transcribe_recording_btn = ModernButton("🎙️ Transcribe Recording", style="secondary")
        self.transcribe_recording_btn.clicked.connect(self.transcribe_current_recording)
        self.transcribe_recording_btn.setMaximumWidth(200)
        self.transcribe_recording_btn.setEnabled(False)
        stt_controls_layout.addWidget(self.transcribe_recording_btn)
        
        # Cancel Transcription button
        self.cancel_transcription_btn = ModernButton("❌ Cancel", style="danger")
        self.cancel_transcription_btn.clicked.connect(self.cancel_transcription)
        self.cancel_transcription_btn.setMaximumWidth(120)
        self.cancel_transcription_btn.setEnabled(False)
        stt_controls_layout.addWidget(self.cancel_transcription_btn)
        
        # Clear button
        self.clear_stt_btn = ModernButton("🗑️ Clear", style="secondary")
        self.clear_stt_btn.clicked.connect(self.clear_stt_results)
        self.clear_stt_btn.setMaximumWidth(100)
        stt_controls_layout.addWidget(self.clear_stt_btn)
        
        stt_controls_layout.addStretch()
        transcript_layout.addLayout(stt_controls_layout)

        # Transcript text area with modern styling (now handles both live transcript and STT results)
        self.transcript_text = QTextEdit()
        self.transcript_text.setPlaceholderText("Live transcript will appear here as you record, or upload audio files for transcription...")
        self.transcript_text.setStyleSheet("""
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
        self.transcript_text.setMinimumHeight(200)
        transcript_layout.addWidget(self.transcript_text)

        scroll_layout.addWidget(transcript_card)

        # Text-to-Speech Section - Modern Card Design
        tts_card = ModernCard()
        tts_layout = QVBoxLayout(tts_card)
        
        # Card header
        tts_header = QLabel("🔊 Text-to-Speech")
        tts_header.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold;
            color: #2C3E50;
            margin-bottom: 15px;
        """)
        tts_layout.addWidget(tts_header)

        # TTS Service Selection
        tts_service_layout = QHBoxLayout()
        tts_service_label = QLabel("TTS Service:")
        tts_service_label.setStyleSheet("font-weight: bold; color: #495057;")
        self.tts_service_combo = QComboBox()
        self.tts_service_combo.addItems(["openai", "local", "google", "azure"])
        self.tts_service_combo.setCurrentText("openai")
        self.tts_service_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                font-size: 14px;
                background: white;
            }
            QComboBox:focus {
                border: 2px solid #3498DB;
            }
        """)
        tts_service_layout.addWidget(tts_service_label)
        tts_service_layout.addWidget(self.tts_service_combo)

        # Voice Selection
        voice_label = QLabel("Voice:")
        voice_label.setStyleSheet("font-weight: bold; color: #495057;")
        self.tts_voice_combo = QComboBox()
        self.tts_voice_combo.addItems(["alloy", "echo", "fable", "onyx", "nova", "shimmer"])
        self.tts_voice_combo.setCurrentText("alloy")
        self.tts_voice_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 2px solid #E0E0E0;
                border-radius: 6px;
                font-size: 14px;
                background: white;
            }
            QComboBox:focus {
                border: 2px solid #3498DB;
            }
        """)
        tts_service_layout.addWidget(voice_label)
        tts_service_layout.addWidget(self.tts_voice_combo)
        tts_service_layout.addStretch()
        tts_layout.addLayout(tts_service_layout)

        # TTS Controls
        tts_controls_layout = QHBoxLayout()
        
        # Generate TTS button
        self.generate_tts_btn = ModernButton("🔊 Generate Speech", style="primary")
        self.generate_tts_btn.clicked.connect(self.generate_tts_from_transcript)
        self.generate_tts_btn.setMaximumWidth(200)
        tts_controls_layout.addWidget(self.generate_tts_btn)
        
        # Play TTS button
        self.play_tts_btn = ModernButton("▶️ Play Audio", style="secondary")
        self.play_tts_btn.clicked.connect(self.play_tts_audio)
        self.play_tts_btn.setMaximumWidth(150)
        self.play_tts_btn.setEnabled(False)
        tts_controls_layout.addWidget(self.play_tts_btn)
        
        # Save TTS button
        self.save_tts_btn = ModernButton("💾 Save Audio", style="secondary")
        self.save_tts_btn.clicked.connect(self.save_tts_audio)
        self.save_tts_btn.setMaximumWidth(150)
        self.save_tts_btn.setEnabled(False)
        tts_controls_layout.addWidget(self.save_tts_btn)
        
        tts_controls_layout.addStretch()
        tts_layout.addLayout(tts_controls_layout)

        # TTS Status
        self.tts_status_label = QLabel("Ready to generate speech from transcript")
        self.tts_status_label.setStyleSheet("color: #6C757D; font-style: italic; padding: 5px;")
        tts_layout.addWidget(self.tts_status_label)

        scroll_layout.addWidget(tts_card)

        # Feedback Display - Modern Card Design
        feedback_card = ModernCard()
        feedback_layout = QVBoxLayout(feedback_card)
        
        # Card header
        feedback_header = QLabel("💡 AI Feedback")
        feedback_header.setStyleSheet("""
            font-size: 18px; 
                font-weight: bold;
            color: #2C3E50;
            margin-bottom: 15px;
        """)
        feedback_layout.addWidget(feedback_header)

        # Feedback text area with modern styling
        self.feedback_text = QTextEdit()
        self.feedback_text.setPlaceholderText("AI feedback will appear here after recording...")
        self.feedback_text.setStyleSheet("""
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
        self.feedback_text.setMinimumHeight(150)
        feedback_layout.addWidget(self.feedback_text)

        scroll_layout.addWidget(feedback_card)

        # Guest Questions Approval - Modern Card Design
        questions_card = ModernCard()
        questions_layout = QVBoxLayout(questions_card)

        # Card header
        questions_header = QLabel("👥 Guest Questions Approval")
        questions_header.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold; 
            color: #2C3E50;
            margin-bottom: 15px;
        """)
        questions_layout.addWidget(questions_header)

        # Input area to add questions (one per line)
        self.questions_input = QTextEdit()
        self.questions_input.setPlaceholderText("Enter questions here (one per line) or paste from your notes...")
        self.questions_input.setStyleSheet("""
            QTextEdit {
                border: 2px solid #E0E0E0;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
                background: white;
            }
            QTextEdit:focus {
                border: 2px solid #3498DB;
            }
        """)
        self.questions_input.setMinimumHeight(120)
        questions_layout.addWidget(self.questions_input)

        # Buttons row
        q_btn_row = QHBoxLayout()
        # Auto extract toggle
        self.auto_extract_checkbox = QCheckBox("Auto-extract from transcript")
        self.auto_extract_checkbox.setChecked(True)
        self.auto_extract_checkbox.toggled.connect(self._toggle_auto_extract)
        q_btn_row.addWidget(self.auto_extract_checkbox)

        self.add_questions_btn = ModernButton("➕ Add Questions", style="primary")
        self.add_questions_btn.clicked.connect(self._add_questions_from_input)
        q_btn_row.addWidget(self.add_questions_btn)

        self.add_from_transcript_btn = ModernButton("📝 Add from Transcript", style="secondary")
        self.add_from_transcript_btn.clicked.connect(self._add_questions_from_transcript)
        q_btn_row.addWidget(self.add_from_transcript_btn)

        self.approve_all_btn = ModernButton("✅ Approve All", style="success")
        self.approve_all_btn.clicked.connect(lambda: self._bulk_update_questions_status("approved"))
        q_btn_row.addWidget(self.approve_all_btn)

        self.deny_all_btn = ModernButton("❌ Deny All", style="secondary")
        self.deny_all_btn.clicked.connect(lambda: self._bulk_update_questions_status("denied"))
        q_btn_row.addWidget(self.deny_all_btn)

        q_btn_row.addStretch()
        questions_layout.addLayout(q_btn_row)

        # List area for questions with approval controls
        self.questions_list_container = QWidget()
        self.questions_list_layout = QVBoxLayout(self.questions_list_container)
        self.questions_list_layout.setSpacing(8)
        self.questions_list_layout.setContentsMargins(0, 0, 0, 0)
        questions_layout.addWidget(self.questions_list_container)

        # Export/Copy row
        export_row = QHBoxLayout()
        self.export_questions_btn = ModernButton("💾 Export JSON", style="secondary")
        self.export_questions_btn.clicked.connect(self._export_questions_json)
        export_row.addWidget(self.export_questions_btn)

        self.copy_questions_btn = ModernButton("📋 Copy", style="secondary")
        self.copy_questions_btn.clicked.connect(self._copy_questions_to_clipboard)
        export_row.addWidget(self.copy_questions_btn)

        export_row.addStretch()
        questions_layout.addLayout(export_row)

        scroll_layout.addWidget(questions_card)

        # Set up scroll area
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        self.setLayout(layout)
        # Start background extraction
        self._questions_timer.start()

        # Initialize OBS connection
        self.obs_connected = False
        self.obs_websocket = None

    def refresh_devices(self):
        """Refresh available audio input devices"""
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            input_devices = []

            print(f"Found {len(devices)} total devices")

            for i, device in enumerate(devices):
                # Check if device has input capabilities
                max_inputs = device.get("max_inputs", 0)
                device_name = device.get("name", f"Device {i}")
                print(f"Device {i}: {device_name} (max_inputs: {max_inputs})")

                if max_inputs > 0:
                    input_devices.append(f"{device_name} (ID: {i})")

            self.device_combo.clear()
            if input_devices:
                self.device_combo.addItems(input_devices)
                print(f"✅ Found {len(input_devices)} input devices")
                # Select the first device by default
                if self.device_combo.count() > 0:
                    self.device_combo.setCurrentIndex(0)
                    # Start audio monitoring after device selection
                    QTimer.singleShot(100, self._start_audio_monitoring_if_needed)
            else:
                # Try to add default device
                try:
                    default_device = sd.default.device[0]  # Get default input device
                    self.device_combo.addItem(f"Default Device (ID: {default_device})")
                    print(f"✅ Using default device (ID: {default_device})")
                    # Start audio monitoring after device selection
                    QTimer.singleShot(100, self._start_audio_monitoring_if_needed)
                except:
                    self.device_combo.addItem("No input devices found")
                    print("⚠️ No input devices found")

        except ImportError:
            self.device_combo.clear()
            self.device_combo.addItem("sounddevice not available")
            print("❌ sounddevice not available")
        except Exception as e:
            self.device_combo.clear()
            self.device_combo.addItem(f"Error: {str(e)}")
            print(f"❌ Audio device detection error: {e}")
            traceback.print_exc()

    def _start_audio_monitoring_if_needed(self):
        """Start audio monitoring if not already running"""
        try:
            if (self.audio_level_thread is None or not self.audio_level_thread.isRunning()) and self.device_combo.count() > 0:
                device_name = self.device_combo.currentText()
                if device_name and "Error" not in device_name and "not available" not in device_name and "Loading" not in device_name:
                    print(f"🎤 Starting audio monitoring for device: {device_name}")
                    self.start_audio_monitoring()
        except Exception as e:
            print(f"Error starting audio monitoring: {e}")

    def on_device_changed(self, device_name):
        """Handle device selection change"""
        if (
            device_name
            and "Error" not in device_name
            and "not available" not in device_name
            and "Loading" not in device_name
        ):
            self.status_label.setText(f"Selected: {device_name}")
            self.status_label.setStyleSheet("font-weight: bold; color: blue;")
            print(f"🎤 Selected device: {device_name}")
            
            # Restart audio monitoring with the new device
            QTimer.singleShot(100, self._restart_audio_monitoring_for_device)
    
    def _restart_audio_monitoring_for_device(self):
        """Restart audio monitoring for the newly selected device"""
        try:
            if self.audio_level_thread and self.audio_level_thread.isRunning():
                self.audio_level_thread.stop_monitoring()
                self.audio_level_thread.wait(1000)  # Wait for thread to finish
            
            # Start monitoring with the new device
            self.start_audio_monitoring()
        except Exception as e:
            print(f"Error restarting audio monitoring for new device: {e}")

    def test_microphone(self):
        """Test the selected microphone with robust error handling"""
        # Prevent double-clicks during testing
        if not self.test_mic_btn.isEnabled():
            return
            
        try:
            import numpy as np
            import sounddevice as sd

            device_name = self.device_combo.currentText()
            if (
                "Error" in device_name
                or "not available" in device_name
                or "Loading" in device_name
                or not device_name.strip()
            ):
                self._show_user_friendly_error("No valid microphone selected", "Please select a valid microphone device first.")
                return

            # Disable button immediately to prevent double-clicks
            self.test_mic_btn.setEnabled(False)
            self.test_mic_btn.setText("🎤 Testing...")
            
            # Show test message
            self.status_label.setText("Testing microphone...")
            self.status_label.setStyleSheet("color: #FFC107; font-weight: bold; padding: 5px 10px; background: #FFF3CD; border-radius: 4px;")

            # Start audio monitoring if not already running
            if self.audio_level_thread is None or not self.audio_level_thread.isRunning():
                try:
                    self.start_audio_monitoring()
                except Exception as monitor_error:
                    self._show_user_friendly_error("Audio monitoring failed", f"Could not start audio monitoring: {str(monitor_error)}")
                    self._finish_microphone_test()
                return
            else:
                print("Audio monitoring already running")
            
            # Re-enable after 3 seconds
            QTimer.singleShot(3000, self._finish_microphone_test)

        except ImportError as e:
            self._show_user_friendly_error("Missing Audio Libraries", "Required audio libraries are not installed. Please install sounddevice and numpy.")
            self._finish_microphone_test()
        except Exception as e:
            self._show_user_friendly_error("Microphone Test Failed", f"An unexpected error occurred: {str(e)}")
            print(f"Microphone test error: {e}")
            import traceback
            traceback.print_exc()
            self._finish_microphone_test()

    def _finish_microphone_test(self):
        """Finish the microphone test"""
        self.test_mic_btn.setEnabled(True)
        self.test_mic_btn.setText("🎤 Test Microphone")
        self.status_label.setText("Microphone test completed")
        self.status_label.setStyleSheet("color: #28A745; font-weight: bold; padding: 5px 10px; background: #D4EDDA; border-radius: 4px;")
    
    def _show_user_friendly_error(self, title: str, message: str, detailed_error: str = None):
        """Show user-friendly error messages with optional technical details"""
        try:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            
            if detailed_error:
                msg_box.setDetailedText(f"Technical details:\n{detailed_error}")
            
            msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg_box.exec()
            
            # Update status label to show error state
            self.status_label.setText(f"Error: {title}")
            self.status_label.setStyleSheet("color: #DC3545; font-weight: bold; padding: 5px 10px; background: #F8D7DA; border-radius: 4px;")

        except Exception as e:
            # Fallback to console if UI error display fails
            print(f"Error displaying error message: {e}")
            print(f"Original error - {title}: {message}")
            if detailed_error:
                print(f"Details: {detailed_error}")
        
        # Stop audio monitoring after test
        self.stop_audio_monitoring()

    def connect_to_obs(self):
        """Connect to OBS WebSocket"""
        if not OBS_AVAILABLE:
            QMessageBox.warning(
                self,
                "OBS Integration",
                "OBS WebSocket not available. Install with: pip install websocket-client",
            )
            return

        try:
            # OBS WebSocket connection
            obs_url = "ws://localhost:4455"  # Default OBS WebSocket URL

            def on_message(ws, message):
                try:
                    data = json.loads(message)
                    if data.get("op") == 1:  # Identify response
                        self.obs_connected = True
                        self.obs_status.setText("Connected")
                        self.obs_status.setStyleSheet(
                            "color: green; font-weight: bold;"
                        )
                        self.obs_connect_btn.setText("🔗 Connected")
                        self.obs_connect_btn.setEnabled(False)

                        # Enable OBS controls
                        self.obs_start_stream_btn.setEnabled(True)
                        self.obs_stop_stream_btn.setEnabled(True)
                        self.obs_start_recording_btn.setEnabled(True)
                        self.obs_stop_recording_btn.setEnabled(True)

                        print("✅ Connected to OBS")
                except Exception as e:
                    print(f"OBS message error: {e}")

            def on_error(ws, error):
                print(f"OBS WebSocket error: {error}")
                self.obs_status.setText("Connection Failed")
                self.obs_status.setStyleSheet("color: red; font-weight: bold;")

            def on_close(ws, close_status_code, close_msg):
                print("OBS WebSocket connection closed")
                self.obs_connected = False
                self.obs_status.setText("Disconnected")
                self.obs_status.setStyleSheet("color: red; font-weight: bold;")
                self.obs_connect_btn.setText("🔗 Connect to OBS")
                self.obs_connect_btn.setEnabled(True)

                # Disable OBS controls
                self.obs_start_stream_btn.setEnabled(False)
                self.obs_stop_stream_btn.setEnabled(False)
                self.obs_start_recording_btn.setEnabled(False)
                self.obs_stop_recording_btn.setEnabled(False)

            def on_open(ws):
                print("OBS WebSocket connection opened")
                # Send identify request
                identify_request = {
                    "op": 1,
                    "d": {
                        "rpcVersion": 1,
                        "authentication": "",
                        "eventSubscriptions": 0,
                    },
                }
                ws.send(json.dumps(identify_request))

            # Create WebSocket connection
            self.obs_websocket = websocket.WebSocketApp(
                obs_url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )

            # Start WebSocket connection in a separate thread
            obs_thread = threading.Thread(target=self.obs_websocket.run_forever)
            obs_thread.daemon = True
            obs_thread.start()

            self.obs_status.setText("Connecting...")
            self.obs_status.setStyleSheet("color: orange; font-weight: bold;")

        except Exception as e:
            QMessageBox.critical(
                self,
                "OBS Connection Error",
                f"Failed to connect to OBS: {str(e)}\n\nMake sure OBS is running with WebSocket enabled.",
            )
            print(f"OBS connection error: {e}")

    def obs_start_stream(self):
        """Start OBS streaming"""
        if not self.obs_connected or not self.obs_websocket:
            QMessageBox.warning(self, "OBS", "Not connected to OBS")
            return

        try:
            request = {"op": 6, "d": {"requestType": "StartStreaming"}}
            self.obs_websocket.send(json.dumps(request))
            print("🎬 Started OBS streaming")
        except Exception as e:
            print(f"OBS start stream error: {e}")

    def obs_stop_stream(self):
        """Stop OBS streaming"""
        if not self.obs_connected or not self.obs_websocket:
            QMessageBox.warning(self, "OBS", "Not connected to OBS")
            return

        try:
            request = {"op": 6, "d": {"requestType": "StopStreaming"}}
            self.obs_websocket.send(json.dumps(request))
            print("🎬 Stopped OBS streaming")
        except Exception as e:
            print(f"OBS stop stream error: {e}")

    def obs_start_recording(self):
        """Start OBS recording"""
        if not self.obs_connected or not self.obs_websocket:
            QMessageBox.warning(self, "OBS", "Not connected to OBS")
            return

        try:
            request = {"op": 6, "d": {"requestType": "StartRecord"}}
            self.obs_websocket.send(json.dumps(request))
            print("🎥 Started OBS recording")
        except Exception as e:
            print(f"OBS start recording error: {e}")

    def obs_stop_recording(self):
        """Stop OBS recording"""
        if not self.obs_connected or not self.obs_websocket:
            QMessageBox.warning(self, "OBS", "Not connected to OBS")
            return

        try:
            request = {"op": 6, "d": {"requestType": "StopRecord"}}
            self.obs_websocket.send(json.dumps(request))
            print("🎥 Stopped OBS recording")
        except Exception as e:
            print(f"OBS stop recording error: {e}")

    def start_audio_monitoring(self):
        """Start audio level monitoring with robust error handling"""
        try:
            # Import check before creating thread
            try:
                import sounddevice as sd
                import numpy as np
            except ImportError as e:
                raise ImportError(f"Required audio libraries not available: {e}")

            # Stop any existing monitoring first
            if self.audio_level_thread and self.audio_level_thread.isRunning():
                self.audio_level_thread.stop_monitoring()
                self.audio_level_thread.wait(2000)  # Wait max 2 seconds for thread to finish
            
            # Only start if not already running
            if self.audio_level_thread is None or not self.audio_level_thread.isRunning():
                self.audio_level_thread = AudioLevelThread()
                self.audio_level_thread.level_updated.connect(self.update_audio_level)
                self.audio_level_thread.error_occurred.connect(self._handle_audio_thread_error)
                
                # Set device if available
                device_name = self.device_combo.currentText()
                if device_name and "Error" not in device_name and "not available" not in device_name and "Loading" not in device_name:
                    # Extract device ID from the device name
                    try:
                        if "(ID:" in device_name:
                            device_id_str = device_name.split("(ID:")[1].split(")")[0].strip()
                            device_id = int(device_id_str)
                            self.audio_level_thread.set_device(device_id)
                            print(f"🎤 Set device ID: {device_id} for monitoring")
                    except (ValueError, IndexError) as e:
                        print(f"Could not parse device ID from '{device_name}': {e}")
                        # Continue without device selection (will use default)
                
            self.audio_level_thread.start_monitoring()
            print("✅ Audio level monitoring started")
        except ImportError as e:
            print(f"❌ Audio libraries not available: {e}")
            self._show_user_friendly_error("Audio Libraries Missing", "Required audio libraries are not installed. Please install sounddevice and numpy.")
            raise
        except Exception as e:
            print(f"❌ Failed to start audio monitoring: {e}")
            self._show_user_friendly_error("Audio Monitoring Failed", f"Could not start audio monitoring: {str(e)}")
            raise
    
    def _handle_audio_thread_error(self, error_message: str):
        """Handle errors from audio monitoring thread"""
        print(f"❌ Audio thread error: {error_message}")
        self.status_label.setText("Audio monitoring error")
        self.status_label.setStyleSheet("color: #DC3545; font-weight: bold; padding: 5px 10px; background: #F8D7DA; border-radius: 4px;")
        
        # Try to restart audio monitoring after error
        QTimer.singleShot(2000, self._restart_audio_monitoring)
    
    def _restart_audio_monitoring(self):
        """Attempt to restart audio monitoring after an error"""
        try:
            print("🔄 Attempting to restart audio monitoring...")
            self.start_audio_monitoring()
        except Exception as e:
            print(f"❌ Failed to restart audio monitoring: {e}")
            self.status_label.setText("Audio monitoring disabled")
            self.status_label.setStyleSheet("color: #DC3545; font-weight: bold; padding: 5px 10px; background: #F8D7DA; border-radius: 4px;")

    def update_audio_level(self, level):
        """Update the audio level display with throttling"""
        try:
            import time
            current_time = time.time()
            
            # Only update UI if enough time has passed
            if current_time - self.last_audio_update >= self.audio_update_interval:
                # Convert level to percentage (0-100) with smoothing
                level_percent = min(100, int(level * 1000))
                
                # Apply smoothing to prevent jittery display
                current_value = self.audio_level_bar.value()
                smoothed_value = int(0.7 * current_value + 0.3 * level_percent)
                
                self.audio_level_bar.setValue(smoothed_value)
                self.last_audio_update = current_time
                
        except Exception as e:
            print(f"Error updating audio level: {e}")

    def stop_audio_monitoring(self):
        """Stop audio level monitoring"""
        try:
            if self.audio_level_thread and self.audio_level_thread.isRunning():
                self.audio_level_thread.stop_monitoring()
                print("✅ Audio level monitoring stopped")
        except Exception as e:
            print(f"Error stopping audio monitoring: {e}")

    def closeEvent(self, event):
        """Clean up when closing"""
        try:
            # Stop audio monitoring
            if self.audio_level_thread and self.audio_level_thread.isRunning():
                self.audio_level_thread.stop_monitoring()
                print("✅ Audio level monitoring stopped")
        except Exception as e:
            print(f"Error stopping audio monitoring: {e}")
        
        try:
            # Stop transcription thread
            if self.transcription_thread and self.transcription_thread.isRunning():
                self.transcription_thread.stop_transcription()
                self.transcription_thread.wait(2000)  # Wait up to 2 seconds
                print("✅ Transcription thread stopped")
        except Exception as e:
            print(f"Error stopping transcription thread: {e}")
        
        super().closeEvent(event)

    def setup_backend(self):
        """Setup backend integration"""
        if not BACKEND_AVAILABLE:
            self.config_status.setText("❌ Backend not available")
            self.record_button.setEnabled(False)
            return

        try:
            # Initialize core with default service
            default_service = self.service_combo.currentText()
            self.core = SoapBoxxCore(transcription_service=default_service)

            # Check configuration
            config = Config()
            api_key = config.get_openai_api_key()

            if api_key:
                self.config_status.setText("✅ OpenAI API configured")
                self.record_button.setEnabled(True)
            else:
                self.config_status.setText("⚠️ OpenAI API key not configured")
                self.record_button.setEnabled(True)  # Enable for local transcription

            # Initialize transcriber and check service status
            self.transcriber = self.core.transcriber
            self.on_service_changed(default_service)

        except Exception as e:
            self.config_status.setText(f"❌ Backend error: {str(e)}")
            self.record_button.setEnabled(False)

    def on_service_changed(self, service):
        """Handle transcription service change"""
        try:
            if self.core:
                # Update the core's transcription service
                self.core.set_transcription_service(service)
                # Get the transcriber from the core
                self.transcriber = self.core.transcriber

            if service == "local":
                # Check local Whisper status
                if self.transcriber:
                    model_info = self.transcriber.get_local_model_info()

                    if model_info.get("available"):
                        self.service_status.setText(
                            f"✅ Local Whisper ({model_info.get('model_size', 'unknown')})"
                        )
                        self.service_status.setStyleSheet("color: green;")
                    else:
                        self.service_status.setText(
                            f"❌ Local Whisper: {model_info.get('error', 'Unknown error')}"
                        )
                        self.service_status.setStyleSheet("color: red;")
                else:
                    self.service_status.setText(
                        "❌ Local Whisper: Transcriber not available"
                    )
                    self.service_status.setStyleSheet("color: red;")

            elif service == "openai":
                # Check OpenAI status
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    self.service_status.setText("✅ OpenAI Whisper API")
                    self.service_status.setStyleSheet("color: green;")
                else:
                    self.service_status.setText("❌ OpenAI API key not configured")
                    self.service_status.setStyleSheet("color: red;")

            elif service == "assemblyai":
                # Check AssemblyAI status
                api_key = os.getenv("ASSEMBLYAI_API_KEY")
                if api_key:
                    self.service_status.setText("✅ AssemblyAI")
                    self.service_status.setStyleSheet("color: green;")
                else:
                    self.service_status.setText("❌ AssemblyAI API key not configured")
                    self.service_status.setStyleSheet("color: red;")

            elif service == "azure":
                # Check Azure status
                api_key = os.getenv("AZURE_SPEECH_KEY")
                if api_key:
                    self.service_status.setText("✅ Azure Speech Services")
                    self.service_status.setStyleSheet("color: green;")
                else:
                    self.service_status.setText("❌ Azure Speech key not configured")
                    self.service_status.setStyleSheet("color: red;")

        except Exception as e:
            self.service_status.setText(f"❌ Service error: {str(e)}")
            self.service_status.setStyleSheet("color: red;")

    def toggle_recording(self):
        """Toggle recording on/off"""
        if not self.recording_thread or not self.recording_thread.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """Start recording"""
        # Prevent double-clicks
        if not self.record_button.isEnabled():
            return
            
        if not self.core:
            self._show_user_friendly_error("Backend Not Available", "The backend service is not available. Please check the application setup.")
            return

        try:
            # Clear previous results
            self.transcript_text.clear()
            self.feedback_text.clear()

            # Get selected service and ensure core is using it
            service = self.service_combo.currentText()
            self.core.set_transcription_service(service)

            # Initialize recording thread
            self.recording_thread = RecordingThread(self.core, service)
            self.recording_thread.transcript_updated.connect(self.update_transcript)
            self.recording_thread.feedback_updated.connect(self.update_feedback)
            self.recording_thread.status_updated.connect(self.update_status)
            self.recording_thread.error_occurred.connect(self.handle_error)

            # Start recording
            self.recording_thread.start()

            # Update UI
            self.record_button.setText("⏹️ Stop Recording")
            self.record_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #DC3545, stop:1 #C82333);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 12px 24px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #E74C3C, stop:1 #DC3545);
                }
            """)
            self.record_button.setEnabled(True)

            # Enable transcribe recording button
            self.transcribe_recording_btn.setEnabled(True)

        except Exception as e:
            self._show_user_friendly_error("Recording Error", f"Failed to start recording: {str(e)}")
            self._reset_recording_ui()
    
    def _reset_recording_ui(self):
        """Reset recording UI to initial state"""
        self.record_button.setEnabled(True)
        self.record_button.setText("🎙️ Start Recording")
        self.record_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #28A745, stop:1 #20C997);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #20C997, stop:1 #17A2B8);
            }
        """)
        self.transcribe_recording_btn.setEnabled(False)

    def stop_recording(self):
        """Stop recording"""
        try:
            if self.recording_thread and self.recording_thread.isRunning():
                self.recording_thread.stop_recording()
                self.recording_thread.wait(5000)  # Wait up to 5 seconds
                
                # Store the recording data for STT
                if hasattr(self.core, 'current_session') and self.core.current_session:
                    if hasattr(self.core.current_session, 'audio_chunks') and self.core.current_session.audio_chunks:
                        # Combine audio chunks
                        combined_audio = self._combine_audio_chunks(self.core.current_session.audio_chunks)
                        self.current_recording_data = combined_audio
                        print(f"✅ Recording data stored for STT: {len(combined_audio)} bytes")
                
                # Update UI
                self.record_button.setText("🎙️ Start Recording")
                self.record_button.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #28A745, stop:1 #20C997);
                        color: white;
                        border: none;
                        border-radius: 8px;
                        padding: 12px 24px;
                        font-weight: bold;
                        font-size: 14px;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #20C997, stop:1 #17A2B8);
                    }
                """)
                self.record_button.setEnabled(True)
                
                # Enable transcribe recording button if we have data
                if hasattr(self, 'current_recording_data') and self.current_recording_data:
                    self.transcribe_recording_btn.setEnabled(True)
                
        except Exception as e:
            self._show_user_friendly_error("Stop Recording Error", f"Failed to stop recording: {str(e)}")
            self._reset_recording_ui()

    def _combine_audio_chunks(self, chunks):
        """Combine audio chunks into a single audio data"""
        try:
            if not chunks:
                return b""
            
            # Simple concatenation for now - in a real implementation you'd want proper audio format handling
            combined = b"".join(chunks)
            return combined
            
        except Exception as e:
            print(f"Error combining audio chunks: {e}")
            return b""

    def update_transcript(self, transcript):
        """Update transcript display"""
        self.transcript_text.setText(transcript)

    def update_feedback(self, feedback):
        """Update feedback display"""
        if isinstance(feedback, dict):
            feedback_text = ""
            if "listener_feedback" in feedback:
                feedback_text += (
                    f"Listener Feedback:\n{feedback['listener_feedback']}\n\n"
                )
            if "coaching_suggestions" in feedback:
                feedback_text += f"Coaching Suggestions:\n"
                for suggestion in feedback["coaching_suggestions"]:
                    feedback_text += f"• {suggestion}\n"
            self.feedback_text.setText(feedback_text)
        else:
            self.feedback_text.setText(str(feedback))

    # ----- Guest Questions Panel Logic -----
    def _add_questions_from_input(self):
        """Parse input box lines and add to the questions list."""
        text = (self.questions_input.toPlainText() or "").strip()
        if not text:
            QMessageBox.information(self, "Guest Questions", "Please enter at least one question.")
            return
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        added = 0
        for ln in lines:
            added += self._append_question_row(ln)
        if added:
            self.questions_input.clear()

    def _add_questions_from_transcript(self):
        """Attempt to extract question-like sentences from current transcript."""
        transcript = (self.transcript_text.toPlainText() or "").strip()
        if not transcript:
            QMessageBox.information(self, "No Transcript", "Transcript is empty. Record or paste transcript first.")
            return
        # Simple heuristic: split on '?'
        parts = transcript.split('?')
        candidates = []
        for p in parts:
            p = p.strip()
            if len(p) >= 8:  # basic length filter
                candidates.append(p + '?')
        if not candidates:
            QMessageBox.information(self, "No Questions Found", "Couldn't find question-like sentences in the transcript.")
            return
        added = 0
        for q in candidates:
            added += self._append_question_row(q)
        QMessageBox.information(self, "Guest Questions", f"Added {added} question(s) from transcript.")

    def _scan_transcript_for_questions(self):
        """Periodic scan to auto-extract questions in near real time."""
        if not self.auto_extract_checkbox.isChecked():
            return
        transcript = (self.transcript_text.toPlainText() or "").strip()
        if not transcript:
            return
        parts = transcript.split('?')
        for p in parts:
            p = p.strip()
            if len(p) < 8:
                continue
            q = p + '?'
            if q not in self._known_questions:
                if self._append_question_row(q):
                    self._known_questions.add(q)

    def _append_question_row(self, question_text: str) -> int:
        """Create a row widget for the question with approve/deny controls."""
        # Prevent duplicates
        if any(q.get("text") == question_text for q in self.questions):
            return 0
        row = QHBoxLayout()
        label = QLabel(question_text)
        label.setWordWrap(True)
        label.setStyleSheet("color: #2C3E50;")
        row.addWidget(label, stretch=1)

        # Status label
        status_label = QLabel("pending")
        status_label.setStyleSheet("color: #6C757D; font-weight: bold; padding: 4px 8px; background: #F8F9FA; border-radius: 4px;")
        row.addWidget(status_label)

        # Approve / Deny buttons
        approve_btn = ModernButton("Approve", style="success")
        deny_btn = ModernButton("Deny", style="secondary")
        row.addWidget(approve_btn)
        row.addWidget(deny_btn)

        # Handlers
        def set_status(new_status: str):
            for q in self.questions:
                if q["text"] == question_text:
                    q["status"] = new_status
                    break
            if new_status == "approved":
                status_label.setText("approved")
                status_label.setStyleSheet("color: white; font-weight: bold; padding: 4px 8px; background: #28A745; border-radius: 4px;")
            elif new_status == "denied":
                status_label.setText("denied")
                status_label.setStyleSheet("color: white; font-weight: bold; padding: 4px 8px; background: #DC3545; border-radius: 4px;")
            else:
                status_label.setText("pending")
                status_label.setStyleSheet("color: #6C757D; font-weight: bold; padding: 4px 8px; background: #F8F9FA; border-radius: 4px;")

        approve_btn.clicked.connect(lambda: set_status("approved"))
        deny_btn.clicked.connect(lambda: set_status("denied"))

        # Add to layout and model
        container = QFrame()
        container.setFrameStyle(QFrame.Shape.NoFrame)
        container.setStyleSheet("QFrame { background: white; border: 1px solid #E9ECEF; border-radius: 8px; padding: 8px; }")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.addLayout(row)
        self.questions_list_layout.addWidget(container)

        self.questions.append({"text": question_text, "status": "pending"})
        return 1

    def _bulk_update_questions_status(self, status: str):
        """Set status for all questions and refresh labels."""
        for i in range(self.questions_list_layout.count()):
            item = self.questions_list_layout.itemAt(i).widget()
            if not item:
                continue
            # The first child layout contains [label, status_label, approve, deny]
            lay = item.layout().itemAt(0).layout() if item.layout() else None
            if not lay:
                continue
            status_label = lay.itemAt(1).widget()
            if isinstance(status_label, QLabel):
                if status == "approved":
                    status_label.setText("approved")
                    status_label.setStyleSheet("color: white; font-weight: bold; padding: 4px 8px; background: #28A745; border-radius: 4px;")
                elif status == "denied":
                    status_label.setText("denied")
                    status_label.setStyleSheet("color: white; font-weight: bold; padding: 4px 8px; background: #DC3545; border-radius: 4px;")
                else:
                    status_label.setText("pending")
                    status_label.setStyleSheet("color: #6C757D; font-weight: bold; padding: 4px 8px; background: #F8F9FA; border-radius: 4px;")
        # Update backing model
        for q in self.questions:
            q["status"] = status

    def _export_questions_json(self):
        """Export current questions with statuses to JSON in Exports/ folder."""
        try:
            from pathlib import Path
            export_dir = Path("Exports")
            export_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = export_dir / f"guest_questions_{ts}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(self.questions, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "Exported", f"Saved questions to:\n{out_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export questions: {e}")

    def _copy_questions_to_clipboard(self):
        """Copy questions JSON to clipboard for external sharing."""
        try:
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(json.dumps(self.questions, indent=2, ensure_ascii=False))
            self.status_label.setText("Questions copied to clipboard")
            self.status_label.setStyleSheet("color: #28A745; font-weight: bold;")
        except Exception as e:
            QMessageBox.critical(self, "Copy Error", f"Failed to copy questions: {e}")

    def _toggle_auto_extract(self, checked: bool):
        """Start/stop the periodic question extraction."""
        if checked:
            self._questions_timer.start()
        else:
            self._questions_timer.stop()

    def update_status(self, status):
        """Update status display"""
        self.status_label.setText(status)
        # if "Recording..." in status and "remaining" in status: # Removed progress bar logic
        #     try:
        #         remaining = int(status.split()[-2].replace("s", ""))
        #         self.progress_bar.setValue(10 - remaining)
        #     except:
        #         pass

    def handle_error(self, error):
        """Handle errors with user-friendly messages"""
        self._show_user_friendly_error("Error", str(error))

    # TTS Methods
    def generate_tts_from_transcript(self):
        """Generate speech from the current transcript"""
        try:
            # Get transcript text
            transcript = self.transcript_text.toPlainText().strip()
            if not transcript:
                self._show_user_friendly_error("No Transcript", "Please record or paste a transcript first.")
                return
            
            # Get TTS settings
            service = self.tts_service_combo.currentText()
            voice = self.tts_voice_combo.currentText()
            
            # Update status
            self.tts_status_label.setText("Generating speech...")
            self.tts_status_label.setStyleSheet("color: #FFC107; font-weight: bold; padding: 5px; background: #FFF3CD; border-radius: 4px;")
            self.generate_tts_btn.setEnabled(False)
            
            # Create TTS generator
            try:
                tts_generator = TTSGenerator(service=service)
                status = tts_generator.get_service_status()
                
                if not status["available"]:
                    self._show_user_friendly_error("TTS Service Unavailable", 
                                                  f"The {service} TTS service is not available or not configured.")
                    self._reset_tts_ui()
                    return
                
                # Generate speech
                timestamp = int(time.time())
                output_path = f"tts_output_{timestamp}.mp3"
                
                result = tts_generator.generate_speech(transcript, voice, output_path)
                
                if result and os.path.exists(result):
                    self.current_tts_file = result
                    self.tts_status_label.setText(f"✅ Speech generated successfully: {os.path.basename(result)}")
                    self.tts_status_label.setStyleSheet("color: #28A745; font-weight: bold; padding: 5px; background: #D4EDDA; border-radius: 4px;")
                    
                    # Enable play and save buttons
                    self.play_tts_btn.setEnabled(True)
                    self.save_tts_btn.setEnabled(True)
                    
                    print(f"✅ TTS generated: {result}")
                else:
                    self._show_user_friendly_error("TTS Generation Failed", "Failed to generate speech. Please check your TTS service configuration.")
                    self._reset_tts_ui()
                    
            except Exception as e:
                self._show_user_friendly_error("TTS Error", f"Error generating speech: {str(e)}")
                self._reset_tts_ui()
                
        except Exception as e:
            self._show_user_friendly_error("TTS Error", f"Unexpected error: {str(e)}")
            self._reset_tts_ui()
    
    def play_tts_audio(self):
        """Play the generated TTS audio"""
        try:
            if not hasattr(self, 'current_tts_file') or not self.current_tts_file:
                self._show_user_friendly_error("No Audio", "No TTS audio file available. Please generate speech first.")
                return
            
            if not os.path.exists(self.current_tts_file):
                self._show_user_friendly_error("File Not Found", "TTS audio file not found. Please regenerate speech.")
                return
            
            # Try to play the audio file
            try:
                import subprocess
                import platform
                
                system = platform.system()
                if system == "Windows":
                    os.startfile(self.current_tts_file)
                elif system == "Darwin":  # macOS
                    subprocess.run(["open", self.current_tts_file])
                else:  # Linux
                    subprocess.run(["xdg-open", self.current_tts_file])
                
                self.tts_status_label.setText("🎵 Playing audio...")
                self.tts_status_label.setStyleSheet("color: #17A2B8; font-weight: bold; padding: 5px; background: #D1ECF1; border-radius: 4px;")
                
            except Exception as e:
                self._show_user_friendly_error("Playback Error", f"Could not play audio file: {str(e)}")
                
        except Exception as e:
            self._show_user_friendly_error("Playback Error", f"Error playing audio: {str(e)}")
    
    def save_tts_audio(self):
        """Save the TTS audio file to a user-selected location"""
        try:
            if not hasattr(self, 'current_tts_file') or not self.current_tts_file:
                self._show_user_friendly_error("No Audio", "No TTS audio file available. Please generate speech first.")
                return
            
            if not os.path.exists(self.current_tts_file):
                self._show_user_friendly_error("File Not Found", "TTS audio file not found. Please regenerate speech.")
                return
            
            # Import QFileDialog for file saving
            from PyQt6.QtWidgets import QFileDialog
            
            # Get save location
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save TTS Audio",
                f"tts_audio_{int(time.time())}.mp3",
                "Audio Files (*.mp3 *.wav *.m4a);;All Files (*)"
            )
            
            if file_path:
                # Copy the file to the selected location
                import shutil
                shutil.copy2(self.current_tts_file, file_path)
                
                self.tts_status_label.setText(f"✅ Audio saved to: {os.path.basename(file_path)}")
                self.tts_status_label.setStyleSheet("color: #28A745; font-weight: bold; padding: 5px; background: #D4EDDA; border-radius: 4px;")
                
                print(f"✅ TTS audio saved: {file_path}")
            else:
                self.tts_status_label.setText("Save cancelled")
                self.tts_status_label.setStyleSheet("color: #6C757D; font-style: italic; padding: 5px;")
                
        except Exception as e:
            self._show_user_friendly_error("Save Error", f"Error saving audio file: {str(e)}")
    
    def _reset_tts_ui(self):
        """Reset TTS UI to initial state"""
        self.tts_status_label.setText("Ready to generate speech from transcript")
        self.tts_status_label.setStyleSheet("color: #6C757D; font-style: italic; padding: 5px;")
        self.generate_tts_btn.setEnabled(True)
        self.play_tts_btn.setEnabled(False)
        self.save_tts_btn.setEnabled(False)

    # STT Methods
    def upload_audio_for_transcription(self):
        """Upload an audio file for transcription"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            
            # Get audio file
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Audio File",
                "",
                "Audio Files (*.mp3 *.wav *.m4a *.flac *.ogg);;All Files (*)"
            )
            
            if not file_path:
                return
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > 25 * 1024 * 1024:  # 25MB limit
                self._show_user_friendly_error("File Too Large", 
                                              f"Audio file is too large ({file_size / (1024*1024):.1f}MB). Maximum size is 25MB.")
                return
            
            # Update status
            self.stt_status_label.setText("Reading audio file...")
            self.stt_status_label.setStyleSheet("color: #FFC107; font-weight: bold; padding: 5px; background: #FFF3CD; border-radius: 4px;")
            self.upload_audio_btn.setEnabled(False)
            
            # Read audio file
            try:
                with open(file_path, 'rb') as f:
                    audio_data = f.read()
                
                # Transcribe the audio
                self._transcribe_audio_data(audio_data, f"Uploaded file: {os.path.basename(file_path)}")
                
            except Exception as e:
                self._show_user_friendly_error("File Read Error", f"Could not read audio file: {str(e)}")
                self._reset_stt_ui()
                
        except Exception as e:
            self._show_user_friendly_error("Upload Error", f"Error uploading audio file: {str(e)}")
            self._reset_stt_ui()
    
    def transcribe_current_recording(self):
        """Transcribe the current recording if available"""
        try:
            if not hasattr(self, 'current_recording_data') or not self.current_recording_data:
                self._show_user_friendly_error("No Recording", "No recording available. Please record audio first.")
                return
            
            # Transcribe the current recording
            self._transcribe_audio_data(self.current_recording_data, "Current recording")
            
        except Exception as e:
            self._show_user_friendly_error("Transcription Error", f"Error transcribing recording: {str(e)}")
            self._reset_stt_ui()
    
    def _transcribe_audio_data(self, audio_data: bytes, source_name: str = "Audio"):
        """Transcribe audio data using the selected service in background thread"""
        try:
            # Get selected service
            service = self.stt_service_combo.currentText()
            
            # Update status
            self.stt_status_label.setText(f"Transcribing {source_name} using {service}...")
            self.stt_status_label.setStyleSheet("color: #FFC107; font-weight: bold; padding: 5px; background: #FFF3CD; border-radius: 4px;")
            
            # Disable buttons during transcription
            self.upload_audio_btn.setEnabled(False)
            self.transcribe_recording_btn.setEnabled(False)
            self.cancel_transcription_btn.setEnabled(True)  # Enable cancel button
            
            # Stop any existing transcription thread
            if self.transcription_thread and self.transcription_thread.isRunning():
                self.transcription_thread.stop_transcription()
                self.transcription_thread.wait(2000)  # Wait up to 2 seconds
            
            # Create and start transcription thread
            self.transcription_thread = TranscriptionThread(audio_data, service, source_name)
            self.transcription_thread.transcription_completed.connect(self._on_transcription_completed)
            self.transcription_thread.transcription_failed.connect(self._on_transcription_failed)
            self.transcription_thread.status_updated.connect(self._on_transcription_status_updated)
            self.transcription_thread.start()
            
        except Exception as e:
            self._show_user_friendly_error("Transcription Error", f"Unexpected error: {str(e)}")
            self._reset_stt_ui()
    
    def _on_transcription_completed(self, result: str):
        """Handle successful transcription completion"""
        try:
            # Display results in the main transcript area
            self.transcript_text.setText(result)
            self.stt_status_label.setText(f"✅ Transcription completed")
            self.stt_status_label.setStyleSheet("color: #28A745; font-weight: bold; padding: 5px; background: #D4EDDA; border-radius: 4px;")
            
            # Enable clear button
            self.clear_stt_btn.setEnabled(True)
            
            # Re-enable buttons and disable cancel
            self.upload_audio_btn.setEnabled(True)
            self.cancel_transcription_btn.setEnabled(False)
            if hasattr(self, 'current_recording_data') and self.current_recording_data:
                self.transcribe_recording_btn.setEnabled(True)
            
            print(f"✅ STT completed: {len(result)} characters")
            
        except Exception as e:
            self._show_user_friendly_error("Transcription Error", f"Error handling transcription result: {str(e)}")
            self._reset_stt_ui()
    
    def _on_transcription_failed(self, error_message: str):
        """Handle transcription failure"""
        try:
            self._show_user_friendly_error("Transcription Failed", error_message)
            self._reset_stt_ui()
        except Exception as e:
            print(f"Error handling transcription failure: {e}")
            self._reset_stt_ui()
    
    def _on_transcription_status_updated(self, status: str):
        """Handle transcription status updates"""
        try:
            self.stt_status_label.setText(status)
        except Exception as e:
            print(f"Error updating transcription status: {e}")
    
    def clear_stt_results(self):
        """Clear transcript results"""
        try:
            self.transcript_text.clear()
            self.stt_status_label.setText("Ready to transcribe speech")
            self.stt_status_label.setStyleSheet("color: #6C757D; font-style: italic; padding: 5px;")
            self.clear_stt_btn.setEnabled(False)
            
        except Exception as e:
            print(f"Error clearing transcript results: {e}")
    
    def _reset_stt_ui(self):
        """Reset STT UI to initial state"""
        self.stt_status_label.setText("Ready to transcribe speech")
        self.stt_status_label.setStyleSheet("color: #6C757D; font-style: italic; padding: 5px;")
        self.upload_audio_btn.setEnabled(True)
        self.transcribe_recording_btn.setEnabled(False)
        self.cancel_transcription_btn.setEnabled(False)
        self.clear_stt_btn.setEnabled(False)

    def cancel_transcription(self):
        """Cancel the current transcription operation"""
        try:
            if self.transcription_thread and self.transcription_thread.isRunning():
                self.transcription_thread.stop_transcription()
                self.transcription_thread.wait(2000)  # Wait up to 2 seconds
                print("✅ Transcription cancelled")
                self.stt_status_label.setText("Transcription cancelled")
                self.stt_status_label.setStyleSheet("color: #DC3545; font-weight: bold; padding: 5px; background: #F8D7DA; border-radius: 4px;")
                self._reset_stt_ui()
        except Exception as e:
            print(f"Error cancelling transcription: {e}")
            self._reset_stt_ui()


class TranscriptionThread(QThread):
    """Thread for handling transcription operations without freezing the UI"""

    transcription_completed = pyqtSignal(str)
    transcription_failed = pyqtSignal(str)
    status_updated = pyqtSignal(str)

    def __init__(self, audio_data: bytes, service: str, source_name: str = "Audio"):
        super().__init__()
        self.audio_data = audio_data
        self.service = service
        self.source_name = source_name
        self.is_transcribing = False
        self.timeout = 30  # Reduced timeout for live transcription

    def run(self):
        """Run transcription in background thread with timeout"""
        try:
            self.is_transcribing = True
            self.status_updated.emit(f"Transcribing {self.source_name} using {self.service}...")
            
            # Validate audio data
            if not self.audio_data or len(self.audio_data) == 0:
                self.transcription_failed.emit("No audio data to transcribe")
                return
                
            print(f"🎵 Transcribing {len(self.audio_data)} bytes of audio data using {self.service}")
            
            # Create transcriber
            transcriber = Transcriber(service=self.service)
            status = transcriber.get_available_services()
            
            if self.service not in status:
                self.transcription_failed.emit(f"The {self.service} transcription service is not available or not configured.")
                return
            
            # Transcribe audio with timeout protection
            self.status_updated.emit("Making API call...")
            
            # Use a timer to implement timeout
            import time
            start_time = time.time()
            
            # Start transcription in a way that can be interrupted
            result = None
            try:
                result = transcriber.transcribe(self.audio_data)
                
                # Check if we've exceeded timeout
                if time.time() - start_time > self.timeout:
                    self.transcription_failed.emit("Transcription timeout - the operation took too long. Please try again.")
                    return
                    
            except Exception as e:
                if "timeout" in str(e).lower():
                    self.transcription_failed.emit("Transcription timeout - the API call took too long. Please try again.")
                else:
                    raise e
            
            if result and not result.startswith("Error:"):
                print(f"✅ Transcription completed: {result[:100]}...")
                self.transcription_completed.emit(result)
            else:
                error_msg = result if result else "Transcription failed with unknown error"
                print(f"❌ Transcription failed: {error_msg}")
                self.transcription_failed.emit(error_msg)
                
        except Exception as e:
            print(f"❌ Transcription error: {str(e)}")
            self.transcription_failed.emit(f"Transcription error: {str(e)}")
        finally:
            self.is_transcribing = False

    def stop_transcription(self):
        """Stop transcription"""
        self.is_transcribing = False
