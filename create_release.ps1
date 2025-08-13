# SoapBoxx Demo - GitHub Release Creator
# Run this script to create a GitHub release

Write-Host "Creating GitHub Release for SoapBoxx Demo" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan

# Check if we're logged in to GitHub
Write-Host "Checking GitHub authentication..." -ForegroundColor Yellow
try {
    $auth_status = gh auth status 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "GitHub CLI authenticated" -ForegroundColor Green
    } else {
        Write-Host "GitHub CLI not authenticated" -ForegroundColor Red
        Write-Host "   Run: gh auth login" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "GitHub CLI not available" -ForegroundColor Red
    Write-Host "   Install from: https://cli.github.com/" -ForegroundColor Yellow
    exit 1
}

# Check if distribution package exists
$zip_file = "SoapBoxx-Demo-Distribution\SoapBoxx-Demo-v1.0.0.zip"
if (-not (Test-Path $zip_file)) {
    Write-Host "Distribution package not found!" -ForegroundColor Red
    Write-Host "   Run 'python create_demo_package.py' first" -ForegroundColor Yellow
    exit 1
}

Write-Host "Distribution package found" -ForegroundColor Green

# Create the release
Write-Host "Creating GitHub release..." -ForegroundColor Yellow
try {
    gh release create v1.0.0 `
        --title "SoapBoxx Demo v1.0.0 - Offline-Capable AI Podcast Studio" `
        --notes-file "RELEASE_NOTES_v1.0.0.md" `
        --target "demo/soapboxx-barebones" `
        $zip_file
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "GitHub release created successfully!" -ForegroundColor Green
        Write-Host "   Visit your repository to view the release" -ForegroundColor Cyan
    } else {
        Write-Host "Failed to create release" -ForegroundColor Red
        Write-Host "   Check the error messages above" -ForegroundColor Yellow
    }
} catch {
    Write-Host "Error creating release: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "   1. Verify the release on GitHub" -ForegroundColor White
Write-Host "   2. Test the download link" -ForegroundColor White
Write-Host "   3. Share with your community" -ForegroundColor White

