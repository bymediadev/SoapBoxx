# backend/soapboxx_core.py
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional

# Try to import backend modules
try:
    from .audio_recorder import AudioRecorder
    from .error_tracker import (ErrorCategory, ErrorSeverity, error_tracker,
                                track_api_error, track_audio_error,
                                track_config_error, track_transcription_error)
    from .feedback_engine import FeedbackEngine
    from .guest_research import GuestResearch
    from .logger import Logger
    from .transcriber import Transcriber
except ImportError:
    try:
        from audio_recorder import AudioRecorder
        from error_tracker import (ErrorCategory, ErrorSeverity, error_tracker,
                                   track_api_error, track_audio_error,
                                   track_config_error,
                                   track_transcription_error)
        from feedback_engine import FeedbackEngine
        from guest_research import GuestResearch
        from logger import Logger
        from transcriber import Transcriber
    except ImportError as e:
        print(f"Warning: Some backend modules not available: {e}")

        # Create placeholder classes
        class AudioRecorder:
            pass

        class FeedbackEngine:
            pass

        class GuestResearch:
            pass

        class Logger:
            pass

        class Transcriber:
            pass

        class ErrorCategory:
            AUDIO = "audio"
            TRANSCRIPTION = "transcription"
            AI_API = "ai_api"
            CONFIGURATION = "configuration"

        class ErrorSeverity:
            MEDIUM = "medium"
            HIGH = "high"

        def track_api_error(message, **kwargs):
            pass

        def track_audio_error(message, **kwargs):
            pass

        def track_config_error(message, **kwargs):
            pass

        def track_transcription_error(message, **kwargs):
            pass

        error_tracker = None


@dataclass
class RecordingSession:
    """Data class for recording session information"""

    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    transcript: str = ""
    feedback: Dict = None
    audio_chunks: List = None
    performance_metrics: Dict = None


class PerformanceMonitor:
    """Monitor system performance and resource usage"""

    def __init__(self):
        self.request_times = defaultdict(list)
        self.error_counts = defaultdict(int)
        self.resource_usage = {}
        self.start_time = time.time()

    def track_request(self, operation: str, duration: float):
        """Track request performance"""
        self.request_times[operation].append(duration)
        # Keep only last 100 requests per operation
        if len(self.request_times[operation]) > 100:
            self.request_times[operation] = self.request_times[operation][-100:]

    def track_error(self, operation: str):
        """Track error occurrence"""
        self.error_counts[operation] += 1

    def get_performance_summary(self) -> Dict:
        """Get performance summary"""
        summary = {
            "uptime": time.time() - self.start_time,
            "operations": {},
            "error_rates": {},
            "resource_usage": self.resource_usage,
        }

        for operation, times in self.request_times.items():
            if times:
                summary["operations"][operation] = {
                    "avg_time": sum(times) / len(times),
                    "min_time": min(times),
                    "max_time": max(times),
                    "total_requests": len(times),
                }

        for operation, count in self.error_counts.items():
            total_requests = len(self.request_times.get(operation, []))
            if total_requests > 0:
                summary["error_rates"][operation] = count / total_requests

        return summary


