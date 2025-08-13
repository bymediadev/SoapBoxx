#!/usr/bin/env python3
"""
Create Enhanced SoapBoxx Demo Package
====================================

This script creates a complete distribution package of the SoapBoxx Demo
with all the enhanced interactive features.
"""

import os
import shutil
import zipfile
from datetime import datetime

def create_enhanced_package():
    """Create the enhanced demo package"""
    
    # Package details
    package_name = "SoapBoxx-Demo-Enhanced-v1.1.0"
    source_dir = "SoapBoxx-Demo"
    output_dir = "."
    
    print(f"🎯 Creating enhanced SoapBoxx Demo package: {package_name}")
    print("=" * 60)
    
    # Check if source directory exists
    if not os.path.exists(source_dir):
        print(f"❌ Error: Source directory '{source_dir}' not found!")
        return False
    
    # Create temporary package directory
    temp_package_dir = package_name
    if os.path.exists(temp_package_dir):
        shutil.rmtree(temp_package_dir)
    
    os.makedirs(temp_package_dir)
    print(f"✅ Created temporary directory: {temp_package_dir}")
    
    # Copy all files from source
    print("\n📁 Copying files...")
    
    # Essential directories and files to include
    essential_items = [
        "frontend/",
        "backend/",
        "docs/",
        "README_DEMO.md",
        "TUTORIAL_DEMO.md",
        "BUILD_CHECKLIST.md",
        "run_demo.bat",
        "run_demo.sh",
        "requirements.txt",
        "setup.py"
    ]
    
    copied_count = 0
    for item in essential_items:
        source_path = os.path.join(source_dir, item)
        dest_path = os.path.join(temp_package_dir, item)
        
        if os.path.exists(source_path):
            if os.path.isdir(source_path):
                shutil.copytree(source_path, dest_path)
                print(f"  📁 {item}/")
            else:
                shutil.copy2(source_path, dest_path)
                print(f"  📄 {item}")
            copied_count += 1
        else:
            print(f"  ⚠️  {item} (not found)")
    
    # Create enhanced README
    enhanced_readme = f"""# SoapBoxx Demo - Enhanced Version v1.1.0

## 🚀 What's New in This Version

### ✨ Interactive Features Added:
- **🎙️ Live Recording Animation**: Pulsing record button with real-time timer
- **🔍 Live Search**: Animated search with "Searching..." dots
- **📊 Real-time Analysis**: Content scoring that updates as you type
- **🎨 Professional UI**: Modern, responsive interface with smooth animations

### 🎯 Demo Capabilities:
- **SoapBoxx Tab**: Recording controls, AI processing simulation, export options
- **Scoop Tab**: Content discovery, trending topics, interactive search results
- **Reverb Tab**: Content feedback, performance metrics, optimization tools

### 🎭 Demo vs. Full Version:
This demo showcases the SoapBoxx interface and user experience without requiring:
- OpenAI API keys
- Complex backend services
- Audio processing libraries
- Web scraping dependencies

## 🚀 Quick Start

### Windows:
```bash
run_demo.bat
```

### macOS/Linux:
```bash
chmod +x run_demo.sh
./run_demo.sh
```

### Manual:
```bash
python frontend/main_window.py
```

## 📋 Requirements
- Python 3.8+
- PyQt6
- See requirements.txt for full list

## 🎉 Features

### Interactive Recording (SoapBoxx Tab)
- Click record button to start live timer
- Watch pulsing animation during recording
- See total recording time when stopped

### Live Search (Scoop Tab)
- Type search terms and watch animation
- Interactive search results with action buttons
- Trending topics you can click to explore

### Real-time Analysis (Reverb Tab)
- Paste content and see scores update instantly
- Engagement, clarity, and impact metrics
- Content optimization suggestions

## 🔧 Technical Details
- Built with PyQt6 for cross-platform compatibility
- Bulletproof tab loading system
- Responsive design with modern UI components
- Demo data and simulated backend responses

## 📞 Support
This is a demonstration version. For the full SoapBoxx application with real AI capabilities, visit the main repository.

---
*Enhanced Demo Package created on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
    
    with open(os.path.join(temp_package_dir, "README_ENHANCED.md"), "w", encoding="utf-8") as f:
        f.write(enhanced_readme)
    
    print(f"  📄 README_ENHANCED.md")
    copied_count += 1
    
    # Create ZIP file
    zip_filename = f"{package_name}.zip"
    zip_path = os.path.join(output_dir, zip_filename)
    
    print(f"\n📦 Creating ZIP package: {zip_filename}")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(temp_package_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, temp_package_dir)
                zipf.write(file_path, arcname)
                print(f"  📦 {arcname}")
    
    # Clean up temporary directory
    shutil.rmtree(temp_package_dir)
    
    # Get file size
    file_size = os.path.getsize(zip_path)
    file_size_mb = file_size / (1024 * 1024)
    
    print(f"\n✅ Package created successfully!")
    print(f"📁 File: {zip_filename}")
    print(f"📏 Size: {file_size_mb:.2f} MB")
    print(f"📊 Files included: {copied_count}")
    
    return True

if __name__ == "__main__":
    try:
        success = create_enhanced_package()
        if success:
            print("\n🎉 Enhanced SoapBoxx Demo package ready for GitHub!")
            print("📤 You can now upload this to your repository.")
        else:
            print("\n❌ Package creation failed!")
    except Exception as e:
        print(f"\n💥 Error creating package: {e}")
        import traceback
        traceback.print_exc()
