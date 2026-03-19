---
name: cyber-news-digest
description: "Pulls cybersecurity headlines from RSS sources, deduplicates and ranks them, then outputs structured context for downstream AI summarization."
metadata:
  openclaw:
    emoji: "🛡️"
    requires:
      bins:
        - python3
        - bash
---

# Cyber News Digest Skill

Curates cybersecurity headlines for Cursor and VS Code workflows by fetching RSS sources, scoring relevance, scraping missing content, and emitting exact sectioned text for the assistant to summarize.

## Quick Setup

From the project root:

```bash
./setup.sh
cp .env.example .env  # optional
```

## Run

```bash
./run.sh
```

### Cursor/VS Code agent contract

Use this command for machine consumption:

```bash
./run.sh
```

Parse **stdout** as this exact sectioned text:

- Overview instructions block
- `## Overview` section
- `## Full Articles (N) — Summarize each in detail` section

Treat anything on **stderr** as diagnostics.  
`run.sh` no longer redirects by default; set `DIGEST_LOG=1` only if you want logging to `/tmp/cyber-news-digest.log`.

## Output

The output content includes scraped article text under each full-article section, between:

- `--- Content to summarize ---`
- `--- End ---`

## How this is used in agent contexts

This skill is designed as an input-prep step for Cursor/VS Code assistants. It does not call a model itself; it prepares article text so your assistant can summarize it in-session.
