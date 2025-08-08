# backend/transcriber.py
import io
import os
import tempfile
from typing import Optional, Union

import numpy as np
import requests
from pydub import AudioSegment

# Try to import error tracker
try:
    from .error_tracker import (ErrorCategory, ErrorSeverity,
                                track_transcription_error)
except ImportError:
    try:
        from error_tracker import (ErrorCategory, ErrorSeverity,
                                   track_transcription_error)
    except ImportError:
        print("Warning: error_tracker not available")

        # Create placeholder classes
        class ErrorCategory:
            TRANSCRIPTION = "transcription"

        class ErrorSeverity:
            HIGH = "high"

        def track_transcription_error(message, **kwargs):
            print(f"Transcription error: {message}")


# Try to import OpenAI - handle version compatibility
try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("Warning: OpenAI package not available. Install with: pip install openai")

# Try to import Whisper for local transcription
try:
    import whisper

    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    print(
        "Warning: Whisper package not available. Install with: pip install openai-whisper"
    )


class Transcriber:
    def __init__(
        self, model="whisper-1", api_key: Optional[str] = None, service="openai"
    ):
        self.model = model
        self.service = service.lower()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.local_model = None

        # Initialize based on service
        if self.service == "openai" and OPENAI_AVAILABLE:
            if self.api_key:
                openai.api_key = self.api_key
            else:
                print("Warning: No OpenAI API key provided. Transcription will fail.")
        elif self.service == "assemblyai":
            self.api_key = api_key or os.getenv("ASSEMBLYAI_API_KEY")
            if not self.api_key:
                print("Warning: No AssemblyAI API key provided.")
        elif self.service == "azure":
            self.api_key = api_key or os.getenv("AZURE_SPEECH_KEY")
            self.region = os.getenv("AZURE_SPEECH_REGION", "eastus")
            if not self.api_key:
                print("Warning: No Azure Speech key provided.")
        elif self.service == "local":
            if WHISPER_AVAILABLE:
                print("Initializing local Whisper model...")
                try:
                    # Use a smaller model for faster loading (tiny, base, small, medium, large)
                    model_size = "base"  # You can change this to "tiny", "small", "medium", "large"
                    self.local_model = whisper.load_model(model_size)
                    print(f"✅ Local Whisper model loaded: {model_size}")
                except Exception as e:
                    print(f"Warning: Failed to load local Whisper model: {e}")
                    self.local_model = None
            else:
                print(
                    "Warning: Whisper not available. Install with: pip install openai-whisper"
                )
        else:
            print(f"Warning: Unknown transcription service: {service}")

    def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio data with comprehensive error handling"""
        # Enhanced input validation
        if audio_data is None:
            return "Error: No audio data provided"

        if not isinstance(audio_data, bytes):
            try:
                audio_data = bytes(audio_data)
            except Exception:
                return "Error: Invalid audio data format"

        if len(audio_data) == 0:
            return "Error: Empty audio data provided"

        # Check file size limit before processing
        if len(audio_data) > 25 * 1024 * 1024:  # 25MB limit
            return f"Error: Audio file too large ({len(audio_data) / (1024*1024):.1f}MB) - maximum size is 25MB"

        try:
            # Validate audio data format
            if not self._is_valid_audio_data(audio_data):
                return "Error: Invalid audio data format - audio appears to be corrupted or unsupported"

            # Attempt transcription based on service
            if self.service == "openai":
                return self._transcribe_openai(audio_data)
            elif self.service == "assemblyai":
                return self._transcribe_assemblyai(audio_data)
            elif self.service == "local":
                return self._transcribe_local(audio_data)
            else:
                return f"Error: Unsupported transcription service: {self.service}"

        except Exception as e:
            error_msg = f"Transcription failed: {str(e)}"
            track_transcription_error(
                error_msg, service=self.service, audio_size=len(audio_data)
            )
            return f"Error: {error_msg}"

    def _is_valid_audio_data(self, audio_data: bytes) -> bool:
        """Validate that audio data appears to be valid"""
        try:
            # Check minimum size
            if len(audio_data) < 100:
                return False

            # Check for common audio file signatures
            if (
                audio_data.startswith(b"RIFF")
                or audio_data.startswith(b"ID3")
                or audio_data.startswith(b"\xff\xfb")
            ):
                return True

            # Check for non-zero data (basic sanity check)
            if all(b == 0 for b in audio_data[:100]):
                return False

            return True

        except Exception:
            return False

    def _convert_audio_to_wav(self, audio_data: bytes) -> bytes:
        """Convert audio data to WAV format for OpenAI.
        Falls back to wrapping raw PCM as WAV if decoding fails.
        """
        try:
            import io

            from pydub import AudioSegment

            # Try to load input via pydub/ffmpeg
            audio = AudioSegment.from_file(io.BytesIO(audio_data))
            # Ensure mono 16kHz for Whisper
            audio = audio.set_channels(1).set_frame_rate(16000)

            # Export to WAV bytes
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            return wav_buffer.getvalue()

        except Exception as e:
            # Fallback: treat input as raw PCM s16le 16kHz mono and wrap as WAV
            try:
                import io as _io
                import wave

                pcm_bytes = audio_data
                wav_io = _io.BytesIO()
                with wave.open(wav_io, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)  # s16le
                    wf.setframerate(16000)
                    wf.writeframes(pcm_bytes)
                return wav_io.getvalue()
            except Exception as wrap_e:
                print(f"⚠️ Audio conversion failed: {e}; raw PCM wrap failed: {wrap_e}")
                return audio_data

    def _transcribe_openai(self, audio_data: bytes) -> str:
        """Transcribe using OpenAI Whisper API with comprehensive error handling - CRITICAL OPERATION"""
        if not self.api_key:
            error_msg = (
                "CRITICAL ERROR: No OpenAI API key configured - Transcription will fail"
            )
            track_transcription_error(error_msg, service="openai", critical=True)
            return f"Error: {error_msg} - Get your key at https://platform.openai.com/api-keys"

        try:
            # Validate audio data size again (defensive programming)
            if len(audio_data) > 25 * 1024 * 1024:  # 25MB limit
                error_msg = f"CRITICAL ERROR: Audio file too large ({len(audio_data) / (1024*1024):.1f}MB) for OpenAI API"
                track_transcription_error(
                    error_msg, service="openai", size=len(audio_data), critical=True
                )
                return f"Error: {error_msg} - Compress audio or use shorter recording"

            # Convert audio to WAV format for OpenAI
            wav_data = self._convert_audio_to_wav(audio_data)

            # Ensure the BytesIO object has a name attribute for OpenAI
            audio_file = io.BytesIO(wav_data)
            audio_file.name = "audio.wav"

            # CRITICAL: Make OpenAI Whisper API call (v1 client if available)
            print("🔑 CRITICAL: Making OpenAI Whisper API call...")
            response = None
            try:
                from openai import OpenAI  # v1 client

                client = OpenAI(api_key=self.api_key)
                resp = client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    response_format="text",
                )
                response = {"text": resp if isinstance(resp, str) else str(resp)}
            except Exception:
                # Fallback to legacy API
                response = openai.Audio.transcribe(
                    model=self.model, file=audio_file, language="en", temperature=0.0
                )

            # Validate response
            if not response or not response.get("text"):
                error_msg = "CRITICAL ERROR: OpenAI returned empty transcription"
                track_transcription_error(error_msg, service="openai", critical=True)
                return f"Error: {error_msg} - Try again or check audio quality"

            transcript = response["text"].strip()

            if transcript:
                print(
                    f"✅ CRITICAL SUCCESS: OpenAI transcription completed ({len(transcript)} characters)"
                )
                return transcript
            else:
                error_msg = "CRITICAL ERROR: OpenAI returned empty transcript"
                track_transcription_error(error_msg, service="openai", critical=True)
                return f"Error: {error_msg} - Check audio quality or try again"

        except Exception as api_error:
            error_str = str(api_error)

            # CRITICAL: Handle specific OpenAI API errors
            if "413" in error_str or "Maximum content size limit" in error_str:
                error_msg = "CRITICAL ERROR: File too large for OpenAI API (413 error) - Compress audio"
            elif "401" in error_str or "Invalid API key" in error_str:
                error_msg = (
                    "CRITICAL ERROR: Invalid OpenAI API key - Check your configuration"
                )
            elif "429" in error_str or "rate limit" in error_str.lower():
                error_msg = "CRITICAL ERROR: OpenAI API rate limit exceeded - Wait and try again"
            elif "quota" in error_str.lower():
                error_msg = "CRITICAL ERROR: OpenAI API quota exceeded - Check billing"
            else:
                error_msg = f"CRITICAL ERROR: OpenAI API error: {error_str}"

            track_transcription_error(
                error_msg, service="openai", api_error=error_str, critical=True
            )
            return f"Error: {error_msg} - This is a CRITICAL system component"

    def _transcribe_assemblyai(self, audio_data: bytes) -> str:
        """Transcribe using AssemblyAI API"""
        if not self.api_key:
            return "Error: No AssemblyAI API key configured"

        try:
            # Upload audio to AssemblyAI
            upload_url = "https://api.assemblyai.com/v2/upload"
            headers = {"authorization": self.api_key}

            response = requests.post(upload_url, headers=headers, data=audio_data)
            upload_url_response = response.json()

            if response.status_code != 200:
                return f"AssemblyAI upload failed: {upload_url_response}"

            # Transcribe the uploaded audio
            transcript_url = "https://api.assemblyai.com/v2/transcript"
            transcript_request = {
                "audio_url": upload_url_response["upload_url"],
                "language_code": "en",
            }

            response = requests.post(
                transcript_url, json=transcript_request, headers=headers
            )
            transcript_response = response.json()

            if response.status_code != 200:
                return f"AssemblyAI transcription failed: {transcript_response}"

            # Poll for completion
            polling_url = (
                f"https://api.assemblyai.com/v2/transcript/{transcript_response['id']}"
            )
            while True:
                polling_response = requests.get(polling_url, headers=headers)
                polling_response = polling_response.json()

                if polling_response["status"] == "completed":
                    return polling_response["text"]
                elif polling_response["status"] == "error":
                    return f"AssemblyAI transcription error: {polling_response}"

                import time

                time.sleep(3)

        except Exception as e:
            return f"AssemblyAI transcription failed: {str(e)}"

    def _transcribe_azure(self, audio_data: bytes) -> str:
        """Transcribe using Azure Speech Services"""
        if not self.api_key:
            return "Error: No Azure Speech key configured"

        try:
            # This would require the Azure Speech SDK
            # For now, return a placeholder
            return "Azure Speech transcription not yet implemented. Please install azure-cognitiveservices-speech"
        except Exception as e:
            return f"Azure transcription failed: {str(e)}"

    def _transcribe_local(self, audio_data: bytes) -> str:
        """Transcribe using local Whisper model"""
        if not WHISPER_AVAILABLE:
            return (
                "Error: Whisper not available. Install with: pip install openai-whisper"
            )

        if not self.local_model:
            return "Error: Local Whisper model not loaded"

        try:
            # Save audio data to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name

            try:
                # Transcribe using local Whisper model
                result = self.local_model.transcribe(temp_path)
                return result.get("text", "").strip()
            except Exception as e:
                # If direct transcription fails, try converting the audio first
                try:
                    # Convert audio to proper format using pydub
                    audio = AudioSegment.from_file(temp_path)
                    # Ensure mono channel and 16kHz sample rate
                    audio = audio.set_channels(1).set_frame_rate(16000)

                    # Export as WAV
                    converted_path = temp_path + "_converted.wav"
                    audio.export(converted_path, format="wav")

                    # Transcribe the converted audio
                    result = self.local_model.transcribe(converted_path)

                    # Clean up converted file
                    if os.path.exists(converted_path):
                        os.unlink(converted_path)

                    return result.get("text", "").strip()
                except Exception as conv_e:
                    return f"Local Whisper transcription failed: {str(e)} (conversion failed: {str(conv_e)})"
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            return f"Local Whisper transcription failed: {str(e)}"

    def get_available_services(self) -> list:
        """Get list of available transcription services"""
        services = []

        if OPENAI_AVAILABLE:
            services.append("openai")

        if os.getenv("ASSEMBLYAI_API_KEY"):
            services.append("assemblyai")

        if os.getenv("AZURE_SPEECH_KEY"):
            services.append("azure")

        if WHISPER_AVAILABLE:
            services.append("local")

        return services

    def get_local_model_info(self) -> dict:
        """Get information about the loaded local model"""
        if not WHISPER_AVAILABLE:
            return {"available": False, "error": "Whisper not installed"}

        if not self.local_model:
            return {"available": False, "error": "No model loaded"}

        try:
            # Get model information
            model_info = {
                "available": True,
                "model_name": "whisper",
                "model_size": "base",  # Default size
                "device": "cpu",  # Default device
            }

            # Try to get actual model information
            if hasattr(self.local_model, "model"):
                model_info["model_size"] = getattr(
                    self.local_model.model, "model_size", "base"
                )

            if hasattr(self.local_model, "device"):
                model_info["device"] = str(self.local_model.device)

            return model_info
        except Exception as e:
            return {"available": False, "error": str(e)}


# Example usage
if __name__ == "__main__":
    # Test with OpenAI API key
    t = Transcriber()
    print("Transcriber initialized. Use transcribe() method with audio data.")
