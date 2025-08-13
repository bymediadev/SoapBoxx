#!/usr/bin/env python3
"""
Barebones SoapBoxx Core for Demo
Provides simplified backend orchestration without complex dependencies
"""

import time
import json
import os
from typing import Dict, List, Optional
from pathlib import Path


class BarebonesSoapBoxxCore:
    """Simplified SoapBoxx core with local functionality only"""
    
    def __init__(self):
        self.session_data = {}
        self.export_directory = "Exports"
        self.logs_directory = "logs"
        self.ensure_directories()
        self.session_id = self._generate_session_id()
    
    def ensure_directories(self):
        """Ensure required directories exist"""
        Path(self.export_directory).mkdir(exist_ok=True)
        Path(self.logs_directory).mkdir(exist_ok=True)
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        timestamp = int(time.time())
        return f"session_{timestamp}"
    
    def start_session(self, session_name: str = None) -> Dict:
        """Start a new SoapBoxx session"""
        if not session_name:
            session_name = f"SoapBoxx Session {time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        self.session_data = {
            "session_id": self.session_id,
            "session_name": session_name,
            "start_time": time.time(),
            "status": "active",
            "modules": {
                "feedback_engine": "barebones",
                "guest_research": "barebones", 
                "transcriber": "barebones",
                "tts_generator": "barebones"
            },
            "features": {
                "local_analysis": True,
                "sample_data": True,
                "mock_transcription": True,
                "mock_tts": True
            }
        }
        
        return {
            "success": True,
            "session_id": self.session_id,
            "session_name": session_name,
            "message": "SoapBoxx session started successfully",
            "session_type": "demo"
        }
    
    def get_session_info(self) -> Dict:
        """Get current session information"""
        if not self.session_data:
            return {"error": "No active session"}
        
        session_duration = time.time() - self.session_data.get("start_time", time.time())
        
        return {
            "session_id": self.session_data["session_id"],
            "session_name": self.session_data["session_name"],
            "start_time": self.session_data["start_time"],
            "duration_seconds": round(session_duration, 2),
            "duration_minutes": round(session_duration / 60.0, 2),
            "status": self.session_data["status"],
            "modules": self.session_data["modules"],
            "features": self.session_data["features"]
        }
    
    def end_session(self) -> Dict:
        """End current session"""
        if not self.session_data:
            return {"error": "No active session to end"}
        
        end_time = time.time()
        session_duration = end_time - self.session_data.get("start_time", end_time)
        
        # Save session summary
        session_summary = {
            "session_id": self.session_data["session_id"],
            "session_name": self.session_data["session_name"],
            "start_time": self.session_data["start_time"],
            "end_time": end_time,
            "duration_seconds": round(session_duration, 2),
            "status": "completed"
        }
        
        # Save to logs
        self._save_session_log(session_summary)
        
        # Clear session data
        self.session_data = {}
        
        return {
            "success": True,
            "message": "Session ended successfully",
            "session_summary": session_summary
        }
    
    def _save_session_log(self, session_summary: Dict):
        """Save session log to file"""
        try:
            log_file = Path(self.logs_directory) / f"session_{int(time.time())}.json"
            with open(log_file, 'w') as f:
                json.dump(session_summary, f, indent=2)
        except Exception as e:
            print(f"Failed to save session log: {e}")
    
    def export_session_data(self, export_format: str = "json") -> Dict:
        """Export current session data"""
        if not self.session_data:
            return {"error": "No active session to export"}
        
        try:
            timestamp = int(time.time())
            filename = f"soapboxx_session_{timestamp}.{export_format}"
            filepath = Path(self.export_directory) / filename
            
            if export_format == "json":
                export_data = self._prepare_json_export()
                with open(filepath, 'w') as f:
                    json.dump(export_data, f, indent=2)
            elif export_format == "txt":
                export_data = self._prepare_text_export()
                with open(filepath, 'w') as f:
                    f.write(export_data)
            else:
                return {"error": f"Unsupported export format: {export_format}"}
            
            return {
                "success": True,
                "message": f"Session data exported to {filename}",
                "file_path": str(filepath),
                "export_format": export_format,
                "file_size": os.path.getsize(filepath)
            }
            
        except Exception as e:
            return {"error": f"Export failed: {str(e)}"}
    
    def _prepare_json_export(self) -> Dict:
        """Prepare session data for JSON export"""
        return {
            "export_info": {
                "export_time": time.time(),
                "export_format": "json",
                "soapboxx_version": "demo-barebones"
            },
            "session_data": self.session_data,
            "system_info": {
                "platform": "demo",
                "modules_loaded": list(self.session_data.get("modules", {}).keys()),
                "features_enabled": list(self.session_data.get("features", {}).keys())
            }
        }
    
    def _prepare_text_export(self) -> str:
        """Prepare session data for text export"""
        lines = []
        lines.append("=" * 50)
        lines.append("SOAPBOXX SESSION EXPORT")
        lines.append("=" * 50)
        lines.append(f"Session ID: {self.session_data.get('session_id', 'N/A')}")
        lines.append(f"Session Name: {self.session_data.get('session_name', 'N/A')}")
        lines.append(f"Start Time: {time.ctime(self.session_data.get('start_time', 0))}")
        lines.append(f"Status: {self.session_data.get('status', 'N/A')}")
        lines.append("")
        lines.append("Modules:")
        for module, version in self.session_data.get("modules", {}).items():
            lines.append(f"  - {module}: {version}")
        lines.append("")
        lines.append("Features:")
        for feature, enabled in self.session_data.get("features", {}).items():
            lines.append(f"  - {feature}: {'Yes' if enabled else 'No'}")
        lines.append("")
        lines.append("=" * 50)
        
        return "\n".join(lines)
    
    def get_system_status(self) -> Dict:
        """Get system status and health"""
        return {
            "status": "healthy",
            "version": "demo-barebones",
            "modules": {
                "feedback_engine": "active",
                "guest_research": "active",
                "transcriber": "active", 
                "tts_generator": "active"
            },
            "directories": {
                "exports": self.export_directory,
                "logs": self.logs_directory
            },
            "session_active": bool(self.session_data),
            "demo_mode": True
        }
    
    def get_available_features(self) -> Dict:
        """Get list of available features"""
        return {
            "core_features": {
                "session_management": True,
                "data_export": True,
                "system_monitoring": True
            },
            "analysis_features": {
                "local_text_analysis": True,
                "content_metrics": True,
                "feedback_generation": True
            },
            "research_features": {
                "sample_guest_data": True,
                "company_information": True,
                "industry_insights": True
            },
            "audio_features": {
                "mock_transcription": True,
                "mock_text_to_speech": True,
                "audio_metrics": True
            },
            "ui_features": {
                "modern_interface": True,
                "theme_switching": True,
                "keyboard_shortcuts": True
            }
        }
    
    def get_usage_statistics(self) -> Dict:
        """Get usage statistics for the session"""
        if not self.session_data:
            return {"error": "No active session"}
        
        session_duration = time.time() - self.session_data.get("start_time", time.time())
        
        return {
            "session_duration": {
                "seconds": round(session_duration, 2),
                "minutes": round(session_duration / 60.0, 2),
                "hours": round(session_duration / 3600.0, 3)
            },
            "modules_used": list(self.session_data.get("modules", {}).keys()),
            "features_used": list(self.session_data.get("features", {}).keys()),
            "export_count": 0,  # Simplified - no export tracking in barebones
            "analysis_count": 0  # Simplified - no analysis tracking in barebones
        }
    
    def reset_session(self) -> Dict:
        """Reset current session"""
        if not self.session_data:
            return {"error": "No active session to reset"}
        
        old_session_id = self.session_data["session_id"]
        
        # End current session
        self.end_session()
        
        # Start new session
        new_session = self.start_session(f"Reset Session {time.strftime('%H:%M:%S')}")
        
        return {
            "success": True,
            "message": "Session reset successfully",
            "old_session_id": old_session_id,
            "new_session_id": new_session["session_id"]
        }
    
    def get_help_info(self) -> Dict:
        """Get help information for the demo"""
        return {
            "demo_mode": True,
            "available_commands": [
                "start_session", "end_session", "get_session_info",
                "export_session_data", "get_system_status", "reset_session"
            ],
            "features": {
                "Local Analysis": "Text analysis without external APIs",
                "Sample Data": "Pre-loaded guest and company information",
                "Mock Transcription": "Simulated audio transcription",
                "Mock TTS": "Simulated text-to-speech generation"
            },
            "limitations": [
                "No real API calls to external services",
                "Limited to sample data and mock functionality",
                "Audio features are simulated only"
            ],
            "contact": "This is a demo version of SoapBoxx"
        }
    
    def clear_cache(self):
        """Clear all caches"""
        # This would clear caches from other modules
        # In barebones version, just log the action
        print("Cache clear requested - no caches to clear in barebones mode")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "total_caches": 0,
            "total_items": 0,
            "message": "No caches in barebones mode"
        }
