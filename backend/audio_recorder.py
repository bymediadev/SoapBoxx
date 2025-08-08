# backend/audio_recorder.py
import queue

import numpy as np
import sounddevice as sd
from error_tracker import ErrorCategory, ErrorSeverity, track_audio_error


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
        """Start recording and collect audio data"""
        try:
            self.recording_chunks = []  # Reset chunks
            self.start()
            return True
        except Exception as e:
            track_audio_error(
                f"Failed to start recording: {e}",
                component="audio_recorder",
                severity=ErrorSeverity.HIGH,
            )
            return False

    def read_chunk(self, timeout=1):
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self):
        """Stop audio recording stream"""
        if self.stream:
            self.stream.stop()
            self.stream.close()

    def stop_recording(self):
        """Stop recording and return collected audio data"""
        try:
            # Collect any remaining chunks
            while True:
                chunk = self.read_chunk(timeout=0.1)
                if chunk is not None:
                    self.recording_chunks.append(chunk)
                else:
                    break
            
            # Stop the stream
            self.stop()
            
            # Combine all chunks into single audio data
            if self.recording_chunks:
                combined_audio = np.concatenate(self.recording_chunks, axis=0)
                return combined_audio.tobytes()
            else:
                return b""
                
        except Exception as e:
            track_audio_error(
                f"Failed to stop recording: {e}",
                component="audio_recorder",
                severity=ErrorSeverity.HIGH,
            )
            return b""

    def cleanup(self):
        """Clean up resources"""
        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
        except Exception as e:
            track_audio_error(
                f"Cleanup error: {e}",
                component="audio_recorder",
                severity=ErrorSeverity.LOW,
            )


# Example usage
if __name__ == "__main__":
    rec = AudioRecorder()
    rec.start()
    print("Recording... (Ctrl+C to stop)")
    try:
        for _ in range(5):
            chunk = rec.read_chunk()
            print(f"Chunk shape: {chunk.shape if chunk is not None else None}")
    finally:
        rec.stop()
