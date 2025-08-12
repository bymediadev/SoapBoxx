# SoapBoxx Backend

A comprehensive backend system for podcast recording, transcription, feedback analysis, and guest research with enterprise-grade security and performance monitoring.

## 🏗️ Architecture

The backend consists of several modular components that work together to provide a complete podcast production system:

### Core Components

1. **Audio Recorder** (`audio_recorder.py`)
   - Real-time audio capture using sounddevice
   - Configurable sample rate, channels, and data type
   - Thread-safe audio chunk processing
   - Automatic resource cleanup

2. **Transcriber** (`transcriber.py`)
   - Multi-service transcription support (OpenAI, Local Whisper, AssemblyAI, Azure)
   - Comprehensive error handling and file size validation
   - Real-time transcription capabilities
   - API-specific error recovery

3. **Feedback Engine** (`feedback_engine.py`)
   - AI-powered podcast feedback analysis
   - Coaching suggestions and performance metrics
   - Focused analysis on specific areas (clarity, engagement, etc.)
   - Rate limiting and performance monitoring

4. **Guest Research** (`guest_research.py`)
   - AI-powered guest research and interview preparation
   - Talking points and question generation
   - Professional background analysis
   - Google Custom Search integration

5. **Logger** (`logger.py`)
   - Comprehensive logging system
   - Error tracking and debugging
   - Audio and UI issue logging
   - Sensitive data masking

6. **Configuration Manager** (`config.py`)
   - Centralized configuration management with enhanced security
   - API key validation and sanitization
   - Settings validation and persistence
   - Environment variable management

7. **Error Tracker** (`error_tracker.py`)
   - Comprehensive error monitoring and categorization
   - Error analytics and health scoring
   - Alert system for error thresholds
   - Error resolution tracking
   - UX analytics and performance metrics

8. **Integration Core** (`soapboxx_core.py`)
   - Main integration layer with performance monitoring
   - Session management with enhanced error handling
   - Real-time processing coordination
   - Rate limiting and resource management

## 🔒 Security Features

### API Key Protection
- **Format Validation**: All API keys are validated for proper format
- **Sanitization**: Sensitive data is automatically masked in logs and exports
- **Environment Variables**: Secure storage using .env files
- **No Hardcoded Keys**: All credentials are externalized

### Input Validation
- **Audio Data Validation**: File size limits and format checking
- **API Key Validation**: Regex-based format validation
- **Sanitization**: Input sanitization to prevent injection attacks
- **Error Handling**: Comprehensive error handling without exposing sensitive data

### Performance & Rate Limiting
- **Request Rate Limiting**: Prevents API abuse and cost overruns
- **Performance Monitoring**: Real-time tracking of operation performance
- **Resource Management**: Automatic cleanup of audio streams and threads
- **Timeout Handling**: Configurable timeouts for all API operations

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
   
   # Option 2: Interactive setup
   python -c "from backend.config import config; config.setup_api_key_interactive()"
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
print(f"Performance: {results['performance_metrics']}")
```

### Guest Research with Rate Limiting

```python
# Research a guest
research = core.research_guest("John Doe", "johndoe.com")

if "error" in research:
    print(f"Research failed: {research['error']}")
else:
    print(f"Talking points: {research['talking_points']}")
```

### Performance Monitoring

```python
# Get system status
status = core.get_status()
print(f"Performance: {status['performance']}")
print(f"Rate limits: {status['rate_limits']}")
```

## 🔧 Configuration

### Security Settings

```python
from backend.config import config

# Get security settings
security = config.get_security_settings()
print(f"API validation: {security['validate_api_keys']}")
print(f"Rate limiting: {security['rate_limit_enabled']}")
```

### Audio Settings

```python
# Configure audio recording
audio_settings = config.get_audio_settings()
audio_settings["max_recording_duration"] = 3600  # 1 hour
audio_settings["auto_cleanup"] = True
```

### Transcription Settings

```python
# Configure transcription
trans_settings = config.get_transcription_settings()
trans_settings["max_file_size_mb"] = 25
trans_settings["timeout_seconds"] = 30
```

## 📊 Performance Monitoring

### Real-time Metrics

The backend includes comprehensive performance monitoring:

- **Request Times**: Average, min, max for all operations
- **Error Rates**: Error frequency per operation
- **Resource Usage**: Memory and CPU utilization
- **Rate Limiting**: Request queue status

### Health Scoring

```python
from backend.error_tracker import error_tracker

