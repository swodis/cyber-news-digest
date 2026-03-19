#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

PYTHON_BIN="python3"
if [ -d .venv ]; then
  PYTHON_BIN=".venv/bin/python"
fi

if [ "${DIGEST_LOG:-0}" = "1" ]; then
  exec "$PYTHON_BIN" main.py >> /tmp/cyber-news-digest.log 2>&1
else
  exec "$PYTHON_BIN" main.py
fi
