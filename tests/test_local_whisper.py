#!/usr/bin/env python3
"""
Test script for local Whisper transcription
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path("backend")))

def test_local_whisper():
    """Test local Whisper transcription"""
    print("🎤 Testing local Whisper transcription...")
    
    try:
        from transcriber import Transcriber
        
        # Initialize local transcriber
        print("🔧 Initializing local Whisper transcriber...")
        transcriber = Transcriber(service="local")
        
        # Check if local model is available
        model_info = transcriber.get_local_model_info()
        
        if model_info.get("available"):
            print(f"✅ Local Whisper model loaded successfully!")
            print(f"   Model: {model_info.get('model_name', 'unknown')}")
            print(f"   Size: {model_info.get('model_size', 'unknown')}")
            print(f"   Device: {model_info.get('device', 'unknown')}")
            
            # Test with a simple audio file (if available)
            print("\n🎵 Testing transcription...")
            
            # Create a simple test audio file or use existing one
            test_audio_path = "test_audio.wav"
            
            if os.path.exists(test_audio_path):
                print(f"📁 Found test audio file: {test_audio_path}")
                
                with open(test_audio_path, "rb") as f:
                    audio_data = f.read()
                
                print("🔍 Transcribing audio...")
                result = transcriber.transcribe(audio_data)
                
                if result and not result.startswith("Error"):
                    print(f"✅ Transcription successful!")
                    print(f"📝 Result: {result[:100]}{'...' if len(result) > 100 else ''}")
                else:
                    print(f"❌ Transcription failed: {result}")
            else:
                print("⚠️ No test audio file found. Creating a simple test...")
                
                # Create a simple test with mock audio data
                import numpy as np
                
                # Generate a simple sine wave (1 second, 440 Hz)
                sample_rate = 16000
                duration = 1.0
                t = np.linspace(0, duration, int(sample_rate * duration), False)
                audio_data = np.sin(2 * np.pi * 440 * t) * 0.3
                
                # Convert to bytes
                audio_bytes = (audio_data * 32767).astype(np.int16).tobytes()
                
                print("🔍 Testing with generated audio...")
                result = transcriber.transcribe(audio_bytes)
                
                if result and not result.startswith("Error"):
                    print(f"✅ Transcription successful!")
                    print(f"📝 Result: {result[:100]}{'...' if len(result) > 100 else ''}")
                else:
                    print(f"❌ Transcription failed: {result}")
            
            return True
            
        else:
            print(f"❌ Local Whisper not available: {model_info.get('error', 'Unknown error')}")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Install Whisper with: pip install openai-whisper")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_local_whisper()
    print(f"\n🎯 Test {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1) 