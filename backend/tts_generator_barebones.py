#!/usr/bin/env python3
"""
Barebones TTS Generator for SoapBoxx Demo
Provides mock text-to-speech functionality without external dependencies
"""

import time
import os
from typing import Dict, List, Optional


class BarebonesTTSGenerator:
    """Simplified TTS generator with mock functionality"""
    
    def __init__(self):
        self.tts_cache = {}
        self.cache_ttl = 3600  # 1 hour
        self.available_voices = self._get_available_voices()
        self.sample_audio_files = self._get_sample_audio_files()
    
    def _get_available_voices(self) -> List[Dict]:
        """Get available TTS voices (mock)"""
        return [
            {
                "id": "en-US-1",
                "name": "US English - Sarah",
                "language": "en-US",
                "gender": "female",
                "description": "Clear, professional female voice"
            },
            {
                "id": "en-US-2", 
                "name": "US English - Mike",
                "language": "en-US",
                "gender": "male",
                "description": "Warm, engaging male voice"
            },
            {
                "id": "en-GB-1",
                "name": "British English - Emma",
                "language": "en-GB",
                "gender": "female",
                "description": "Sophisticated British accent"
            },
            {
                "id": "en-GB-2",
                "name": "British English - James",
                "language": "en-GB",
                "gender": "male",
                "description": "Professional British accent"
            }
        ]
    
    def _get_sample_audio_files(self) -> Dict[str, str]:
        """Get sample audio file paths for demo"""
        return {
            "en-US-1": "sample_audio_sarah.wav",
            "en-US-2": "sample_audio_mike.wav", 
            "en-GB-1": "sample_audio_emma.wav",
            "en-GB-2": "sample_audio_james.wav"
        }
    
    def generate_speech(self, text: str, voice_id: str = "en-US-1", 
                        output_format: str = "wav", speed: float = 1.0) -> Dict:
        """
        Generate speech from text using mock functionality
        """
        if not text:
            return self._get_fallback_result("No text provided")
        
        try:
            # Check cache first
            cache_key = f"{hash(text)}_{voice_id}_{output_format}_{speed}"
            if cache_key in self.tts_cache:
                cached = self.tts_cache[cache_key]
                if time.time() - cached.get("timestamp", 0) < self.cache_ttl:
                    return cached["result"]
            
            # Generate mock audio file path
            audio_file_path = self._generate_mock_audio_file(text, voice_id, output_format)
            
            # Calculate mock metrics
            metrics = self._calculate_tts_metrics(text, voice_id, speed)
            
            result = {
                "success": True,
                "audio_file_path": audio_file_path,
                "text": text,
                "voice_id": voice_id,
                "output_format": output_format,
                "speed": speed,
                "metrics": metrics,
                "timestamp": time.time(),
                "tts_type": "mock"
            }
            
            # Cache the result
            self.tts_cache[cache_key] = {
                "result": result,
                "timestamp": time.time()
            }
            
            return result
            
        except Exception as e:
            return self._get_fallback_result(f"TTS generation failed: {str(e)}")
    
    def _generate_mock_audio_file(self, text: str, voice_id: str, output_format: str) -> str:
        """Generate mock audio file path"""
        # Create a mock filename based on text content and voice
        text_hash = hash(text) % 10000
        timestamp = int(time.time())
        
        filename = f"mock_audio_{voice_id}_{text_hash}_{timestamp}.{output_format}"
        
        # Return path in a mock audio directory
        return f"mock_audio/{filename}"
    
    def _calculate_tts_metrics(self, text: str, voice_id: str, speed: float) -> Dict:
        """Calculate TTS generation metrics"""
        words = text.split()
        characters = len(text)
        
        # Estimate duration based on text length and speed
        # Average speaking rate: 150 words per minute
        base_duration_seconds = len(words) / 150.0 * 60
        adjusted_duration = base_duration_seconds / speed
        
        return {
            "word_count": len(words),
            "character_count": characters,
            "estimated_duration_seconds": round(adjusted_duration, 2),
            "estimated_duration_minutes": round(adjusted_duration / 60.0, 2),
            "speaking_rate_wpm": round(150 * speed, 1),
            "voice_used": voice_id,
            "output_format": "wav"
        }
    
    def _get_fallback_result(self, reason: str) -> Dict:
        """Provide fallback result when TTS generation fails"""
        return {
            "success": False,
            "error": reason,
            "audio_file_path": None,
            "text": "Unable to generate speech at this time.",
            "voice_id": "en-US-1",
            "output_format": "wav",
            "speed": 1.0,
            "metrics": {
                "word_count": 0,
                "character_count": 0,
                "estimated_duration_seconds": 0,
                "estimated_duration_minutes": 0,
                "speaking_rate_wpm": 150,
                "voice_used": "en-US-1",
                "output_format": "wav"
            },
            "timestamp": time.time(),
            "tts_type": "fallback"
        }
    
    def get_available_voices(self, language: str = None) -> List[Dict]:
        """Get available TTS voices"""
        if language:
            return [voice for voice in self.available_voices if voice["language"].startswith(language)]
        return self.available_voices
    
    def get_voice_info(self, voice_id: str) -> Optional[Dict]:
        """Get information about a specific voice"""
        for voice in self.available_voices:
            if voice["id"] == voice_id:
                return voice
        return None
    
    def preview_voice(self, voice_id: str, sample_text: str = "Hello, this is a voice preview.") -> Dict:
        """Preview a voice with sample text"""
        voice_info = self.get_voice_info(voice_id)
        if not voice_info:
            return {"error": f"Voice {voice_id} not found"}
        
        # Generate mock preview
        preview_result = self.generate_speech(sample_text, voice_id)
        
        return {
            "voice_info": voice_info,
            "sample_text": sample_text,
            "preview_audio": preview_result.get("audio_file_path"),
            "preview_metrics": preview_result.get("metrics")
        }
    
    def batch_generate_speech(self, texts: List[str], voice_id: str = "en-US-1", 
                             output_format: str = "wav") -> List[Dict]:
        """Generate speech for multiple text inputs"""
        if not texts:
            return [{"error": "No texts provided"}]
        
        results = []
        for i, text in enumerate(texts):
            result = self.generate_speech(text, voice_id, output_format)
            result["batch_index"] = i
            results.append(result)
        
        return results
    
    def get_tts_status(self, job_id: str) -> Dict:
        """Get TTS job status (mock)"""
        return {
            "job_id": job_id,
            "status": "completed",
            "progress": 100,
            "estimated_completion": time.time(),
            "message": "Mock TTS generation completed successfully"
        }
    
    def list_tts_jobs(self) -> List[Dict]:
        """List TTS jobs (mock)"""
        return [
            {
                "job_id": "mock_tts_001",
                "status": "completed",
                "created_at": time.time() - 3600,
                "completed_at": time.time() - 1800,
                "text_preview": "Welcome to the SoapBoxx podcast...",
                "voice_id": "en-US-1"
            },
            {
                "job_id": "mock_tts_002",
                "status": "processing",
                "created_at": time.time() - 1800,
                "completed_at": None,
                "text_preview": "Today we're talking about...",
                "voice_id": "en-US-2"
            }
        ]
    
    def delete_tts_job(self, job_id: str) -> Dict:
        """Delete TTS job (mock)"""
        return {
            "success": True,
            "job_id": job_id,
            "message": "Mock TTS job deleted successfully"
        }
    
    def clear_cache(self):
        """Clear the TTS cache"""
        self.tts_cache.clear()
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "cache_size": len(self.tts_cache),
            "cache_ttl": self.cache_ttl,
            "total_voices": len(self.available_voices),
            "cache_hits": 0  # Simplified - no hit tracking in barebones version
        }
