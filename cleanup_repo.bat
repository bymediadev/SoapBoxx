@echo off
echo === SoapBoxx Repository Cleanup ===
echo This will remove large .zip files from git history
echo.

echo Step 1: Checking current git status...
git status

echo.
echo Press Enter to continue with cleanup...
pause

echo Step 2: Aborting any pending merge...
git merge --abort 2>nul
if %errorlevel% equ 0 (
    echo Merge aborted successfully
) else (
    echo No merge to abort or already clean
)

echo Step 3: Removing .zip files from current staging...
git rm --cached *.zip 2>nul
if %errorlevel% equ 0 (
    echo Removed .zip files from staging
) else (
    echo No .zip files in staging or already removed
)

echo Step 4: Adding .zip to .gitignore...
findstr /c:"*.zip" .gitignore >nul 2>&1
if %errorlevel% neq 0 (
    echo *.zip >> .gitignore
    echo Added *.zip to .gitignore
) else (
    echo *.zip already in .gitignore
)

echo Step 5: Committing .gitignore changes...
git add .gitignore
git commit -m "Add .zip to .gitignore to prevent large file commits"

echo Step 6: Removing .zip files from entire git history...
echo This may take a few minutes...
git filter-branch --force --index-filter "git rm --cached --ignore-unmatch '*.zip'" --prune-empty --tag-name-filter cat -- --all

if %errorlevel% equ 0 (
    echo Successfully removed .zip files from history
) else (
    echo Error during filter-branch operation
    pause
    exit /b 1
)

echo Step 7: Cleaning up backup references...
for /f "tokens=*" %%i in ('git for-each-ref --format="%%(refname)" refs/original/') do git update-ref -d %%i 2>nul

echo Step 8: Running aggressive garbage collection...
git reflog expire --expire=now --all
git gc --prune=now --aggressive

echo Step 9: Checking final repository status...
git status

echo.
echo === CLEANUP COMPLETE ===
echo.
echo Next steps:
echo 1. Force push the cleaned repository:
echo    git push origin main --force
echo    git push origin --tags --force
echo.
echo 2. Create a new release tag:
echo    git tag v1.0.1
echo    git push origin v1.0.1
echo.
echo 3. Upload your .zip files as GitHub Release assets (NOT in git)
echo    - Go to GitHub Releases
echo    - Attach your distribution .zip files there
echo    - GitHub allows large files as release assets
echo.
echo Press Enter to exit...
pause
