import json
import os
import sys
import threading
import time
import traceback
from datetime import datetime

# Add backend to path - use absolute path for better compatibility
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(os.path.dirname(current_dir), "backend")
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
from PyQt6.QtCore import QThread, QTimer, pyqtSignal, Qt
from PyQt6.QtWidgets import (QComboBox, QFrame, QGridLayout, QGroupBox,
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

        BACKEND_AVAILABLE = True
        print("✅ Backend imported using alternative method")
    except ImportError as e2:
        print(f"Alternative import also failed: {e2}")
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
    """Thread for monitoring audio levels"""

    level_updated = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.is_monitoring = False
        self.last_update_time = 0
        self.update_interval = 0.1  # Update every 100ms to prevent overflow

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
            with sd.InputStream(
                callback=audio_callback, 
                channels=1, 
                samplerate=16000,
                blocksize=1024,  # Larger block size
                latency='high'   # Higher latency for stability
            ):
                while self.is_monitoring:
                    time_module.sleep(0.05)  # Shorter sleep time for responsiveness

        except ImportError:
            print("sounddevice not available for audio level monitoring")
        except Exception as e:
            print(f"Audio level monitoring error: {e}")

    def start_monitoring(self):
        """Start audio level monitoring"""
        self.is_monitoring = True
        self.last_update_time = 0
        self.start()

    def stop_monitoring(self):
        """Stop audio level monitoring"""
        self.is_monitoring = False
        if self.isRunning():
            self.wait()


class RecordingThread(QThread):
    """Thread for handling recording operations"""

    transcript_updated = pyqtSignal(str)
    feedback_updated = pyqtSignal(dict)
    status_updated = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, core, transcription_service="openai"):
        super().__init__()
        self.core = core
        self.transcription_service = transcription_service
        self.is_recording = False

    def run(self):
        """Start recording"""
        try:
            self.is_recording = True
            self.status_updated.emit("Recording started...")

            # Start recording
            if self.core.start_recording("SoapBoxx Session"):
                self.status_updated.emit("Recording in progress...")

                # Simulate recording for 10 seconds (for demo)
                for i in range(10):
                    if not self.is_recording:
                        break
                    time.sleep(1)
                    self.status_updated.emit(f"Recording... {10-i}s remaining")

                # Stop recording
                if self.is_recording:
                    results = self.core.stop_recording()
                    self.status_updated.emit("Processing results...")

                    # Emit results
                    if results.get("transcript"):
                        self.transcript_updated.emit(results["transcript"])
                    if results.get("feedback"):
                        self.feedback_updated.emit(results["feedback"])

                    self.status_updated.emit("Recording completed!")
            else:
                self.error_occurred.emit("Failed to start recording")

        except Exception as e:
            self.error_occurred.emit(f"Recording error: {str(e)}")
        finally:
            self.is_recording = False

    def stop_recording(self):
        """Stop recording"""
        self.is_recording = False
        if self.core.is_recording:
            self.core.stop_recording()


