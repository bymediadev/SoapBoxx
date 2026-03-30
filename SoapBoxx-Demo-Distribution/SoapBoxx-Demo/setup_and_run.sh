#!/usr/bin/env bash
# SoapBoxx Demo — one-step setup and launch (macOS / Linux)
# After unzipping the GitHub Release:
#   chmod +x setup_and_run.sh
#   ./setup_and_run.sh
# Or double-click setup_and_run.command (macOS) after chmod +x.

set -e
cd "$(dirname "$0")"

echo ""
echo "========================================"
echo "  SoapBoxx Demo — setup and run"
echo "========================================"

if [[ ! -f "frontend/main_window.py" ]]; then
  echo ""
  echo "ERROR: Run this from inside the SoapBoxx-Demo folder (where frontend/main_window.py lives)."
  echo "Current folder: $(pwd)"
  exit 1
fi

if [[ ! -f "requirements_demo.txt" ]]; then
  echo "ERROR: requirements_demo.txt not found."
  exit 1
fi

PY=""
if command -v python3 >/dev/null 2>&1; then
  PY="python3"
elif command -v python >/dev/null 2>&1; then
  PY="python"
else
  echo ""
  echo "ERROR: Python 3.8+ not found. Install Python and ensure 'python3' is on your PATH."
  echo "  macOS: https://www.python.org/downloads/  or  brew install python@3"
  exit 1
fi

echo ""
echo "==> Using: $PY"
$PY --version

echo ""
echo "==> Installing dependencies (pip install -r requirements_demo.txt)"
$PY -m pip install -r requirements_demo.txt

echo ""
echo "==> Starting SoapBoxx Demo"
exec $PY frontend/main_window.py
