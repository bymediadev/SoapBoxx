#!/bin/bash
# macOS: double-click in Finder (runs Terminal). If macOS blocks it:
#   Right-click → Open, or: chmod +x setup_and_run.command
cd "$(dirname "$0")"
exec bash "$(dirname "$0")/setup_and_run.sh"
