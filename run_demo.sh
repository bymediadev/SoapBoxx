#!/bin/bash
set -euo pipefail

echo
echo "========================================"
echo " SoapBoxx Production Studio Demo"
echo "========================================"
echo

if [ ! -f "frontend/main_window.py" ]; then
  echo "[ERROR] Run this from SoapBoxx root folder."
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD="python"
else
  echo "[ERROR] Python is not installed or not in PATH."
  exit 1
fi

export SOAPBOXX_BUCKET="demo"
export SOAPBOXX_DEMO_EXPIRES_ON="2026-05-20"

echo "Launching demo mode..."
echo "  bucket=$SOAPBOXX_BUCKET"
echo "  expires_on=$SOAPBOXX_DEMO_EXPIRES_ON"
echo

$PYTHON_CMD frontend/main_window.py
