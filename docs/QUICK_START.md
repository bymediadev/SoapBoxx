# 🚀 SoapBoxx Quick Start Guide

## ✅ System Status: READY TO USE!

Your SoapBoxx podcast recording system is now fully operational!

## 🎯 What's Working

- ✅ **Backend Tests**: All 7 tests passing
- ✅ **API Configuration**: OpenAI API key configured
- ✅ **Frontend Integration**: Modern PyQt6 interface
- ✅ **Audio Recording**: Real-time capture system
- ✅ **AI Transcription**: OpenAI Whisper integration
- ✅ **Feedback Engine**: AI-powered coaching
- ✅ **Guest Research**: Automated research system
- ✅ **Error Tracking**: Comprehensive monitoring
- ✅ **Environment Variables**: API keys for Scoop and Reverb tabs

## 🎙️ How to Use

### 1. Start the Application
```bash
# Method 1: Direct launch
python frontend/main_window.py

# Method 2: Using the shortcut (if created)
run_soapboxx.bat
```

### 2. Record Your First Podcast

1. **Open SoapBoxx** - The application will launch with a tabbed interface
2. **Check Status** - Look for green "✅ Configured" status in the SoapBoxx tab
3. **Start Recording** - Click the green "Start Recording" button
4. **Speak Naturally** - The system will capture and transcribe your audio
5. **Get Feedback** - AI will analyze your content and provide coaching
6. **Stop Recording** - Click "Stop Recording" when finished

### 3. Features Available

#### 🎙️ SoapBoxx Tab
- **Recording Controls** - Start/stop with visual feedback
- **Real-time Transcript** - Live transcription display
- **AI Feedback** - Instant coaching and performance analysis
- **Status Monitoring** - System health and configuration

#### 📰 Scoop Tab
- **News Integration** - Get latest news using News API
- **Social Media Trends** - Twitter trends and hashtags
- **Content Research** - Google Custom Search integration
- **YouTube Trends** - Video content and trending topics
- **API Key Status** - Visual status of all configured API keys

#### 🔊 Reverb Tab
- **Content Analysis** - AI-powered content quality and engagement analysis
- **Performance Coaching** - Personalized coaching for podcast hosting skills
- **Engagement Analysis** - Audience retention and engagement insights
- **Storytelling Feedback** - Feedback on narrative structure and storytelling techniques
- **Guest Interview Coaching** - Coaching for interview preparation and techniques
- **Podcast Analytics** - Performance metrics and audience insights using podcast APIs
- **API Key Status** - Visual status of all configured API keys

> **Note:** Reverb is a feedback and coaching tool for podcasters, not an audio processing tool. It provides AI-powered analysis and coaching to help improve podcast quality and performance.

### Alternative Podcast-Specific APIs

If you're looking for podcast-specific integrations, consider these APIs:

- **Podchaser API** - Podcast database and analytics - [Get it here](https://www.podchaser.com/developers)
- **Listen Notes API** - Podcast search and discovery - [Get it here](https://www.listennotes.com/api/)
- **Apple Podcasts** - Limited API access for podcast directory
- **Google Podcasts** - Limited API access for podcast discovery

### Alternative Transcription Services

If you're experiencing issues with OpenAI transcription, consider these alternatives:

- **AssemblyAI** - High-quality transcription with speaker diarization - [Get it here](https://www.assemblyai.com/)
- **Azure Speech Services** - Microsoft's speech recognition service - [Get it here](https://azure.microsoft.com/services/cognitive-services/speech-services/)
- **Local Transcription** - Offline transcription using local models (requires additional setup)

## 🔧 Configuration

### API Keys

#### Required API Keys
- **OpenAI API Key**: For transcription and AI features (already configured)

#### Optional API Keys (for Scoop and Reverb tabs)

**Scoop Tab APIs:**
- **News API Key**: For news integration - [Get it here](https://newsapi.org/)
- **Twitter API Key**: For social media trends - [Get it here](https://developer.twitter.com/)
- **Google API Key**: For content research - [Get it here](https://console.cloud.google.com/)
- **YouTube API Key**: For video content - [Get it here](https://console.cloud.google.com/)

**Reverb Tab APIs:**
- **ElevenLabs API Key**: For text-to-speech - [Get it here](https://elevenlabs.io/)
- **AssemblyAI API Key**: For audio analysis - [Get it here](https://www.assemblyai.com/)
- **Azure Speech Key**: For speech recognition - [Get it here](https://azure.microsoft.com/services/cognitive-services/speech-services/)
- **Spotify Client ID**: For music integration (background music, royalty-free tracks) - [Get it here](https://developer.spotify.com/)

### Setting Up Environment Variables

#### Method 1: Interactive Setup
```bash
# Run the setup script
python setup.py

# Choose 'y' when prompted for environment variables setup
```

#### Method 2: Manual Setup
1. **Copy the example file**:
   ```bash
   copy env.example .env
   ```

2. **Edit the .env file** with your API keys:
   ```bash
   # Open .env in your preferred editor
   notepad .env
   ```

3. **Add your API keys**:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   NEWS_API_KEY=your_news_api_key_here
   TWITTER_API_KEY=your_twitter_api_key_here
   # ... add other keys as needed
   ```

#### Method 3: Using the Config Tool
```bash
python -c "from backend.config import Config; Config().setup_environment_variables()"
```

## 🧪 Testing

### Run Backend Tests
```bash
cd backend
python test_backend.py
```

### Check System Status
```bash
# Test configuration
python -c "from backend.config import Config; print('Config valid:', Config().validate_config()['valid'])"

# Test core system
python -c "from backend.soapboxx_core import SoapBoxxCore; print('Core status:', SoapBoxxCore().get_status())"
```

## 🐛 Troubleshooting

### Common Issues

#### "Audio recording fails"
- Check microphone permissions in Windows
- Verify audio device is connected
- Test with: `python backend/test_backend.py`

#### "Transcription errors"
- Verify internet connection
- Check OpenAI API key is valid
- Ensure audio quality is sufficient

#### "Frontend won't start"
- Install dependencies: `pip install -r requirements.txt`
- Check Python version (3.8+ required)

## 📊 Performance Tips

1. **Audio Quality**: Use 16kHz sample rate for optimal transcription
2. **Recording Length**: Start with short recordings (1-2 minutes) to test
3. **API Limits**: Monitor OpenAI API usage
4. **Memory**: Large audio files may require more memory

## 🎉 Ready to Create Amazing Podcasts!

Your SoapBoxx system is now ready for production use. Start recording your first podcast and experience the power of AI-assisted podcast production!

---

**Need help?** Check the main README.md for detailed documentation. 