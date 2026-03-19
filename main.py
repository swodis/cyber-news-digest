#!/usr/bin/env python3
"""Cyber News Digest - Fetches, filters, summarizes and reports cybersecurity news."""

import json
import os
import re
from datetime import datetime
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# Configuration
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "news-sources.json"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:14b")
OUTPUT_MODE = os.environ.get("DIGEST_OUTPUT", "json").lower()

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 10
SCRAPE_TIMEOUT = 5


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def fetch_feed(source: dict) -> list[dict]:
    try:
        print(f"Fetching {source['name']}...")
        feed = feedparser.parse(
            source["url"],
            agent=USER_AGENT,
            request_headers={"User-Agent": USER_AGENT},
        )
        items = []
        for entry in feed.entries:
            content = ""
            if hasattr(entry, "content") and entry.content:
                content = entry.content[0].get("value", "")
            elif hasattr(entry, "content_encoded"):
                content = entry.content_encoded
            elif hasattr(entry, "description"):
                content = entry.description

            pub_date = datetime.now()
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                pub_date = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                pub_date = datetime(*entry.updated_parsed[:6])

            items.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "content": content,
                "pubDate": pub_date,
                "source": source["name"],
                "region": source.get("region", "global"),
            })
        return items
    except Exception as e:
        print(f"Error fetching {source['name']}: {e}")
        return []


def score_article(article: dict, keywords: list[str]) -> int:
    score = 0
    text = (article["title"] + " " + article["content"]).lower()

    for kw in keywords:
        if kw.lower() in text:
            score += 5

    if "zero-day" in text or "0-day" in text:
        score += 3
    if any(x in text for x in ["critical", "vulnerability", "cve-"]):
        score += 2
    if any(x in text for x in ["breach", "hack", "ransomware"]):
        score += 1

    today = datetime.now().date()
    if article["pubDate"].date() == today:
        score += 2

    return score


def summarize_with_ollama(text: str) -> str:
    if not text or len(text) < 100:
        return "Content too short to summarize."

    truncated = text[:6000]
    prompt = (
        "You are a cybersecurity analyst. Summarize the following article in a "
        "concise bulleted list (max 15 sentences total). "
        "Focus specifically on the impact to Europe and Scandinavia if mentioned. "
        "If no specific region is mentioned, focus on the technical severity and impact. "
        "Do not use markdown bolding in the summary text, just plain text.\n\n"
        "Article Text:\n"
        f"{truncated}"
    )

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
    except Exception as error:
        print(f"Ollama summary error: {error}")
        return "Failed to generate summary."


def scrape_content(url: str) -> str:
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=SCRAPE_TIMEOUT,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup.select("script, style, nav, footer, header, .ads, .comments"):
            tag.decompose()

        article = soup.find("article") or soup.find("main") or soup.find("body")
        if not article:
            return ""

        text = article.get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text).strip()
    except Exception:
        return ""


def build_plain_output(digest: list[dict]) -> str:
    lines = [f"Cyber News Digest - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"]
    lines.append("")
    for idx, item in enumerate(digest, 1):
        lines.append(f"{idx}. {item['title']}")
        lines.append(f"Source: {item['source']}")
        lines.append(f"Link: {item['link']}")
        lines.append(f"Score: {item['score']}")
        lines.append(f"Summary: {item['summary']}")
        lines.append("")
    return "\n".join(lines).strip()


def main() -> None:
    print(f"[{datetime.now().isoformat()}] Starting Cyber News Digest...")
    config = load_config()
    keywords = config.get("focusKeywords", [])

    all_articles = []
    for source in config["sources"]:
        all_articles.extend(fetch_feed(source))

    if not all_articles:
        print("No articles fetched from any source.")
        return

    seen_titles = set()
    unique_articles = []
    for art in all_articles:
        normalized = art["title"].lower().strip()
        if normalized not in seen_titles:
            seen_titles.add(normalized)
            unique_articles.append(art)

    for art in unique_articles:
        art["score"] = score_article(art, keywords)

    unique_articles.sort(key=lambda x: x["score"], reverse=True)
    top_articles = unique_articles[: config.get("maxArticles", 5)]

    if not top_articles:
        print("No articles found after filtering.")
        return

    print(f"Processing top {len(top_articles)} articles...")

    digest = []
    for article in top_articles:
        print(f"Summarizing: {article['title']}")
        text_to_summarize = article["content"]
        if len(text_to_summarize) < 500:
            scraped = scrape_content(article["link"])
            if len(scraped) > len(text_to_summarize):
                text_to_summarize = scraped

        summary = summarize_with_ollama(text_to_summarize)

        digest.append({
            "title": article["title"],
            "link": article["link"],
            "source": article["source"],
            "region": article["region"],
            "score": article["score"],
            "summary": summary,
            "generatedAt": datetime.now().isoformat(),
        })

    payload = {
        "generatedAt": datetime.now().isoformat(),
        "items": digest,
    }

    if OUTPUT_MODE == "text":
        print(build_plain_output(digest))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
