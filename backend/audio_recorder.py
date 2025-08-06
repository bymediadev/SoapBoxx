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
        self.stream = sd.InputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            dtype=self.dtype,
            callback=self._callback,
        )
        self.stream.start()

    def read_chunk(self, timeout=1):
        try:
            return self.q.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()


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
