#!/usr/bin/env python3
"""
Simplified Export Manager for SoapBoxx Demo
Provides basic export functionality without complex dependencies
"""

import json
import os
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import QFileDialog, QMessageBox

class ExportManager:
    """Simplified export manager for demo"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.export_dir = Path("Exports")
        self.export_dir.mkdir(exist_ok=True)
    
    def export_to_json(self, data, filename=None):
        """Export data to JSON format"""
        try:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"soapboxx_export_{timestamp}.json"
            
            filepath = self.export_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            if self.parent:
                QMessageBox.information(
                    self.parent,
                    "Export Successful",
                    f"Data exported to:\n{filepath}"
                )
            
            return str(filepath)
            
        except Exception as e:
            if self.parent:
                QMessageBox.critical(
                    self.parent,
                    "Export Failed",
                    f"Failed to export data:\n{str(e)}"
                )
            return None
    
    def export_to_txt(self, text, filename=None):
        """Export text to TXT format"""
        try:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"soapboxx_export_{timestamp}.txt"
            
            filepath = self.export_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(text)
            
            if self.parent:
                QMessageBox.information(
                    self.parent,
                    "Export Successful",
                    f"Text exported to:\n{filepath}"
                )
            
            return str(filepath)
            
        except Exception as e:
            if self.parent:
                QMessageBox.critical(
                    self.parent,
                    "Export Failed",
                    f"Failed to export text:\n{str(e)}"
                )
            return None
    
    def get_export_directory(self):
        """Get the export directory path"""
        return str(self.export_dir)
    
    def open_export_directory(self):
        """Open the export directory in file explorer"""
        try:
            os.startfile(str(self.export_dir)) if os.name == 'nt' else os.system(f"open {self.export_dir}")
        except Exception:
            pass  # Silently fail if we can't open the directory
