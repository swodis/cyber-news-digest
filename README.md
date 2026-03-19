# Cyber News Digest

Fetches, filters, and prepares cybersecurity news digests for local AI tools (Cursor/VS Code).

Cursor/VS Code can load this as a skill via `SKILL.md`.

## Setup

1. No model setup required.
2. Run:

```bash
./setup.sh
```
3. Edit `news-sources.json` to configure RSS feeds and keywords

For a single-command first run:

```bash
./start.sh
```

## Run

```bash
./run.sh
# or: python main.py
```

## Requirements

- Python 3 with dependencies from `requirements.txt` (installed by `setup.sh`)
- Node.js + npm for optional legacy `index.js` usage

## Output

By default, output is JSON to stdout with a list of extracted items ready for agent-side summarization.
The `summary` field contains the article text prepared for your model to summarize.

```json
{
  "generatedAt": "...",
  "items": [...]
}
```

Switch to plain text mode with `DIGEST_OUTPUT=text`.
