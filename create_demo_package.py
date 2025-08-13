#!/usr/bin/env python3
"""
SoapBoxx Demo Distribution Package Creator
Automatically creates a complete distribution package with all necessary files
"""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime

def create_distribution_package():
    """Create the complete SoapBoxx Demo distribution package"""
    
    print("🚀 Creating SoapBoxx Demo Distribution Package")
    print("=" * 60)
    
    # Distribution directory
    dist_dir = Path("SoapBoxx-Demo-Distribution")
    
    # Clean up existing directory
    if dist_dir.exists():
        print("🧹 Cleaning up existing distribution directory...")
        shutil.rmtree(dist_dir)
    
    # Create distribution structure
    print("📁 Creating distribution structure...")
    dist_dir.mkdir()
    
    # Main application directory
    app_dir = dist_dir / "SoapBoxx-Demo"
    app_dir.mkdir()
    
    # Create subdirectories
    (app_dir / "backend").mkdir()
    (app_dir / "frontend").mkdir()
    (app_dir / "docs").mkdir()
    (app_dir / "scripts").mkdir()
    (app_dir / "samples").mkdir()
    (app_dir / "logs").mkdir()
    (app_dir / "Exports").mkdir()
    
    print("✅ Directory structure created")
    
    # Copy backend barebones modules
    print("🔧 Copying backend modules...")
    backend_files = [
        "feedback_engine_barebones.py",
        "guest_research_barebones.py", 
        "transcriber_barebones.py",
        "tts_generator_barebones.py",
        "soapboxx_core_barebones.py"
    ]
    
    for file in backend_files:
        src = Path("backend") / file
        dst = app_dir / "backend" / file
        if src.exists():
            shutil.copy2(src, dst)
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file} (not found)")
    
    # Copy frontend files
    print("🎨 Copying frontend files...")
    frontend_files = [
        "main_window.py",
        "soapboxx_tab.py",
        "scoop_tab.py", 
        "reverb_tab.py",
        "theme_manager.py",
        "keyboard_shortcuts.py",
        "__init__.py"
    ]
    
    for file in frontend_files:
        src = Path("frontend") / file
        dst = app_dir / "frontend" / file
        if src.exists():
            shutil.copy2(src, dst)
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file} (not found)")
    
    # Copy documentation
    print("📚 Copying documentation...")
    doc_files = [
        "README_DEMO.md",
        "TUTORIAL_DEMO.md"
    ]
    
    for file in doc_files:
        src = Path(file)
        dst = app_dir / "docs" / file
        if src.exists():
            shutil.copy2(src, dst)
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file} (not found)")
    
    # Copy launch scripts
    print("🚀 Copying launch scripts...")
    script_files = [
        "run_demo.bat",
        "run_demo.sh"
    ]
    
    for file in script_files:
        src = Path(file)
        dst = app_dir / "scripts" / file
        if src.exists():
            shutil.copy2(src, dst)
            print(f"   ✅ {file}")
        else:
            print(f"   ❌ {file} (not found)")
    
    # Copy test script
    print("🧪 Copying test script...")
    test_src = Path("test_barebones_modules.py")
    test_dst = app_dir / "test_barebones_modules.py"
    if test_src.exists():
        shutil.copy2(test_src, test_dst)
        print("   ✅ test_barebones_modules.py")
    else:
        print("   ❌ test_barebones_modules.py (not found)")
    
    # Create requirements file
    print("📦 Creating requirements file...")
    requirements_content = """# SoapBoxx Demo - Minimal Dependencies
# These are the minimum packages needed to run the demo

PyQt6>=6.4.0
numpy>=1.21.0
requests>=2.25.0
python-dotenv>=0.19.0

# Optional packages for enhanced experience
# pyaudio>=0.2.11  # For microphone support
# azure-cognitiveservices-speech>=1.25.0  # For Azure Speech
# pyttsx3>=2.90  # For local TTS
"""
    
    with open(app_dir / "requirements_demo.txt", "w") as f:
        f.write(requirements_content)
    print("   ✅ requirements_demo.txt")
    
    # Create main README
    print("📖 Creating main README...")
    main_readme = """# 🎙️ SoapBoxx Demo - AI-Powered Podcast Production Studio

> **A fully functional, offline-capable demo of SoapBoxx that showcases all features without external dependencies**

## 🚀 Quick Start

### Windows Users:
```bash
# Double-click the launcher
scripts\\run_demo.bat

# Or run manually
python -m pip install -r requirements_demo.txt
python frontend/main_window.py
```

### macOS/Linux Users:
```bash
# Make script executable and run
chmod +x scripts/run_demo.sh
./scripts/run_demo.sh

# Or run manually
python3 -m pip install -r requirements_demo.txt
python3 frontend/main_window.py
```

## ✨ What You Get

- **🧠 Content Analysis**: Local text analysis with detailed feedback
- **🔍 Guest Research**: Sample guest profiles and company information  
- **🎵 Audio Features**: Mock transcription and text-to-speech
- **📊 Session Management**: Track and export your work
- **🎨 Modern UI**: Professional interface with theme customization
- **⌨️ Keyboard Shortcuts**: Full accessibility support

## 📚 Documentation

- **[TUTORIAL_DEMO.md](docs/TUTORIAL_DEMO.md)** - Complete usage guide
- **[README_DEMO.md](docs/README_DEMO.md)** - Detailed feature overview

## 🧪 Testing

Test all modules before running:
```bash
python test_barebones_modules.py
```

## 🎯 Perfect For

- **Podcast creators** exploring production tools
- **Content marketers** evaluating AI assistance
- **Educators** teaching podcast production
- **Sales teams** demonstrating capabilities
- **Anyone** wanting to experience SoapBoxx without setup

## 🔧 System Requirements

- Python 3.8 or higher
- Windows 10/11, macOS 10.14+, or Linux
- 4GB RAM minimum (8GB recommended)
- 500MB disk space

## 🚫 Demo Limitations

- **AI Analysis**: Uses local text analysis, not GPT
- **Guest Research**: Sample data, not real web scraping
- **Transcription**: Mock results, not actual audio processing
- **TTS**: File path generation, not real audio creation

## 🆘 Getting Help

1. Check the **docs/** folder for detailed guides
2. Run the test script to verify installation
3. Use the built-in help system (F1 key)
4. Check the status bar for system information

---

**🎯 Ready to create amazing podcasts? Start with the demo, then upgrade to the full SoapBoxx experience!**

*This is the SoapBoxx Demo version. For full functionality with real AI analysis and transcription, visit the main SoapBoxx repository.*
"""
    
    with open(app_dir / "README.md", "w", encoding="utf-8") as f:
        f.write(main_readme)
    print("   ✅ README.md")
    
    # Create installation guide
    print("📋 Creating installation guide...")
    install_guide = """# 🚀 SoapBoxx Demo - Installation Guide

## 📋 Prerequisites

- **Python 3.8+** installed and in PATH
- **Git** (optional, for updates)
- **4GB RAM** minimum (8GB recommended)
- **500MB disk space**

## 🖥️ Windows Installation

### Option 1: Automatic Launcher (Recommended)
1. **Extract** the distribution package
2. **Double-click** `scripts\\run_demo.bat`
3. **Wait** for dependencies to install
4. **Enjoy** SoapBoxx Demo!

### Option 2: Manual Installation
```cmd
# Open Command Prompt as Administrator
cd path\\to\\SoapBoxx-Demo

# Install dependencies
python -m pip install -r requirements_demo.txt

# Run the demo
python frontend/main_window.py
```

## 🍎 macOS Installation

### Option 1: Automatic Launcher (Recommended)
1. **Extract** the distribution package
2. **Open Terminal** and navigate to the package
3. **Run**: `./scripts/run_demo.sh`
4. **Wait** for dependencies to install
5. **Enjoy** SoapBoxx Demo!

### Option 2: Manual Installation
```bash
# Open Terminal
cd path/to/SoapBoxx-Demo

# Install dependencies
python3 -m pip install -r requirements_demo.txt

# Run the demo
python3 frontend/main_window.py
```

## 🐧 Linux Installation

### Option 1: Automatic Launcher (Recommended)
1. **Extract** the distribution package
2. **Open Terminal** and navigate to the package
3. **Make script executable**: `chmod +x scripts/run_demo.sh`
4. **Run**: `./scripts/run_demo.sh`
5. **Wait** for dependencies to install
6. **Enjoy** SoapBoxx Demo!

### Option 2: Manual Installation
```bash
# Open Terminal
cd path/to/SoapBoxx-Demo

# Install system dependencies (Ubuntu/Debian)
sudo apt update
sudo apt install python3-pip python3-venv

# Install Python dependencies
python3 -m pip install -r requirements_demo.txt

# Run the demo
python3 frontend/main_window.py
```

## 🔧 Troubleshooting

### Common Issues:

#### **"Python not found"**
- Install Python 3.8+ from [python.org](https://python.org)
- Ensure Python is added to PATH during installation

#### **"PyQt6 installation failed"**
- Update pip: `python -m pip install --upgrade pip`
- Install system dependencies (Linux: `sudo apt install python3-pyqt6`)

#### **"Module not found" errors**
- Run: `python test_barebones_modules.py`
- Ensure you're in the correct directory
- Check that all files were extracted properly

#### **"Permission denied" (Linux/macOS)**
- Make scripts executable: `chmod +x scripts/*.sh`
- Run with appropriate permissions

### Performance Tips:
- **Close other applications** for best performance
- **Use shorter text** for faster analysis
- **Restart** if the application becomes slow

## ✅ Verification

After installation, verify everything works:
```bash
python test_barebones_modules.py
```

You should see: **"🎉 All modules working correctly!"**

## 🆘 Still Having Issues?

1. **Check the logs** in the `logs/` directory
2. **Run the test script** to identify specific problems
3. **Check system requirements** and Python version
4. **Try manual installation** instead of launcher scripts

---

**🎯 Ready to start? Launch SoapBoxx Demo and begin creating amazing podcasts!**
"""
    
    with open(app_dir / "INSTALLATION.md", "w", encoding="utf-8") as f:
        f.write(install_guide)
    print("   ✅ INSTALLATION.md")
    
    # Create sample content
    print("📝 Creating sample content...")
    sample_transcript = """Welcome to the SoapBoxx Demo Podcast!

This is a sample transcript to help you get started with content analysis. 
You can copy this text into the SoapBoxx tab and analyze it to see how 
the feedback engine works.

The demo version provides local analysis without needing external API keys, 
making it perfect for learning and testing. Try different analysis depths 
from Basic to Expert to see varying levels of detail.

Remember, this is a demo - all features work offline with sample data!
"""
    
    with open(app_dir / "samples" / "sample_transcript.txt", "w", encoding="utf-8") as f:
        f.write(sample_transcript)
    print("   ✅ sample_transcript.txt")
    
    # Create sample analysis
    sample_analysis = {
        "demo_content": {
            "title": "Sample Podcast Introduction",
            "transcript": "Welcome to our podcast about artificial intelligence and machine learning. Today we're discussing the future of AI in business.",
            "analysis_depth": "comprehensive",
            "metrics": {
                "word_count": 25,
                "sentence_count": 2,
                "reading_time_minutes": 0.13,
                "topic_coherence_score": 0.85
            },
            "scores": {
                "clarity": 8.5,
                "engagement": 7.2,
                "structure": 6.8,
                "energy": 7.5,
                "professionalism": 8.0,
                "overall_score": 7.6
            },
            "feedback": "Good introduction with clear topic focus. Consider adding more engaging questions and transition words for better structure."
        }
    }
    
    with open(app_dir / "samples" / "sample_analysis.json", "w", encoding="utf-8") as f:
        json.dump(sample_analysis, f, indent=2)
    print("   ✅ sample_analysis.json")
    
    # Create demo instructions
    demo_instructions = """# 🎮 SoapBoxx Demo - Quick Start Guide

## 🚀 Your First 5 Minutes with SoapBoxx Demo

### 1. **Launch the Application** (1 minute)
- Run `scripts\\run_demo.bat` (Windows) or `./scripts/run_demo.sh` (macOS/Linux)
- Wait for dependencies to install
- The application will launch automatically

### 2. **Explore the Interface** (1 minute)
- **SoapBoxx Tab**: Content analysis and feedback
- **Scoop Tab**: Guest research and company information
- **Reverb Tab**: Audio features and effects
- **Menu Bar**: File, Edit, View, Help options

### 3. **Test Content Analysis** (2 minutes)
- Go to **SoapBoxx Tab**
- Copy the sample transcript from `samples/sample_transcript.txt`
- Paste it into the text area
- Choose "Comprehensive" analysis depth
- Click "Analyze Content"
- Review the feedback scores and suggestions

### 4. **Try Guest Research** (1 minute)
- Go to **Scoop Tab**
- Enter "John Doe" in the guest name field
- Click "Search Guest"
- View the detailed guest profile
- Explore company information

### 5. **Test Audio Features** (1 minute)
- Go to **Reverb Tab**
- Enter "Welcome to our podcast!" in the TTS field
- Choose a voice and speed
- Click "Generate Speech"
- View the generated metrics

## 🎯 What You'll Experience

✅ **Real PyQt6 Interface** - Professional, modern UI
✅ **Working Features** - All tabs functional and responsive
✅ **Local Processing** - No internet connection required
✅ **Sample Data** - Rich, realistic examples
✅ **Error Handling** - Graceful fallbacks and clear messages

## 🔍 Demo vs. Full Version

| Feature | Demo Version | Full Version |
|---------|-------------|--------------|
| **Content Analysis** | Local text analysis | GPT-powered AI analysis |
| **Guest Research** | Sample data | Real web scraping |
| **Transcription** | Mock results | Actual audio processing |
| **TTS Generation** | File paths | Real audio creation |
| **API Dependencies** | None | OpenAI, Google, etc. |
| **Cost** | Free | API usage costs |

## 🚀 Next Steps

1. **Practice** with the sample content
2. **Try different analysis depths** (Basic → Expert)
3. **Explore all three tabs** thoroughly
4. **Use keyboard shortcuts** for efficiency
5. **Customize themes** via View → Theme
6. **Export session data** to see the full workflow

## 💡 Pro Tips

- **Use real content** for the most meaningful feedback
- **Experiment with different voices** in the TTS tab
- **Try partial guest names** to see search matching
- **Check the status bar** for real-time information
- **Use F1** for built-in help

---

**🎉 Congratulations! You're now ready to explore the full power of SoapBoxx!**

*For the complete experience with real AI analysis, visit the main SoapBoxx repository.*
"""
    
    with open(app_dir / "samples" / "DEMO_INSTRUCTIONS.md", "w", encoding="utf-8") as f:
        f.write(demo_instructions)
    print("   ✅ DEMO_INSTRUCTIONS.md")
    
    # Create version info
    version_info = {
        "version": "1.0.0",
        "release_date": datetime.now().strftime("%Y-%m-%d"),
        "demo_type": "barebones-offline",
        "features": [
            "Local content analysis",
            "Sample guest research", 
            "Mock transcription",
            "Mock TTS generation",
            "Session management",
            "Theme customization",
            "Keyboard shortcuts"
        ],
        "requirements": {
            "python": "3.8+",
            "ram": "4GB+",
            "disk_space": "500MB+"
        },
        "supported_platforms": [
            "Windows 10/11",
            "macOS 10.14+",
            "Linux (Ubuntu 18.04+)"
        ]
    }
    
    with open(app_dir / "VERSION.json", "w", encoding="utf-8") as f:
        json.dump(version_info, f, indent=2)
    print("   ✅ VERSION.json")
    
    # Create package info
    package_info = {
        "package_name": "SoapBoxx-Demo",
        "description": "AI-Powered Podcast Production Studio - Demo Version",
        "author": "SoapBoxx Team",
        "license": "Same as main SoapBoxx project",
        "homepage": "https://github.com/yourusername/SoapBoxx",
        "demo_features": "Offline-capable with mock data and local analysis",
        "upgrade_path": "Switch to main branch for full functionality",
        "support": "Check documentation and test scripts for help"
    }
    
    with open(app_dir / "PACKAGE_INFO.json", "w", encoding="utf-8") as f:
        json.dump(package_info, f, indent=2)
    print("   ✅ PACKAGE_INFO.json")
    
    # Create distribution summary
    print("\n📊 Distribution Package Summary")
    print("=" * 60)
    
    # Count files
    total_files = 0
    for root, dirs, files in os.walk(app_dir):
        total_files += len(files)
    
    print(f"📁 Package Directory: {app_dir}")
    print(f"📦 Total Files: {total_files}")
    print(f"🔧 Backend Modules: {len(backend_files)}")
    print(f"🎨 Frontend Files: {len(frontend_files)}")
    print(f"📚 Documentation: {len(doc_files)}")
    print(f"🚀 Launch Scripts: {len(script_files)}")
    print(f"📝 Sample Content: 3 files")
    
    # Create ZIP archive
    print("\n🗜️ Creating distribution archive...")
    import zipfile
    
    zip_path = dist_dir / "SoapBoxx-Demo-v1.0.0.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(app_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(dist_dir)
                zipf.write(file_path, arcname)
    
    zip_size = zip_path.stat().st_size / (1024 * 1024)  # MB
    print(f"✅ Archive created: {zip_path.name} ({zip_size:.1f} MB)")
    
    print("\n🎉 SoapBoxx Demo Distribution Package Complete!")
    print("=" * 60)
    print(f"📦 Package Location: {dist_dir}")
    print(f"🗜️ Archive: {zip_path}")
    print(f"📁 Application: {app_dir}")
    print("\n🚀 Ready for distribution!")
    
    return dist_dir, zip_path

if __name__ == "__main__":
    try:
        dist_dir, zip_path = create_distribution_package()
        print(f"\n✅ Successfully created distribution package at: {dist_dir}")
        print(f"📦 Distribution archive: {zip_path}")
    except Exception as e:
        print(f"\n❌ Error creating distribution package: {e}")
        import traceback
        traceback.print_exc()
