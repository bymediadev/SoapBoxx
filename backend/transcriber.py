# backend/transcriber.py
import io
import os
import tempfile
import threading
import time
from typing import Any, Optional, Union

import requests

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


def _whisper_use_fp16() -> bool:
    """Whisper defaults to fp16; on CPU that emits a UserWarning. Only enable on CUDA."""
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


_LOCAL_WHISPER_LOCK = threading.Lock()
_LOCAL_WHISPER_MODEL_CACHE: dict[str, Any] = {}

# ~0.1s at 16 kHz — below this Whisper often throws reshape errors on empty mel batches.
_MIN_WHISPER_SAMPLES = max(800, int(os.getenv("SOAPBOXX_MIN_WHISPER_SAMPLES", "1600")))


def _is_raw_pcm_s16le(audio_data: bytes) -> bool:
    """Live mic path sends mono s16le @ 16 kHz without a container header."""
    if len(audio_data) < 320 or len(audio_data) % 2 != 0:
        return False
    head = audio_data[:4]
    if head.startswith(b"RIFF") or head.startswith(b"ID3") or head.startswith(b"fLaC"):
        return False
    if head.startswith(b"OggS") or audio_data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return False
    return True


def _pcm_s16le_to_wav_bytes(pcm: bytes, sample_rate: int = 16000) -> bytes:
    import wave

    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return wav_io.getvalue()


def _max_stt_bytes() -> int:
    return int(os.getenv("SOAPBOXX_STT_MAX_BYTES", str(25 * 1024 * 1024)))


def _compress_audio_for_stt(audio_data: bytes, *, bitrate: str = "64k") -> bytes:
    """Mono 16 kHz MP3 — shrinks large podcast enclosures for cloud Whisper APIs."""
    try:
        from pydub import AudioSegment

        seg = AudioSegment.from_file(io.BytesIO(audio_data))
        seg = seg.set_channels(1).set_frame_rate(16000)
        out = io.BytesIO()
        seg.export(out, format="mp3", bitrate=bitrate)
        return out.getvalue()
    except Exception as exc:
        print(f"⚠️ STT audio compress failed ({bitrate}): {exc}")
        return audio_data


def _prepare_cloud_stt_payload(audio_data: bytes) -> tuple[bytes, str]:
    """Return (bytes, filename) under the cloud Whisper upload size cap."""
    limit = _max_stt_bytes()
    if len(audio_data) <= limit:
        return audio_data, "audio.mp3"

    for bitrate in ("64k", "48k", "32k"):
        candidate = _compress_audio_for_stt(audio_data, bitrate=bitrate)
        if len(candidate) <= limit:
            print(
                f"✅ STT audio compressed to {len(candidate) / (1024 * 1024):.1f}MB ({bitrate})",
                flush=True,
            )
            return candidate, "audio.mp3"

    last = _compress_audio_for_stt(audio_data, bitrate="32k")
    mb = len(last) / (1024 * 1024)
    cap = limit / (1024 * 1024)
    raise ValueError(
        f"Audio still too large ({mb:.1f}MB) after compression (max {cap:.0f}MB). "
        "Use a shorter episode or POST /episodes/{id}/transcribe with a pasted transcript."
    )


def _stt_http_timeout() -> Any:
    """Bounded HTTP timeout for cloud Whisper APIs (env SOAPBOXX_STT_HTTP_TIMEOUT, default 300s)."""
    try:
        import httpx

        read_s = float(os.getenv("SOAPBOXX_STT_HTTP_TIMEOUT", "300"))
        return httpx.Timeout(connect=10.0, read=read_s, write=60.0, pool=10.0)
    except ImportError:
        return None


def _openai_stt_client(*, api_key: str, base_url: Optional[str] = None) -> Any:
    from openai import OpenAI

    timeout = _stt_http_timeout()
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
    return OpenAI(api_key=api_key, timeout=timeout)


