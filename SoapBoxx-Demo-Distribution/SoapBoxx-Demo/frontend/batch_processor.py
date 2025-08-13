#!/usr/bin/env python3
"""
Simplified Batch Processor for SoapBoxx Demo
Provides basic functionality without complex dependencies
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit
from PyQt6.QtCore import Qt

class BatchProcessorDialog(QDialog):
    """Simplified batch processor dialog for demo"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Processor - Demo Version")
        self.setModal(True)
        self.resize(500, 400)
        
        # Setup UI
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Batch Processor (Demo)")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Info
        info = QLabel("This is a demo version of the batch processor.\n"
                     "In the full version, you can process multiple files at once.")
        info.setStyleSheet("margin: 10px; color: #666;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)
        
        # Demo content
        demo_text = QTextEdit()
        demo_text.setPlainText("Demo Batch Processing Results:\n\n"
                              "✅ File 1: sample_transcript.txt - Processed\n"
                              "✅ File 2: demo_content.txt - Processed\n"
                              "✅ File 3: test_audio.wav - Processed\n\n"
                              "Total files processed: 3\n"
                              "Success rate: 100%\n"
                              "Processing time: 2.3 seconds")
        demo_text.setReadOnly(True)
        layout.addWidget(demo_text)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078D4;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #106EBE;
            }
        """)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)
