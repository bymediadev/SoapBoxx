#!/usr/bin/env python3
"""
Barebones Transcriber for SoapBoxx Demo
Provides mock transcription without external API dependencies
"""

import time
from typing import Dict, List, Optional


class BarebonesTranscriber:
    """Simplified transcriber with mock functionality"""
    
    def __init__(self):
        self.transcription_cache = {}
        self.cache_ttl = 3600  # 1 hour
        self.sample_transcripts = self._load_sample_transcripts()
    
    def _load_sample_transcripts(self) -> Dict[str, str]:
        """Load sample transcripts for demo purposes"""
        return {
            "podcast_intro": """Welcome to the SoapBoxx podcast! I'm your host, and today we're diving deep into the world of podcast production and content creation. We'll be exploring how AI tools are revolutionizing the way we create, edit, and distribute our content. Whether you're a seasoned podcaster or just getting started, this episode has something for everyone. Let's jump right in!""",
            
            "business_discussion": """Today we're talking about building successful businesses in the digital age. The landscape has changed dramatically over the past decade, and entrepreneurs need to adapt quickly to stay competitive. We'll discuss key strategies for growth, common pitfalls to avoid, and how to build a team that can scale with your vision. This is going to be an exciting conversation!""",
            
            "tech_trends": """Artificial intelligence is transforming every industry, and podcasting is no exception. From automated editing tools to AI-powered content recommendations, the technology is evolving rapidly. We'll explore what's available now, what's coming next, and how to leverage these tools without losing the human touch that makes podcasts special. It's a fascinating time to be in content creation!""",
            
            "interview_excerpt": """Q: What's your biggest piece of advice for new podcasters? A: Start with what you know and what you're passionate about. Don't try to be perfect from day one - just start recording and improve as you go. The most successful podcasters I know started with simple equipment and basic knowledge, but they had genuine enthusiasm for their topics. That authenticity comes through to listeners.""",
            
            "conclusion": """That wraps up today's episode! I hope you found this discussion valuable and inspiring. Remember, the best time to start your podcasting journey is now. Don't let perfectionism hold you back - just start creating and sharing your voice with the world. Thanks for listening, and I'll see you in the next episode!"""
        }
    
    def transcribe_audio(self, audio_data: bytes = None, audio_file_path: str = None) -> Dict:
        """
        Transcribe audio using mock functionality
        """
        if not audio_data and not audio_file_path:
            return self._get_fallback_transcript("No audio provided")
        
        try:
            # Generate mock transcription based on input
            if audio_file_path:
                transcript = self._generate_mock_transcript_from_file(audio_file_path)
            else:
                transcript = self._generate_mock_transcript_from_audio(audio_data)
            
            # Calculate mock metrics
            metrics = self._calculate_transcription_metrics(transcript)
            
            result = {
                "success": True,
                "transcript": transcript,
                "metrics": metrics,
                "confidence": 0.95,
                "language": "en",
                "timestamp": time.time(),
                "transcription_type": "mock"
            }
            
            # Cache the result
            cache_key = f"{hash(str(audio_data) if audio_data else audio_file_path)}"
            self.transcription_cache[cache_key] = {
                "result": result,
                "timestamp": time.time()
            }
            
            return result
            
        except Exception as e:
            return self._get_fallback_transcript(f"Transcription failed: {str(e)}")
    
    def _generate_mock_transcript_from_file(self, file_path: str) -> str:
        """Generate mock transcript based on file path"""
        # Extract key words from filename to determine content type
        file_lower = file_path.lower()
        
        if "intro" in file_lower or "welcome" in file_lower:
            return self.sample_transcripts["podcast_intro"]
        elif "business" in file_lower or "entrepreneur" in file_lower:
            return self.sample_transcripts["business_discussion"]
        elif "tech" in file_lower or "ai" in file_lower:
            return self.sample_transcripts["tech_trends"]
        elif "interview" in file_lower or "qa" in file_lower:
            return self.sample_transcripts["interview_excerpt"]
        elif "conclusion" in file_lower or "ending" in file_lower:
            return self.sample_transcripts["conclusion"]
        else:
            # Return a combination of sample transcripts
            return self._combine_sample_transcripts()
    
    def _generate_mock_transcript_from_audio(self, audio_data: bytes) -> str:
        """Generate mock transcript based on audio data"""
        # Use audio data length to determine content length
        audio_length = len(audio_data) if audio_data else 0
        
        if audio_length < 1000:
            return "Short audio clip detected. Content appears to be brief."
        elif audio_length < 10000:
            return self.sample_transcripts["interview_excerpt"]
        elif audio_length < 50000:
            return self.sample_transcripts["tech_trends"]
        else:
            return self._combine_sample_transcripts()
    
    def _combine_sample_transcripts(self) -> str:
        """Combine multiple sample transcripts for variety"""
        combined = ""
        for key, transcript in self.sample_transcripts.items():
            combined += transcript + "\n\n"
        return combined.strip()
    
    def _calculate_transcription_metrics(self, transcript: str) -> Dict:
        """Calculate basic transcription metrics"""
        words = transcript.split()
        sentences = transcript.split('.')
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return {
            "word_count": len(words),
            "sentence_count": len(sentences),
            "average_sentence_length": round(len(words) / len(sentences), 2) if sentences else 0,
            "estimated_duration_minutes": round(len(words) / 150.0, 2),  # 150 words per minute
            "unique_words": len(set(word.lower() for word in words)),
            "vocabulary_diversity": round(len(set(word.lower() for word in words)) / len(words), 3) if words else 0
        }
    
    def _get_fallback_transcript(self, reason: str) -> Dict:
        """Provide fallback transcript when transcription fails"""
        return {
            "success": False,
            "error": reason,
            "transcript": "Unable to transcribe audio at this time. Please check your input and try again.",
            "metrics": {
                "word_count": 0,
                "sentence_count": 0,
                "average_sentence_length": 0,
                "estimated_duration_minutes": 0,
                "unique_words": 0,
                "vocabulary_diversity": 0
            },
            "confidence": 0.0,
            "language": "en",
            "timestamp": time.time(),
            "transcription_type": "fallback"
        }
    
    def transcribe_file(self, file_path: str) -> Dict:
        """Transcribe audio file"""
        return self.transcribe_audio(audio_file_path=file_path)
    
    def get_transcription_status(self, job_id: str) -> Dict:
        """Get transcription job status (mock)"""
        return {
            "job_id": job_id,
            "status": "completed",
            "progress": 100,
            "estimated_completion": time.time(),
            "message": "Mock transcription completed successfully"
        }
    
    def list_transcription_jobs(self) -> List[Dict]:
        """List transcription jobs (mock)"""
        return [
            {
                "job_id": "mock_job_001",
                "status": "completed",
                "created_at": time.time() - 3600,
                "completed_at": time.time() - 1800,
                "file_name": "sample_audio_001.wav"
            },
            {
                "job_id": "mock_job_002",
                "status": "processing",
                "created_at": time.time() - 1800,
                "completed_at": None,
                "file_name": "sample_audio_002.wav"
            }
        ]
    
    def delete_transcription_job(self, job_id: str) -> Dict:
        """Delete transcription job (mock)"""
        return {
            "success": True,
            "job_id": job_id,
            "message": "Mock transcription job deleted successfully"
        }
    
    def clear_cache(self):
        """Clear the transcription cache"""
        self.transcription_cache.clear()
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "cache_size": len(self.transcription_cache),
            "cache_ttl": self.cache_ttl,
            "total_transcripts": len(self.sample_transcripts),
            "cache_hits": 0  # Simplified - no hit tracking in barebones version
        }
