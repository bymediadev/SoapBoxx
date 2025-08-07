import os
import sys
import threading
import time
import traceback
import json
from datetime import datetime

# Add backend to path - use absolute path for better compatibility
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(os.path.dirname(current_dir), 'backend')
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
from PyQt6.QtCore import QTimer, pyqtSignal, QThread
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QTextEdit, 
                             QVBoxLayout, QWidget, QProgressBar, QMessageBox,
                             QComboBox, QGroupBox, QGridLayout, QSlider, QFrame)

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
    from backend.soapboxx_core import SoapBoxxCore
    from backend.config import Config
    from backend.transcriber import Transcriber
    BACKEND_AVAILABLE = True
except ImportError as e:
    print(f"Backend not available: {e}")
    print(f"Backend directory: {backend_dir}")
    print(f"Current sys.path: {sys.path}")
    # Try alternative import method
    try:
        from soapboxx_core import SoapBoxxCore
        from config import Config
        from transcriber import Transcriber
        BACKEND_AVAILABLE = True
        print("✅ Backend imported using alternative method")
    except ImportError as e2:
        print(f"Alternative import also failed: {e2}")
        BACKEND_AVAILABLE = False


class AudioLevelThread(QThread):
    """Thread for monitoring audio levels"""
    level_updated = pyqtSignal(float)
    
    def __init__(self):
        super().__init__()
        self.is_monitoring = False
        
    def run(self):
        """Monitor audio levels"""
        try:
            import sounddevice as sd
            import numpy as np
            import time as time_module
            
            def audio_callback(indata, frames, time, status):
                if status:
                    print(f"Audio callback status: {status}")
                if self.is_monitoring:
                    # Calculate RMS level
                    level = np.sqrt(np.mean(indata**2))
                    self.level_updated.emit(float(level))
            
            with sd.InputStream(callback=audio_callback, channels=1, samplerate=16000):
                while self.is_monitoring:
                    time_module.sleep(0.1)
                    
        except ImportError:
            print("sounddevice not available for audio level monitoring")
        except Exception as e:
            print(f"Audio level monitoring error: {e}")
    
    def start_monitoring(self):
        """Start audio level monitoring"""
        self.is_monitoring = True
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
                    if results.get('transcript'):
                        self.transcript_updated.emit(results['transcript'])
                    if results.get('feedback'):
                        self.feedback_updated.emit(results['feedback'])
                    
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
        self.core = None
        self.recording_thread = None
        self.transcriber = None
        self.audio_level_thread = None
        self.setup_ui()
        self.setup_backend()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("🎤 SoapBoxx - Recording & Transcription")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Microphone Input Section
        mic_group = QGroupBox("🎤 Microphone Input")
        mic_layout = QGridLayout()
        
        # Device selection with better layout
        device_label = QLabel("Input Device:")
        device_label.setStyleSheet("font-weight: bold;")
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(300)
        self.device_combo.addItem("Loading devices...")
        self.device_combo.currentTextChanged.connect(self.on_device_changed)
        mic_layout.addWidget(device_label, 0, 0)
        mic_layout.addWidget(self.device_combo, 0, 1)
        
        # Refresh devices button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_devices)
        refresh_btn.setMaximumWidth(100)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        mic_layout.addWidget(refresh_btn, 0, 2)
        
        # Audio level meter with better styling
        level_label = QLabel("Audio Level:")
        level_label.setStyleSheet("font-weight: bold;")
        self.audio_level_bar = QProgressBar()
        self.audio_level_bar.setRange(0, 100)
        self.audio_level_bar.setValue(0)
        self.audio_level_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #ccc;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
                background-color: #f0f0f0;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00ff00, stop:0.5 #ffff00, stop:1 #ff0000);
                border-radius: 3px;
            }
        """)
        mic_layout.addWidget(level_label, 1, 0)
        mic_layout.addWidget(self.audio_level_bar, 1, 1, 1, 2)
        
        # Test microphone button
        self.test_mic_btn = QPushButton("🎤 Test Microphone")
        self.test_mic_btn.clicked.connect(self.test_microphone)
        self.test_mic_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        mic_layout.addWidget(self.test_mic_btn, 2, 0, 1, 3)
        
        mic_group.setLayout(mic_layout)
        layout.addWidget(mic_group)
        
        # OBS Integration Section
        obs_group = QGroupBox("🎬 OBS Integration")
        obs_layout = QGridLayout()
        
        # OBS Status
        obs_status_label = QLabel("OBS Status:")
        obs_status_label.setStyleSheet("font-weight: bold;")
        self.obs_status = QLabel("Not Connected")
        self.obs_status.setStyleSheet("color: red; font-weight: bold;")
        obs_layout.addWidget(obs_status_label, 0, 0)
        obs_layout.addWidget(self.obs_status, 0, 1)
        
        # OBS Connection
        self.obs_connect_btn = QPushButton("🔗 Connect to OBS")
        self.obs_connect_btn.clicked.connect(self.connect_to_obs)
        self.obs_connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        obs_layout.addWidget(self.obs_connect_btn, 0, 2)
        
        # OBS Controls
        obs_controls_layout = QHBoxLayout()
        
        self.obs_start_stream_btn = QPushButton("📺 Start Stream")
        self.obs_start_stream_btn.clicked.connect(self.obs_start_stream)
        self.obs_start_stream_btn.setEnabled(False)
        self.obs_start_stream_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 6px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        
        self.obs_stop_stream_btn = QPushButton("⏹️ Stop Stream")
        self.obs_stop_stream_btn.clicked.connect(self.obs_stop_stream)
        self.obs_stop_stream_btn.setEnabled(False)
        self.obs_stop_stream_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 6px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        
        self.obs_start_recording_btn = QPushButton("🎥 Start Recording")
        self.obs_start_recording_btn.clicked.connect(self.obs_start_recording)
        self.obs_start_recording_btn.setEnabled(False)
        self.obs_start_recording_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 6px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        
        self.obs_stop_recording_btn = QPushButton("⏹️ Stop Recording")
        self.obs_stop_recording_btn.clicked.connect(self.obs_stop_recording)
        self.obs_stop_recording_btn.setEnabled(False)
        self.obs_stop_recording_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 6px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        
        obs_controls_layout.addWidget(self.obs_start_stream_btn)
        obs_controls_layout.addWidget(self.obs_stop_stream_btn)
        obs_controls_layout.addWidget(self.obs_start_recording_btn)
        obs_controls_layout.addWidget(self.obs_stop_recording_btn)
        
        obs_layout.addLayout(obs_controls_layout, 1, 0, 1, 3)
        
        obs_group.setLayout(obs_layout)
        layout.addWidget(obs_group)
        
        # Transcription Service Selection
        service_group = QGroupBox("🔧 Transcription Service")
        service_layout = QGridLayout()
        
        # Service selector
        service_label = QLabel("Service:")
        service_label.setStyleSheet("font-weight: bold;")
        self.service_combo = QComboBox()
        self.service_combo.addItems(["openai", "local", "assemblyai", "azure"])
        self.service_combo.currentTextChanged.connect(self.on_service_changed)
        service_layout.addWidget(service_label, 0, 0)
        service_layout.addWidget(self.service_combo, 0, 1)
        
        # Service status
        self.service_status = QLabel("Checking service...")
        self.service_status.setStyleSheet("color: gray;")
        service_layout.addWidget(self.service_status, 1, 0, 1, 2)
        
        service_group.setLayout(service_layout)
        layout.addWidget(service_group)
        
        # Status section
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("font-weight: bold; color: green;")
        status_layout.addWidget(self.status_label)
        
        # Configuration status
        self.config_status = QLabel("Checking configuration...")
        self.config_status.setStyleSheet("color: gray;")
        status_layout.addWidget(self.config_status)
        
        layout.addLayout(status_layout)
        
        # Recording controls
        controls_layout = QHBoxLayout()
        
        self.record_button = QPushButton("Start Recording")
        self.record_button.clicked.connect(self.toggle_recording)
        self.record_button.setEnabled(False)
        self.record_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        controls_layout.addWidget(self.record_button)
        
        self.stop_button = QPushButton("Stop Recording")
        self.stop_button.clicked.connect(self.stop_recording)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #ccc;
            }
        """)
        controls_layout.addWidget(self.stop_button)
        
        layout.addLayout(controls_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Results section
        results_layout = QHBoxLayout()
        
        # Transcript section
        transcript_group = QGroupBox("📝 Transcript")
        transcript_layout = QVBoxLayout()
        self.transcript_text = QTextEdit()
        self.transcript_text.setPlaceholderText("Transcript will appear here...")
        self.transcript_text.setMaximumHeight(200)
        transcript_layout.addWidget(self.transcript_text)
        transcript_group.setLayout(transcript_layout)
        results_layout.addWidget(transcript_group)
        
        # Feedback section
        feedback_group = QGroupBox("🎯 Feedback")
        feedback_layout = QVBoxLayout()
        self.feedback_text = QTextEdit()
        self.feedback_text.setPlaceholderText("AI feedback will appear here...")
        self.feedback_text.setMaximumHeight(200)
        feedback_layout.addWidget(self.feedback_text)
        feedback_group.setLayout(feedback_layout)
        results_layout.addWidget(feedback_group)
        
        layout.addLayout(results_layout)
        
        self.setLayout(layout)
        
        # Start audio level monitoring
        self.start_audio_monitoring()
        
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
                max_inputs = device.get('max_inputs', 0)
                device_name = device.get('name', f'Device {i}')
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
        if device_name and "Error" not in device_name and "not available" not in device_name and "Loading" not in device_name:
            self.status_label.setText(f"Selected: {device_name}")
            self.status_label.setStyleSheet("font-weight: bold; color: blue;")
            print(f"🎤 Selected device: {device_name}")
    
    def test_microphone(self):
        """Test the selected microphone"""
        try:
            import sounddevice as sd
            import numpy as np
            
            device_name = self.device_combo.currentText()
            if "Error" in device_name or "not available" in device_name or "Loading" in device_name:
                QMessageBox.warning(self, "Error", "No valid microphone selected")
                return
            
            # Find device ID
            devices = sd.query_devices()
            device_id = None
            for i, device in enumerate(devices):
                max_inputs = device.get('max_inputs', 0)
                device_name_check = device.get('name', f'Device {i}')
                if max_inputs > 0 and device_name_check in device_name:
                    device_id = i
                    break
            
            if device_id is None:
                QMessageBox.warning(self, "Error", "Could not find selected device")
                return
            
            # Test recording for 3 seconds
            duration = 3  # seconds
            sample_rate = 16000
            
            self.test_mic_btn.setText("🎤 Testing...")
            self.test_mic_btn.setEnabled(False)
            
            # Record test audio
            recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, 
                             channels=1, device=device_id, dtype='float32')
            sd.wait()
            
            # Calculate audio level
            rms = np.sqrt(np.mean(recording**2))
            level_percent = min(100, int(rms * 1000))
            
            self.test_mic_btn.setText("🎤 Test Microphone")
            self.test_mic_btn.setEnabled(True)
            
            if level_percent > 5:
                QMessageBox.information(self, "Success", 
                    f"Microphone test successful!\nAudio level: {level_percent}%")
            else:
                QMessageBox.warning(self, "Warning", 
                    f"Microphone test completed but audio level is low ({level_percent}%)\nPlease check your microphone settings.")
                
        except Exception as e:
            self.test_mic_btn.setText("🎤 Test Microphone")
            self.test_mic_btn.setEnabled(True)
            QMessageBox.critical(self, "Error", f"Microphone test failed: {str(e)}")
            print(f"Microphone test error: {e}")
    
    def connect_to_obs(self):
        """Connect to OBS WebSocket"""
        if not OBS_AVAILABLE:
            QMessageBox.warning(self, "OBS Integration", 
                "OBS WebSocket not available. Install with: pip install websocket-client")
            return
            
        try:
            # OBS WebSocket connection
            obs_url = "ws://localhost:4455"  # Default OBS WebSocket URL
            
            def on_message(ws, message):
                try:
                    data = json.loads(message)
                    if data.get('op') == 1:  # Identify response
                        self.obs_connected = True
                        self.obs_status.setText("Connected")
                        self.obs_status.setStyleSheet("color: green; font-weight: bold;")
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
                        "eventSubscriptions": 0
                    }
                }
                ws.send(json.dumps(identify_request))
            
            # Create WebSocket connection
            self.obs_websocket = websocket.WebSocketApp(
                obs_url,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            
            # Start WebSocket connection in a separate thread
            obs_thread = threading.Thread(target=self.obs_websocket.run_forever)
            obs_thread.daemon = True
            obs_thread.start()
            
            self.obs_status.setText("Connecting...")
            self.obs_status.setStyleSheet("color: orange; font-weight: bold;")
            
        except Exception as e:
            QMessageBox.critical(self, "OBS Connection Error", 
                f"Failed to connect to OBS: {str(e)}\n\nMake sure OBS is running with WebSocket enabled.")
            print(f"OBS connection error: {e}")
    
    def obs_start_stream(self):
        """Start OBS streaming"""
        if not self.obs_connected or not self.obs_websocket:
            QMessageBox.warning(self, "OBS", "Not connected to OBS")
            return
        
        try:
            request = {
                "op": 6,
                "d": {
                    "requestType": "StartStreaming"
                }
            }
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
            request = {
                "op": 6,
                "d": {
                    "requestType": "StopStreaming"
                }
            }
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
            request = {
                "op": 6,
                "d": {
                    "requestType": "StartRecord"
                }
            }
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
            request = {
                "op": 6,
                "d": {
                    "requestType": "StopRecord"
                }
            }
            self.obs_websocket.send(json.dumps(request))
            print("🎥 Stopped OBS recording")
        except Exception as e:
            print(f"OBS stop recording error: {e}")
    
    def start_audio_monitoring(self):
        """Start audio level monitoring"""
        try:
            self.audio_level_thread = AudioLevelThread()
            self.audio_level_thread.level_updated.connect(self.update_audio_level)
            self.audio_level_thread.start_monitoring()
        except Exception as e:
            print(f"Failed to start audio monitoring: {e}")
    
    def update_audio_level(self, level):
        """Update the audio level display"""
        try:
            # Convert level to percentage (0-100)
            level_percent = min(100, int(level * 1000))
            self.audio_level_bar.setValue(level_percent)
        except Exception as e:
            print(f"Error updating audio level: {e}")
    
    def closeEvent(self, event):
        """Clean up when closing"""
        if self.audio_level_thread:
            self.audio_level_thread.stop_monitoring()
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
                        self.service_status.setText(f"✅ Local Whisper ({model_info.get('model_size', 'unknown')})")
                        self.service_status.setStyleSheet("color: green;")
                    else:
                        self.service_status.setText(f"❌ Local Whisper: {model_info.get('error', 'Unknown error')}")
                        self.service_status.setStyleSheet("color: red;")
                else:
                    self.service_status.setText("❌ Local Whisper: Transcriber not available")
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
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 10)
            
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
        self.progress_bar.setVisible(False)
        self.status_label.setText("Ready")
    
    def update_transcript(self, transcript):
        """Update transcript display"""
        self.transcript_text.setText(transcript)
    
    def update_feedback(self, feedback):
        """Update feedback display"""
        if isinstance(feedback, dict):
            feedback_text = ""
            if 'listener_feedback' in feedback:
                feedback_text += f"Listener Feedback:\n{feedback['listener_feedback']}\n\n"
            if 'coaching_suggestions' in feedback:
                feedback_text += f"Coaching Suggestions:\n"
                for suggestion in feedback['coaching_suggestions']:
                    feedback_text += f"• {suggestion}\n"
            self.feedback_text.setText(feedback_text)
        else:
            self.feedback_text.setText(str(feedback))
    
    def update_status(self, status):
        """Update status display"""
        self.status_label.setText(status)
        if "Recording..." in status and "remaining" in status:
            try:
                remaining = int(status.split()[-2].replace('s', ''))
                self.progress_bar.setValue(10 - remaining)
            except:
                pass
    
    def handle_error(self, error):
        """Handle errors"""
        self.status_label.setText(f"Error: {error}")
        self.status_label.setStyleSheet("font-weight: bold; color: red;")
        self.record_button.setText("Start Recording")
        self.record_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        QMessageBox.critical(self, "Error", error)
