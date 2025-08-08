#!/usr/bin/env python3
"""
Setup script for OpenAI API key and testing
"""

import json
import os
from pathlib import Path

def setup_openai_api_key():
    """Set up OpenAI API key in configuration"""
    config_file = Path("soapboxx_config.json")
    
    # Load existing config
    if config_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
    else:
        config = {}
    
    print("🔑 OpenAI API Key Setup")
    print("=" * 40)
    
    # Check if API key already exists
    current_key = config.get("openai_api_key", "")
    if current_key:
        print(f"✅ OpenAI API key already configured: {current_key[:8]}...")
        use_existing = input("Use existing key? (y/n): ").lower().strip()
        if use_existing == 'y':
            return current_key
    
    # Get new API key
    print("\nTo get an OpenAI API key:")
    print("1. Go to https://platform.openai.com/api-keys")
    print("2. Sign in or create an account")
    print("3. Click 'Create new secret key'")
    print("4. Copy the key (it starts with 'sk-')")
    print("\n⚠️  Keep your API key secret and never share it!")
    
    api_key = input("\nEnter your OpenAI API key (or press Enter to skip): ").strip()
    
    if not api_key:
        print("❌ No API key provided. OpenAI features will not work.")
        return None
    
    if not api_key.startswith("sk-"):
        print("❌ Invalid API key format. OpenAI API keys start with 'sk-'")
        return None
    
    # Save to config
    config["openai_api_key"] = api_key
    
    # Ensure config directory exists
    config_file.parent.mkdir(exist_ok=True)
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"✅ API key saved to {config_file}")
    return api_key

def test_openai_connection(api_key):
    """Test OpenAI connection with a simple request"""
    if not api_key:
        print("❌ No API key to test")
        return False
    
    try:
        import openai
        
        # Configure OpenAI
        openai.api_key = api_key
        
        print("\n🧪 Testing OpenAI connection...")
        
        # Test with a simple completion
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": "Hello! This is a test message. Please respond with 'Connection successful!'"}
            ],
            max_tokens=10
        )
        
        if response.choices and response.choices[0].message:
            print("✅ OpenAI connection successful!")
            print(f"Response: {response.choices[0].message.content}")
            return True
        else:
            print("❌ Unexpected response format")
            return False
            
    except ImportError:
        print("❌ OpenAI library not installed. Install with: pip install openai")
        return False
    except Exception as e:
        print(f"❌ OpenAI connection failed: {e}")
        return False

def test_audio_libraries():
    """Test if required audio libraries are available"""
    print("\n🎤 Testing Audio Libraries")
    print("=" * 30)
    
    libraries = [
        ("sounddevice", "Audio input/output"),
        ("numpy", "Numerical processing"),
        ("openai-whisper", "Local transcription")
    ]
    
    all_available = True
    
    for lib_name, description in libraries:
        try:
            __import__(lib_name)
            print(f"✅ {lib_name} - {description}")
        except ImportError:
            print(f"❌ {lib_name} - {description} (not installed)")
            all_available = False
    
    if not all_available:
        print(f"\n📦 Install missing libraries with:")
        print("pip install sounddevice numpy openai-whisper")
    
    return all_available

def main():
    """Main setup function"""
    print("🚀 SoapBoxx Setup and Testing")
    print("=" * 40)
    
    # Test audio libraries
    audio_ok = test_audio_libraries()
    
    # Setup OpenAI
    api_key = setup_openai_api_key()
    
    if api_key:
        # Test OpenAI connection
        openai_ok = test_openai_connection(api_key)
        
        if openai_ok:
            print("\n🎉 Setup complete! OpenAI is ready to use.")
        else:
            print("\n⚠️  OpenAI setup incomplete. Check your API key and internet connection.")
    else:
        print("\n⚠️  OpenAI not configured. Question extraction will use basic methods.")
    
    if audio_ok:
        print("\n🎤 Audio libraries are ready for transcription.")
    else:
        print("\n⚠️  Some audio libraries are missing. Install them for full functionality.")
    
    print("\n📖 Next steps:")
    print("1. Run the main application: python frontend/main_window.py")
    print("2. Test your microphone in the SoapBoxx tab")
    print("3. Try recording and transcription")
    if api_key:
        print("4. Use the '🤖 Extract with OpenAI' button for intelligent question extraction")

if __name__ == "__main__":
    main()
