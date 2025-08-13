# GitHub Release Upload Script

## Option 1: GitHub CLI (Recommended)

If you have GitHub CLI installed:

```bash
# Create a new release
gh release create v1.1.0 \
  --title "SoapBoxx Demo v1.1.0 - Enhanced Interactive Experience" \
  --notes-file RELEASE_NOTES_v1.1.0.md \
  --repo yourusername/SoapBoxx \
  SoapBoxx-Demo-Enhanced-v1.1.0.zip
```

## Option 2: GitHub Web Interface

1. Go to your repository: https://github.com/yourusername/SoapBoxx
2. Click "Releases" on the right side
3. Click "Create a new release"
4. Tag: `v1.1.0`
5. Title: `SoapBoxx Demo v1.1.0 - Enhanced Interactive Experience`
6. Description: Copy content from `RELEASE_NOTES_v1.1.0.md`
7. Upload `SoapBoxx-Demo-Enhanced-v1.1.0.zip` as a binary
8. Click "Publish release"

## Option 3: Git Commands

```bash
# Add the new package
git add SoapBoxx-Demo-Enhanced-v1.1.0.zip
git add RELEASE_NOTES_v1.1.0.md

# Commit
git commit -m "Add enhanced SoapBoxx Demo v1.1.0 with interactive features"

# Push
git push origin main

# Create and push tag
git tag -a v1.1.0 -m "Enhanced Demo v1.1.0"
git push origin v1.1.0
```

## Package Details

- **File**: SoapBoxx-Demo-Enhanced-v1.1.0.zip
- **Size**: ~84KB
- **Version**: 1.1.0
- **Features**: Interactive recording, live search, real-time analysis
- **Compatibility**: Windows, macOS, Linux
