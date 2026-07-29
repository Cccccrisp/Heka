#!/usr/bin/env bash
set -euo pipefail

MODEL="${HEKA_OLLAMA_MODEL:-qwen3:8b}"

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed yet."
  echo "Install it from https://ollama.com/download, open Ollama once, then run this script again."
  exit 1
fi

echo "Downloading the local Heka organizer: ${MODEL}"
ollama pull "${MODEL}"
echo "Done. Start Heka with: python3 server.py"
