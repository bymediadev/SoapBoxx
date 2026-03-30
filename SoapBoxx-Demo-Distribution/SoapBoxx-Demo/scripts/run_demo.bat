@echo off
echo.
echo ========================================
echo    SoapBoxx Demo - Quick Launcher
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

REM Check if we're in the right directory
if not exist "frontend\main_window.py" (
    echo ❌ main_window.py not found
    echo Please run this script from the SoapBoxx root directory
    pause
    exit /b 1
)

REM Git branch check only when this folder is a git clone (not a release ZIP)
if exist ".git\" (
    git branch --show-current 2>nul | findstr "demo/soapboxx-barebones" >nul
    if errorlevel 1 (
        echo ⚠️  Warning: Not on demo branch
        echo Current branch:
        git branch --show-current
        echo.
        echo To switch to demo branch: git checkout demo/soapboxx-barebones
        echo.
        set /p continue="Continue anyway? (y/N): "
        if /i not "%continue%"=="y" (
            echo Aborted.
            pause
            exit /b 1
        )
    )
)

echo ✅ Python found: 
python --version
echo.

REM Check if required modules are installed
echo 🔍 Checking dependencies...
python -c "import PyQt6" >nul 2>&1
if errorlevel 1 (
    echo ❌ PyQt6 not installed
    echo Installing PyQt6...
    pip install PyQt6
    if errorlevel 1 (
        echo ❌ Failed to install PyQt6
        pause
        exit /b 1
    )
)

python -c "import numpy" >nul 2>&1
if errorlevel 1 (
    echo ❌ numpy not installed
    echo Installing numpy...
    pip install numpy
)

python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo ❌ requests not installed
    echo Installing requests...
    pip install requests
)

echo ✅ Dependencies ready!
echo.

REM Check if barebones modules exist
echo 🔍 Checking barebones modules...
if not exist "backend\feedback_engine_barebones.py" (
    echo ❌ Missing: feedback_engine_barebones.py
    echo Please ensure you're on the demo branch
    pause
    exit /b 1
)

if not exist "backend\guest_research_barebones.py" (
    echo ❌ Missing: guest_research_barebones.py
    echo Please ensure you're on the demo branch
    pause
    exit /b 1
)

if not exist "backend\transcriber_barebones.py" (
    echo ❌ Missing: transcriber_barebones.py
    echo Please ensure you're on the demo branch
    pause
    exit /b 1
)

if not exist "backend\tts_generator_barebones.py" (
    echo ❌ Missing: tts_generator_barebones.py
    echo Please ensure you're on the demo branch
    pause
    exit /b 1
)

if not exist "backend\soapboxx_core_barebones.py" (
    echo ❌ Missing: soapboxx_core_barebones.py
    echo Please ensure you're on the demo branch
    pause
    exit /b 1
)

echo ✅ All barebones modules found!
echo.

echo 🚀 Launching SoapBoxx Demo...
echo.
echo ========================================
echo    Demo Features Available:
echo ========================================
echo 🧠 Content Analysis (SoapBoxx Tab)
echo 🔍 Guest Research (Scoop Tab)  
echo 🎵 Audio Features (Reverb Tab)
echo 📊 Session Management
echo 🎨 Theme Customization
echo ⌨️  Keyboard Shortcuts
echo ========================================
echo.

REM Launch the application
python frontend\main_window.py

REM Check exit code
if errorlevel 1 (
    echo.
    echo ❌ SoapBoxx Demo exited with an error
    echo Check the error messages above for details
    echo.
    echo For help, see TUTORIAL_DEMO.md or README_DEMO.md
) else (
    echo.
    echo ✅ SoapBoxx Demo closed successfully
)

echo.
pause
