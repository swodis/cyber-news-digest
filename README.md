# Cyber News Digest

Fetches, filters, and scores cybersecurity news from RSS feeds. Outputs raw article content for the AI to summarize.

**No LLM API calls, no URLs in code, no secrets.** The script only fetches and prepares data. When you run it (e.g. "run it now" in Cursor), the AI in your context does the summarization.

## Requirements

- Node.js 18+

## Setup

```bash
cd cyber-news-digest
npm install
```

## Run

```bash
npm start
# or
./run.sh
# or
node index.js
```

## How it works

1. Fetches RSS feeds from sources in `news-sources.json`
2. Deduplicates, scores (Europe/Scandinavia focus, critical threats)
3. Outputs top articles with full content to stdout
4. **You** (or Cursor, VS Code AI) summarize the output in your context

## Configuration

Edit `news-sources.json` to change sources, regions, max articles, and focus keywords.

## Output

- **stdout**: Raw article content, ready for the AI to summarize
- **stderr**: Progress and logs

## Seen tracking

The skill stores shown article links in `data/seen.json` so each run shows only **new** articles. Entries are pruned after 30 days. Delete `data/seen.json` to reset.

## Portable

Copy the folder anywhere. No API keys, no model config, no URLs in code. Run `npm install` on the target machine.
