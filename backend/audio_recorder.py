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
    def __init__(self, samplerate=16000, channels=1, dtype="int16", chunk_duration=0.1):
        self.samplerate = samplerate
        self.channels = channels
        self.dtype = dtype
        self.chunk_duration = chunk_duration  # Duration of each chunk in seconds
        self.chunk_size = int(samplerate * chunk_duration)  # Frames per chunk
        self.q = queue.Queue(maxsize=100)  # Limit queue size to prevent memory issues
        self.stream = None
        self.recording_chunks = []
        self.is_recording = False

    def _callback(self, indata, frames, time, status):
        if status:
            print(f"AudioRecorder status: {status}")
            track_audio_error(
                f"AudioRecorder status: {status}",
                component="audio_recorder",
                severity=ErrorSeverity.MEDIUM,
            )
        
        if self.is_recording:
            # Only add to queue if we're recording
            try:
                # Put with timeout to prevent blocking
                self.q.put_nowait(indata.copy())
                
                # Debug: Print audio levels occasionally
                if hasattr(self, '_debug_counter'):
                    self._debug_counter += 1
                else:
                    self._debug_counter = 0
                    
                if self._debug_counter % 100 == 0:  # Every 100 chunks
                    audio_level = np.abs(indata).mean()
                    print(f"🎤 Audio callback: {indata.shape}, level: {audio_level:.4f}, queue: {self.q.qsize()}")
                    
            except queue.Full:
                # If queue is full, remove oldest item and add new one
                try:
                    self.q.get_nowait()
                    self.q.put_nowait(indata.copy())
                    print("⚠️ Audio queue full, removed oldest chunk")
                except queue.Empty:
                    pass  # Queue was emptied by another thread
        else:
            # Debug: Print when not recording
            if hasattr(self, '_debug_counter'):
                self._debug_counter += 1
            else:
                self._debug_counter = 0
                
            if self._debug_counter % 200 == 0:  # Every 200 calls
                print(f"⏸️ Audio callback: not recording, queue: {self.q.qsize()}")

    def start(self):
        """Start audio recording stream"""
        try:
            self.stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=self.channels,
                dtype=self.dtype,
                callback=self._callback,
                blocksize=self.chunk_size,
                latency='low'  # Reduce latency for real-time processing
            )
            self.stream.start()
            self.is_recording = True
            return True
        except Exception as e:
            track_audio_error(f"Failed to start audio stream: {str(e)}")
            return False

    def start_recording(self):
        """Start recording and return success status"""
        try:
            if self.start():
                return True
            return False
        except Exception as e:
            track_audio_error(f"Failed to start recording: {str(e)}")
            return False

    def stop_recording(self):
        """Stop recording and return success status"""
        try:
            self.is_recording = False
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
            chunk = self.q.get_nowait()
            
            # Debug: Print chunk info occasionally
            if hasattr(self, '_get_chunk_counter'):
                self._get_chunk_counter += 1
            else:
                self._get_chunk_counter = 0
                
            if self._get_chunk_counter % 50 == 0:  # Every 50 chunks
                if chunk is not None:
                    audio_level = np.abs(chunk).mean()
                    print(f"📥 Got chunk: {chunk.shape}, level: {audio_level:.4f}, queue: {self.q.qsize()}")
                else:
                    print(f"📥 No chunk available, queue: {self.q.qsize()}")
                    
            return chunk
        except queue.Empty:
            return None

    def get_all_chunks(self):
        """Get all available chunks as a list"""
        chunks = []
        while not self.q.empty():
            try:
                chunk = self.q.get_nowait()
                if chunk is not None:
                    chunks.append(chunk)
            except queue.Empty:
                break
        return chunks

    def get_queue_size(self):
        """Get current queue size"""
        return self.q.qsize()

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
