@echo off
setlocal
set "SOAPBOXX_BUCKET=demo"
set "SOAPBOXX_DEMO_EXPIRES_ON=2026-06-01"
start "" "%~dp0SoapBoxxProductionStudioDemo\SoapBoxxProductionStudioDemo.exe"
endlocal
