# SoapBoxx Backend

A comprehensive backend system for podcast recording, transcription, feedback analysis, and guest research.

## 🏗️ Architecture

The backend consists of several modular components that work together to provide a complete podcast production system:

### Core Components

1. **Audio Recorder** (`audio_recorder.py`)
   - Real-time audio capture using sounddevice
   - Configurable sample rate, channels, and data type
   - Thread-safe audio chunk processing

2. **Transcriber** (`transcriber.py`)
   - OpenAI Whisper API integration
   - Support for multiple audio formats
   - Real-time transcription capabilities

3. **Feedback Engine** (`feedback_engine.py`)
   - AI-powered podcast feedback analysis
   - Coaching suggestions and performance metrics
   - Focused analysis on specific areas (clarity, engagement, etc.)

4. **Guest Research** (`guest_research.py`)
   - AI-powered guest research and interview preparation
   - Talking points and question generation
   - Professional background analysis

5. **Logger** (`logger.py`)
   - Comprehensive logging system
   - Error tracking and debugging
   - Audio and UI issue logging

6. **Configuration Manager** (`config.py`)
   - Centralized configuration management
   - API key handling
   - Settings validation and persistence

7. **Error Tracker** (`error_tracker.py`)
   - Comprehensive error monitoring and categorization
   - Error analytics and health scoring
   - Alert system for error thresholds
   - Error resolution tracking

8. **Integration Core** (`soapboxx_core.py`)
   - Main integration layer
   - Session management
   - Real-time processing coordination

## 🚀 Quick Start

### Prerequisites

1. **Python 3.8+**
2. **OpenAI API Key** (for transcription and AI features)
3. **Audio input device** (microphone)

### Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up API key:**
   ```bash
   # Option 1: Environment variable
   export OPENAI_API_KEY="your-api-key-here"
   
   # Option 2: Configuration file
   python -c "from backend.config import config; config.set_openai_api_key('your-api-key-here')"
   ```

3. **Test the system:**
   ```bash
   python backend/test_backend.py
   ```

## 📋 Usage Examples

### Basic Recording and Transcription

```python
from backend.soapboxx_core import SoapBoxxCore

# Initialize the system
core = SoapBoxxCore()

# Start recording
core.start_recording("My Podcast Episode")

# ... record for some time ...

# Stop recording and get results
results = core.stop_recording()
print(f"Transcript: {results['transcript']}")
print(f"Feedback: {results['feedback']}")
```

### Guest Research

```python
from backend.guest_research import GuestResearch

research = GuestResearch()

# Research a guest
guest_info = research.research(
    guest_name="Jane Doe",
    website="https://janedoe.com",
    additional_info="AI researcher and podcast host"
)

print(f"Profile: {guest_info['profile']}")
print(f"Talking Points: {guest_info['talking_points']}")
print(f"Questions: {guest_info['questions']}")
```

### Feedback Analysis

```python
from backend.feedback_engine import FeedbackEngine

engine = FeedbackEngine()

# Analyze a transcript
feedback = engine.analyze(
    transcript="Hello, welcome to the show! Today we're talking about AI..."
)

print(f"Listener Feedback: {feedback['listener_feedback']}")
print(f"Coaching Suggestions: {feedback['coaching_suggestions']}")
```

### Configuration Management

```python
from backend.config import config

# Set API key
config.set_openai_api_key("your-api-key")

# Get audio settings
audio_settings = config.get_audio_settings()
print(f"Sample Rate: {audio_settings['sample_rate']}")

# Validate configuration
validation = config.validate_config()
print(f"Valid: {validation['valid']}")
```

### Error Tracking

```python
from backend.error_tracker import error_tracker, ErrorSeverity, ErrorCategory

# Track errors
error_tracker.track_error("APIError", "Connection failed", severity=ErrorSeverity.HIGH)

# Use convenience functions
from backend.error_tracker import track_api_error, track_audio_error, track_transcription_error
track_api_error("API connection failed")
track_audio_error("Microphone not detected")
track_transcription_error("Transcription failed")

# Get error summary
summary = error_tracker.get_error_summary()
print(f"Total errors: {summary['total_errors']}")
print(f"Health score: {error_tracker.get_health_score():.1f}/100")

# Get detailed analytics
analytics = error_tracker.get_error_analytics(days=7)
print(f"Errors in last 7 days: {analytics['total_errors_in_period']}")

# Filter errors
critical_errors = error_tracker.get_errors(severity=ErrorSeverity.CRITICAL)
unresolved_errors = error_tracker.get_errors(resolved=False)
audio_errors = error_tracker.get_errors(category=ErrorCategory.AUDIO)

# Resolve errors
error_tracker.resolve_error(0, "Fixed API connection issue")
```

