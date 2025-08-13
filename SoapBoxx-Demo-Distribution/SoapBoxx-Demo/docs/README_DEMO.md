# 🎙️ **SoapBoxx Demo - AI-Powered Podcast Production Studio**

> **A fully functional, offline-capable demo of SoapBoxx that showcases all features without external dependencies**

---

## 🚀 **What is SoapBoxx Demo?**

**SoapBoxx Demo** is a complete, working version of the SoapBoxx podcast production software that runs completely offline. It provides the full user experience with mock data and local analysis, making it perfect for:

- **Demoing SoapBoxx capabilities** to potential users
- **Learning the interface** before upgrading to the full version
- **Testing workflows** without API costs or internet requirements
- **Presentations and showcases** in any environment

---

## ✨ **Key Features**

### 🧠 **Content Analysis (SoapBoxx Tab)**
- **Local text analysis** with detailed metrics
- **Feedback scoring** (1-10) for clarity, engagement, structure, energy, and professionalism
- **Improvement suggestions** based on content analysis
- **Multiple analysis depths**: Basic, Standard, Comprehensive, Expert
- **Content metrics**: Word count, sentence count, reading time, topic coherence

### 🔍 **Guest Research (Scoop Tab)**
- **Sample guest profiles** with realistic data
- **Company information** and industry insights
- **Contact details** and social media information
- **Expertise areas** and podcast topics
- **Achievement tracking** and professional background

### 🎵 **Audio Features (Reverb Tab)**
- **Mock transcription** with realistic results
- **Text-to-speech generation** with multiple voices
- **Audio metrics** and timing calculations
- **Voice customization** (US English, British English)
- **Speed control** (0.5x to 2.0x)

### 📊 **Session Management**
- **Session tracking** with unique IDs
- **Usage statistics** and performance metrics
- **Export functionality** (JSON, TXT formats)
- **System health monitoring**
- **Module status tracking**

---

## 🎯 **Demo Capabilities vs. Limitations**

### ✅ **What Works (Real Features):**
- **Full PyQt6 user interface** with all tabs and navigation
- **Local data processing** and calculations
- **File export** and session management
- **Theme customization** (8 different themes)
- **Keyboard shortcuts** and accessibility features
- **Error handling** and graceful fallbacks

### 🔄 **What's Simulated (Mock Features):**
- **AI Analysis**: Local text analysis instead of GPT
- **Guest Research**: Sample data instead of web scraping
- **Transcription**: Mock results instead of actual audio processing
- **TTS**: File path generation instead of real audio creation

---

## 🚀 **Quick Start**

### **Prerequisites:**
- Python 3.8 or higher
- Windows 10/11 (tested), macOS, or Linux
- No internet connection required! 🎉

### **Installation:**
```bash
# 1. Clone the repository
git clone https://github.com/yourusername/SoapBoxx.git
cd SoapBoxx

# 2. Switch to demo branch
git checkout demo/soapboxx-barebones

# 3. Install minimal dependencies
pip install PyQt6 numpy requests python-dotenv

# 4. Run SoapBoxx Demo
python frontend/main_window.py
```

### **Alternative: Quick Launch Script**
```bash
# Windows
.\run_demo.bat

# macOS/Linux
./run_demo.sh
```

---

## 🎮 **How to Use**

### **1. Content Analysis**
1. Go to **SoapBoxx Tab**
2. Enter your podcast script or transcript
3. Choose analysis depth (Basic → Expert)
4. Click "Analyze Content"
5. Review scores and improvement suggestions

### **2. Guest Research**
1. Go to **Scoop Tab**
2. Enter guest name (e.g., "John Doe")
3. Optionally add company name
4. Click "Search Guest" or "Search Company"
5. Review profile and contact information

### **3. Audio Features**
1. Go to **Reverb Tab**
2. For transcription: Enter audio filename and click "Transcribe"
3. For TTS: Enter text, choose voice/speed, click "Generate Speech"
4. View metrics and output information

