#!/bin/zsh

# Double-click this file on macOS to start Heka and open it in your browser.
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Heka needs Python 3. Please install Python 3 first."
  read "?Press Enter to close..."
  exit 1
fi

for HEKA_PORT in 8787 8788 8789; do
  HEKA_URL="http://127.0.0.1:${HEKA_PORT}"

  # An already-running Heka should be reused, not started a second time.
  if /usr/bin/curl --silent --fail "${HEKA_URL}/api/v1/health" >/dev/null 2>&1; then
    /usr/bin/open "${HEKA_URL}"
    echo "Heka is already running and is now open in your browser."
    exit 0
  fi

  # Leave a port used by another app alone and try the next local port.
  if /usr/sbin/lsof -nP -iTCP:"${HEKA_PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
    continue
  fi

  echo "Starting Heka... Keep this window open while you use it."
  HEKA_OPEN_BROWSER=0 HEKA_PORT="${HEKA_PORT}" python3 server.py &
  HEKA_PID=$!
  for _ in {1..20}; do
    if /usr/bin/curl --silent --fail "${HEKA_URL}/api/v1/health" >/dev/null 2>&1; then
      /usr/bin/open "${HEKA_URL}"
      echo "Heka is open in your browser. Keep this window open while you use it."
      wait "$HEKA_PID"
      exit $?
    fi
    sleep 0.25
  done
  wait "$HEKA_PID" 2>/dev/null
done

echo "Heka could not find an available local port. Press Enter to close."
read "?"
