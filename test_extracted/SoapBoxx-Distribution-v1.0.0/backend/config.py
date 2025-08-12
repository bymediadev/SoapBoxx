# backend/config.py
import json
import os
import re
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration manager for SoapBoxx backend with enhanced security"""

    def __init__(self, config_file: str = "soapboxx_config.json"):
        self.config_file = Path(config_file)
        self.config = self._load_config()
        self._validate_security_settings()

    def _validate_security_settings(self):
        """Validate and enhance security settings"""
        # Ensure sensitive data is not logged
        if "logging" in self.config:
            log_settings = self.config["logging"]
            if "sensitive_fields" not in log_settings:
                log_settings["sensitive_fields"] = [
                    "openai_api_key",
                    "google_api_key",
                    "news_api_key",
                    "youtube_api_key",
                    "podchaser_api_key",
                    "listen_notes_api_key",
                ]
            if "mask_sensitive_data" not in log_settings:
                log_settings["mask_sensitive_data"] = True

    def _load_config(self) -> Dict:
        """Load configuration from file or create default with enhanced security"""
        default_config = {
            "openai_api_key": "",
            "google_cse_id": "0628a50c1bb4e4976",  # Default Google CSE ID
            "audio_settings": {
                "sample_rate": 16000,
                "channels": 1,
                "dtype": "int16",
                "chunk_size": 1024,
                "max_recording_duration": 3600,  # 1 hour max
                "auto_cleanup": True,
            },
            "transcription_settings": {
                "model": "whisper-1",
                "language": "en",
                "temperature": 0.0,
                "max_file_size_mb": 25,
                "timeout_seconds": 30,
            },
            "feedback_settings": {
                "model": "gpt-4",
                "max_tokens": 800,
                "temperature": 0.3,
                "analysis_depth": "comprehensive",
                "enable_caching": True,
                "cache_ttl": 3600,
                "enable_quantitative_scoring": True,
                "enable_comparative_analysis": True,
                "default_focus_areas": [
                    "clarity",
                    "engagement",
                    "structure",
                    "energy",
                    "professionalism",
                ],
                "scoring_weights": {
                    "clarity": 0.25,
                    "engagement": 0.25,
                    "structure": 0.2,
                    "energy": 0.15,
                    "professionalism": 0.15,
                },
            },
            "research_settings": {
                "model": "gpt-3.5-turbo",
                "max_tokens": 800,
                "temperature": 0.7,
                "search_depth": "moderate",
            },
            "logging": {
                "level": "INFO",
                "file": "soapboxx.log",
                "max_size": "10MB",
                "backup_count": 5,
                "mask_sensitive_data": True,
                "sensitive_fields": [
                    "openai_api_key",
                    "google_api_key",
                    "news_api_key",
                    "youtube_api_key",
                    "podchaser_api_key",
                    "listen_notes_api_key",
                ],
            },
            "ui_settings": {
                "theme": "default",
                "auto_save": True,
                "auto_transcribe": True,
                "show_api_status": True,
                "hide_sensitive_data": True,
            },
            "security": {
                "validate_api_keys": True,
                "sanitize_inputs": True,
                "rate_limit_enabled": True,
                "max_concurrent_requests": 5,
                "request_timeout": 30,
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
        """Save configuration to file with security validation"""
        try:
            # Sanitize sensitive data before saving
            sanitized_config = self._sanitize_config_for_saving(config)
            with open(self.config_file, "w") as f:
                json.dump(sanitized_config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def _sanitize_config_for_saving(self, config: Dict) -> Dict:
        """Remove sensitive data before saving to file"""
        sanitized = config.copy()

        # Remove API keys from saved config
        sensitive_fields = [
            "openai_api_key",
            "google_api_key",
            "news_api_key",
            "youtube_api_key",
            "podchaser_api_key",
            "listen_notes_api_key",
        ]

        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = "[HIDDEN]"

        return sanitized

    def get(self, key: str, default=None):
        """Get configuration value by key (supports dot notation)"""
        keys = key.split(".")
        value = self.config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

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
        self._save_config(self.config)

    def debug_api_keys(self):
        """Debug method to check API key status"""
        print("🔍 DEBUG: Checking API key status...")

        # Check environment variables
        openai_env = os.getenv("OPENAI_API_KEY")
        google_env = os.getenv("GOOGLE_API_KEY")
        news_env = os.getenv("NEWS_API_KEY")

        print(f"Environment variables:")
        print(f"  OPENAI_API_KEY: {'✅ Set' if openai_env else '❌ Not set'}")
        if openai_env:
            print(f"    Length: {len(openai_env)} characters")
            print(f"    Starts with 'sk-': {openai_env.startswith('sk-')}")
            print(f"    Preview: {openai_env[:10]}...")

        print(f"  GOOGLE_API_KEY: {'✅ Set' if google_env else '❌ Not set'}")
        print(f"  NEWS_API_KEY: {'✅ Set' if news_env else '❌ Not set'}")

        # Check config file
        config_openai = self.get("openai_api_key")
        print(f"Config file:")
        print(f"  openai_api_key: {'✅ Set' if config_openai else '❌ Not set'}")
        if config_openai:
            print(f"    Length: {len(config_openai)} characters")
            print(f"    Starts with 'sk-': {config_openai.startswith('sk-')}")
            print(f"    Preview: {config_openai[:10]}...")

        # Test validation
        print(f"Validation test:")
        if openai_env:
            print(
                f"  Environment key validation: {self._validate_api_key_format(openai_env, 'openai')}"
            )
        if config_openai:
            print(
                f"  Config key validation: {self._validate_api_key_format(config_openai, 'openai')}"
            )

    def get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key with validation - CRITICAL FOR SYSTEM OPERATION"""
        api_key = self.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
        if api_key and self._validate_api_key_format(api_key, "openai"):
            return api_key
        return None

    def set_openai_api_key(self, api_key: str):
        """Set OpenAI API key with validation - CRITICAL FOR SYSTEM OPERATION"""
        if self._validate_api_key_format(api_key, "openai"):
            self.set("openai_api_key", api_key)
            print("✅ OpenAI API key configured successfully - CRITICAL COMPONENT")
        else:
            raise ValueError("Invalid OpenAI API key format - CRITICAL ERROR")

    def _validate_api_key_format(self, api_key: str, key_type: str) -> bool:
        """Validate API key format for security"""
        if not api_key or api_key.strip() == "":
            return False

        if key_type == "openai":
            # OpenAI keys start with sk- and can have varying lengths
            # CRITICAL: This is the most important API key for the system
            # More flexible validation for different OpenAI key formats
            api_key_clean = api_key.strip()

            # Check if it starts with sk- (required for OpenAI)
            if not api_key_clean.startswith("sk-"):
                print("❌ Invalid OpenAI API key format - CRITICAL ERROR")
                print("   OpenAI API keys must start with 'sk-'")
                print(
                    f"   Current key: {api_key_clean[:10]}... (length: {len(api_key_clean)})"
                )
                return False

            # Check if it has reasonable length (OpenAI keys can vary)
            if len(api_key_clean) < 10:  # Very permissive minimum
                print("❌ Invalid OpenAI API key format - CRITICAL ERROR")
                print(f"   OpenAI API key too short: {len(api_key_clean)} characters")
                print(f"   Current key: {api_key_clean}")
                return False

            # Check if it contains only valid characters (more permissive)
            if not re.match(r"^sk-[a-zA-Z0-9_-]+$", api_key_clean):
                print("❌ Invalid OpenAI API key format - CRITICAL ERROR")
                print("   OpenAI API key contains invalid characters")
                print(f"   Current key: {api_key_clean[:10]}...")
                return False

            print("🔑 OpenAI API key format validated - CRITICAL COMPONENT")
            print(f"   Key length: {len(api_key_clean)} characters")
            return True

        elif key_type == "google":
            # Google API keys are typically 39 characters
            return bool(re.match(r"^AIza[a-zA-Z0-9]{35}$", api_key.strip()))
        elif key_type == "news":
            # News API keys are typically 32 characters
            return bool(re.match(r"^[a-f0-9]{32}$", api_key.strip()))

        # For other API types, just check basic format
        return len(api_key.strip()) > 10

    def setup_api_key_interactive(self):
        """Interactive API key setup with validation - CRITICAL SETUP"""
        print("🔑 CRITICAL: Setting up OpenAI API key...")
        print("⚠️  This is the MOST IMPORTANT API key for SoapBoxx operation!")
        print("   - Transcription (Whisper API)")
        print("   - AI Feedback Analysis")
        print("   - Guest Research")
        print("   - Podcast Coaching")
        print()

        while True:
            api_key = input(
                "Enter your OpenAI API key (CRITICAL - or press Enter to skip): "
            ).strip()

            if not api_key:
                print("⚠️  CRITICAL WARNING: No OpenAI API key provided!")
                print("   - Transcription will fail")
                print("   - AI feedback will be unavailable")
                print("   - Guest research will be limited")
                print("   - Most core features will not work")
                break

            if self._validate_api_key_format(api_key, "openai"):
                self.set_openai_api_key(api_key)
                print("🎉 CRITICAL SUCCESS: OpenAI API key configured!")
                print("   ✅ Transcription will work")
                print("   ✅ AI feedback will be available")
                print("   ✅ Guest research will work")
                print("   ✅ All core features enabled")
                break
            else:
                print("❌ CRITICAL ERROR: Invalid API key format!")
                print("   OpenAI API keys should:")
                print("   - Start with 'sk-'")
                print("   - Be between 20-100 characters long")
                print("   - Contain only letters, numbers, hyphens, and underscores")
                print("   Get your key at: https://platform.openai.com/api-keys")

    def is_openai_configured(self) -> bool:
        """Check if OpenAI API is properly configured - CRITICAL CHECK"""
        api_key = self.get_openai_api_key()
        if api_key:
            print("✅ CRITICAL: OpenAI API is properly configured")
            return True
        else:
            print("❌ CRITICAL ERROR: OpenAI API is NOT configured!")
            print("   This will severely limit system functionality")
            return False

    def get_openai_status(self) -> Dict:
        """Get detailed OpenAI API status - CRITICAL STATUS"""
        api_key = self.get_openai_api_key()

        status = {
            "configured": bool(api_key),
            "critical": True,  # OpenAI is critical for system operation
            "features_enabled": [],
            "features_disabled": [],
            "recommendations": [],
        }

        if api_key:
            status["features_enabled"] = [
                "Audio Transcription (Whisper API)",
                "AI Feedback Analysis",
                "Guest Research",
                "Podcast Coaching",
                "Content Analysis",
            ]
            status["recommendations"] = [
                "Monitor API usage to control costs",
                "Set up billing alerts",
                "Consider usage limits for production",
            ]
        else:
            status["features_disabled"] = [
                "Audio Transcription (Whisper API)",
                "AI Feedback Analysis",
                "Guest Research",
                "Podcast Coaching",
                "Content Analysis",
            ]
            status["recommendations"] = [
                "Get OpenAI API key from https://platform.openai.com/api-keys",
                "Configure the key using setup_api_key_interactive()",
                "This is CRITICAL for system operation",
            ]

        return status

    def setup_environment_variables(self):
        """Set up environment variables for the application"""
        print("🔧 Setting up environment variables...")

        # OpenAI API Key
        if not os.getenv("OPENAI_API_KEY"):
            api_key = input(
                "Enter your OpenAI API key (or press Enter to skip): "
            ).strip()
            if api_key:
                os.environ["OPENAI_API_KEY"] = api_key
                print("✅ OpenAI API key set in environment")

        # Google API Key
        if not os.getenv("GOOGLE_API_KEY"):
            google_key = input(
                "Enter your Google API key (or press Enter to skip): "
            ).strip()
            if google_key:
                os.environ["GOOGLE_API_KEY"] = google_key
                print("✅ Google API key set in environment")

        # News API Key
        if not os.getenv("NEWS_API_KEY"):
            news_key = input(
                "Enter your News API key (or press Enter to skip): "
            ).strip()
            if news_key:
                os.environ["NEWS_API_KEY"] = news_key
                print("✅ News API key set in environment")

        # YouTube API Key
        if not os.getenv("YOUTUBE_API_KEY"):
            youtube_key = input(
                "Enter your YouTube API key (or press Enter to skip): "
            ).strip()
            if youtube_key:
                os.environ["YOUTUBE_API_KEY"] = youtube_key
                print("✅ YouTube API key set in environment")

        print("🎉 Environment setup complete!")

    def get_google_cse_id(self) -> Optional[str]:
        """Get Google Custom Search Engine ID"""
        return self.get("google_cse_id") or os.getenv("GOOGLE_CSE_ID")

    def set_google_cse_id(self, cse_id: str):
        """Set Google Custom Search Engine ID"""
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
        """Get research settings"""
        return self.get("research_settings", {})

    def get_logging_settings(self) -> Dict:
        """Get logging settings"""
        return self.get("logging", {})

    def get_ui_settings(self) -> Dict:
        """Get UI settings"""
        return self.get("ui_settings", {})

    def get_security_settings(self) -> Dict:
        """Get security settings"""
        return self.get("security", {})

    def is_configured(self) -> bool:
        """Check if the system is properly configured"""
        return bool(self.get_openai_api_key())

    def validate_config(self) -> Dict:
        """Validate configuration and return status"""
        issues = []
        warnings = []

        # Check OpenAI API key
        if not self.get_openai_api_key():
            issues.append("OpenAI API key not configured")

        # Check audio settings
        audio_settings = self.get_audio_settings()
        if audio_settings.get("sample_rate", 0) <= 0:
            issues.append("Invalid sample rate in audio settings")

        # Check transcription settings
        trans_settings = self.get_transcription_settings()
        if trans_settings.get("max_file_size_mb", 0) <= 0:
            issues.append("Invalid max file size in transcription settings")

        # Check security settings
        security_settings = self.get_security_settings()
        if not security_settings.get("validate_api_keys", True):
            warnings.append("API key validation is disabled")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "configured": self.is_configured(),
        }

    def export_config(self) -> Dict:
        """Export configuration (excluding sensitive data)"""
        export_config = self.config.copy()

        # Remove sensitive data
        sensitive_fields = [
            "openai_api_key",
            "google_api_key",
            "news_api_key",
            "youtube_api_key",
            "podchaser_api_key",
            "listen_notes_api_key",
        ]

        for field in sensitive_fields:
            if field in export_config:
                export_config[field] = "[HIDDEN]"

        return export_config

    def reset_to_defaults(self):
        """Reset configuration to defaults"""
        default_config = self._load_config()
        self.config = default_config
        self._save_config(self.config)
        print("✅ Configuration reset to defaults")


# Global config instance
config = Config()
