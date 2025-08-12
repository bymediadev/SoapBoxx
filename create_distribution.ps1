# SoapBoxx Distribution Package Creator
# This script creates a professional distribution package for SoapBoxx

param(
    [string]$Version = "1.0.0",
    [switch]$Help
)

if ($Help) {
    Write-Host @"
SoapBoxx Distribution Package Creator

Usage:
    .\create_distribution.ps1 [-Version "1.0.0"] [-Help]

Parameters:
    -Version    Version number for the distribution (default: 1.0.0)
    -Help       Show this help message

Examples:
    .\create_distribution.ps1
    .\create_distribution.ps1 -Version "1.1.0"

"@
    exit 0
}

# Set console title and colors
$Host.UI.RawUI.WindowTitle = "SoapBoxx Distribution Creator v$Version"
$Host.UI.RawUI.ForegroundColor = "Cyan"

Write-Host @"

========================================
    SoapBoxx Distribution Creator
========================================
    Version: $Version

"@ -ForegroundColor Green

# Check if we're in the right directory
if (-not (Test-Path "frontend\main_window.py")) {
    Write-Host "❌ Error: Please run this script from the SoapBoxx root directory!" -ForegroundColor Red
    Write-Host "   Make sure you're in the folder containing 'frontend' and 'backend' directories" -ForegroundColor Red
    exit 1
}

# Create distribution directory
$distDir = "SoapBoxx-Distribution-v$Version"
if (Test-Path $distDir) {
    Write-Host "🗑️  Removing existing distribution directory..." -ForegroundColor Yellow
    Remove-Item $distDir -Recurse -Force
}

Write-Host "📁 Creating distribution directory: $distDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Path $distDir | Out-Null

# Copy core directories
Write-Host "📦 Copying core modules..." -ForegroundColor Cyan
$directories = @("backend", "frontend", "docs")
foreach ($dir in $directories) {
    if (Test-Path $dir) {
        Write-Host "   📁 Copying $dir..." -ForegroundColor White
        Copy-Item $dir -Destination $distDir -Recurse
    }
}

# Copy essential files
Write-Host "📄 Copying essential files..." -ForegroundColor Cyan
$files = @(
    "launch_SoapBoxx.bat",
    "launch_SoapBoxx.ps1", 
    "requirements.txt",
    "soapboxx_config.json",
    "DISTRIBUTION_README.md",
    "GITHUB_RELEASE_TEMPLATE.md"
)

foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "   📄 Copying $file..." -ForegroundColor White
        Copy-Item $file -Destination $distDir
    } else {
        Write-Host "   ⚠️  Warning: $file not found" -ForegroundColor Yellow
    }
}

# Create empty directories that will be created on first run
Write-Host "📁 Creating runtime directories..." -ForegroundColor Cyan
$runtimeDirs = @("logs", "Exports")
foreach ($dir in $runtimeDirs) {
    $runtimePath = Join-Path $distDir $dir
    New-Item -ItemType Directory -Path $runtimePath | Out-Null
    Write-Host "   📁 Created $dir/" -ForegroundColor White
}

# Create a simple README for the distribution
$readmeContent = @"
# SoapBoxx v$Version - AI-Powered Podcast Studio

## Quick Start

1. Double-click launch_SoapBoxx.bat to start
2. That's it! - No installation required

## Full Documentation

See DISTRIBUTION_README.md for complete instructions.

## Setup Required

- OpenAI API Key for AI features
- Microphone for audio recording

## Support

- GitHub Issues: Report bugs and request features
- Built-in Help: Check the app's help system

---

Built with love using Python, PyQt6, and OpenAI
"@

$readmeContent | Out-File -FilePath (Join-Path $distDir "README.md") -Encoding UTF8

# Create .gitignore for the distribution
$gitignoreContent = @"
# Runtime files
logs/
Exports/
*.log
*.tmp

# Python cache
__pycache__/
*.pyc
*.pyo

# Environment
.venv/
.env

# IDE files
.vscode/
.idea/
*.swp
*.swo

# OS files
.DS_Store
Thumbs.db
"@

$gitignoreContent | Out-File -FilePath (Join-Path $distDir ".gitignore") -Encoding UTF8

# Calculate package size
$packageSize = (Get-ChildItem $distDir -Recurse | Measure-Object -Property Length -Sum).Sum
$packageSizeMB = [math]::Round($packageSize / 1MB, 2)

Write-Host ""
Write-Host "✅ Distribution package created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Package Details:" -ForegroundColor Cyan
Write-Host "   📁 Directory: $distDir" -ForegroundColor White
Write-Host "   📦 Size: $packageSizeMB MB" -ForegroundColor White
Write-Host "   🚀 Launcher: launch_SoapBoxx.bat" -ForegroundColor White
Write-Host "   📖 Documentation: DISTRIBUTION_README.md" -ForegroundColor White
Write-Host ""

# Create ZIP archive
$zipPath = "$distDir.zip"
Write-Host "🗜️  Creating ZIP archive..." -ForegroundColor Cyan

try {
    if (Get-Command "Compress-Archive" -ErrorAction SilentlyContinue) {
        Compress-Archive -Path $distDir -DestinationPath $zipPath -Force
        $zipSize = (Get-Item $zipPath).Length
        $zipSizeMB = [math]::Round($zipSize / 1MB, 2)
        
        Write-Host "✅ ZIP archive created: $zipPath" -ForegroundColor Green
        Write-Host "   📦 ZIP Size: $zipSizeMB MB" -ForegroundColor White
    } else {
        Write-Host "⚠️  ZIP creation skipped (Compress-Archive not available)" -ForegroundColor Yellow
        Write-Host "   You can manually create a ZIP of the $distDir folder" -ForegroundColor White
    }
} catch {
    Write-Host "⚠️  ZIP creation failed: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "   You can manually create a ZIP of the $distDir folder" -ForegroundColor White
}

Write-Host ""
Write-Host "🎉 Distribution package ready!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Next Steps:" -ForegroundColor Cyan
Write-Host "   1. Test the package by extracting and running launch_SoapBoxx.bat" -ForegroundColor White
Write-Host "   2. Upload to GitHub Releases using GITHUB_RELEASE_TEMPLATE.md" -ForegroundColor White
Write-Host "   3. Share with testers for feedback" -ForegroundColor White
Write-Host ""
Write-Host "💡 Pro Tip: The launcher approach ensures 100% reliability!" -ForegroundColor Yellow
Write-Host ""
