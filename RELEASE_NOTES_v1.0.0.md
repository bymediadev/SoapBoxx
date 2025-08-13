# 🎙️ SoapBoxx Demo v1.0.0 - Offline-Capable AI Podcast Studio

## 🚀 What's New

**SoapBoxx Demo** is a fully functional, offline-capable version of the SoapBoxx podcast production software that showcases all features without external dependencies.

## ✨ Key Features

### 🧠 **Content Analysis (SoapBoxx Tab)**
- **Local text analysis** with detailed metrics and feedback
- **Multi-level analysis depths**: Basic, Standard, Comprehensive, Expert
- **Feedback scoring** (1-10) for clarity, engagement, structure, energy, and professionalism
- **Improvement suggestions** based on content analysis
- **Content metrics**: Word count, sentence count, reading time, topic coherence

### 🔍 **Guest Research (Scoop Tab)**
- **Sample guest profiles** with realistic data (John Doe, Jane Smith, Mike Johnson, Sarah Wilson)
- **Company information** and industry insights
- **Contact details** and social media information
- **Expertise areas** and podcast topics
- **Achievement tracking** and professional background

### 🎵 **Audio Features (Reverb Tab)**
- **Mock transcription** with realistic results and confidence scores
- **Text-to-speech generation** with multiple voices (US English, British English)
- **Audio metrics** and timing calculations
- **Voice customization** and speed control (0.5x to 2.0x)

### 📊 **Session Management**
- **Session tracking** with unique IDs and timestamps
- **Usage statistics** and performance metrics
- **Export functionality** (JSON, TXT formats)
- **System health monitoring** and module status

### 🎨 **User Interface**
- **Modern PyQt6 interface** with all tabs functional
- **Theme customization** (8 different themes)
- **Keyboard shortcuts** for accessibility
- **Professional appearance** perfect for demos

## 🔧 Technical Details

- **Backend Modules**: 5 barebones modules with same API interface
- **Frontend Files**: 7 UI components with full functionality
- **Dependencies**: Minimal (PyQt6, numpy, requests, python-dotenv)
- **Platform Support**: Windows 10/11, macOS 10.14+, Linux (Ubuntu 18.04+)
- **System Requirements**: Python 3.8+, 4GB RAM, 500MB disk space

## 🎯 Perfect For

- **Podcast creators** exploring production tools
- **Content marketers** evaluating AI assistance
- **Educators** teaching podcast production
- **Sales teams** demonstrating capabilities
- **Anyone** wanting to experience SoapBoxx without setup

## 🚫 Demo Limitations

- **AI Analysis**: Uses local text analysis, not GPT
- **Guest Research**: Sample data, not real web scraping
- **Transcription**: Mock results, not actual audio processing
- **TTS**: File path generation, not real audio creation

## 📦 Installation

### Windows Users:
```bash
# Extract the ZIP file
# Double-click: scripts\run_demo.bat
```

### macOS/Linux Users:
```bash
# Extract the ZIP file
chmod +x scripts/run_demo.sh
./scripts/run_demo.sh
```

## 🧪 Testing

After installation, verify everything works:
```bash
python test_barebones_modules.py
```

You should see: **"🎉 All modules working correctly!"**

## 📚 Documentation

- **README.md**: Quick start and overview
- **INSTALLATION.md**: Platform-specific installation guides
- **docs/TUTORIAL_DEMO.md**: Complete usage guide
- **docs/README_DEMO.md**: Detailed feature overview
- **samples/DEMO_INSTRUCTIONS.md**: 5-minute quick start

## 🔄 Upgrade Path

When ready for the full SoapBoxx experience:
1. Switch to main branch: `git checkout main`
2. Install full dependencies: `pip install -r requirements.txt`
3. Add API keys: OpenAI, Google, etc.
4. Enjoy real AI analysis and transcription

## 🆘 Support

- **Built-in Help**: Press F1 in the application
- **Documentation**: Check the docs/ folder
- **Test Scripts**: Run test_barebones_modules.py
- **Status Bar**: Real-time system information

## 📊 Package Contents

- **25 total files** in professional package
- **Cross-platform launchers** with dependency checking
- **Complete documentation** for users
- **Sample content** for immediate testing
- **Test scripts** for verification

---

**🎯 Ready to create amazing podcasts? Start with the demo, then upgrade to the full SoapBoxx experience!**

*This is the SoapBoxx Demo version. For full functionality with real AI analysis and transcription, visit the main SoapBoxx repository.*
