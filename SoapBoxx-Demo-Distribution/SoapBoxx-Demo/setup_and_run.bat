@echo off
REM SoapBoxx Demo — double-click this after unzipping (GitHub Release ZIP).
REM Installs dependencies and launches the app (runs setup_and_run.ps1).

title SoapBoxx Demo — setup and run
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_and_run.ps1"
set EXITCODE=%ERRORLEVEL%

if %EXITCODE% neq 0 (
  echo.
  echo Press any key to close...
  pause >nul
)
exit /b %EXITCODE%
