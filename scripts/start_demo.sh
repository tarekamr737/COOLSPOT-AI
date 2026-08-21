#!/bin/sh
set -eu

api_port="${API_PORT:-8000}"
web_port="${PORT:-7860}"

python -m uvicorn api.app.main:app --host 127.0.0.1 --port "$api_port" &
api_pid=$!

cleanup() {
  kill "$api_pid" 2>/dev/null || true
  wait "$api_pid" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

API_BASE_URL="http://127.0.0.1:${api_port}" \
HOSTNAME="0.0.0.0" \
PORT="$web_port" \
node web/server.js