### **4. Session Management**
1. Use **File → Start Session** to begin tracking
2. Monitor session progress in status bar
3. Export data with **File → Export Session**
4. End session with **File → End Session**

---

## 🎨 **Customization**

### **Themes Available:**
- **Modern**: Light, Dark, Blue, Green
- **Classic**: Light, Dark, Blue, Green

### **Keyboard Shortcuts:**
- `Ctrl+1/2/3`: Switch between tabs
- `Ctrl+A`: Content analysis
- `Ctrl+G`: Guest research
- `F1`: Help system
- `Ctrl+?`: Show all shortcuts

---

## 🔧 **Troubleshooting**

### **Common Issues:**

#### **"Module Not Found" Error:**
```
❌ Error: No module named 'openai'
✅ Solution: This is expected in the demo! 
   The barebones modules provide mock functionality.
```

#### **"API Key Required" Message:**
```
❌ Error: OpenAI API key required
✅ Solution: Demo works offline - no API keys needed!
   All features use sample data and local analysis.
```

#### **Blank UI or Missing Tabs:**
```
❌ Issue: Only some tabs visible
✅ Solution: Ensure you're on demo branch and 
   all barebones modules are present.
```

### **Performance Tips:**
- Close other applications for best performance
- Use shorter text for faster analysis
- Restart if the application becomes slow
- Check system resources (CPU, memory)

---

## 📁 **File Structure**

```
SoapBoxx/
├── backend/
│   ├── feedback_engine_barebones.py    # Local content analysis
│   ├── guest_research_barebones.py     # Sample guest data
│   ├── transcriber_barebones.py        # Mock transcription
│   ├── tts_generator_barebones.py      # Mock TTS generation
│   └── soapboxx_core_barebones.py      # Session management
├── frontend/
│   ├── main_window.py                  # Main application
│   ├── soapboxx_tab.py                # Content analysis tab
│   ├── scoop_tab.py                   # Guest research tab
│   └── reverb_tab.py                  # Audio features tab
├── TUTORIAL_DEMO.md                   # Detailed usage guide
├── README_DEMO.md                     # This file
└── run_demo.bat                       # Windows quick launch
```

---

## 🚀 **Upgrading to Full SoapBoxx**

When you're ready for the complete experience:

1. **Switch to main branch**: `git checkout main`
2. **Install full dependencies**: `pip install -r requirements.txt`
3. **Add API keys**: OpenAI, Google, etc.
4. **Test real functionality**: Actual transcription, AI analysis
5. **Enjoy full features**: All the power of real SoapBoxx!

---

## 🎯 **Perfect For:**

- **Podcast creators** exploring production tools
- **Content marketers** evaluating AI assistance
- **Educators** teaching podcast production
- **Developers** understanding the SoapBoxx architecture
- **Sales teams** demonstrating capabilities
- **Anyone** wanting to experience SoapBoxx without setup

---

## 📚 **Documentation**

- **[TUTORIAL_DEMO.md](TUTORIAL_DEMO.md)** - Complete step-by-step guide
- **[README_DEMO.md](README_DEMO.md)** - This overview (you're reading it!)
- **Built-in Help** - Press F1 in the application
- **Status Bar** - Real-time system information

---

## 🤝 **Support & Community**

- **Demo Issues**: Check troubleshooting section above
- **Feature Requests**: Create issue on GitHub
- **Contributions**: Fork and submit pull requests
- **Questions**: Use GitHub Discussions

---

## 📄 **License**

This demo version is provided under the same license as the main SoapBoxx project.

---

## 🎉 **Get Started Now!**

```bash
git checkout demo/soapboxx-barebones
pip install PyQt6 numpy requests python-dotenv
python frontend/main_window.py
```

**🎯 Experience the future of podcast production with SoapBoxx Demo!**

---

*This is the SoapBoxx Demo version. For full functionality with real AI analysis and transcription, switch to the main branch.*
