#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "$(dirname "$0")"

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

if [ -d .venv ]; then
  exec .venv/bin/python main.py >> /tmp/cyber-news-digest.log 2>&1
else
  exec python3 main.py >> /tmp/cyber-news-digest.log 2>&1
fi
