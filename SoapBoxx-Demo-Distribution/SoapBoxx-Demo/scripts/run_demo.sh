#!/bin/bash

echo ""
echo "========================================"
echo "   SoapBoxx Demo - Quick Launcher"
echo "========================================"
echo ""

# Find Python command
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ Python is not installed or not in PATH"
    echo "Please install Python 3.8+ and try again"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "frontend/main_window.py" ]; then
    echo "❌ main_window.py not found"
    echo "Please run this script from the SoapBoxx-Demo directory"
    echo ""
    echo "Current directory: $(pwd)"
    echo "Expected files: frontend/main_window.py"
    echo ""
    echo "Make sure you extracted the ZIP file and are in the SoapBoxx-Demo folder"
    exit 1
fi

# Check if we're in a demo package (standalone)
echo "✅ Running from SoapBoxx Demo package"
echo ""

echo "✅ Python found:"
$PYTHON_CMD --version
echo ""

# Check if required modules are installed
echo "🔍 Checking dependencies..."

if ! $PYTHON_CMD -c "import PyQt6" &> /dev/null; then
    echo "❌ PyQt6 not installed"
    echo "Installing PyQt6..."
    pip install PyQt6
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install PyQt6"
        exit 1
    fi
fi

if ! $PYTHON_CMD -c "import numpy" &> /dev/null; then
    echo "❌ numpy not installed"
    echo "Installing numpy..."
    pip install numpy
fi

if ! $PYTHON_CMD -c "import requests" &> /dev/null; then
    echo "❌ requests not installed"
    echo "Installing requests..."
    pip install requests
fi

echo "✅ Dependencies ready!"
echo ""

# Check if barebones modules exist
echo "🔍 Checking barebones modules..."

MISSING_MODULES=()

if [ ! -f "backend/feedback_engine_barebones.py" ]; then
    MISSING_MODULES+=("feedback_engine_barebones.py")
fi

if [ ! -f "backend/guest_research_barebones.py" ]; then
    MISSING_MODULES+=("guest_research_barebones.py")
fi

if [ ! -f "backend/transcriber_barebones.py" ]; then
    MISSING_MODULES+=("transcriber_barebones.py")
fi

if [ ! -f "backend/tts_generator_barebones.py" ]; then
    MISSING_MODULES+=("tts_generator_barebones.py")
fi

if [ ! -f "backend/soapboxx_core_barebones.py" ]; then
    MISSING_MODULES+=("soapboxx_core_barebones.py")
fi

if [ ${#MISSING_MODULES[@]} -gt 0 ]; then
    echo "❌ Missing modules:"
    for module in "${MISSING_MODULES[@]}"; do
        echo "   - $module"
    done
    echo "Please ensure the demo package is complete"
    exit 1
fi

echo "✅ All barebones modules found!"
echo ""

echo "🚀 Launching SoapBoxx Demo..."
echo ""
echo "========================================"
echo "   Demo Features Available:"
echo "========================================"
echo "🧠 Content Analysis (SoapBoxx Tab)"
echo "🔍 Guest Research (Scoop Tab)"
echo "🎵 Audio Features (Reverb Tab)"
echo "📊 Session Management"
echo "🎨 Theme Customization"
echo "⌨️  Keyboard Shortcuts"
echo "========================================"
echo ""

# Launch the application
$PYTHON_CMD frontend/main_window.py

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ SoapBoxx Demo closed successfully"
else
    echo ""
    echo "❌ SoapBoxx Demo exited with an error"
    echo "Check the error messages above for details"
    echo ""
    echo "For help, see TUTORIAL_DEMO.md or README_DEMO.md"
fi

echo ""
read -p "Press Enter to continue..."
