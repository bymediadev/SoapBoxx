# 🎓 **SoapBoxx Demo - Complete Tutorial**

## 🚀 **Welcome to SoapBoxx Demo!**

This tutorial walks through the **SoapBoxx demo** UI. The core tour works **without** API keys; optional keys enable cloud-backed features where wired. For **download, install, credits, and email**, use **[README_DEMO.md](README_DEMO.md)** as the source of truth.

---

## 📋 **Table of Contents:**

1. [Getting Started](#getting-started)
2. [Basic Navigation](#basic-navigation)
3. [Content Analysis (SoapBoxx Tab)](#content-analysis-soapboxx-tab)
4. [Guest Research (Scoop Tab)](#guest-research-scoop-tab)
5. [Audio Features (Reverb Tab)](#audio-features-reverb-tab)
6. [Export, workflow, and usage](#export-workflow-and-usage)
7. [Keyboard Shortcuts](#keyboard-shortcuts)
8. [Theme Customization](#theme-customization)
9. [Troubleshooting](#troubleshooting)
10. [Next Steps](#next-steps)

---

## 🚀 **Getting Started**

### **Prerequisites:**
- Python 3.8+ installed
- Basic understanding of desktop applications
- Internet optional unless you use cloud APIs or SMTP

### **Installation:**
From the **`SoapBoxx-Demo`** folder (see **[README_DEMO.md](README_DEMO.md)** for clone/ZIP paths):

```bash
python -m pip install -r requirements_demo.txt
python frontend/main_window.py
```

### **First launch:**
When you first launch the demo, you'll typically see:
- **Login / Sign up** (or similar portal) — create an account or sign in
- **Setup** tab (optional) — API keys, GitHub local setup
- **Main window** with **SoapBoxx**, **Scoop**, **Reverb** tabs; **Settings**; status bar with usage (e.g. **0/3** episode credits)

---

## 🧭 **Basic Navigation**

### **Main Window Layout:**
```
┌─────────────────────────────────────────────────────────┐
│                    SoapBoxx Demo                        │
├─────────────────────────────────────────────────────────┤
│ [SoapBoxx] [Scoop] [Reverb]                           │
├─────────────────────────────────────────────────────────┤
│                                                         │
│                    Tab Content                          │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ Status: user, usage (e.g. 1/3), API key status          │
└─────────────────────────────────────────────────────────┘
```

### **Tab navigation:**
- **SoapBoxx Tab**: Recording / export style workflow (demo)
- **Scoop Tab**: Search / research style UI (sample data)
- **Reverb Tab**: Analysis / feedback style UI (local mock metrics)

### **Menu bar (current demo build):**
- **File**: Export Data, Download Everything, Download from GitHub (local setup), Exit
- **Beta**: Login / Switch User, API Keys, Complete Episode Workflow
- **Help**: Full description, About

---

## 🧠 **Content Analysis (SoapBoxx Tab)**

### **What You Can Do:**
- Analyze text content for podcast improvement
- Get feedback on clarity, engagement, and structure
- View detailed metrics and suggestions
- Compare multiple content pieces

### **Step-by-Step Analysis:**

#### **1. Enter Your Content:**
```
┌─────────────────────────────────────────┐
│ Enter your podcast transcript or script │
│                                         │
│ Welcome to our podcast! Today we're    │
│ talking about artificial intelligence   │
│ and how it's changing the world...     │
│                                         │
└─────────────────────────────────────────┘
```

#### **2. Choose Analysis Depth:**
- **Basic**: Quick overview and basic metrics
- **Standard**: Detailed feedback and suggestions
- **Comprehensive**: Full analysis with improvement areas
- **Expert**: Advanced metrics and detailed breakdown

#### **3. Click "Analyze Content"**
The system will process your text and provide:

**📊 Content Metrics:**
- Word count and sentence count
- Average sentence length
- Reading time estimate
- Topic coherence score

**🎯 Feedback Scores (1-10):**
- **Clarity**: How easy to understand
- **Engagement**: How interesting and interactive
- **Structure**: How well organized
- **Energy**: How dynamic and enthusiastic
- **Professionalism**: How polished and appropriate

**💡 Improvement Suggestions:**
- Specific ways to improve each area
- Examples and best practices
- Next steps for enhancement

### **Example Analysis Output:**
```
🎯 Content Analysis Results

📊 Metrics:
- Words: 247
- Sentences: 12
- Reading Time: 1.2 minutes
- Topic Coherence: 85%

⭐ Scores:
- Clarity: 8.5/10
- Engagement: 7.2/10
- Structure: 6.8/10
- Energy: 7.5/10
- Professionalism: 8.0/10
- Overall: 7.6/10

💡 Suggestions:
- Break long sentences for better clarity
- Add more questions to increase engagement
- Use transition words to improve structure
```

### **Pro Tips:**
- **Use real content** for the most meaningful feedback
- **Try different analysis depths** to see varying detail levels
- **Compare multiple versions** to track improvement
- **Export results** for future reference

---

## 🔍 **Guest Research (Scoop Tab)**

### **What You Can Do:**
- Research potential podcast guests
- Get company and industry information
- Find contact details and social media
- Discover guest expertise areas

### **Step-by-Step Research:**

#### **1. Search for a Guest:**
```
┌─────────────────────────────────────────┐
│ Guest Name: [John Doe]                 │
│ Company:   [TechStart Inc.] (optional) │
│                                         │
│ [Search Guest] [Search Company]         │
└─────────────────────────────────────────┘
```

#### **2. View Guest Profile:**
**Sample Guest Results Include:**
- **Personal Information**: Name, title, company
- **Bio**: Professional background and experience
- **Expertise**: Key areas of knowledge
- **Recent Achievements**: Notable accomplishments
- **Podcast Topics**: What they can discuss
- **Contact Information**: Email, phone, social media

#### **3. Company Research:**
Get detailed company information:
- Industry and founding date
- Employee count and funding
- Key products and services
- Leadership team
- Company description

### **Example Guest Profile:**
```
👤 John Doe
🏢 CEO & Founder at TechStart Inc.

📖 Bio:
Serial entrepreneur with 15+ years in software 
development. Founded 3 successful startups and 
helped scale 10+ companies.

🎯 Expertise:
- Software Development
- Startup Strategy  
- Team Building
- Product Management

🏆 Recent Achievements:
- Raised $50M Series B funding
- Named to Forbes 30 Under 30
- Company acquired for $200M

🎙️ Podcast Topics:
- Building successful startups
- Scaling engineering teams
- Venture capital insights
- Product-market fit

📧 Contact: john@techstart.com
📱 Phone: +1-555-0123
```

### **Pro Tips:**
- **Search by name only** to see all matching profiles
- **Add company name** for more specific results
- **Use partial names** - the system will find matches
- **Explore different industries** for variety

---

## 🎵 **Audio Features (Reverb Tab)**

### **What You Can Do:**
- Generate mock transcriptions
- Create text-to-speech previews
- Analyze audio metrics
- Test different voice options

### **Step-by-Step Audio Features:**

#### **1. Mock Transcription:**
```
┌─────────────────────────────────────────┐
│ Audio File Path: [sample_audio.wav]    │
│                                         │
│ [Transcribe Audio]                      │
└─────────────────────────────────────────┘
```

**What Happens:**
- System analyzes filename for content type
- Generates appropriate sample transcript
- Provides word count and timing metrics
- Shows confidence score (mock: 95%)

#### **2. Text-to-Speech Generation:**
```
┌─────────────────────────────────────────┐
│ Text: [Enter text to convert to speech]│
│ Voice: [US English - Sarah ▼]          │
│ Speed: [1.0x ▼]                        │
│                                         │
│ [Generate Speech]                       │
└─────────────────────────────────────────┘
```

**Available Voices:**
- **US English - Sarah**: Clear, professional female
- **US English - Mike**: Warm, engaging male
- **British English - Emma**: Sophisticated British accent
- **British English - James**: Professional British accent

**Speed Options:**
- 0.5x (slow)
- 1.0x (normal)
- 1.5x (fast)
- 2.0x (very fast)

#### **3. Audio Metrics:**
For each audio operation, you get:
- Word count and character count
- Estimated duration
- Speaking rate (words per minute)
- Output format information

### **Example TTS Output:**
```
🎵 Text-to-Speech Generated

📝 Text: "Welcome to the SoapBoxx podcast!"
🎤 Voice: US English - Sarah
⚡ Speed: 1.0x

📊 Metrics:
- Words: 7
- Characters: 35
- Duration: 2.8 seconds
- Speaking Rate: 150 WPM

💾 Output: mock_audio/en-US-1_1234_1234567890.wav
```

### **Pro Tips:**
- **Use descriptive filenames** for better transcription results
- **Experiment with different voices** to find your preference
- **Adjust speed** for different content types
- **Test with short text** first to verify settings

---

## 📊 **Export, workflow, and usage**

### **What you can do**
- **File → Export Data** — export app data in a portable form (formats depend on build).
- **File → Download Everything** — zip the local demo folder for backup.
- **Header “Complete Episode Workflow”** or **Beta → Complete Episode Workflow** — runs the demo episode pipeline; consumes **one** of your **3 episode credits** per run (unless playground mode is on — see **[README_DEMO.md](README_DEMO.md)**).
- **Status bar** — shows signed-in user and usage (e.g. **2/3**).

The older “Start Session / End Session” flow is **not** the primary model in this demo build; use **Export** and **Complete Episode Workflow** instead.

---

## ⌨️ **Keyboard Shortcuts**

### **Essential Shortcuts:**
```
Ctrl+R          Start/Stop Recording
Ctrl+P          Pause/Resume Recording
Ctrl+Tab        Next Tab
Ctrl+Shift+Tab  Previous Tab
Ctrl+1          SoapBoxx Tab
Ctrl+2          Reverb Tab
Ctrl+3          Scoop Tab
Ctrl+E          Export Transcript
Ctrl+Shift+E    Export Feedback
Ctrl+A          Content Analysis
Ctrl+C          Performance Coaching
Ctrl+G          Guest Research
F1              Show Help
Ctrl+?          Show Shortcuts
```

### **Navigation Shortcuts:**
- **Tab Switching**: Quick navigation between features
- **Analysis**: Instant content analysis
- **Export**: Quick data export
- **Help**: Access tutorial and support

---

## 🎨 **Theme Customization**

### **Available Themes:**
- **Modern Light**: Clean, professional appearance
- **Modern Dark**: Easy on the eyes
- **Modern Blue**: Corporate, trustworthy feel
- **Modern Green**: Creative, growth-oriented
- **Classic Light**: Traditional, familiar
- **Classic Dark**: Classic dark mode
- **Classic Blue**: Professional blue theme
- **Classic Green**: Natural, organic feel

### **How to Change Themes:**
1. Go to **View → Theme**
2. Select your preferred theme
3. Theme applies immediately
4. Setting persists between sessions

### **Theme Features:**
- **Consistent styling** across all tabs
- **Professional appearance** for demos
- **Accessibility options** for different users
- **Custom color schemes** for branding

---

## 🔧 **Troubleshooting**

### **Common Issues and Solutions:**

#### **1. "Module Not Found" Error:**
```
❌ Error: No module named 'openai'
✅ Solution: You're using the demo version - this is expected!
   The barebones modules provide mock functionality.
```

#### **2. "API Key Required" Message:**
```
❌ Error: OpenAI API key required
✅ Solution: Demo version works offline - no API keys needed!
   All features use sample data and local analysis.
```

#### **3. "Audio File Not Found":**
```
❌ Error: Audio file not found
✅ Solution: Use any filename - the system generates mock transcripts
   based on filename content.
```

#### **4. "Network Connection Required":**
```
❌ Error: Network connection required
✅ Solution: Demo version works completely offline!
   All data is local and sample-based.
```

### **Performance Tips:**
- **Close other applications** for best performance
- **Use shorter text** for faster analysis
- **Restart application** if it becomes slow
- **Clear cache** if needed (though minimal in demo)

---

## 🚀 **Next Steps**

### **What You've Learned:**
✅ **Content Analysis**: How to analyze and improve podcast content
✅ **Guest Research**: How to find and research potential guests
✅ **Audio Features**: How to use transcription and TTS features
✅ **Export and workflow**: File export, episode workflow, usage credits
✅ **Navigation**: How to use keyboard shortcuts and themes

### **Practice Exercises:**

#### **Exercise 1: Content Analysis**
1. Write a short podcast introduction (3-4 sentences)
2. Analyze it with "Comprehensive" depth
3. Note the feedback scores
4. Make improvements based on suggestions
5. Re-analyze to see improvement

#### **Exercise 2: Guest Research**
1. Search for "Jane Smith" (marketing expert)
2. Research "GrowthCorp" company
3. Note potential podcast topics
4. Plan interview questions based on expertise

#### **Exercise 3: Audio Features**
1. Generate TTS for a podcast intro
2. Try different voices and speeds
3. Create a mock transcription
4. Compare metrics between different settings

### **Moving to Full Version:**
When you're ready for the full SoapBoxx experience:

1. **Switch to main branch**: `git checkout main`
2. **Install full dependencies**: `pip install -r requirements.txt`
3. **Add API keys**: OpenAI, Google, etc.
4. **Test real functionality**: Actual transcription, AI analysis
5. **Enjoy full features**: All the power of real SoapBoxx!

---

## 🎯 **Demo Limitations (Remember!)**

### **What's Simulated:**
- **AI Analysis**: Uses local text analysis, not GPT
- **Guest Research**: Sample data, not real web scraping
- **Transcription**: Mock results, not actual audio processing
- **TTS**: File path generation, not real audio creation

### **What's Real:**
- **User Interface**: Full PyQt6 functionality
- **Navigation**: All tabs and features work
- **Data Processing**: Real calculations and metrics
- **Export Features**: Actual file generation
- **Usage / export**: Real local state and file export where implemented

---

## 🆘 **Getting Help**

### **Built-in help:**
- **Help Menu**: Full description (from `PACKAGE_INFO.json`), About
- **Status Bar**: Current system status
- **Error Messages**: Clear explanations of issues

### **Demo Features:**
- **Offline Operation**: No internet required
- **Sample Data**: Rich, realistic examples
- **Mock Functionality**: Simulates real features
- **Error Handling**: Graceful fallbacks

---

## 🎉 **Congratulations!**

You've successfully learned how to use the **SoapBoxx Demo**! You now have:

- ✅ **Working knowledge** of all SoapBoxx features
- ✅ **Hands-on experience** with content analysis
- ✅ **Understanding** of guest research capabilities
- ✅ **Familiarity** with audio features
- ✅ **Confidence** to use the full version

### **Your SoapBoxx Journey:**
1. **Demo Version** (Current) → Learn and explore
2. **Full Version** → Real AI analysis and transcription
3. **Customization** → Tailor to your specific needs
4. **Production** → Use for real podcast creation

---

**🎯 Ready to create amazing podcasts? Start with the demo, then upgrade to the full SoapBoxx experience!**

---

*This tutorial covers the SoapBoxx Demo version. For full functionality, switch to the main branch and add API keys.*
