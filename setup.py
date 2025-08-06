#!/usr/bin/env python3
"""
SoapBoxx Setup Script
Helps users configure and set up the SoapBoxx podcast recording system
"""

import os
import sys
import subprocess
import json
from pathlib import Path


def print_banner():
    """Print setup banner"""
    print("=" * 60)
    print("🎙️  SoapBoxx Setup")
    print("=" * 60)
    print("Welcome to SoapBoxx - Your AI-Powered Podcast Assistant!")
    print()


def check_python_version():
    """Check if Python version is compatible"""
    print("🐍 Checking Python version...")
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required. Current version:", sys.version)
        return False
    else:
        print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
        return True


def install_dependencies():
    """Install required dependencies"""
    print("\n📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False


def setup_configuration():
    """Setup configuration and API keys"""
    print("\n🔧 Setting up configuration...")
    
    # Check if config exists
    config_file = Path("soapboxx_config.json")
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
        except:
            config = {}
    else:
        config = {}
    
    # Setup OpenAI API key
    print("\n🔑 OpenAI API Key Setup")
    print("You need an OpenAI API key for transcription and AI features.")
    print("Get one at: https://platform.openai.com/api-keys")
    print()
    
    current_key = config.get("openai_api_key", "")
    if current_key:
        print(f"✅ API key already configured: {current_key[:8]}...")
        update_key = input("Update API key? (y/N): ").strip().lower()
        if update_key != 'y':
            return True
    
    api_key = input("Enter your OpenAI API key: ").strip()
    if api_key:
        config["openai_api_key"] = api_key
        
        # Save config
        try:
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            print("✅ Configuration saved successfully!")
        except Exception as e:
            print(f"❌ Failed to save configuration: {e}")
            return False
    else:
        print("⚠️  No API key provided. Some features will be limited.")
    
    # Setup environment variables for Scoop and Reverb tabs
    print("\n🔧 Environment Variables Setup")
    print("This will help you configure API keys for Scoop and Reverb tabs.")
    setup_env = input("Setup environment variables? (y/N): ").strip().lower()
    
    if setup_env == 'y':
        try:
            # Import and run environment setup
            sys.path.insert(0, str(Path("backend")))
            from config import Config
            config_instance = Config()
            config_instance.setup_environment_variables()
        except Exception as e:
            print(f"⚠️  Environment setup failed: {e}")
            print("You can manually create a .env file using env.example as a template.")
    
    return True


def test_backend():
    """Test backend functionality"""
    print("\n🧪 Testing backend...")
    try:
        # Add backend to path
        backend_path = Path("backend")
        if backend_path.exists():
            sys.path.insert(0, str(backend_path))
            
            # Import and test
            from test_backend import main as test_main
            result = test_main()
            
            if result == 0:
                print("✅ Backend tests passed!")
                return True
            else:
                print("⚠️  Some backend tests failed. Check the output above.")
                return False
        else:
            print("❌ Backend directory not found")
            return False
            
    except ImportError as e:
        print(f"❌ Backend test failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Backend test error: {e}")
        return False


def create_shortcuts():
    """Create shortcuts for easy access"""
    print("\n🔗 Creating shortcuts...")
    
    # Create run script
    run_script = """@echo off
cd /d "%~dp0"
python frontend\\main_window.py
pause
"""
    
    try:
        with open("run_soapboxx.bat", "w") as f:
            f.write(run_script)
        print("✅ Created run_soapboxx.bat")
    except Exception as e:
        print(f"⚠️  Failed to create run script: {e}")
    
    return True


def main():
    """Main setup function"""
    print_banner()
    
    # Check Python version
    if not check_python_version():
        print("\n❌ Setup failed. Please upgrade Python to 3.8+")
        return 1
    
    # Install dependencies
    if not install_dependencies():
        print("\n❌ Setup failed. Please check your internet connection and try again.")
        return 1
    
    # Setup configuration
    if not setup_configuration():
        print("\n❌ Setup failed. Please check your configuration.")
        return 1
    
    # Test backend
    if not test_backend():
        print("\n⚠️  Backend tests failed. Some features may not work.")
    
    # Create shortcuts
    create_shortcuts()
    
    print("\n" + "=" * 60)
    print("🎉 Setup Complete!")
    print("=" * 60)
    print("SoapBoxx is now ready to use!")
    print()
    print("Next steps:")
    print("1. Run: python frontend/main_window.py")
    print("2. Or double-click: run_soapboxx.bat")
    print("3. Start recording your podcast!")
    print()
    print("For help, check the README.md file.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 