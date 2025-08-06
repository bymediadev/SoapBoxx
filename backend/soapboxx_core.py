# backend/soapboxx_core.py
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional

from audio_recorder import AudioRecorder
from error_tracker import (ErrorCategory, ErrorSeverity, error_tracker,
                           track_api_error, track_audio_error,
                           track_config_error, track_transcription_error)
from feedback_engine import FeedbackEngine
from guest_research import GuestResearch
from logger import Logger
from transcriber import Transcriber


@dataclass
class RecordingSession:
    """Data class for recording session information"""

    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    transcript: str = ""
    feedback: Dict = None
    audio_chunks: List = None


class SoapBoxxCore:
    """
    Main integration class that coordinates all backend components
    """

    def __init__(self, api_key: Optional[str] = None, transcription_service: str = "openai"):
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

        # Session management
        self.current_session: Optional[RecordingSession] = None
        self.is_recording = False
        self.recording_thread: Optional[threading.Thread] = None

        # Callbacks for UI updates
        self.transcript_callback: Optional[Callable] = None
        self.feedback_callback: Optional[Callable] = None
        self.error_callback: Optional[Callable] = None

        self.logger.logger.info(f"SoapBoxxCore initialized with transcription service: {transcription_service}")

    def start_recording(self, session_name: str = None) -> bool:
        """
        Start a new recording session

        Args:
            session_name: Optional name for the session

        Returns:
            True if recording started successfully
        """
        try:
            if self.is_recording:
                self.logger.log_warning("Recording already in progress")
                return False

            # Create new session
            session_id = f"session_{int(time.time())}"
            self.current_session = RecordingSession(
                session_id=session_id, start_time=datetime.now(), audio_chunks=[]
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
            self.logger.log_error(f"Failed to start recording: {e}")
            track_audio_error(
                f"Failed to start recording: {e}",
                component="audio_recorder",
                exception=e,
            )
            if self.error_callback:
                self.error_callback(f"Failed to start recording: {e}")
            return False

    def stop_recording(self) -> Dict:
        """
        Stop the current recording session and process results

        Returns:
            Dictionary containing session results
        """
        try:
            if not self.is_recording or not self.current_session:
                return {"error": "No active recording session"}

            # Stop recording
            self.is_recording = False
            self.audio_recorder.stop()

            # Wait for recording thread to finish
            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=5)

            # Process the recording
            self.current_session.end_time = datetime.now()
            results = self._process_recording()

            self.logger.logger.info(
                f"Recording stopped: {self.current_session.session_id}"
            )
            return results

        except Exception as e:
            self.logger.log_error(f"Failed to stop recording: {e}")
            track_audio_error(
                f"Failed to stop recording: {e}",
                component="audio_recorder",
                exception=e,
            )
            if self.error_callback:
                self.error_callback(f"Failed to stop recording: {e}")
            return {"error": f"Failed to stop recording: {e}"}

    def _recording_loop(self):
        """Main recording loop that processes audio chunks"""
        try:
            while self.is_recording:
                # Read audio chunk
                chunk = self.audio_recorder.read_chunk(timeout=0.1)
                if chunk is not None:
                    self.current_session.audio_chunks.append(chunk)

                    # Process chunks in batches for transcription
                    if (
                        len(self.current_session.audio_chunks) >= 10
                    ):  # Process every 10 chunks
                        self._process_audio_chunks()

        except Exception as e:
            self.logger.log_error(f"Recording loop error: {e}")
            track_audio_error(
                f"Recording loop error: {e}", component="audio_recorder", exception=e
            )
            if self.error_callback:
                self.error_callback(f"Recording error: {e}")

    def _process_audio_chunks(self):
        """Process accumulated audio chunks for transcription"""
        try:
            if not self.current_session.audio_chunks:
                return

            # Combine chunks into single audio data
            combined_audio = self._combine_audio_chunks(
                self.current_session.audio_chunks
            )

            # Transcribe
            transcript = self.transcriber.transcribe(combined_audio)

            if transcript and transcript.strip():
                self.current_session.transcript += " " + transcript.strip()

                # Update UI with transcript
                if self.transcript_callback:
                    self.transcript_callback(self.current_session.transcript.strip())

                # Clear processed chunks
                self.current_session.audio_chunks = []

        except Exception as e:
            self.logger.log_error(f"Audio processing error: {e}")
            track_audio_error(
                f"Audio processing error: {e}", component="audio_recorder", exception=e
            )

    def _combine_audio_chunks(self, chunks: List) -> bytes:
        """Combine multiple audio chunks into single audio data"""
        import numpy as np

        if not chunks:
            return b""

        # Convert chunks to numpy arrays and concatenate
        arrays = [np.frombuffer(chunk, dtype=np.int16) for chunk in chunks]
        combined = np.concatenate(arrays)

        return combined.tobytes()

    def _process_recording(self) -> Dict:
        """Process the complete recording session"""
        try:
            # Process any remaining audio chunks
            if self.current_session.audio_chunks:
                self._process_audio_chunks()

            # Get final transcript
            final_transcript = self.current_session.transcript.strip()

            # Generate feedback
            feedback = self.feedback_engine.analyze(transcript=final_transcript)
            self.current_session.feedback = feedback

            # Prepare results
            results = {
                "session_id": self.current_session.session_id,
                "start_time": self.current_session.start_time.isoformat(),
                "end_time": self.current_session.end_time.isoformat(),
                "duration": (
                    self.current_session.end_time - self.current_session.start_time
                ).total_seconds(),
                "transcript": final_transcript,
                "feedback": feedback,
                "word_count": len(final_transcript.split()) if final_transcript else 0,
            }

            # Update UI with feedback
            if self.feedback_callback:
                self.feedback_callback(feedback)

            return results

        except Exception as e:
            self.logger.log_error(f"Failed to process recording: {e}")
            track_audio_error(
                f"Failed to process recording: {e}",
                component="audio_recorder",
                exception=e,
            )
            return {"error": f"Failed to process recording: {e}"}

    def research_guest(
        self, guest_name: str, website: str = None, additional_info: str = None
    ) -> Dict:
        """
        Research a guest for interview preparation

        Args:
            guest_name: Name of the guest
            website: Guest's website or social media
            additional_info: Additional information about the guest

        Returns:
            Dictionary containing research results
        """
        try:
            self.logger.logger.info(f"Researching guest: {guest_name}")
            research = self.guest_research.research(
                guest_name, website, additional_info
            )
            return research

        except Exception as e:
            self.logger.log_error(f"Guest research error: {e}")
            track_api_error(
                f"Guest research failed: {e}", component="guest_research", exception=e
            )
            return {"error": f"Guest research failed: {e}"}

    def get_feedback(self, transcript: str, focus_area: str = None) -> Dict:
        """
        Get feedback for a specific transcript

        Args:
            transcript: Text to analyze
            focus_area: Specific area to focus on (optional)

        Returns:
            Dictionary containing feedback
        """
        try:
            if focus_area:
                feedback = self.feedback_engine.get_specific_feedback(
                    transcript, focus_area
                )
            else:
                feedback = self.feedback_engine.analyze(transcript=transcript)

            return feedback

        except Exception as e:
            self.logger.log_error(f"Feedback analysis error: {e}")
            track_api_error(
                f"Feedback analysis failed: {e}",
                component="feedback_engine",
                exception=e,
            )
            return {"error": f"Feedback analysis failed: {e}"}

    def transcribe_audio(self, audio_data: bytes) -> str:
        """
        Transcribe audio data to text

        Args:
            audio_data: Audio data as bytes

        Returns:
            Transcribed text
        """
        try:
            transcript = self.transcriber.transcribe(audio_data)
            return transcript

        except Exception as e:
            self.logger.log_error(f"Transcription error: {e}")
            track_transcription_error(
                f"Transcription failed: {e}", component="transcriber", exception=e
            )
            return f"Transcription failed: {e}"

    def set_callbacks(
        self,
        transcript_callback: Callable = None,
        feedback_callback: Callable = None,
        error_callback: Callable = None,
    ):
        """Set callback functions for UI updates"""
        self.transcript_callback = transcript_callback
        self.feedback_callback = feedback_callback
        self.error_callback = error_callback

    def get_status(self) -> Dict:
        """Get current system status"""
        return {
            "is_recording": self.is_recording,
            "current_session": (
                self.current_session.session_id if self.current_session else None
            ),
            "components": {
                "audio_recorder": "initialized",
                "transcriber": "initialized",
                "feedback_engine": "initialized",
                "guest_research": "initialized",
                "logger": "initialized",
                "error_tracker": "initialized",
            },
            "error_summary": error_tracker.get_error_summary(),
            "health_score": error_tracker.get_health_score(),
        }

    def cleanup(self):
        """Clean up resources"""
        if self.is_recording:
            self.stop_recording()

        if self.audio_recorder:
            self.audio_recorder.stop()

    def set_transcription_service(self, service: str):
        """Change the transcription service dynamically"""
        try:
            self.transcription_service = service
            
            # Get appropriate API key for the service
            api_key = None
            if service == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
            elif service == "assemblyai":
                api_key = os.getenv("ASSEMBLYAI_API_KEY")
            elif service == "azure":
                api_key = os.getenv("AZURE_SPEECH_KEY")
            
            # Create new transcriber with the appropriate service and API key
            self.transcriber = Transcriber(service=service, api_key=api_key)
            self.logger.logger.info(f"Transcription service changed to: {service}")
        except Exception as e:
            self.logger.log_error(f"Failed to change transcription service to {service}: {e}")
            raise e


# Example usage
if __name__ == "__main__":
    core = SoapBoxxCore()
    print("SoapBoxxCore initialized successfully")
    print(f"Status: {core.get_status()}")
