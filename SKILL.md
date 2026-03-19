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

Curates cybersecurity headlines for Cursor and VS Code workflows by fetching RSS sources, scoring relevance, scraping missing content, and emitting ready-to-use JSON payloads.

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

If you need plain-text output:

```bash
export DIGEST_OUTPUT=text
./run.sh
```

## Output

- JSON: object with `generatedAt` and `items`
- `items[]` includes:
  - `title`
  - `link`
  - `source`
  - `region`
  - `score`
  - `summary` (article text prepared for your model to summarize)

## How this is used in agent contexts

This skill is designed as an input-prep step for Cursor/VS Code assistants. It does not call a model itself; it prepares article text so your assistant can summarize it in-session.