class SoapBoxxTab(QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.core = None
        self.transcriber = None
        self.audio_level_thread = None
        self.recording_thread = None
        self.obs_websocket = None
        self.last_audio_update = 0
        self.audio_update_interval = 0.1  # Update UI every 100ms
        self.setup_backend()

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
        transcript_header = QLabel("📝 Live Transcript")
        transcript_header.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold; 
            color: #2C3E50;
            margin-bottom: 15px;
        """)
        transcript_layout.addWidget(transcript_header)

        # Transcript text area with modern styling
        self.transcript_text = QTextEdit()
        self.transcript_text.setPlaceholderText("Transcript will appear here as you record...")
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

        # Set up scroll area
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        self.setLayout(layout)

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
            else:
                # Try to add default device
                try:
                    default_device = sd.default.device[0]  # Get default input device
                    self.device_combo.addItem(f"Default Device (ID: {default_device})")
                    print(f"✅ Using default device (ID: {default_device})")
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

    def test_microphone(self):
        """Test the selected microphone"""
        try:
            import numpy as np
            import sounddevice as sd

            device_name = self.device_combo.currentText()
            if (
                "Error" in device_name
                or "not available" in device_name
                or "Loading" in device_name
            ):
                QMessageBox.warning(self, "Error", "No valid microphone selected")
                return

            # Start audio monitoring if not already running
            if self.audio_level_thread is None or not self.audio_level_thread.isRunning():
                self.start_audio_monitoring()
            else:
                print("Audio monitoring already running")

            # Show test message
            self.status_label.setText("Testing microphone...")
            self.status_label.setStyleSheet("color: #FFC107; font-weight: bold; padding: 5px 10px; background: #FFF3CD; border-radius: 4px;")
            
            # Enable the test button to show it's working
            self.test_mic_btn.setEnabled(False)
            self.test_mic_btn.setText("🎤 Testing...")
            
            # Re-enable after 3 seconds
            QTimer.singleShot(3000, self._finish_microphone_test)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Microphone test failed: {str(e)}")
            print(f"Microphone test error: {e}")

    def _finish_microphone_test(self):
        """Finish the microphone test"""
        self.test_mic_btn.setEnabled(True)
        self.test_mic_btn.setText("🎤 Test Microphone")
        self.status_label.setText("Microphone test completed")
        self.status_label.setStyleSheet("color: #28A745; font-weight: bold; padding: 5px 10px; background: #D4EDDA; border-radius: 4px;")
        
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
        """Start audio level monitoring"""
        try:
            # Stop any existing monitoring first
            if self.audio_level_thread and self.audio_level_thread.isRunning():
                self.audio_level_thread.stop_monitoring()
                self.audio_level_thread.wait()  # Wait for thread to finish
            
            # Only start if not already running
            if self.audio_level_thread is None or not self.audio_level_thread.isRunning():
                self.audio_level_thread = AudioLevelThread()
                self.audio_level_thread.level_updated.connect(self.update_audio_level)
                self.audio_level_thread.start_monitoring()
                print("✅ Audio level monitoring started")
        except Exception as e:
            print(f"Failed to start audio monitoring: {e}")

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
            if self.audio_level_thread and self.audio_level_thread.isRunning():
                self.audio_level_thread.stop_monitoring()
                print("✅ Audio level monitoring stopped")
        except Exception as e:
            print(f"Error stopping audio monitoring: {e}")
        
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
                self.config_status.setText(f"✅ Configured (API: {api_key[:8]}...)")
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
        if not self.core:
            QMessageBox.warning(self, "Error", "Backend not available")
            return

        try:
            # Clear previous results
            self.transcript_text.clear()
            self.feedback_text.clear()

            # Get selected service and ensure core is using it
            service = self.service_combo.currentText()
            self.core.set_transcription_service(service)

            # Start recording thread
            self.recording_thread = RecordingThread(self.core, service)
            self.recording_thread.transcript_updated.connect(self.update_transcript)
            self.recording_thread.feedback_updated.connect(self.update_feedback)
            self.recording_thread.status_updated.connect(self.update_status)
            self.recording_thread.error_occurred.connect(self.handle_error)

            self.recording_thread.start()

            # Update UI
            self.record_button.setText("Recording...")
            self.record_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            # self.progress_bar.setVisible(True) # Removed progress bar as it's not in the new UI
            # self.progress_bar.setRange(0, 10) # Removed progress bar as it's not in the new UI

        except Exception as e:
            self.handle_error(f"Failed to start recording: {str(e)}")

    def stop_recording(self):
        """Stop recording"""
        if self.recording_thread:
            self.recording_thread.stop_recording()
            self.recording_thread.wait()

        # Update UI
        self.record_button.setText("Start Recording")
        self.record_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        # self.progress_bar.setVisible(False) # Removed progress bar as it's not in the new UI
        self.status_label.setText("Ready")

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
        """Handle errors"""
        self.status_label.setText(f"Error: {error}")
        self.status_label.setStyleSheet("font-weight: bold; color: red;")
        self.record_button.setText("Start Recording")
        self.record_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        # self.progress_bar.setVisible(False) # Removed progress bar as it's not in the new UI

        QMessageBox.critical(self, "Error", error)
