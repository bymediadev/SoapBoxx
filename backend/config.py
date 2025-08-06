# backend/config.py
import json
import os
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration manager for SoapBoxx backend"""

    def __init__(self, config_file: str = "soapboxx_config.json"):
        self.config_file = Path(config_file)
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load configuration from file or create default"""
        default_config = {
            "openai_api_key": "",
            "google_cse_id": "0628a50c1bb4e4976",  # Default Google CSE ID
            "audio_settings": {
                "sample_rate": 16000,
                "channels": 1,
                "dtype": "int16",
                "chunk_size": 1024,
            },
            "transcription_settings": {
                "model": "whisper-1",
                "language": "en",
                "temperature": 0.0,
            },
            "feedback_settings": {
                "model": "gpt-3.5-turbo",
                "max_tokens": 500,
                "temperature": 0.7,
            },
            "research_settings": {
                "model": "gpt-3.5-turbo",
                "max_tokens": 800,
                "temperature": 0.7,
            },
            "logging": {
                "level": "INFO",
                "file": "soapboxx.log",
                "max_size": "10MB",
                "backup_count": 5,
            },
            "ui_settings": {
                "theme": "default",
                "auto_save": True,
                "auto_transcribe": True,
            },
        }

        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    loaded_config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    return self._merge_configs(default_config, loaded_config)
            except Exception as e:
                print(f"Error loading config: {e}")
                return default_config
        else:
            # Create default config file
            self._save_config(default_config)
            return default_config

    def _merge_configs(self, default: Dict, loaded: Dict) -> Dict:
        """Recursively merge loaded config with defaults"""
        result = default.copy()

        for key, value in loaded.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value

        return result

    def _save_config(self, config: Dict):
        """Save configuration to file"""
        try:
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key: str, default=None):
        """Get configuration value by key (supports dot notation)"""
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value):
        """Set configuration value by key (supports dot notation)"""
        keys = key.split(".")
        config = self.config

        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # Set the value
        config[keys[-1]] = value

        # Save to file
        self._save_config(self.config)

    def get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key from config or environment"""
        api_key = self.get("openai_api_key")
        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY")
        return api_key

    def set_openai_api_key(self, api_key: str):
        """Set OpenAI API key"""
        self.config["openai_api_key"] = api_key
        self._save_config(self.config)
        
    def setup_api_key_interactive(self):
        """Interactive setup for OpenAI API key"""
        current_key = self.get_openai_api_key()
        if current_key:
            print(f"✅ OpenAI API key already configured: {current_key[:8]}...")
            return True
            
        print("🔑 OpenAI API Key Setup")
        print("You need an OpenAI API key for transcription and AI features.")
        print("Get one at: https://platform.openai.com/api-keys")
        print()
        
        api_key = input("Enter your OpenAI API key (or press Enter to skip): ").strip()
        if api_key:
            self.set_openai_api_key(api_key)
            print("✅ API key saved successfully!")
            return True
        else:
            print("⚠️  No API key provided. Some features will be limited.")
            return False
    
    def setup_environment_variables(self):
        """Interactive setup for environment variables"""
        print("🔧 Environment Variables Setup")
        print("This will help you configure API keys for Scoop and Reverb tabs.")
        print()
        
        # Check if .env file exists
        env_file = Path(".env")
        env_vars = {}
        
        if env_file.exists():
            print("📄 Found existing .env file")
            # Read existing variables
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key] = value
        
        # Define all possible API keys
        api_keys = {
            "OPENAI_API_KEY": {
                "description": "OpenAI API Key (for transcription and AI features)",
                "url": "https://platform.openai.com/api-keys",
                "required": True
            },
            "GOOGLE_CSE_ID": {
                "description": "Google Custom Search Engine ID (for web search)",
                "url": "https://programmablesearchengine.google.com/",
                "required": False
            },
            "GOOGLE_API_KEY": {
                "description": "Google API Key (for Google Custom Search API)",
                "url": "https://console.cloud.google.com/",
                "required": False
            },
            "NEWS_API_KEY": {
                "description": "News API Key (for news integration in Scoop tab)",
                "url": "https://newsapi.org/",
                "required": False
            },
            "TWITTER_API_KEY": {
                "description": "Twitter API Key (for social media trends)",
                "url": "https://developer.twitter.com/",
                "required": False
            },
            "SPOTIFY_CLIENT_ID": {
                "description": "Spotify Client ID (for music integration - background music, royalty-free tracks)",
                "url": "https://developer.spotify.com/",
                "required": False
            },
            "YOUTUBE_API_KEY": {
                "description": "YouTube API Key (for video content integration)",
                "url": "https://console.cloud.google.com/",
                "required": False
            },
            "AZURE_SPEECH_KEY": {
                "description": "Azure Speech Key (for speech recognition)",
                "url": "https://azure.microsoft.com/services/cognitive-services/speech-services/",
                "required": False
            },
            "ELEVENLABS_API_KEY": {
                "description": "ElevenLabs API Key (for text-to-speech)",
                "url": "https://elevenlabs.io/",
                "required": False
            },
            "ASSEMBLYAI_API_KEY": {
                "description": "AssemblyAI API Key (for audio analysis)",
                "url": "https://www.assemblyai.com/",
                "required": False
            },
            "PODCHASER_API_KEY": {
                "description": "Podchaser API Key (for podcast database and analytics)",
                "url": "https://www.podchaser.com/developers",
                "required": False
            },
            "LISTEN_NOTES_API_KEY": {
                "description": "Listen Notes API Key (for podcast search and discovery)",
                "url": "https://www.listennotes.com/api/",
                "required": False
            },
            "APPLE_PODCASTS_API_KEY": {
                "description": "Apple Podcasts API Key (for podcast directory - limited access)",
                "url": "https://developer.apple.com/",
                "required": False
            },
            "GOOGLE_PODCASTS_API_KEY": {
                "description": "Google Podcasts API Key (for podcast discovery - limited access)",
                "url": "https://console.cloud.google.com/",
                "required": False
            }
        }
        
        print("Available API keys to configure:")
        for i, (key, info) in enumerate(api_keys.items(), 1):
            status = "✅" if env_vars.get(key) else "❌"
            required = " (Required)" if info["required"] else ""
            print(f"{i:2d}. {status} {key}{required}")
            print(f"    {info['description']}")
            print(f"    Get it at: {info['url']}")
            print()
        
        print("Enter the number of the API key you want to configure (or press Enter to skip):")
        
        try:
            choice = input("Choice: ").strip()
            if choice and choice.isdigit():
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(api_keys):
                    key_name = list(api_keys.keys())[choice_idx]
                    key_info = api_keys[key_name]
                    
                    current_value = env_vars.get(key_name, "")
                    if current_value:
                        print(f"Current value: {current_value[:8]}...")
                        update = input("Update this key? (y/N): ").strip().lower()
                        if update != 'y':
                            return True
                    
                    print(f"\n🔑 {key_name} Setup")
                    print(f"Description: {key_info['description']}")
                    print(f"Get it at: {key_info['url']}")
                    print()
                    
                    new_value = input(f"Enter your {key_name}: ").strip()
                    if new_value:
                        env_vars[key_name] = new_value
                        print(f"✅ {key_name} saved!")
                    else:
                        print(f"⚠️  {key_name} not updated.")
                else:
                    print("❌ Invalid choice.")
            else:
                print("⏭️  Skipping API key setup.")
        except KeyboardInterrupt:
            print("\n⏭️  Setup cancelled.")
            return False
        
        # Save to .env file
        try:
            with open(env_file, 'w') as f:
                f.write("# SoapBoxx Environment Variables\n")
                f.write("# Generated by setup_environment_variables()\n\n")
                
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
            
            print(f"\n✅ Environment variables saved to {env_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving environment variables: {e}")
            return False

    def get_google_cse_id(self) -> Optional[str]:
        """Get Google CSE ID from config or environment"""
        cse_id = self.get("google_cse_id")
        if not cse_id:
            cse_id = os.getenv("GOOGLE_CSE_ID")
        return cse_id

    def set_google_cse_id(self, cse_id: str):
        """Set Google CSE ID"""
        self.set("google_cse_id", cse_id)

    def get_audio_settings(self) -> Dict:
        """Get audio recording settings"""
        return self.get("audio_settings", {})

    def get_transcription_settings(self) -> Dict:
        """Get transcription settings"""
        return self.get("transcription_settings", {})

    def get_feedback_settings(self) -> Dict:
        """Get feedback analysis settings"""
        return self.get("feedback_settings", {})

    def get_research_settings(self) -> Dict:
        """Get guest research settings"""
        return self.get("research_settings", {})

    def get_logging_settings(self) -> Dict:
        """Get logging settings"""
        return self.get("logging", {})

    def get_ui_settings(self) -> Dict:
        """Get UI settings"""
        return self.get("ui_settings", {})

    def is_configured(self) -> bool:
        """Check if the system is properly configured"""
        api_key = self.get_openai_api_key()
        return bool(api_key and api_key.strip())

    def validate_config(self) -> Dict:
        """Validate configuration and return issues"""
        issues = []

        # Check OpenAI API key
        if not self.get_openai_api_key():
            issues.append("OpenAI API key not configured")

        # Check audio settings
        audio_settings = self.get_audio_settings()
        if not audio_settings.get("sample_rate"):
            issues.append("Audio sample rate not configured")

        # Check file permissions
        try:
            test_file = Path("test_config_write.tmp")
            test_file.write_text("test")
            test_file.unlink()
        except Exception:
            issues.append("Cannot write to current directory")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "configured": self.is_configured(),
        }

    def export_config(self) -> Dict:
        """Export current configuration (without sensitive data)"""
        export_config = self.config.copy()

        # Mask API key
        if "openai_api_key" in export_config:
            api_key = export_config["openai_api_key"]
            if api_key:
                export_config["openai_api_key"] = (
                    api_key[:8] + "..." if len(api_key) > 8 else "***"
                )

        return export_config

    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        default_config = {
            "openai_api_key": "",
            "audio_settings": {
                "sample_rate": 16000,
                "channels": 1,
                "dtype": "int16",
                "chunk_size": 1024,
            },
            "transcription_settings": {
                "model": "whisper-1",
                "language": "en",
                "temperature": 0.0,
            },
            "feedback_settings": {
                "model": "gpt-3.5-turbo",
                "max_tokens": 500,
                "temperature": 0.7,
            },
            "research_settings": {
                "model": "gpt-3.5-turbo",
                "max_tokens": 800,
                "temperature": 0.7,
            },
            "logging": {
                "level": "INFO",
                "file": "soapboxx.log",
                "max_size": "10MB",
                "backup_count": 5,
            },
            "ui_settings": {
                "theme": "default",
                "auto_save": True,
                "auto_transcribe": True,
            },
        }

        self.config = default_config
        self._save_config(default_config)


# Global config instance
config = Config()

# Example usage
if __name__ == "__main__":
    # Test configuration
    print("Configuration loaded:")
    print(f"OpenAI API Key configured: {config.is_configured()}")
    print(f"Audio settings: {config.get_audio_settings()}")
    print(f"Validation: {config.validate_config()}")
