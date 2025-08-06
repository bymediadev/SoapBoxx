# 🎙️ SoapBoxx

**AI-Powered Podcast Recording and Production System**

SoapBoxx is a comprehensive podcast recording system that combines real-time audio capture, AI-powered transcription, intelligent feedback analysis, and guest research capabilities.

## ✨ Features

- 🎤 **Real-time Audio Recording** - High-quality audio capture with configurable settings
- 🤖 **AI Transcription** - OpenAI Whisper integration for accurate speech-to-text
- 💡 **Intelligent Feedback** - AI-powered podcast coaching and performance analysis
- 🔍 **Guest Research** - Automated guest research and interview preparation
- 📊 **Error Tracking** - Comprehensive error monitoring and health scoring
- 🎨 **Modern UI** - PyQt6-based interface with real-time updates

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- OpenAI API key (for transcription and AI features)
- Microphone/audio input device

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd SoapBoxx
   ```

2. **Run the setup script**
   ```bash
   python setup.py
   ```
   
   This will:
   - Install dependencies
   - Configure API keys
   - Test the backend
   - Create shortcuts

3. **Alternative manual setup**
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Configure API key
   python -c "from backend.config import Config; Config().setup_api_key_interactive()"
   ```

## 🎯 Usage

### Starting the Application

```bash
# Method 1: Direct launch
python frontend/main_window.py

# Method 2: Using the generated shortcut
run_soapboxx.bat
```

### Recording a Podcast

1. **Open SoapBoxx** - Launch the application
2. **Check Configuration** - Ensure API key is configured (green status)
3. **Start Recording** - Click "Start Recording" button
4. **Speak Naturally** - The system will capture and transcribe in real-time
5. **Get Feedback** - AI will analyze your content and provide coaching suggestions
6. **Stop Recording** - Click "Stop Recording" when finished

### Features by Tab

#### 🎙️ SoapBoxx Tab
- **Recording Controls** - Start/stop recording with visual feedback
- **Real-time Transcript** - Live transcription display
- **AI Feedback** - Instant coaching and performance analysis
- **Status Monitoring** - System health and configuration status

#### 📰 Scoop Tab
- **News Integration** - Coming soon
- **Content Research** - Coming soon

#### 🔊 Reverb Tab
- **Audio Processing** - Coming soon
- **Effects & Filters** - Coming soon

## 🔧 Configuration

### API Keys

#### OpenAI API Key
Required for transcription and AI features:

1. **Get an API key** at [OpenAI Platform](https://platform.openai.com/api-keys)
2. **Configure the key**:
   ```python
   from backend.config import Config
   config = Config()
   config.set_openai_api_key("your-api-key-here")
   ```

### Audio Settings

Configure audio recording parameters in `soapboxx_config.json`:

```json
{
  "audio_settings": {
    "sample_rate": 16000,
    "channels": 1,
    "dtype": "int16",
    "chunk_size": 1024
  }
}
```

## 🧪 Testing

### Run Backend Tests

```bash
cd backend
python test_backend.py
```

This will test:
- ✅ Configuration system
- ✅ Audio recording
- ✅ Transcription (with fallback)
- ✅ Feedback analysis
- ✅ Guest research
- ✅ Logging system
- ✅ Full integration

### Test Report

Tests generate a report at `backend_test_report.json` with detailed results.

## 🏗️ Architecture

### Backend Components

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
└── test_backend.py       # Comprehensive test suite
```

### Frontend Components

```
frontend/
├── main_window.py        # Main application window
├── soapboxx_tab.py       # Recording and transcription tab
├── scoop_tab.py          # News and research tab
├── reverb_tab.py         # Audio processing tab
└── feedback_dialog.py    # Issue reporting dialog
```

## 🐛 Troubleshooting

### Common Issues

#### "No OpenAI API key configured"
- Run: `python -c "from backend.config import Config; Config().setup_api_key_interactive()"`
- Or manually edit `soapboxx_config.json`

#### "Audio recording fails"
- Check microphone permissions
- Verify audio device is connected
- Test with: `python backend/test_backend.py`

#### "Transcription errors"
- Verify API key is valid
- Check internet connection
- Ensure audio quality is sufficient

#### "Import errors"
- Install dependencies: `pip install -r requirements.txt`
- Check Python version (3.8+ required)

### Debug Mode

Enable detailed logging:

```python
from backend.logger import Logger
logger = Logger()
logger.logger.setLevel("DEBUG")
```

## 📊 Performance

### Optimization Tips

1. **Audio Quality** - Use 16kHz sample rate for optimal transcription
2. **Chunk Size** - Adjust audio chunk size based on your needs
3. **API Limits** - Monitor OpenAI API usage and rate limits
4. **Memory** - Large audio files may require more memory

### Monitoring

The system provides comprehensive monitoring:
- Real-time status updates
- Performance metrics
- Error tracking
- Session analytics

## 🤝 Contributing

To contribute to SoapBoxx:

1. **Follow the existing code structure**
2. **Add comprehensive tests**
3. **Update documentation**
4. **Validate configuration changes**

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:

1. Check the troubleshooting section above
2. Review the test reports
3. Check the logs in `soapboxx.log`
4. Open an issue with detailed information

---

**🎉 Ready to create amazing podcasts with AI assistance!** 