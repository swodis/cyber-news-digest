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

If you hit SSL certificate errors while fetching RSS or article pages in a corporate network, no manual changes are required by default:

1. The script now detects `HTTP_PROXY`/`HTTPS_PROXY` and automatically retries with an
   insecure connection once if needed.
2. It will also reuse `DIGEST_CA_BUNDLE`, `REQUESTS_CA_BUNDLE`, or `SSL_CERT_FILE` automatically.

If you need strict TLS without fallback, set:

```bash
DIGEST_SSL_VERIFY=1 DIGEST_SSL_FALLBACK=0 ./run.sh
```

Prefer fixing CA trust on the host. You can point Requests at a custom CA file with:

```bash
export DIGEST_CA_BUNDLE=/path/to/ca-bundle.pem
./run.sh
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
