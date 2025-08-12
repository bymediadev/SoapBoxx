@echo off
title SoapBoxx Launcher
echo.
echo ========================================
echo        SoapBoxx v1.0.0 Launcher
echo ========================================
echo.

echo 🚀 Starting SoapBoxx...
echo.

REM Check if virtual environment exists
if not exist ".venv\Scripts\Activate.ps1" (
    echo ❌ Virtual environment not found!
    echo.
    echo Please run the setup first:
    echo python -m venv .venv
    echo .\.venv\Scripts\Activate.ps1
    echo pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment and run
echo ✅ Virtual environment found
echo 🔧 Activating environment...
echo.

REM Activate virtual environment and run Python directly
call .\.venv\Scripts\activate.bat
python frontend\main_window.py

echo.
echo SoapBoxx has closed.
pause