## 🔧 Configuration

### Audio Settings

```python
config.set("audio_settings.sample_rate", 16000)
config.set("audio_settings.channels", 1)
config.set("audio_settings.dtype", "int16")
```

### Transcription Settings

```python
config.set("transcription_settings.model", "whisper-1")
config.set("transcription_settings.language", "en")
```

### Feedback Settings

```python
config.set("feedback_settings.model", "gpt-3.5-turbo")
config.set("feedback_settings.max_tokens", 500)
```

## 🧪 Testing

Run the comprehensive test suite:

```bash
python backend/test_backend.py
```

This will test:
- ✅ Configuration system
- ✅ Audio recording
- ✅ Transcription (with fallback)
- ✅ Feedback analysis
- ✅ Guest research
- ✅ Logging system
- ✅ Error tracking
- ✅ Full integration

## 📊 Features

### ✅ Completed Features

1. **Real-time Audio Recording**
   - Multi-platform audio capture
   - Configurable audio settings
   - Thread-safe processing

2. **AI-Powered Transcription**
   - OpenAI Whisper integration
   - Real-time transcription
   - Multiple audio format support

3. **Intelligent Feedback System**
   - Podcast-specific analysis
   - Coaching suggestions
   - Performance benchmarking

4. **Guest Research Engine**
   - Automated guest research
   - Interview question generation
   - Talking points creation

5. **Comprehensive Logging**
   - Error tracking
   - Debug information
   - Performance monitoring

6. **Configuration Management**
   - Centralized settings
   - API key management
   - Validation and persistence

7. **Error Tracking & Monitoring**
   - Comprehensive error categorization
   - Health scoring and analytics
   - Alert system for error thresholds
   - Error resolution tracking

### 🔄 Real-time Processing

The system supports real-time processing with:
- Live audio capture
- Streaming transcription
- Immediate feedback updates
- Session management

### 🛡️ Error Handling

Robust error handling includes:
- Graceful API failures
- Audio device issues
- Network connectivity problems
- Configuration validation

## 📁 File Structure

```
backend/
├── audio_recorder.py      # Audio capture system
├── transcriber.py         # Speech-to-text conversion
├── feedback_engine.py     # AI feedback analysis
├── guest_research.py      # Guest research system
├── logger.py             # Logging system
├── config.py             # Configuration management
├── error_tracker.py      # Error tracking and monitoring
├── soapboxx_core.py      # Main integration layer
├── test_backend.py       # Comprehensive test suite
└── README.md            # This documentation
```

## 🔑 API Requirements

### OpenAI API
- **Whisper API**: For transcription
- **GPT-3.5-turbo**: For feedback analysis and guest research

### Audio Requirements
- **sounddevice**: Audio capture
- **numpy**: Audio processing
- **pydub**: Audio format conversion

## 🚨 Troubleshooting

### Common Issues

1. **"No OpenAI API key configured"**
   - Set your API key: `config.set_openai_api_key("your-key")`
   - Or use environment variable: `export OPENAI_API_KEY="your-key"`

2. **Audio recording fails**
   - Check microphone permissions
   - Verify audio device is connected
   - Test with: `python backend/test_backend.py`

3. **Transcription errors**
   - Verify API key is valid
   - Check internet connection
   - Ensure audio quality is sufficient

4. **Import errors**
   - Install dependencies: `pip install -r requirements.txt`
   - Check Python version (3.8+ required)

### Debug Mode

Enable detailed logging:

```python
from backend.logger import Logger
logger = Logger()
logger.logger.setLevel("DEBUG")
```

## 📈 Performance

### Optimization Tips

1. **Audio Quality**: Use 16kHz sample rate for optimal transcription
2. **Chunk Size**: Adjust audio chunk size based on your needs
3. **API Limits**: Monitor OpenAI API usage and rate limits
4. **Memory**: Large audio files may require more memory

### Monitoring

The system provides comprehensive monitoring:
- Real-time status updates
- Performance metrics
- Error tracking
- Session analytics

## 🤝 Contributing

To contribute to the backend:

1. **Follow the existing code structure**
2. **Add comprehensive tests**
3. **Update documentation**
4. **Validate configuration changes**

## 📄 License

This backend is part of the SoapBoxx project. See the main project license for details.

---

**🎉 The backend is now complete and ready for production use!** 