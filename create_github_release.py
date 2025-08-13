#!/usr/bin/env python3
"""
GitHub Release Creator for SoapBoxx Demo
Helps create a professional GitHub release with the distribution package
"""

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

def create_github_release():
    """Create a GitHub release for SoapBoxx Demo"""
    
    print("🚀 Creating GitHub Release for SoapBoxx Demo")
    print("=" * 60)
    
    # Check if distribution package exists
    dist_dir = Path("SoapBoxx-Demo-Distribution")
    zip_file = dist_dir / "SoapBoxx-Demo-v1.0.0.zip"
    
    if not dist_dir.exists():
        print("❌ Distribution directory not found!")
        print("   Run 'python create_demo_package.py' first")
        return False
    
    if not zip_file.exists():
        print("❌ Distribution ZIP not found!")
        print("   Run 'python create_demo_package.py' first")
        return False
    
    print("✅ Distribution package found")
    
    # Check git status
    print("\n🔍 Checking git status...")
    try:
        result = subprocess.run(["git", "status", "--porcelain"], 
                              capture_output=True, text=True, check=True)
        if result.stdout.strip():
            print("⚠️  Uncommitted changes detected:")
            print(result.stdout)
            print("   Consider committing changes before release")
        else:
            print("✅ Working directory clean")
    except subprocess.CalledProcessError:
        print("⚠️  Could not check git status")
    
    # Check current branch
    try:
        result = subprocess.run(["git", "branch", "--show-current"], 
                              capture_output=True, text=True, check=True)
        current_branch = result.stdout.strip()
        print(f"📍 Current branch: {current_branch}")
        
        if current_branch != "demo/soapboxx-barebones":
            print("⚠️  Not on demo branch")
            print("   Consider switching to demo/soapboxx-barebones")
    except subprocess.CmdProcessError:
        print("⚠️  Could not determine current branch")
    
    # Check if gh CLI is available
    print("\n🔧 Checking GitHub CLI...")
    try:
        result = subprocess.run(["gh", "--version"], 
                              capture_output=True, text=True, check=True)
        print("✅ GitHub CLI available")
        gh_available = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ GitHub CLI not available")
        print("   Install from: https://cli.github.com/")
        gh_available = False
    
    # Create release notes
    print("\n📝 Creating release notes...")
    release_notes = create_release_notes()
    
    # Save release notes
    release_file = Path("RELEASE_NOTES_v1.0.0.md")
    with open(release_file, "w", encoding="utf-8") as f:
        f.write(release_notes)
    
    print(f"✅ Release notes saved to: {release_file}")
    
    # Create release script
    print("\n🚀 Creating release script...")
    release_script = create_release_script(gh_available)
    
    script_file = Path("create_release.ps1")
    with open(script_file, "w", encoding="utf-8") as f:
        f.write(release_script)
    
    print(f"✅ Release script saved to: {script_file}")
    
    # Final instructions
    print("\n" + "=" * 60)
    print("🎉 GitHub Release Preparation Complete!")
    print("=" * 60)
    print(f"📝 Release notes: {release_file}")
    print(f"🚀 Release script: {script_file}")
    print(f"📦 Distribution package: {zip_file}")
    
    if gh_available:
        print("\n🎯 To create the release:")
        print("   1. Review the release notes")
        print("   2. Run: .\\create_release.ps1")
        print("   3. Or manually: gh release create v1.0.0 --title '...' --notes-file ...")
    else:
        print("\n🎯 To create the release:")
        print("   1. Install GitHub CLI: https://cli.github.com/")
        print("   2. Authenticate: gh auth login")
        print("   3. Run: .\\create_release.ps1")
    
    print("\n📚 Manual release steps:")
    print("   1. Go to GitHub repository")
    print("   2. Click 'Releases' → 'Create a new release'")
    print("   3. Tag: v1.0.0")
    print("   4. Title: SoapBoxx Demo v1.0.0 - Offline-Capable AI Podcast Studio")
    print("   5. Copy content from RELEASE_NOTES_v1.0.0.md")
    print("   6. Upload SoapBoxx-Demo-v1.0.0.zip")
    print("   7. Publish release")
    
    return True

