#!/usr/bin/env python3
"""
Export Manager for SoapBoxx
Handles exporting transcripts, feedback, and analytics to various formats
"""

import os
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal


class ExportManager(QObject):
    """Manages export functionality for SoapBoxx"""
    
    export_completed = pyqtSignal(str, str)  # filename, format
    export_failed = pyqtSignal(str)  # error message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.export_dir = Path.home() / "SoapBoxx" / "Exports"
        self.export_dir.mkdir(parents=True, exist_ok=True)
    
    def export_transcript(self, transcript: str, session_name: str = None) -> bool:
        """Export transcript to text file"""
        try:
            if not session_name:
                session_name = f"transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            filename = self.export_dir / f"{session_name}_transcript.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"SOAPBOXX TRANSCRIPT\n")
                f.write(f"Session: {session_name}\n")
                f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*50}\n\n")
                f.write(transcript)
            
            self.export_completed.emit(str(filename), "text")
            return True
            
        except Exception as e:
            self.export_failed.emit(f"Failed to export transcript: {str(e)}")
            return False
    
    def export_feedback(self, feedback: Dict, session_name: str = None) -> bool:
        """Export feedback to JSON file"""
        try:
            if not session_name:
                session_name = f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            filename = self.export_dir / f"{session_name}_feedback.json"
            
            export_data = {
                "session_name": session_name,
                "export_date": datetime.now().isoformat(),
                "feedback": feedback
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            self.export_completed.emit(str(filename), "json")
            return True
            
        except Exception as e:
            self.export_failed.emit(f"Failed to export feedback: {str(e)}")
            return False
    
    def export_analytics(self, analytics: Dict, session_name: str = None) -> bool:
        """Export analytics to CSV file"""
        try:
            if not session_name:
                session_name = f"analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            filename = self.export_dir / f"{session_name}_analytics.csv"
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow(['Metric', 'Value', 'Timestamp'])
                
                # Write data
                for metric, value in analytics.items():
                    if isinstance(value, dict):
                        for sub_metric, sub_value in value.items():
                            writer.writerow([f"{metric}_{sub_metric}", sub_value, datetime.now().isoformat()])
                    else:
                        writer.writerow([metric, value, datetime.now().isoformat()])
            
            self.export_completed.emit(str(filename), "csv")
            return True
            
        except Exception as e:
            self.export_failed.emit(f"Failed to export analytics: {str(e)}")
            return False
    
    def export_session_report(self, session_data: Dict) -> bool:
        """Export complete session report"""
        try:
            session_name = session_data.get('session_name', f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            # Create comprehensive report
            report = {
                "session_info": {
                    "name": session_name,
                    "date": datetime.now().isoformat(),
                    "duration": session_data.get('duration', 'N/A'),
                    "status": session_data.get('status', 'completed')
                },
                "transcript": session_data.get('transcript', ''),
                "feedback": session_data.get('feedback', {}),
                "analytics": session_data.get('analytics', {}),
                "metadata": session_data.get('metadata', {})
            }
            
            filename = self.export_dir / f"{session_name}_complete_report.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            self.export_completed.emit(str(filename), "report")
            return True
            
        except Exception as e:
            self.export_failed.emit(f"Failed to export session report: {str(e)}")
            return False
    
    def get_export_directory(self) -> str:
        """Get the export directory path"""
        return str(self.export_dir)
    
    def open_export_directory(self) -> bool:
        """Open the export directory in file explorer"""
        try:
            os.startfile(str(self.export_dir))
            return True
        except Exception as e:
            self.export_failed.emit(f"Failed to open export directory: {str(e)}")
            return False


class ExportDialog:
    """Dialog for export options"""
    
    @staticmethod
    def show_export_options(parent, available_data: Dict) -> Optional[str]:
        """Show export options dialog"""
        options = []
        
        if available_data.get('transcript'):
            options.append("Transcript (TXT)")
        if available_data.get('feedback'):
            options.append("Feedback (JSON)")
        if available_data.get('analytics'):
            options.append("Analytics (CSV)")
        if available_data.get('session_data'):
            options.append("Complete Report (JSON)")
        
        if not options:
            QMessageBox.information(parent, "Export", "No data available for export.")
            return None
        
        # For now, return the first available option
        # In a full implementation, this would show a dialog with checkboxes
        return options[0] if options else None 