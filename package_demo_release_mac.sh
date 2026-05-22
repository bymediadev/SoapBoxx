#!/usr/bin/env bash
# SoapBoxx Production Studio Demo — macOS packager (run on a Mac or CI macos-latest).
set -euo pipefail

VERSION="${1:-1.2.3}"
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

APP_NAME="SoapBoxxProductionStudioDemo"
DIST_ROOT="dist/demo"
BUILD_ROOT="build/demo"
RELEASE_ROOT="releases"
RELEASE_NAME="SoapBoxx-Production-Studio-Demo-v${VERSION}-mac"
RELEASE_DIR="${RELEASE_ROOT}/${RELEASE_NAME}"
ZIP_PATH="${RELEASE_DIR}.zip"

echo ""
echo "==============================================="
echo " SoapBoxx Production Studio Demo (macOS)"
echo "==============================================="
echo "Version: ${VERSION}"
echo ""

if [[ ! -f "frontend/main_window.py" ]]; then
  echo "Run this script from the repository root." >&2
  exit 1
fi

rm -rf "${DIST_ROOT}" "${BUILD_ROOT}" "${RELEASE_DIR}" "${ZIP_PATH}"
mkdir -p "${BUILD_ROOT}" "${RELEASE_DIR}"

RUNTIME_HOOK="${BUILD_ROOT}/demo_runtime_env.py"
cat > "${RUNTIME_HOOK}" <<'PY'
import os
import sys

os.environ.setdefault("SOAPBOXX_BUCKET", "demo")

try:
    from backend.runtime_paths import configure_frozen_runtime
    configure_frozen_runtime()
except Exception as exc:
    print(f"SoapBoxx demo runtime hook: {exc}", file=sys.stderr)
PY

echo "Installing packaging dependency (PyInstaller)..."
python3 -m pip install --upgrade pip pyinstaller

echo "Building demo app bundle..."
python3 -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "${APP_NAME}" \
  --distpath "${DIST_ROOT}" \
  --workpath "${BUILD_ROOT}" \
  --specpath "${BUILD_ROOT}" \
  --runtime-hook "${RUNTIME_HOOK}" \
  --collect-submodules backend \
  --collect-submodules frontend \
  --exclude-module torch \
  --exclude-module onnxruntime \
  --exclude-module pandas \
  --exclude-module pyarrow \
  --exclude-module av \
  --exclude-module numba \
  --exclude-module llvmlite \
  --exclude-module pytest \
  --exclude-module openpyxl \
  --exclude-module lxml \
  --exclude-module sqlalchemy \
  --exclude-module jinja2 \
  --add-data "${REPO_ROOT}/backend:backend" \
  --add-data "${REPO_ROOT}/frontend:frontend" \
  demo_entry.py

BUILT_APP="${DIST_ROOT}/${APP_NAME}.app"
if [[ ! -d "${BUILT_APP}" ]]; then
  echo "Build output not found: ${BUILT_APP}" >&2
  exit 1
fi

echo "Preparing release folder..."
cp -R "${BUILT_APP}" "${RELEASE_DIR}/"
for f in README_DEMO.md DEMO_INSTRUCTIONS.md TESTER_QUICKSTART.md TESTER_QUICKSTART.html; do
  [[ -f "$f" ]] && cp "$f" "${RELEASE_DIR}/"
done
[[ -d docs/demo-guide ]] && cp -R docs/demo-guide "${RELEASE_DIR}/"
[[ -f soapboxx_config.demo.json ]] && cp soapboxx_config.demo.json "${RELEASE_DIR}/"
[[ -f .env.example ]] && cp .env.example "${RELEASE_DIR}/"

cat > "${RELEASE_DIR}/00_EXTRACT_THIS_ZIP_FIRST.txt" <<'TXT'
SoapBoxx Production Studio Demo (macOS)
========================================

1. Double-click the zip to unzip (or right-click → Open With → Archive Utility).
2. Open the unzipped folder.
3. Read TESTER_QUICKSTART.html for pictures and steps.
4. First launch: right-click "Launch SoapBoxx Production Studio Demo.command"
   → Open (macOS may block unsigned apps the first time).
   Or: Terminal → chmod +x "Launch SoapBoxx Production Studio Demo.command" → double-click.

If macOS says the app is damaged or from an unidentified developer:
  System Settings → Privacy & Security → Open Anyway
  (or right-click the .app → Open once).
TXT

cat > "${RELEASE_DIR}/Launch SoapBoxx Production Studio Demo.command" <<'CMD'
#!/bin/bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
APP="${DIR}/SoapBoxxProductionStudioDemo.app"
if [[ ! -d "$APP" ]]; then
  echo "Missing: $APP"
  echo "Unzip the full archive first."
  read -r -p "Press Enter to close..."
  exit 1
fi
export SOAPBOXX_BUCKET=demo
export SOAPBOXX_CONFIG_FILE="${DIR}/soapboxx_config.demo.json"
cd "$DIR"
open -a "$APP"
CMD
chmod +x "${RELEASE_DIR}/Launch SoapBoxx Production Studio Demo.command"

cat > "${RELEASE_DIR}/demo_release.json" <<JSON
{
  "name": "SoapBoxx Production Studio Demo",
  "version": "${VERSION}",
  "platform": "macos",
  "bucket": "demo"
}
JSON

echo "Creating zip archive..."
ditto -c -k --sequesterRsrc --keepParent "${RELEASE_DIR}" "${ZIP_PATH}"

echo ""
echo "Demo package ready:"
echo "  Folder: ${RELEASE_DIR}"
echo "  Zip:    ${ZIP_PATH}"
echo ""
echo "Tester run: double-click Launch SoapBoxx Production Studio Demo.command"
