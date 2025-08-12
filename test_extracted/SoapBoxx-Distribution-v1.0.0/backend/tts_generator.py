#!/usr/bin/env python3
"""
Text-to-Speech Generator for SoapBoxx
Comprehensive TTS system with multiple service support
"""

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Union

# Try to import error tracker
try:
    from .error_tracker import ErrorCategory, ErrorSeverity, track_api_error
except ImportError:
    try:
        from error_tracker import ErrorCategory, ErrorSeverity, track_api_error
    except ImportError:
        print("Warning: error_tracker not available")

        # Create placeholder classes
        class ErrorCategory:
            TTS = "tts"
            AI_API = "ai_api"

        class ErrorSeverity:
            MEDIUM = "medium"
            HIGH = "high"

        def track_api_error(message, **kwargs):
            print(f"TTS error: {message}")


# Try to import OpenAI
try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("Warning: OpenAI package not available. Install with: pip install openai")

# Try to import Azure Speech
try:
    import azure.cognitiveservices.speech as speechsdk

    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    print(
        "Warning: Azure Speech SDK not available. Install with: pip install azure-cognitiveservices-speech"
    )

# Try to import pyttsx3 for local TTS
try:
    import pyttsx3

    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    print("Warning: pyttsx3 not available. Install with: pip install pyttsx3")

# Try to import gTTS for Google TTS
try:
    from gtts import gTTS

    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False
    print("Warning: gTTS not available. Install with: pip install gTTS")

# Try to import pydub for audio processing
try:
    from pydub import AudioSegment

    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("Warning: pydub not available. Install with: pip install pydub")