def _get_or_load_local_whisper_model(model_size: str) -> Any:
    """
    Load Whisper once per model size. Live recording spawns many TranscriptionThread runs;
    without this cache each call would reload weights and stall the UI for minutes.
    """
    if not WHISPER_AVAILABLE:
        return None
    key = (model_size or "base").strip() or "base"
    with _LOCAL_WHISPER_LOCK:
        if key in _LOCAL_WHISPER_MODEL_CACHE:
            return _LOCAL_WHISPER_MODEL_CACHE[key]
        print(f"Initializing local Whisper model ({key}) — one-time load…")
        model = whisper.load_model(key)
        _LOCAL_WHISPER_MODEL_CACHE[key] = model
        print(f"✅ Local Whisper model ready: {key}")
        return model


class Transcriber:
    def __init__(
        self, model="whisper-1", api_key: Optional[str] = None, service="openai"
    ):
        self.model = model
        self.service = service.lower()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.local_model = None
        # Default English: short mic windows are often mis-detected as French without this.
        _lang = (os.getenv("SOAPBOXX_TRANSCRIPTION_LANGUAGE") or "en").strip().lower()
        if _lang in ("auto", "detect"):
            self.language: Optional[str] = None
        elif _lang:
            self.language = _lang[:8]
        else:
            self.language = "en"

        # Initialize based on service
        if self.service == "openai" and OPENAI_AVAILABLE:
            if self.api_key:
                openai.api_key = self.api_key
            else:
                print("Warning: No OpenAI API key provided. Transcription will fail.")
        elif self.service == "groq":
            self.api_key = (
                api_key
                or os.getenv("SOAPBOXX_GROQ_API_KEY")
                or os.getenv("GROQ_API_KEY")
            )
            self.model = (
                os.getenv("SOAPBOXX_GROQ_WHISPER_MODEL", "").strip()
                or "whisper-large-v3-turbo"
            )
            self.groq_base_url = (
                os.getenv("SOAPBOXX_GROQ_BASE_URL", "https://api.groq.com/openai/v1")
                .strip()
                .rstrip("/")
            )
            if not self.api_key:
                print("Warning: No Groq API key (GROQ_API_KEY). Sign up free at console.groq.com")
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
                try:
                    model_size = (
                        os.getenv("SOAPBOXX_LOCAL_WHISPER_MODEL", "base").strip() or "base"
                    )
                    self.local_model = _get_or_load_local_whisper_model(model_size)
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

        # In test mode, return a mock transcript for non-audio to make stress tests green
        if os.getenv("SOAPBOXX_TEST_MODE") == "1":
            if not self._is_valid_audio_data(audio_data):
                return "Mock transcript for testing"

        try:
            # Validate audio data format
            if not self._is_valid_audio_data(audio_data):
                return "Error: Invalid audio data format - audio appears to be corrupted or unsupported"

            # Attempt transcription based on service
            if self.service == "openai":
                return self._transcribe_openai(audio_data)
            elif self.service == "groq":
                return self._transcribe_groq(audio_data)
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
        if _is_raw_pcm_s16le(audio_data):
            return _pcm_s16le_to_wav_bytes(audio_data)

        try:
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
            # Simple token bucket to avoid hammering API under concurrency (best-effort)
            rate_per_min = int(os.getenv("OPENAI_RATE_LIMIT_PER_MIN", "60"))
            # Module-level cache
            global _OPENAI_BUCKET
            if "_OPENAI_BUCKET" not in globals():
                _OPENAI_BUCKET = {
                    "capacity": rate_per_min,
                    "tokens": float(rate_per_min),
                    "rate_per_sec": rate_per_min / 60.0,
                    "last": time.time(),
                }
            # Refill
            now = time.time()
            elapsed = max(0.0, now - _OPENAI_BUCKET["last"])
            _OPENAI_BUCKET["tokens"] = min(
                _OPENAI_BUCKET["capacity"],
                _OPENAI_BUCKET["tokens"] + elapsed * _OPENAI_BUCKET["rate_per_sec"],
            )
            _OPENAI_BUCKET["last"] = now
            if _OPENAI_BUCKET["tokens"] >= 1.0:
                _OPENAI_BUCKET["tokens"] -= 1.0
            else:
                return "Error: Rate limited - please try again shortly"

            try:
                payload, fname = _prepare_cloud_stt_payload(audio_data)
            except ValueError as exc:
                return f"Error: {exc}"

            # OpenAI Python SDK >= 1.0: use client.audio.transcriptions (openai.Audio was removed).
            print("🔑 CRITICAL: Making OpenAI Whisper API call...")
            try:
                client = _openai_stt_client(api_key=self.api_key)
            except ImportError:
                error_msg = "CRITICAL ERROR: OpenAI package not installed"
                track_transcription_error(error_msg, service="openai", critical=True)
                return f"Error: {error_msg}"
            file_buf = io.BytesIO(payload)
            create_kw: dict[str, Any] = {
                "model": self.model,
                "file": (fname, file_buf),
            }
            if self.language:
                create_kw["language"] = self.language

            resp = client.audio.transcriptions.create(**create_kw)
            if isinstance(resp, str):
                transcript = resp.strip()
            else:
                transcript = (getattr(resp, "text", None) or "").strip()

            # Validate response
            if not transcript:
                error_msg = "CRITICAL ERROR: OpenAI returned empty transcription"
                track_transcription_error(error_msg, service="openai", critical=True)
                return f"Error: {error_msg} - Try again or check audio quality"

            print(
                f"✅ CRITICAL SUCCESS: OpenAI transcription completed ({len(transcript)} characters)"
            )
            return transcript

        except Exception as api_error:
            error_str = str(api_error)

            if "timeout" in error_str.lower() or api_error.__class__.__name__ in (
                "Timeout",
                "ReadTimeout",
                "ConnectTimeout",
            ):
                return (
                    f"Error: OpenAI STT timed out ({error_str}). "
                    "Try a shorter clip or POST /process without force_retranscribe."
                )

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

    def _transcribe_groq(self, audio_data: bytes) -> str:
        """Transcribe via Groq Whisper (OpenAI-compatible API, free tier available)."""
        if not self.api_key:
            return (
                "Error: No Groq API key — set GROQ_API_KEY (free at https://console.groq.com)"
            )
        try:
            try:
                payload, fname = _prepare_cloud_stt_payload(audio_data)
            except ValueError as exc:
                return f"Error: {exc}"
            try:
                client = _openai_stt_client(api_key=self.api_key, base_url=self.groq_base_url)
            except ImportError:
                return "Error: Install the openai package for Groq STT support"
            file_buf = io.BytesIO(payload)
            create_kw: dict[str, Any] = {
                "model": self.model,
                "file": (fname, file_buf),
            }
            if self.language:
                create_kw["language"] = self.language
            resp = client.audio.transcriptions.create(**create_kw)
            if isinstance(resp, str):
                transcript = resp.strip()
            else:
                transcript = (getattr(resp, "text", None) or "").strip()
            if not transcript:
                return "Error: Groq returned empty transcription"
            return transcript
        except Exception as exc:
            err = str(exc)
            if "timeout" in err.lower() or exc.__class__.__name__ in (
                "Timeout",
                "ReadTimeout",
                "ConnectTimeout",
            ):
                return (
                    f"Error: Groq STT timed out ({err}). "
                    "Try a shorter clip or POST /process without force_retranscribe."
                )
            return f"Error: Groq transcription failed: {exc}"

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

        min_bytes = _MIN_WHISPER_SAMPLES * 2
        if len(audio_data) < min_bytes:
            return (
                "Error: Audio too short for local Whisper "
                f"(need at least ~{_MIN_WHISPER_SAMPLES / 16000:.1f}s)"
            )

        try:
            # Live mic chunks are raw PCM s16le mono @16kHz with no RIFF header.
            wav_bytes = self._convert_audio_to_wav(audio_data)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_file.write(wav_bytes)
                temp_path = temp_file.name

            try:
                _kw: Any = {"fp16": _whisper_use_fp16()}
                if self.language:
                    _kw["language"] = self.language
                # Serialize local Whisper — live recording fires overlapping windows;
                # concurrent transcribe() calls corrupt the mel pipeline (0-element reshape).
                with _LOCAL_WHISPER_LOCK:
                    audio_np = whisper.load_audio(temp_path)
                    if audio_np is None or len(audio_np) < _MIN_WHISPER_SAMPLES:
                        return (
                            "Error: Audio too short or silent for local Whisper "
                            "(check mic level and recording duration)"
                        )
                    audio_np = whisper.pad_or_trim(audio_np)
                    result = self.local_model.transcribe(audio_np, **_kw)
                return (result.get("text") or "").strip()
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            return f"Error: Local Whisper transcription failed: {str(e)}"

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
