@echo off
setlocal

echo.
echo ========================================
echo   SoapBoxx Production Studio Demo
echo ========================================
echo.

if not exist "frontend\main_window.py" (
    echo [ERROR] Run this from SoapBoxx root folder.
    pause
    exit /b 1
)

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

set "SOAPBOXX_BUCKET=demo"
set "SOAPBOXX_DEMO_EXPIRES_ON=2026-05-20"

echo Launching demo mode...
echo   bucket=%SOAPBOXX_BUCKET%
echo   expires_on=%SOAPBOXX_DEMO_EXPIRES_ON%
echo.

python "frontend\main_window.py"

if errorlevel 1 (
    echo.
    echo [ERROR] Demo exited with an error.
    exit /b 1
)

echo.
echo Demo closed successfully.
endlocal
