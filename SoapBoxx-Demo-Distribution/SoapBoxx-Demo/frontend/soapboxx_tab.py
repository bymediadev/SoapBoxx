#!/usr/bin/env python3
"""
SoapBoxx Tab - Demo Version
===========================

This is a demo version that shows what the real SoapBoxx tab looks like
without requiring complex backend dependencies.
"""

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QComboBox, QSlider,
                             QGroupBox, QGridLayout, QProgressBar, QFrame)

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

class SoapBoxxTab(QWidget):
    """Demo version of the SoapBoxx tab with realistic UI"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
        # Demo timer for fake updates
        self.demo_timer = QTimer()
        self.demo_timer.timeout.connect(self.update_demo_status)
        self.demo_timer.start(2000)  # Update every 2 seconds
        
        # Recording timer
        self.recording_timer = QTimer()
        self.recording_timer.timeout.connect(self.update_recording_timer)
        self.recording_time = 0
        self.is_recording = False
    
    def setup_ui(self):
        """Set up the tab UI"""
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Header
        header = QLabel("🎙️ SoapBoxx - AI-Powered Podcast Creation")
        header.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2C3E50;
                padding: 20px;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #ECF0F1, stop:1 #BDC3C7);
                border-radius: 12px;
                margin: 10px;
            }
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        # Main controls section
        controls_card = ModernCard()
        controls_layout = QVBoxLayout()
        controls_card.setLayout(controls_layout)
        
        # Recording controls
        recording_group = QGroupBox("🎤 Recording Controls")
        recording_layout = QGridLayout()
        
        # Microphone selection
        recording_layout.addWidget(QLabel("Microphone:"), 0, 0)
        mic_combo = QComboBox()
        mic_combo.addItems(["Default Microphone", "USB Mic", "Built-in Mic"])
        recording_layout.addWidget(mic_combo, 0, 1)
        
        # Recording button
        self.record_button = ModernButton("🔴 Start Recording", style="primary")
        self.record_button.clicked.connect(self.toggle_recording)
        recording_layout.addWidget(self.record_button, 1, 0, 1, 2)
        
        # Recording status and timer
        recording_status_layout = QHBoxLayout()
        self.recording_status = QLabel("⏸️ Ready to record")
        self.recording_status.setStyleSheet("color: #27AE60; font-weight: bold;")
        recording_status_layout.addWidget(self.recording_status)
        
        self.recording_timer_label = QLabel("00:00")
        self.recording_timer_label.setStyleSheet("color: #E74C3C; font-weight: bold; font-size: 16px;")
        self.recording_timer_label.setVisible(False)
        recording_status_layout.addWidget(self.recording_timer_label)
        
        recording_layout.addLayout(recording_status_layout, 2, 0, 1, 2)
        
        recording_group.setLayout(recording_layout)
        controls_layout.addWidget(recording_group)
        
        # AI Processing section
        ai_group = QGroupBox("🤖 AI Processing")
        ai_layout = QVBoxLayout()
        
        # Transcription status
        self.transcription_status = QLabel("📝 Transcription: Ready")
        self.transcription_status.setStyleSheet("color: #3498DB; font-weight: bold;")
        ai_layout.addWidget(self.transcription_status)
        
        # AI enhancement slider
        ai_layout.addWidget(QLabel("AI Enhancement Level:"))
        self.ai_slider = QSlider(Qt.Orientation.Horizontal)
        self.ai_slider.setRange(0, 100)
        self.ai_slider.setValue(75)
        self.ai_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #BDC3C7;
                height: 8px;
                background: #ECF0F1;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #3498DB;
                border: 1px solid #2980B9;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
        """)
        ai_layout.addWidget(self.ai_slider)
        
        ai_group.setLayout(ai_layout)
        controls_layout.addWidget(ai_group)
        
        # Output section
        output_group = QGroupBox("📤 Output & Export")
        output_layout = QVBoxLayout()
        
        # Export buttons
        export_buttons = QHBoxLayout()
        export_buttons.addWidget(ModernButton("📁 Export Audio", style="secondary"))
        export_buttons.addWidget(ModernButton("📄 Export Transcript", style="secondary"))
        export_buttons.addWidget(ModernButton("🎬 Export Video", style="secondary"))
        output_layout.addLayout(export_buttons)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #BDC3C7;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3498DB;
                border-radius: 3px;
            }
        """)
        output_layout.addWidget(self.progress_bar)
        
        output_group.setLayout(output_layout)
        controls_layout.addWidget(output_group)
        
        # Demo info
        demo_info = QLabel("🎭 This is a demo version. The real SoapBoxx includes:\n"
                          "• Live audio recording and processing\n"
                          "• AI-powered transcription and enhancement\n"
                          "• Advanced export options\n"
                          "• OBS integration for streaming")
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
        controls_layout.addWidget(demo_info)
        
        layout.addWidget(controls_card)
        
        # Status bar
        self.status_bar = QLabel("🚀 SoapBoxx Demo - Ready to create amazing content!")
        self.status_bar.setStyleSheet("""
            QLabel {
                color: #2C3E50;
                font-weight: bold;
                padding: 10px;
                background-color: #E8F5E8;
                border: 1px solid #C3E6C3;
                border-radius: 6px;
                margin: 10px;
            }
        """)
        self.status_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_bar)
    
    def toggle_recording(self):
        """Toggle recording state (demo)"""
        if not self.is_recording:
            # Start recording
            self.is_recording = True
            self.recording_time = 0
            self.record_button.setText("⏹️ Stop Recording")
            self.record_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #E74C3C, stop:1 #C0392B);
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 14px;
                    animation: pulse 1s infinite;
                }
            """)
            self.recording_status.setText("🔴 Recording in progress...")
            self.recording_status.setStyleSheet("color: #E74C3C; font-weight: bold;")
            self.recording_timer_label.setVisible(True)
            self.status_bar.setText("🎙️ Recording... Speak clearly into your microphone!")
            
            # Start recording timer
            self.recording_timer.start(1000)  # Update every second
        else:
            # Stop recording
            self.is_recording = False
            self.record_button.setText("🔴 Start Recording")
            self.record_button.update_style()
            self.recording_status.setText("⏸️ Ready to record")
            self.recording_status.setStyleSheet("color: #27AE60; font-weight: bold;")
            self.recording_timer_label.setVisible(False)
            self.status_bar.setText(f"✅ Recording stopped. Total time: {self.recording_timer_label.text()}")
            
            # Stop recording timer
            self.recording_timer.stop()
    
    def update_recording_timer(self):
        """Update the recording timer display"""
        if self.is_recording:
            self.recording_time += 1
            minutes = self.recording_time // 60
            seconds = self.recording_time % 60
            self.recording_timer_label.setText(f"{minutes:02d}:{seconds:02d}")
            
            # Add pulsing animation effect
            if self.recording_time % 2 == 0:
                self.record_button.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #E74C3C, stop:1 #C0392B);
                        color: white;
                        border: none;
                        padding: 12px 24px;
                        border-radius: 8px;
                        font-weight: bold;
                        font-size: 14px;
                        box-shadow: 0 0 20px #E74C3C;
                    }
                """)
            else:
                self.record_button.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                            stop:0 #E74C3C, stop:1 #C0392B);
                        color: white;
                        border: none;
                        padding: 12px 24px;
                        border-radius: 8px;
                        font-weight: bold;
                        font-size: 14px;
                    }
                """)
    
    def update_demo_status(self):
        """Update demo status periodically"""
        import random
        
        # Simulate some activity
        if random.random() < 0.3:  # 30% chance
            self.status_bar.setText("🤖 AI is analyzing your content...")
        elif random.random() < 0.5:  # 50% chance
            self.status_bar.setText("📊 Processing audio quality metrics...")
        else:
            self.status_bar.setText("🚀 SoapBoxx Demo - Ready to create amazing content!")
