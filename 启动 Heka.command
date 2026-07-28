#!/bin/zsh

# Double-click this file on macOS to start Heka and open it in your browser.
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Heka needs Python 3. Please install Python 3 first."
  read "?Press Enter to close..."
  exit 1
fi

echo "Starting Heka... Keep this window open while you use it."
HEKA_OPEN_BROWSER=0 python3 server.py &
HEKA_PID=$!

# Wait until the local service is actually ready, then use macOS's own opener.
for _ in {1..20}; do
  if /usr/bin/curl --silent --fail http://127.0.0.1:8787/api/v1/health >/dev/null 2>&1; then
    /usr/bin/open "http://127.0.0.1:8787"
    echo "Heka is open in your browser. Keep this window open while you use it."
    wait "$HEKA_PID"
    exit $?
  fi
  sleep 0.25
done

echo "Heka could not start. Check the message above, then press Enter to close."
wait "$HEKA_PID"