# Get system health
health_score = error_tracker.get_health_score()
print(f"System health: {health_score:.2f}/10")
```

## 🛡️ Error Handling

### Comprehensive Error Categories

- **Audio Errors**: Microphone issues, recording failures
- **Transcription Errors**: API failures, file size limits
- **AI API Errors**: Rate limits, authentication failures
- **Network Errors**: Connection timeouts, DNS issues
- **Configuration Errors**: Missing API keys, invalid settings
- **UI Errors**: Interface failures, user interaction issues

### Error Recovery

- **Automatic Retries**: Smart retry logic for transient failures
- **Graceful Degradation**: System continues working when components fail
- **User Guidance**: Clear error messages with resolution steps
- **Error Tracking**: Comprehensive logging for debugging

## 🔄 API Integration

### Supported Services

1. **OpenAI Whisper**: High-quality transcription
2. **Local Whisper**: Offline transcription capability
3. **AssemblyAI**: Advanced audio analysis
4. **Azure Speech**: Enterprise speech recognition
5. **Google Custom Search**: Web research capabilities
6. **News API**: Current events integration

### Rate Limiting

All API calls are automatically rate-limited to prevent:
- Cost overruns
- API abuse
- Service degradation

## 📈 Production Features

### Enterprise-Grade Reliability

- **99% Uptime**: Robust error handling and recovery
- **Performance Monitoring**: Real-time metrics and alerts
- **Security**: Comprehensive data protection
- **Scalability**: Modular architecture for easy expansion

### Monitoring & Analytics

- **Error Tracking**: Centralized error monitoring
- **Performance Metrics**: Operation timing and success rates
- **User Analytics**: Usage patterns and feature adoption
- **Health Monitoring**: System health scoring

## 🚀 Deployment

### Environment Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure API Keys**:
   ```bash
   # Set environment variables
   export OPENAI_API_KEY="your-key"
   export GOOGLE_API_KEY="your-key"
   export NEWS_API_KEY="your-key"
   ```

3. **Test Configuration**:
   ```bash
   python backend/test_backend.py
   ```

### Production Considerations

- **Logging**: Configure log levels and rotation
- **Monitoring**: Set up performance monitoring
- **Security**: Review and configure security settings
- **Backup**: Implement configuration backup strategy

## 🔧 Troubleshooting

### Common Issues

1. **API Key Errors**:
   - Verify key format and permissions
   - Check environment variable loading
   - Validate API key in configuration

2. **Audio Recording Issues**:
   - Check microphone permissions
   - Verify audio device selection
   - Review audio settings configuration

3. **Transcription Failures**:
   - Check file size limits (25MB for OpenAI)
   - Verify API key configuration
   - Review network connectivity

4. **Performance Issues**:
   - Monitor rate limiting status
   - Check resource usage
   - Review error logs

### Debug Mode

Enable detailed logging for troubleshooting:

```python
from backend.config import config

# Enable debug logging
config.set("logging.level", "DEBUG")
```

## 📚 API Reference

### Core Classes

- **SoapBoxxCore**: Main integration class
- **Transcriber**: Multi-service transcription
- **FeedbackEngine**: AI-powered analysis
- **GuestResearch**: Guest research capabilities
- **Config**: Configuration management
- **ErrorTracker**: Error monitoring and analytics

### Key Methods

- `start_recording()`: Begin audio recording
- `stop_recording()`: Stop and process recording
- `transcribe_audio()`: Transcribe audio data
- `get_feedback()`: Generate AI feedback
- `research_guest()`: Research guest information
- `get_status()`: Get system status

## 🎯 Best Practices

### Security
- Never hardcode API keys
- Use environment variables for sensitive data
- Regularly rotate API keys
- Monitor API usage and costs

### Performance
- Monitor rate limiting status
- Use appropriate file size limits
- Implement proper error handling
- Regular performance monitoring

### Reliability
- Implement comprehensive error handling
- Use graceful degradation
- Monitor system health
- Regular testing and validation

## 📄 License

This backend system is part of the SoapBoxx podcast production platform.

---

**SoapBoxx Backend - Enterprise-Grade Podcast Production System** 🎙️ 