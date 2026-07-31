#!/usr/bin/env bash
# Portable fallback for Macs whose Command Line Tools cannot compile Swift.
# Personal data and credentials stay outside Heka.app.
set -euo pipefail

APP_ROOT="$(cd "$(dirname "$0")/../Resources/heka" && pwd)"
DATA_ROOT="$HOME/Library/Application Support/Heka"
mkdir -p "$DATA_ROOT"

export HEKA_DATA_DIR="$DATA_ROOT"
export HEKA_CONFIG_FILE="$DATA_ROOT/.env"
export HEKA_OPEN_BROWSER=1

# Port 0 lets the operating system select a free local port, avoiding the
# common 'address already in use' failure from a previous Heka session.
export HEKA_PORT=0
exec python3 "$APP_ROOT/server.py"
