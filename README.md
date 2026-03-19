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

For environments with Node.js disabled or unavailable, Python-only setup works by default. If you need optional Node-based legacy support:

```bash
INSTALL_NODE_DEPS=1 ./setup.sh
```

For a single-command first run:

```bash
./start.sh
```

## Run

```bash
./run.sh
# or: python main.py
```

By default, `run.sh` writes output to stdout/stderr for agent parsing.
To keep the old log redirection behavior, set:

```bash
DIGEST_LOG=1 ./run.sh
```

## Requirements

- Python 3 with dependencies from `requirements.txt` (installed by `setup.sh`)
- Node.js + npm for optional legacy `index.js` usage

## Output

Output is written to stdout in this exact sectioned text format:

```text
Daily Security News Briefing — Month Day, Year

## Instructions for Overview
...
## Overview
• **headline title** (source)
  source link
  excerpt...

## Full Articles (N) — Summarize each in detail
## Article: ...
Source: ...
Link: ...
--- Content to summarize ---
...
--- End ---
```

Runtime diagnostics are sent to `stderr` only when `DIGEST_VERBOSE=1`.
