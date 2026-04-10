@echo off
setlocal
REM Run from the folder where this .bat lives (SoapBoxx repo root) so backend/ loads correctly.
cd /d "%~dp0"

title SoapBoxx Launcher
echo.
echo ========================================
echo        SoapBoxx v1.0.0 Launcher
echo ========================================
echo.

echo 🚀 Starting SoapBoxx...
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo ❌ Virtual environment not found in this folder!
    echo.
    echo From the SoapBoxx repo root, run:
    echo   python -m venv .venv
    echo   .\.venv\Scripts\activate.bat
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo ✅ Virtual environment found
echo 🔧 Activating environment...
echo.

call ".venv\Scripts\activate.bat"
python frontend\main_window.py

echo.
echo SoapBoxx has closed.
pause
