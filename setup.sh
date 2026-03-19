#!/usr/bin/env bash
set -euo pipefail

echo "Installing Cyber News Digest dependencies..."

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

if [[ "${INSTALL_NODE_DEPS:-0}" == "1" && -f package.json ]]; then
  if command -v npm >/dev/null 2>&1; then
    npm install
  else
    echo "npm not found. Skipping Node.js dependency installation."
  fi
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example. Review values before running."
fi

echo "Setup complete."
echo "Run: ./run.sh"
