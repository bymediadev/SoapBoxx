# SoapBoxx v1.0.0 PowerShell Installer
# Run with: PowerShell -ExecutionPolicy Bypass -File install_SoapBoxx.ps1

param(
    [string]$OpenAIKey = "",
    [switch]$SkipSetup,
    [switch]$Help
)

if ($Help) {
    Write-Host @"
SoapBoxx v1.0.0 PowerShell Installer

Usage:
    .\install_SoapBoxx.ps1 [-OpenAIKey "your_key"] [-SkipSetup] [-Help]

Parameters:
    -OpenAIKey    Set OpenAI API key during installation
    -SkipSetup    Skip setup and launch directly
    -Help         Show this help message

Examples:
    .\install_SoapBoxx.ps1
    .\install_SoapBoxx.ps1 -OpenAIKey "sk-..."
    .\install_SoapBoxx.ps1 -SkipSetup

"@
    exit 0
}

# Set console title and colors
$Host.UI.RawUI.WindowTitle = "SoapBoxx v1.0.0 Setup"
$Host.UI.RawUI.ForegroundColor = "Cyan"

Write-Host @"

========================================
        SoapBoxx v1.0.0 Setup
========================================

"@ -ForegroundColor Green

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

if (-not $isAdmin) {
    Write-Host "⚠️  Running without administrator privileges" -ForegroundColor Yellow
    Write-Host "   Some features may be limited" -ForegroundColor Yellow
    Write-Host ""
}

# OpenAI API Key Setup
if (-not $SkipSetup) {
    $currentKey = [Environment]::GetEnvironmentVariable("OPENAI_API_KEY", "User")
    
    if ($OpenAIKey -ne "") {
        $apiKey = $OpenAIKey
        Write-Host "🔑 Using provided OpenAI API key..." -ForegroundColor Green
    } elseif ($currentKey -ne "") {
        $apiKey = $currentKey
        Write-Host "✅ OpenAI API key found in environment variables" -ForegroundColor Green
    } else {
        Write-Host "⚠️  No OpenAI API key found" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "To use AI features, you need an OpenAI API key:" -ForegroundColor White
        Write-Host "1. Visit: https://platform.openai.com/api-keys" -ForegroundColor White
        Write-Host "2. Create a new API key" -ForegroundColor White
        Write-Host "3. Enter it below (or press Enter to skip)" -ForegroundColor White
        Write-Host ""
        
        $apiKey = Read-Host "Enter your OpenAI API key (or press Enter to skip)"
        
        if ($apiKey -ne "") {
            try {
                [Environment]::SetEnvironmentVariable("OPENAI_API_KEY", $apiKey, "User")
                Write-Host "✅ OpenAI API key saved to environment variables" -ForegroundColor Green
            } catch {
                Write-Host "❌ Failed to save API key. You may need to run as administrator." -ForegroundColor Red
                Write-Host "   You can still use SoapBoxx with limited functionality." -ForegroundColor Yellow
            }
        } else {
            Write-Host "⏭️  Skipping API key setup" -ForegroundColor Yellow
            Write-Host "   SoapBoxx will run with limited AI functionality" -ForegroundColor Yellow
        }
    }
}

# Check if SoapBoxx.exe exists
if (-not (Test-Path "SoapBoxx.exe")) {
    Write-Host "❌ SoapBoxx.exe not found in current directory!" -ForegroundColor Red
    Write-Host "   Make sure you're running this installer from the same folder as SoapBoxx.exe" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# System check
Write-Host ""
Write-Host "🔍 Checking system requirements..." -ForegroundColor Cyan

$os = Get-WmiObject -Class Win32_OperatingSystem
$ram = [math]::Round((Get-WmiObject -Class Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)

Write-Host "   OS: $($os.Caption) $($os.OSArchitecture)" -ForegroundColor White
Write-Host "   RAM: $ram GB" -ForegroundColor White

if ($ram -lt 4) {
    Write-Host "   ⚠️  RAM below recommended (4GB minimum)" -ForegroundColor Yellow
} else {
    Write-Host "   ✅ RAM meets requirements" -ForegroundColor Green
}

# Launch SoapBoxx
Write-Host ""
Write-Host "🚀 Launching SoapBoxx..." -ForegroundColor Green
Write-Host ""

try {
    Start-Process "SoapBoxx.exe" -ErrorAction Stop
    Write-Host "✅ SoapBoxx launched successfully!" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to launch SoapBoxx: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "🎉 Setup complete! SoapBoxx is now running." -ForegroundColor Green
Write-Host ""
Write-Host "💡 Quick Tips:" -ForegroundColor Cyan
Write-Host "   • Use '🎤 Test Microphone' to verify audio" -ForegroundColor White
Write-Host "   • Check 'Guest Questions Approval' for auto-extraction" -ForegroundColor White
Write-Host "   • Explore all three tabs: SoapBoxx, Scoop, and Reverb" -ForegroundColor White
Write-Host "   • Set your OpenAI API key in environment variables for full AI features" -ForegroundColor White
Write-Host ""

if (-not $SkipSetup) {
    Read-Host "Press Enter to exit installer"
}
