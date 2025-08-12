@echo off
title SoapBoxx Installer
echo.
echo ========================================
echo        SoapBoxx v1.0.0 Setup
echo ========================================
echo.

echo Welcome to SoapBoxx - Your AI-Powered Podcast Studio!
echo.

REM Check if OpenAI API key is set
if "%OPENAI_API_KEY%"=="" (
    echo ⚠️  OpenAI API key not found in environment variables.
    echo.
    echo To use AI features, you need to set your OpenAI API key:
    echo.
    echo 1. Get your API key from: https://platform.openai.com/api-keys
    echo 2. Set it as an environment variable:
    echo    setx OPENAI_API_KEY "your_api_key_here"
    echo 3. Restart this installer
    echo.
    echo Or you can run SoapBoxx without AI features (limited functionality).
    echo.
    pause
) else (
    echo ✅ OpenAI API key found and configured!
    echo.
)

echo.
echo 🚀 Launching SoapBoxx...
echo.

REM Launch the application
start "" "SoapBoxx.exe"

echo.
echo SoapBoxx is now launching!
echo.
echo 💡 Tips:
echo    - Use the "🎤 Test Microphone" button to verify audio
echo    - Check the "Guest Questions Approval" section for auto-extraction
echo    - Explore all three tabs: SoapBoxx, Scoop, and Reverb
echo.
pause
