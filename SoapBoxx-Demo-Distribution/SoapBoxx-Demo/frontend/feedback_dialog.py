#!/usr/bin/env python3
"""
Simplified Feedback Dialog for SoapBoxx Demo
Provides basic feedback functionality without complex dependencies
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QScrollArea, QWidget)
from PyQt6.QtCore import Qt

class FeedbackDialog(QDialog):
    """Simplified feedback dialog for demo"""
    
    def __init__(self, feedback_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Content Feedback - Demo Version")
        self.setModal(True)
        self.resize(600, 500)
        
        # Setup UI
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Content Feedback Analysis")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Feedback content
        if feedback_data:
            self.display_feedback(feedback_data, layout)
        else:
            # Demo feedback
            demo_feedback = {
                "scores": {
                    "clarity": 8.5,
                    "engagement": 7.8,
                    "structure": 9.2,
                    "energy": 8.0,
                    "professionalism": 8.7,
                    "overall_score": 8.4
                },
                "feedback": {
                    "strengths": [
                        "Clear and concise language",
                        "Good logical structure",
                        "Engaging opening and closing",
                        "Professional tone maintained"
                    ],
                    "improvements": [
                        "Consider adding more examples",
                        "Vary sentence length for rhythm",
                        "Include more interactive elements"
                    ]
                },
                "metrics": {
                    "word_count": 245,
                    "sentence_count": 18,
                    "reading_time": "1.2 minutes",
                    "topic_coherence": "High"
                }
            }
            self.display_feedback(demo_feedback, layout)
        
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
    
    def display_feedback(self, feedback_data, layout):
        """Display feedback data in the dialog"""
        
        # Scores section
        scores_layout = QHBoxLayout()
        scores_widget = QWidget()
        scores_widget.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 10px;
                margin: 5px;
            }
        """)
        
        scores_text = "📊 **Scores:**\n"
        scores = feedback_data.get("scores", {})
        for key, value in scores.items():
            if key != "overall_score":
                scores_text += f"• {key.title()}: {value}/10\n"
        
        scores_text += f"\n⭐ **Overall Score: {scores.get('overall_score', 'N/A')}/10**"
        
        scores_label = QLabel(scores_text)
        scores_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        scores_layout.addWidget(scores_label)
        scores_widget.setLayout(scores_layout)
        layout.addWidget(scores_widget)
        
        # Metrics section
        metrics_layout = QHBoxLayout()
        metrics_widget = QWidget()
        metrics_widget.setStyleSheet("""
            QWidget {
                background-color: #e8f5e8;
                border: 1px solid #c3e6c3;
                border-radius: 8px;
                padding: 10px;
                margin: 5px;
            }
        """)
        
        metrics_text = "📈 **Metrics:**\n"
        metrics = feedback_data.get("metrics", {})
        for key, value in metrics.items():
            metrics_text += f"• {key.replace('_', ' ').title()}: {value}\n"
        
        metrics_label = QLabel(metrics_text)
        metrics_label.setStyleSheet("font-family: monospace; font-size: 12px;")
        metrics_layout.addWidget(metrics_label)
        metrics_widget.setLayout(metrics_layout)
        layout.addWidget(metrics_widget)
        
        # Feedback section
        feedback_widget = QWidget()
        feedback_widget.setStyleSheet("""
            QWidget {
                background-color: #fff3cd;
                border: 1px solid #ffeaa7;
                border-radius: 8px;
                padding: 10px;
                margin: 5px;
            }
        """)
        
        feedback_layout = QVBoxLayout()
        
        # Strengths
        strengths_label = QLabel("✅ **Strengths:**")
        strengths_label.setStyleSheet("font-weight: bold; color: #856404;")
        feedback_layout.addWidget(strengths_label)
        
        strengths = feedback_data.get("feedback", {}).get("strengths", [])
        for strength in strengths:
            strength_item = QLabel(f"• {strength}")
            strength_item.setStyleSheet("margin-left: 20px; color: #856404;")
            feedback_layout.addWidget(strength_item)
        
        # Improvements
        improvements_label = QLabel("\n🔧 **Areas for Improvement:**")
        improvements_label.setStyleSheet("font-weight: bold; color: #856404;")
        feedback_layout.addWidget(improvements_label)
        
        improvements = feedback_data.get("feedback", {}).get("improvements", [])
        for improvement in improvements:
            improvement_item = QLabel(f"• {improvement}")
            improvement_item.setStyleSheet("margin-left: 20px; color: #856404;")
            feedback_layout.addWidget(improvement_item)
        
        feedback_widget.setLayout(feedback_layout)
        layout.addWidget(feedback_widget)
