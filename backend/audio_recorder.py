# backend/audio_recorder.py
import queue

import numpy as np
import sounddevice as sd

# Try to import error tracker
try:
    from .error_tracker import ErrorCategory, ErrorSeverity, track_audio_error
except ImportError:
    try:
        from error_tracker import ErrorCategory, ErrorSeverity, track_audio_error
    except ImportError:
        print("Warning: error_tracker not available")
        # Create placeholder classes
        class ErrorCategory:
            AUDIO = "audio"
        class ErrorSeverity:
            MEDIUM = "medium"
        def track_audio_error(message, **kwargs):
            print(f"Audio error: {message}")


class AudioRecorder:
    def __init__(self, samplerate=16000, channels=1, dtype="int16"):
        self.samplerate = samplerate
        self.channels = channels
        self.dtype = dtype
        self.q = queue.Queue()
        self.stream = None
        self.recording_chunks = []

    def _callback(self, indata, frames, time, status):
        if status:
            print(f"AudioRecorder status: {status}")
            track_audio_error(
                f"AudioRecorder status: {status}",
                component="audio_recorder",
                severity=ErrorSeverity.MEDIUM,
            )
        self.q.put(indata.copy())

    def start(self):
        """Start audio recording stream"""
        self.stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            dtype=self.dtype,
            callback=self._callback,
        )
        self.stream.start()

    def start_recording(self):
        """Start recording and return success status"""
        try:
            self.start()
            return True
        except Exception as e:
            track_audio_error(f"Failed to start recording: {str(e)}")
            return False

    def stop_recording(self):
        """Stop recording and return success status"""
        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            return True
        except Exception as e:
            track_audio_error(f"Failed to stop recording: {str(e)}")
            return False

    def get_chunk(self):
        """Get the next audio chunk from the queue"""
        try:
            return self.q.get_nowait()
        except queue.Empty:
            return None

    def cleanup(self):
        """Clean up resources"""
        try:
            self.stop_recording()
            # Clear the queue
            while not self.q.empty():
                try:
                    self.q.get_nowait()
                except queue.Empty:
                    break
        except Exception as e:
            track_audio_error(f"Failed to cleanup: {str(e)}")


# Example usage
if __name__ == "__main__":
    rec = AudioRecorder()
    rec.start()
    print("Recording... (Ctrl+C to stop)")
    try:
        for _ in range(5):
            chunk = rec.get_chunk()
            print(f"Chunk shape: {chunk.shape if chunk is not None else None}")
    finally:
        rec.cleanup()
