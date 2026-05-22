@echo off
setlocal
set "EXE=%~dp0SoapBoxxProductionStudioDemo\SoapBoxxProductionStudioDemo.exe"
if not exist "%EXE%" (
    echo.
    echo  SoapBoxx Demo could not start.
    echo  Extract the ENTIRE zip to a folder first ??? do not run this file from inside WinRAR.
    echo.
    echo  Missing: %EXE%
    echo.
    pause
    exit /b 1
)
set "SOAPBOXX_BUCKET=demo"
set "SOAPBOXX_CONFIG_FILE=%~dp0soapboxx_config.demo.json"
start "" "%EXE%"
endlocal
