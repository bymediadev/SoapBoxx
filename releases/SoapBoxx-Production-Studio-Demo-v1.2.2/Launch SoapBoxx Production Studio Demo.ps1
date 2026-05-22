\Stop = "Stop"
\ = Join-Path \C:\Users\yasuk\SoapBoxx "SoapBoxxProductionStudioDemo\SoapBoxxProductionStudioDemo.exe"
if (-not (Test-Path \)) {
    Write-Host ""
    Write-Host "Extract the ENTIRE zip to a folder first â€” do not run from inside WinRAR."
    Write-Host "Missing: \"
    exit 1
}
\ = "demo"
Start-Process -FilePath \