class RateLimiter:
    """Simple rate limiter for API calls"""

    def __init__(self, max_requests: int = 5, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = defaultdict(list)
        self._lock = threading.Lock()

    def can_make_request(self, operation: str) -> bool:
        """Check if request can be made"""
        with self._lock:
            now = time.time()
            # Clean old requests
            self.requests[operation] = [
                req_time
                for req_time in self.requests[operation]
                if now - req_time < self.time_window
            ]

            if len(self.requests[operation]) < self.max_requests:
                self.requests[operation].append(now)
                return True
            return False

    def get_wait_time(self, operation: str) -> float:
        """Get time to wait before next request"""
        with self._lock:
            if not self.requests[operation]:
                return 0

            oldest_request = min(self.requests[operation])
            return max(0, self.time_window - (time.time() - oldest_request))


class SoapBoxxCore:
    """
    Main integration class that coordinates all backend components
    """

    def __init__(
        self, api_key: Optional[str] = None, transcription_service: str = "openai"
    ):
        # Initialize all components
        self.logger = Logger()
        self.audio_recorder = AudioRecorder()
        self.transcription_service = transcription_service
        self.transcriber = Transcriber(api_key=api_key, service=transcription_service)
        self.feedback_engine = FeedbackEngine(api_key=api_key)

        # Get Google CSE ID from config
        from config import config

        google_cse_id = config.get_google_cse_id()
        self.guest_research = GuestResearch(
            openai_api_key=api_key, google_cse_id=google_cse_id
        )

        # Performance monitoring and rate limiting
        self.performance_monitor = PerformanceMonitor()
        self.rate_limiter = RateLimiter(
            max_requests=config.get_security_settings().get(
                "max_concurrent_requests", 5
            ),
            time_window=60,
        )

        # Session management
        self.current_session: Optional[RecordingSession] = None
        self.is_recording = False
        self.recording_thread: Optional[threading.Thread] = None

        # Callbacks for UI updates
        self.transcript_callback: Optional[Callable] = None
        self.feedback_callback: Optional[Callable] = None
        self.error_callback: Optional[Callable] = None

        self.logger.logger.info(
            f"SoapBoxxCore initialized with transcription service: {transcription_service}"
        )

    def start_recording(self, session_name: str = None) -> bool:
        """
        Start a new recording session with enhanced error handling

        Args:
            session_name: Optional name for the session

        Returns:
            True if recording started successfully
        """
        try:
            if self.is_recording:
                self.logger.log_warning("Recording already in progress")
                return False

            # Create new session with performance tracking
            session_id = f"session_{int(time.time())}"
            self.current_session = RecordingSession(
                session_id=session_id,
                start_time=datetime.now(),
                audio_chunks=[],
                performance_metrics={},
            )

            # Start audio recording
            self.audio_recorder.start()
            self.is_recording = True

            # Start recording thread
            self.recording_thread = threading.Thread(target=self._recording_loop)
            self.recording_thread.daemon = True
            self.recording_thread.start()

            self.logger.logger.info(f"Recording started: {session_id}")
            return True

        except Exception as e:
            error_msg = f"Failed to start recording: {str(e)}"
            track_audio_error(error_msg, {"session_name": session_name})
            self.logger.log_error(error_msg)
            return False

    def stop_recording(self) -> Dict:
        """
        Stop recording and process results with enhanced error handling

        Returns:
            Dictionary containing transcript, feedback, and metadata
        """
        try:
            if not self.is_recording:
                return {"error": "No recording in progress"}

            # Stop recording
            self.is_recording = False
            self.audio_recorder.stop()

            # Wait for recording thread to finish
            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=10)

            # Process the recording
            results = self._process_recording()

            # Update session with end time
            if self.current_session:
                self.current_session.end_time = datetime.now()
                self.current_session.transcript = results.get("transcript", "")
                self.current_session.feedback = results.get("feedback", {})
                self.current_session.performance_metrics = (
                    self.performance_monitor.get_performance_summary()
                )

            return results

        except Exception as e:
            error_msg = f"Failed to stop recording: {str(e)}"
            track_audio_error(error_msg)
            self.logger.log_error(error_msg)
            return {"error": error_msg}

    def _recording_loop(self):
        """Enhanced recording loop with performance monitoring"""
        try:
            while self.is_recording:
                # Get audio chunk
                chunk = self.audio_recorder.get_chunk()
                if chunk and self.current_session:
                    self.current_session.audio_chunks.append(chunk)

                time.sleep(0.1)  # Small delay to prevent CPU overload

        except Exception as e:
            error_msg = f"Recording loop error: {str(e)}"
            track_audio_error(error_msg)
            self.logger.log_error(error_msg)

    def _process_audio_chunks(self):
        """Process audio chunks with performance monitoring"""
        start_time = time.time()

        try:
            if not self.current_session or not self.current_session.audio_chunks:
                return None

            # Combine audio chunks
            combined_audio = self._combine_audio_chunks(
                self.current_session.audio_chunks
            )

            # Track performance
            duration = time.time() - start_time
            self.performance_monitor.track_request("audio_processing", duration)

            return combined_audio

        except Exception as e:
            self.performance_monitor.track_error("audio_processing")
            error_msg = f"Audio processing failed: {str(e)}"
            track_audio_error(error_msg)
            self.logger.log_error(error_msg)
            return None

    def _combine_audio_chunks(self, chunks: List) -> bytes:
        """Combine audio chunks with error handling"""
        try:
            if not chunks:
                return b""

            # Simple concatenation for now
            combined = b"".join(chunks)
            return combined

        except Exception as e:
            error_msg = f"Failed to combine audio chunks: {str(e)}"
            track_audio_error(error_msg)
            self.logger.log_error(error_msg)
            return b""

    def _process_recording(self) -> Dict:
        """Process recording with enhanced error handling and performance monitoring"""
        try:
            # Process audio chunks
            audio_data = self._process_audio_chunks()
            if not audio_data:
                return {"error": "No audio data to process"}

            # Transcribe audio
            transcript_start = time.time()
            transcript = self.transcribe_audio(audio_data)
            transcript_duration = time.time() - transcript_start
            self.performance_monitor.track_request("transcription", transcript_duration)

            if transcript.startswith("Error:"):
                return {"error": transcript, "transcript": ""}

            # Generate feedback
            feedback_start = time.time()
            feedback = self.get_feedback(transcript)
            feedback_duration = time.time() - feedback_start
            self.performance_monitor.track_request(
                "feedback_generation", feedback_duration
            )

            return {
                "transcript": transcript,
                "feedback": feedback,
                "session_id": (
                    self.current_session.session_id if self.current_session else None
                ),
                "duration": (
                    len(self.current_session.audio_chunks) * 0.1
                    if self.current_session
                    else 0
                ),
                "performance_metrics": self.performance_monitor.get_performance_summary(),
            }

        except Exception as e:
            error_msg = f"Recording processing failed: {str(e)}"
            track_audio_error(error_msg)
            self.logger.log_error(error_msg)
            return {"error": error_msg}

    def research_guest(
        self, guest_name: str, website: str = None, additional_info: str = None
    ) -> Dict:
        """Research guest with rate limiting and performance monitoring"""
        operation = "guest_research"

        # Check rate limiting
        if not self.rate_limiter.can_make_request(operation):
            wait_time = self.rate_limiter.get_wait_time(operation)
            return {
                "error": f"Rate limit exceeded. Please wait {wait_time:.1f} seconds.",
                "wait_time": wait_time,
            }

        start_time = time.time()

        try:
            result = self.guest_research.research(guest_name, website, additional_info)

            # Track performance
            duration = time.time() - start_time
            self.performance_monitor.track_request(operation, duration)

            return result

        except Exception as e:
            self.performance_monitor.track_error(operation)
            error_msg = f"Guest research failed: {str(e)}"
            track_api_error(error_msg, {"guest_name": guest_name})
            return {"error": error_msg}

    def get_feedback(self, transcript: str, focus_area: str = None) -> Dict:
        """Get feedback with rate limiting and performance monitoring"""
        operation = "feedback_generation"

        # Check rate limiting
        if not self.rate_limiter.can_make_request(operation):
            wait_time = self.rate_limiter.get_wait_time(operation)
            return {
                "error": f"Rate limit exceeded. Please wait {wait_time:.1f} seconds.",
                "wait_time": wait_time,
            }

        start_time = time.time()

        try:
            result = self.feedback_engine.analyze(transcript, focus_area)

            # Track performance
            duration = time.time() - start_time
            self.performance_monitor.track_request(operation, duration)

            return result

        except Exception as e:
            self.performance_monitor.track_error(operation)
            error_msg = f"Feedback generation failed: {str(e)}"
            track_api_error(error_msg, {"transcript_length": len(transcript)})
            return {"error": error_msg}

    def transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio with rate limiting and performance monitoring"""
        operation = "transcription"

        # Check rate limiting
        if not self.rate_limiter.can_make_request(operation):
            wait_time = self.rate_limiter.get_wait_time(operation)
            return f"Error: Rate limit exceeded. Please wait {wait_time:.1f} seconds."

        start_time = time.time()

        try:
            result = self.transcriber.transcribe(audio_data)

            # Track performance
            duration = time.time() - start_time
            self.performance_monitor.track_request(operation, duration)

            return result

        except Exception as e:
            self.performance_monitor.track_error(operation)
            error_msg = f"Transcription failed: {str(e)}"
            track_transcription_error(error_msg, {"audio_size": len(audio_data)})
            return f"Error: {error_msg}"

    def set_callbacks(
        self,
        transcript_callback: Callable = None,
        feedback_callback: Callable = None,
        error_callback: Callable = None,
    ):
        """Set UI callbacks for real-time updates"""
        self.transcript_callback = transcript_callback
        self.feedback_callback = feedback_callback
        self.error_callback = error_callback

    def get_status(self) -> Dict:
        """Get comprehensive system status"""
        try:
            status = {
                "recording": self.is_recording,
                "transcription_service": self.transcription_service,
                "session_id": (
                    self.current_session.session_id if self.current_session else None
                ),
                "performance": self.performance_monitor.get_performance_summary(),
                "rate_limits": {
                    "can_make_request": self.rate_limiter.can_make_request(
                        "transcription"
                    ),
                    "wait_time": self.rate_limiter.get_wait_time("transcription"),
                },
                "components": {
                    "audio_recorder": self.audio_recorder is not None,
                    "transcriber": self.transcriber is not None,
                    "feedback_engine": self.feedback_engine is not None,
                    "guest_research": self.guest_research is not None,
                },
            }

            return status

        except Exception as e:
            error_msg = f"Failed to get status: {str(e)}"
            track_config_error(error_msg)
            return {"error": error_msg}

    def cleanup(self):
        """Cleanup resources with enhanced error handling"""
        try:
            if self.is_recording:
                self.stop_recording()

            if self.audio_recorder:
                self.audio_recorder.cleanup()

            # Clear callbacks
            self.transcript_callback = None
            self.feedback_callback = None
            self.error_callback = None

            self.logger.logger.info("SoapBoxxCore cleanup completed")

        except Exception as e:
            error_msg = f"Cleanup failed: {str(e)}"
            track_config_error(error_msg)
            self.logger.log_error(error_msg)

    def set_transcription_service(self, service: str):
        """Set transcription service with validation"""
        try:
            valid_services = ["openai", "local", "assemblyai", "azure"]
            if service.lower() not in valid_services:
                raise ValueError(
                    f"Invalid service: {service}. Valid services: {valid_services}"
                )

            self.transcription_service = service.lower()
            self.transcriber = Transcriber(service=service.lower())

            self.logger.logger.info(f"Transcription service changed to: {service}")

        except Exception as e:
            error_msg = f"Failed to set transcription service: {str(e)}"
            track_config_error(error_msg, {"service": service})
            self.logger.log_error(error_msg)


# Example usage
if __name__ == "__main__":
    core = SoapBoxxCore()
    print("SoapBoxxCore initialized successfully")
    print(f"Status: {core.get_status()}")
