#!/usr/bin/env python3
"""
Simple microphone test script
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from audio_recorder import AudioRecorder
import time
import numpy as np

def test_microphone():
    print("🎤 Testing microphone input...")
    
    # Create recorder
    rec = AudioRecorder()
    
    try:
        # Start recording
        print("Starting recording...")
        if rec.start_recording():
            print("✅ Recording started successfully")
        else:
            print("❌ Failed to start recording")
            return
        
        # Collect audio chunks for 5 seconds
        print("Recording for 5 seconds... Speak into your microphone!")
        chunks = []
        start_time = time.time()
        
        while time.time() - start_time < 5:
            chunk = rec.get_chunk()
            if chunk is not None:
                chunks.append(chunk)
                # Calculate audio level
                level = np.max(np.abs(chunk))
                print(f"Audio level: {level:6.1f} | Chunks: {len(chunks)}")
            time.sleep(0.1)
        
        # Stop recording
        rec.stop_recording()
        print("✅ Recording stopped")
        
        # Analyze results
        if chunks:
            print(f"\n📊 Results:")
            print(f"Total chunks collected: {len(chunks)}")
            
            # Calculate audio levels
            levels = [np.max(np.abs(chunk)) for chunk in chunks]
            avg_level = np.mean(levels)
            max_level = np.max(levels)
            min_level = np.min(levels)
            
            print(f"Average audio level: {avg_level:.1f}")
            print(f"Maximum audio level: {max_level:.1f}")
            print(f"Minimum audio level: {min_level:.1f}")
            
            # Check if we're getting audio
            if max_level > 100:  # Threshold for detecting audio
                print("✅ Microphone is working - audio detected!")
            else:
                print("⚠️  Microphone may not be picking up audio")
                print("   - Check microphone permissions in Windows")
                print("   - Ensure microphone is not muted")
                print("   - Try speaking louder")
        else:
            print("❌ No audio chunks collected")
            print("   - Check microphone permissions")
            print("   - Ensure microphone is not muted")
            print("   - Try a different audio device")
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
    finally:
        rec.cleanup()

if __name__ == "__main__":
    test_microphone()