class TTSGenerator:
    """
    Comprehensive Text-to-Speech generator with multiple service support
    """

    def __init__(self, service: str = "openai", api_key: Optional[str] = None):
        self.service = service.lower()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.azure_key = os.getenv("AZURE_SPEECH_KEY")
        self.azure_region = os.getenv("AZURE_SPEECH_REGION", "eastus")

        # Initialize service-specific components
        self._init_service()

        # Default settings
        self.default_voice = "alloy"  # OpenAI default
        self.default_speed = 1.0
        self.default_volume = 1.0

        # Supported voices by service
        self.supported_voices = self._get_supported_voices()

    def _init_service(self):
        """Initialize the selected TTS service"""
        if self.service == "openai" and OPENAI_AVAILABLE:
            if self.api_key:
                openai.api_key = self.api_key
                print("✅ OpenAI TTS service initialized")
            else:
                print("⚠️ OpenAI API key not provided")
        elif self.service == "azure" and AZURE_AVAILABLE:
            if self.azure_key:
                print("✅ Azure Speech TTS service initialized")
            else:
                print("⚠️ Azure Speech key not provided")
        elif self.service == "local" and PYTTSX3_AVAILABLE:
            try:
                self.local_engine = pyttsx3.init()
                print("✅ Local TTS service initialized")
            except Exception as e:
                print(f"⚠️ Local TTS initialization failed: {e}")
        elif self.service == "google" and GTTS_AVAILABLE:
            print("✅ Google TTS service initialized")
        else:
            print(f"⚠️ Service {self.service} not available or not configured")

    def _get_supported_voices(self) -> Dict[str, List[str]]:
        """Get supported voices for each service"""
        voices = {
            "openai": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
            "azure": [
                "en-US-AriaNeural",
                "en-US-GuyNeural",
                "en-US-JennyNeural",
                "en-US-DavisNeural",
            ],
            "local": ["default"],
            "google": ["en", "en-US", "en-GB", "en-AU", "en-CA"],
        }
        return voices

    def generate_speech(
        self,
        text: str,
        voice: Optional[str] = None,
        output_path: Optional[str] = None,
        speed: float = 1.0,
        volume: float = 1.0,
    ) -> Optional[str]:
        """
        Generate speech from text using the selected service

        Args:
            text: Text to convert to speech
            voice: Voice to use (service-specific)
            output_path: Output file path (optional)
            speed: Speech speed (0.5 to 2.0)
            volume: Volume level (0.0 to 1.0)

        Returns:
            Path to generated audio file or None if failed
        """
        try:
            if not text.strip():
                track_api_error(
                    "Empty text provided for TTS generation",
                    category=ErrorCategory.TTS,
                    severity=ErrorSeverity.MEDIUM,
                )
                return None

            # Validate parameters
            speed = max(0.5, min(2.0, speed))
            volume = max(0.0, min(1.0, volume))

            # Use default voice if none specified
            if not voice:
                voice = self.default_voice

            # Generate output path if not provided
            if not output_path:
                timestamp = int(time.time())
                output_path = f"tts_output_{timestamp}.mp3"

            # Generate speech based on service
            if self.service == "openai":
                return self._generate_openai_speech(text, voice, output_path, speed)
            elif self.service == "azure":
                return self._generate_azure_speech(text, voice, output_path, speed)
            elif self.service == "local":
                return self._generate_local_speech(text, voice, output_path, speed)
            elif self.service == "google":
                return self._generate_google_speech(text, voice, output_path, speed)
            else:
                track_api_error(
                    f"Unsupported TTS service: {self.service}",
                    category=ErrorCategory.TTS,
                    severity=ErrorSeverity.HIGH,
                )
                return None

        except Exception as e:
            track_api_error(
                f"TTS generation failed: {str(e)}",
                category=ErrorCategory.TTS,
                severity=ErrorSeverity.HIGH,
            )
            return None

    def _generate_openai_speech(
        self, text: str, voice: str, output_path: str, speed: float
    ) -> Optional[str]:
        """Generate speech using OpenAI TTS"""
        try:
            if not OPENAI_AVAILABLE:
                track_api_error(
                    "OpenAI TTS not available",
                    category=ErrorCategory.TTS,
                    severity=ErrorSeverity.HIGH,
                )
                return None

            # Validate voice
            if voice not in self.supported_voices["openai"]:
                voice = "alloy"  # Default fallback

            # Create OpenAI client
            client = openai.OpenAI(api_key=self.api_key)

            # Generate speech
            response = client.audio.speech.create(
                model="tts-1", voice=voice, input=text, speed=speed
            )

            # Save to file
            with open(output_path, "wb") as f:
                f.write(response.content)

            print(f"✅ OpenAI TTS generated: {output_path}")
            return output_path

        except Exception as e:
            track_api_error(
                f"OpenAI TTS generation failed: {str(e)}",
                category=ErrorCategory.AI_API,
                severity=ErrorSeverity.HIGH,
            )
            return None

    def _generate_azure_speech(
        self, text: str, voice: str, output_path: str, speed: float
    ) -> Optional[str]:
        """Generate speech using Azure Speech TTS"""
        try:
            if not AZURE_AVAILABLE:
                track_api_error(
                    "Azure Speech TTS not available",
                    category=ErrorCategory.TTS,
                    severity=ErrorSeverity.HIGH,
                )
                return None

            # Validate voice
            if voice not in self.supported_voices["azure"]:
                voice = "en-US-AriaNeural"  # Default fallback

            # Configure speech config
            speech_config = speechsdk.SpeechConfig(
                subscription=self.azure_key, region=self.azure_region
            )
            speech_config.speech_synthesis_voice_name = voice

            # Configure audio output
            audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)

            # Create synthesizer
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=speech_config, audio_config=audio_config
            )

            # Generate speech
            result = synthesizer.speak_text_async(text).get()

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                print(f"✅ Azure TTS generated: {output_path}")
                return output_path
            else:
                track_api_error(
                    f"Azure TTS failed: {result.reason}",
                    category=ErrorCategory.TTS,
                    severity=ErrorSeverity.HIGH,
                )
                return None

        except Exception as e:
            track_api_error(
                f"Azure TTS generation failed: {str(e)}",
                category=ErrorCategory.TTS,
                severity=ErrorSeverity.HIGH,
            )
            return None

    def _generate_local_speech(
        self, text: str, voice: str, output_path: str, speed: float
    ) -> Optional[str]:
        """Generate speech using local TTS (pyttsx3)"""
        try:
            if not PYTTSX3_AVAILABLE:
                track_api_error(
                    "Local TTS not available",
                    category=ErrorCategory.TTS,
                    severity=ErrorSeverity.HIGH,
                )
                return None

            # Configure local engine
            self.local_engine.setProperty(
                "rate", int(200 * speed)
            )  # Default rate is 200
            self.local_engine.setProperty("volume", 1.0)

            # Get available voices
            voices = self.local_engine.getProperty("voices")
            if voices:
                self.local_engine.setProperty("voice", voices[0].id)

            # Generate speech
            self.local_engine.save_to_file(text, output_path)
            self.local_engine.runAndWait()

            print(f"✅ Local TTS generated: {output_path}")
            return output_path

        except Exception as e:
            track_api_error(
                f"Local TTS generation failed: {str(e)}",
                category=ErrorCategory.TTS,
                severity=ErrorSeverity.HIGH,
            )
            return None

    def _generate_google_speech(
        self, text: str, voice: str, output_path: str, speed: float
    ) -> Optional[str]:
        """Generate speech using Google TTS"""
        try:
            if not GTTS_AVAILABLE:
                track_api_error(
                    "Google TTS not available",
                    category=ErrorCategory.TTS,
                    severity=ErrorSeverity.HIGH,
                )
                return None

            # Validate voice
            if voice not in self.supported_voices["google"]:
                voice = "en"  # Default fallback

            # Generate speech
            tts = gTTS(text=text, lang=voice, slow=(speed < 1.0))
            tts.save(output_path)

            print(f"✅ Google TTS generated: {output_path}")
            return output_path

        except Exception as e:
            track_api_error(
                f"Google TTS generation failed: {str(e)}",
                category=ErrorCategory.TTS,
                severity=ErrorSeverity.HIGH,
            )
            return None

    def get_available_voices(self) -> Dict[str, List[str]]:
        """Get available voices for the current service"""
        return {self.service: self.supported_voices.get(self.service, [])}

    def get_service_status(self) -> Dict[str, any]:
        """Get status of the TTS service"""
        status = {
            "service": self.service,
            "available": False,
            "voices": [],
            "error": None,
        }

        try:
            if self.service == "openai":
                status["available"] = OPENAI_AVAILABLE and bool(self.api_key)
                status["voices"] = self.supported_voices["openai"]
            elif self.service == "azure":
                status["available"] = AZURE_AVAILABLE and bool(self.azure_key)
                status["voices"] = self.supported_voices["azure"]
            elif self.service == "local":
                status["available"] = PYTTSX3_AVAILABLE
                status["voices"] = self.supported_voices["local"]
            elif self.service == "google":
                status["available"] = GTTS_AVAILABLE
                status["voices"] = self.supported_voices["google"]

        except Exception as e:
            status["error"] = str(e)

        return status

    def test_service(self) -> bool:
        """Test the TTS service with a simple text"""
        try:
            test_text = "Hello, this is a test of the text-to-speech service."
            test_output = f"test_tts_{int(time.time())}.mp3"

            result = self.generate_speech(test_text, output_path=test_output)

            if result and os.path.exists(result):
                # Clean up test file
                try:
                    os.remove(result)
                except:
                    pass
                return True
            else:
                return False

        except Exception as e:
            track_api_error(
                f"TTS service test failed: {str(e)}",
                category=ErrorCategory.TTS,
                severity=ErrorSeverity.MEDIUM,
            )
            return False


