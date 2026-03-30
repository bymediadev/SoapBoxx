@echo off
REM Local sandbox: high episode limit + same UI as demo (set SOAPBOXX_DEV_PLAYGROUND=1)
cd /d "%~dp0.."
echo.
echo ========================================
echo   SoapBoxx Demo — Playground mode
echo   (relaxed episode limit for testing)
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Install Python 3.8+ and try again.
    pause
    exit /b 1
)

if not exist "frontend\main_window.py" (
    echo Run this from SoapBoxx-Demo folder. frontend\main_window.py not found.
    pause
    exit /b 1
)

echo Installing/checking dependencies...
python -m pip install -q -r requirements_demo.txt 2>nul
if errorlevel 1 (
    pip install PyQt6 numpy requests python-dotenv
)

set SOAPBOXX_DEV_PLAYGROUND=1
echo.
echo Launching with SOAPBOXX_DEV_PLAYGROUND=1 ...
echo.
python frontend\main_window.py
set exitcode=%errorlevel%
set SOAPBOXX_DEV_PLAYGROUND=
if %exitcode% neq 0 pause
exit /b %exitcode%
