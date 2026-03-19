# Cyber News Digest

Fetches, filters, summarizes and prepares cybersecurity news digests using a local LLM (Ollama).

## Setup

1. Copy `.env.example` to `.env` and optionally set:
   - `OLLAMA_URL` (default: `http://localhost:11434/api/generate`)
   - `OLLAMA_MODEL` (default: `qwen3:14b`)
   - `DIGEST_OUTPUT` (`json` for machine consumption, `text` for human-friendly output)
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
- Python packages from `requirements.txt`

## Output

By default, output is JSON to stdout with a list of summarized items.

```json
{
  "generatedAt": "...",
  "items": [...]
}
```

Switch to plain text mode with `DIGEST_OUTPUT=text`.
