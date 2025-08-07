# backend/transcriber.py
import io
import os
import tempfile
from typing import Optional, Union

import numpy as np
import requests
from error_tracker import (ErrorCategory, ErrorSeverity,
                           track_transcription_error)
from pydub import AudioSegment

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

    def _convert_audio_to_wav(self, audio_data: Union[bytes, np.ndarray]) -> bytes:
        """Convert audio data to WAV format for API compatibility"""
        if isinstance(audio_data, np.ndarray):
            # Convert numpy array to bytes
            audio_bytes = audio_data.tobytes()
        else:
            audio_bytes = audio_data

        # Create temporary file for conversion
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name

        try:
            # Load and convert to WAV format
            audio = AudioSegment.from_file(temp_path)
            # Ensure mono channel and 16kHz sample rate
            audio = audio.set_channels(1).set_frame_rate(16000)

            # Export as WAV bytes
            wav_buffer = io.BytesIO()
            audio.export(wav_buffer, format="wav")
            return wav_buffer.getvalue()
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def transcribe(self, audio: Union[bytes, str, np.ndarray]) -> str:
        """
        Transcribe audio to text using the configured service

        Args:
            audio: Audio data as bytes, file path, or numpy array

        Returns:
            Transcribed text string
        """
        try:
            # Handle different input types
            if isinstance(audio, str):
                # File path
                with open(audio, "rb") as audio_file:
                    audio_data = audio_file.read()
            elif isinstance(audio, np.ndarray):
                # Convert numpy array to WAV format
                audio_data = self._convert_audio_to_wav(audio)
            else:
                # Assume bytes, convert to WAV format
                audio_data = self._convert_audio_to_wav(audio)

            # Route to appropriate service
            if self.service == "openai":
                return self._transcribe_openai(audio_data)
            elif self.service == "assemblyai":
                return self._transcribe_assemblyai(audio_data)
            elif self.service == "azure":
                return self._transcribe_azure(audio_data)
            elif self.service == "local":
                return self._transcribe_local(audio_data)
            else:
                return f"Unknown transcription service: {self.service}"

        except Exception as e:
            error_msg = f"Transcription failed: {str(e)}"
            track_transcription_error(error_msg)
            return error_msg

    def _transcribe_openai(self, audio_data: bytes) -> str:
        """Transcribe using OpenAI Whisper API"""
        if not self.api_key:
            return "Error: No OpenAI API key configured"

        try:
            # Use OpenAI API with version compatibility
            if hasattr(openai, "Audio") and hasattr(openai.Audio, "transcribe"):
                # New OpenAI API (v1.0.0+)
                try:
                    from openai import OpenAI

                    client = OpenAI(api_key=self.api_key)
                    response = client.audio.transcriptions.create(
                        model=self.model,
                        file=io.BytesIO(audio_data),
                        response_format="text",
                    )
                    return response.strip()
                except ImportError:
                    # Fallback to old API
                    response = openai.Audio.transcribe(
                        model=self.model, file=io.BytesIO(audio_data)
                    )
                    return response.get("text", "").strip()
            else:
                # Legacy OpenAI API
                response = openai.Audio.transcribe(
                    model=self.model, file=io.BytesIO(audio_data)
                )
                return response.get("text", "").strip()
        except Exception as e:
            return f"OpenAI transcription failed: {str(e)}"

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
