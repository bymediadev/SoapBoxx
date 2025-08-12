# SoapBoxx Repository Cleanup Script
# This script will remove large .zip files from git history and prepare for clean push

Write-Host "=== SoapBoxx Repository Cleanup ===" -ForegroundColor Green
Write-Host "This will remove large .zip files from git history" -ForegroundColor Yellow
Write-Host ""

# Step 1: Check current status
Write-Host "Step 1: Checking current git status..." -ForegroundColor Cyan
git status

Write-Host ""
Write-Host "Press Enter to continue with cleanup..." -ForegroundColor Yellow
Read-Host

# Step 2: Abort any pending merge if needed
Write-Host "Step 2: Aborting any pending merge..." -ForegroundColor Cyan
git merge --abort 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Merge aborted successfully" -ForegroundColor Green
} else {
    Write-Host "No merge to abort or already clean" -ForegroundColor Yellow
}

# Step 3: Remove .zip files from current staging
Write-Host "Step 3: Removing .zip files from current staging..." -ForegroundColor Cyan
git rm --cached *.zip 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Removed .zip files from staging" -ForegroundColor Green
} else {
    Write-Host "No .zip files in staging or already removed" -ForegroundColor Yellow
}

# Step 4: Add .zip to .gitignore
Write-Host "Step 4: Adding .zip to .gitignore..." -ForegroundColor Cyan
if (-not (Select-String -Path ".gitignore" -Pattern "\.zip" -Quiet)) {
    Add-Content -Path ".gitignore" -Value "*.zip"
    Write-Host "Added *.zip to .gitignore" -ForegroundColor Green
} else {
    Write-Host "*.zip already in .gitignore" -ForegroundColor Yellow
}

# Step 5: Commit the .gitignore changes
Write-Host "Step 5: Committing .gitignore changes..." -ForegroundColor Cyan
git add .gitignore
git commit -m "Add .zip to .gitignore to prevent large file commits"

# Step 6: Remove .zip files from entire git history
Write-Host "Step 6: Removing .zip files from entire git history..." -ForegroundColor Cyan
Write-Host "This may take a few minutes..." -ForegroundColor Yellow

# Use git filter-branch to remove .zip files from all commits
git filter-branch --force --index-filter "git rm --cached --ignore-unmatch '*.zip'" --prune-empty --tag-name-filter cat -- --all

if ($LASTEXITCODE -eq 0) {
    Write-Host "Successfully removed .zip files from history" -ForegroundColor Green
} else {
    Write-Host "Error during filter-branch operation" -ForegroundColor Red
    exit 1
}

# Step 7: Clean up backup references
Write-Host "Step 7: Cleaning up backup references..." -ForegroundColor Cyan
git for-each-ref --format="%(refname)" refs/original/ | ForEach-Object { git update-ref -d $_ } 2>$null

# Step 8: Aggressive garbage collection
Write-Host "Step 8: Running aggressive garbage collection..." -ForegroundColor Cyan
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Step 9: Check final status
Write-Host "Step 9: Checking final repository status..." -ForegroundColor Cyan
git status

Write-Host ""
Write-Host "=== CLEANUP COMPLETE ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Force push the cleaned repository:" -ForegroundColor White
Write-Host "   git push origin main --force" -ForegroundColor Cyan
Write-Host "   git push origin --tags --force" -ForegroundColor Cyan
Write-Host ""
Write-Host "2. Create a new release tag:" -ForegroundColor White
Write-Host "   git tag v1.0.1" -ForegroundColor Cyan
Write-Host "   git push origin v1.0.1" -ForegroundColor Cyan
Write-Host ""
Write-Host "3. Upload your .zip files as GitHub Release assets (NOT in git)" -ForegroundColor White
Write-Host "   - Go to GitHub Releases" -ForegroundColor Cyan
Write-Host "   - Attach your distribution .zip files there" -ForegroundColor Cyan
Write-Host "   - GitHub allows large files as release assets" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Enter to exit..." -ForegroundColor Yellow
Read-Host
