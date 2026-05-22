@echo off
setlocal
cd /d "%~dp0"
set "EXE=%~dp0SoapBoxxProductionStudioDemo.exe"
if not exist "%EXE%" (
    echo Missing demo executable: %EXE%
    pause
    exit /b 1
)
set "SOAPBOXX_BUCKET=demo"
start "" "%EXE%"
endlocal
