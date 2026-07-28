#!/bin/zsh

# Double-click this file on macOS to start Heka and open it in your browser.
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Heka needs Python 3. Please install Python 3 first."
  read "?Press Enter to close..."
  exit 1
fi

echo "Starting Heka... Keep this window open while you use it."
python3 server.py