# Convenience functions
def create_tts_generator(
    service: str = "openai", api_key: Optional[str] = None
) -> TTSGenerator:
    """Create a TTS generator instance"""
    return TTSGenerator(service=service, api_key=api_key)


def generate_speech_from_text(
    text: str,
    service: str = "openai",
    voice: Optional[str] = None,
    output_path: Optional[str] = None,
) -> Optional[str]:
    """Convenience function to generate speech from text"""
    tts = TTSGenerator(service=service)
    return tts.generate_speech(text, voice, output_path)


if __name__ == "__main__":
    # Test the TTS generator
    print("🎤 Testing TTS Generator...")

    # Test OpenAI TTS
    if OPENAI_AVAILABLE:
        print("\n🔍 Testing OpenAI TTS...")
        tts_openai = TTSGenerator(service="openai")
        status = tts_openai.get_service_status()
        print(f"OpenAI Status: {status}")

        if status["available"]:
            test_result = tts_openai.test_service()
            print(f"OpenAI Test: {'✅ PASSED' if test_result else '❌ FAILED'}")

    # Test Local TTS
    if PYTTSX3_AVAILABLE:
        print("\n🔍 Testing Local TTS...")
        tts_local = TTSGenerator(service="local")
        status = tts_local.get_service_status()
        print(f"Local Status: {status}")

        if status["available"]:
            test_result = tts_local.test_service()
            print(f"Local Test: {'✅ PASSED' if test_result else '❌ FAILED'}")

    print("\n🎤 TTS Generator testing complete!")
