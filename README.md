# Cyber News Digest

Fetches, filters, summarizes and reports cybersecurity news using a local LLM (Ollama). Sends a daily brief to Telegram.

## Setup

1. Copy `.env.example` to `.env` and set `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID`
2. Edit `news-sources.json` to configure RSS feeds and keywords
3. Create venv and install deps:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

```bash
./run.sh
# or: python main.py
```

## Requirements

- Ollama with `qwen3:14b` (or set `OLLAMA_MODEL`)
- Telegram bot token and chat ID