def create_release_notes():
    """Create comprehensive release notes"""
    
    return """# 🎙️ SoapBoxx Demo v1.0.0 - Offline-Capable AI Podcast Studio

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
# Double-click: scripts\\run_demo.bat
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
"""

def create_release_script(gh_available):
    """Create PowerShell script for release creation"""
    
    if gh_available:
        return """# SoapBoxx Demo - GitHub Release Creator
# Run this script to create a GitHub release

Write-Host "🚀 Creating GitHub Release for SoapBoxx Demo" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan

# Check if we're logged in to GitHub
Write-Host "🔐 Checking GitHub authentication..." -ForegroundColor Yellow
try {
    $auth_status = gh auth status 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ GitHub CLI authenticated" -ForegroundColor Green
    } else {
        Write-Host "❌ GitHub CLI not authenticated" -ForegroundColor Red
        Write-Host "   Run: gh auth login" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "❌ GitHub CLI not available" -ForegroundColor Red
    Write-Host "   Install from: https://cli.github.com/" -ForegroundColor Yellow
    exit 1
}

# Check if distribution package exists
$zip_file = "SoapBoxx-Demo-Distribution\\SoapBoxx-Demo-v1.0.0.zip"
if (-not (Test-Path $zip_file)) {
    Write-Host "❌ Distribution package not found!" -ForegroundColor Red
    Write-Host "   Run 'python create_demo_package.py' first" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Distribution package found" -ForegroundColor Green

# Create the release
Write-Host "🚀 Creating GitHub release..." -ForegroundColor Yellow
try {
    gh release create v1.0.0 `
        --title "SoapBoxx Demo v1.0.0 - Offline-Capable AI Podcast Studio" `
        --notes-file "RELEASE_NOTES_v1.0.0.md" `
        --target "demo/soapboxx-barebones" `
        $zip_file
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "🎉 GitHub release created successfully!" -ForegroundColor Green
        Write-Host "   Visit your repository to view the release" -ForegroundColor Cyan
    } else {
        Write-Host "❌ Failed to create release" -ForegroundColor Red
        Write-Host "   Check the error messages above" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Error creating release: $_" -ForegroundColor Red
}

Write-Host "`n🎯 Next steps:" -ForegroundColor Cyan
Write-Host "   1. Verify the release on GitHub" -ForegroundColor White
Write-Host "   2. Test the download link" -ForegroundColor White
Write-Host "   3. Share with your community!" -ForegroundColor White
"""
    else:
        return """# SoapBoxx Demo - GitHub Release Creator
# Manual release creation script

Write-Host "🚀 SoapBoxx Demo - GitHub Release Preparation" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Cyan

Write-Host "📦 Distribution package found" -ForegroundColor Green

Write-Host "`n🎯 To create the GitHub release manually:" -ForegroundColor Cyan
Write-Host "   1. Go to your GitHub repository" -ForegroundColor White
Write-Host "   2. Click 'Releases' → 'Create a new release'" -ForegroundColor White
Write-Host "   3. Tag: v1.0.0" -ForegroundColor White
Write-Host "   4. Title: SoapBoxx Demo v1.0.0 - Offline-Capable AI Podcast Studio" -ForegroundColor White
Write-Host "   5. Copy content from RELEASE_NOTES_v1.0.0.md" -ForegroundColor White
Write-Host "   6. Upload SoapBoxx-Demo-v1.0.0.zip" -ForegroundColor White
Write-Host "   7. Publish release" -ForegroundColor White

Write-Host "`n📝 Release notes are in: RELEASE_NOTES_v1.0.0.md" -ForegroundColor Yellow
Write-Host "📦 Distribution package: SoapBoxx-Demo-v1.0.0.zip" -ForegroundColor Yellow

Write-Host "`n🔧 For automated releases, install GitHub CLI:" -ForegroundColor Cyan
Write-Host "   https://cli.github.com/" -ForegroundColor White
"""

def main():
    """Main function"""
    try:
        success = create_github_release()
        if success:
            print("\n🎉 GitHub release preparation complete!")
            print("   Review the files and run the release script")
        else:
            print("\n❌ GitHub release preparation failed")
        
        return success
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

