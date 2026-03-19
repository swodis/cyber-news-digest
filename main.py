#!/usr/bin/env python3
"""
Cyber News Digest - Fetches, filters, summarizes and reports cybersecurity news using local LLM.
"""

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

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "news-sources.json"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:14b")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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

    prompt = """You are a cybersecurity analyst. Summarize the following article in a concise bulleted list (max 15 sentences total).
Focus specifically on the impact to Europe and Scandinavia if mentioned.
If no specific region is mentioned, focus on the technical severity and impact.
Do not use markdown bolding in the summary text, just plain text.

Article Text:
"""
    prompt += truncated

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": MODEL, "prompt": prompt, "stream": False},
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    except Exception as e:
        print(f"Ollama summary error: {e}")
        return "Failed to generate summary."


def scrape_content(url: str) -> str:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=SCRAPE_TIMEOUT,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup.select("script, style, nav, footer, header, .ads, .comments"):
            tag.decompose()

        article = soup.find("article") or soup.find("main") or soup.find("body")
        if not article:
            return ""
        text = article.get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text).strip()
    except Exception:
        return ""


def send_to_telegram(message: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("TELEGRAM_TOKEN and TELEGRAM_CHAT_ID must be set.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    params = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }

    try:
        resp = requests.post(url, params=params, timeout=REQUEST_TIMEOUT)
        if not resp.ok:
            print(f"Telegram send error (API): {resp.text}")
        else:
            print("Message sent to Telegram.")
    except Exception as e:
        print(f"Telegram send error (Network): {e}")


def escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def main() -> None:
    print(f"[{datetime.now().isoformat()}] Starting Cyber News Digest...")
    config = load_config()
    keywords = config.get("focusKeywords", [])

    all_articles = []
    for source in config["sources"]:
        items = fetch_feed(source)
        all_articles.extend(items)

    if not all_articles:
        print("No articles fetched from any source.")
        return

    seen_titles = set()
    unique = []
    for art in all_articles:
        norm = art["title"].lower().strip()
        if norm not in seen_titles:
            seen_titles.add(norm)
            unique.append(art)

    for art in unique:
        art["score"] = score_article(art, keywords)

    unique.sort(key=lambda a: a["score"], reverse=True)
    top = unique[: config.get("maxArticles", 5)]

    if not top:
        print("No articles found after filtering.")
        return

    print(f"Processing top {len(top)} articles...")

    send_to_telegram(
        f"<b>🇪🇺 Cyber News Brief</b> ({datetime.now().strftime('%Y-%m-%d')})\n"
        f"<i>Top stories focused on Europe/Scandinavia & Critical Threats</i>"
    )

    for article in top:
        print(f"Summarizing: {article['title']}")

        text_to_summarize = article["content"]
        if len(text_to_summarize) < 500:
            scraped = scrape_content(article["link"])
            if len(scraped) > len(text_to_summarize):
                text_to_summarize = scraped

        summary = summarize_with_ollama(text_to_summarize)

        safe_title = escape_html(article["title"])
        safe_source = escape_html(article["source"])
        safe_summary = escape_html(summary)

        message = (
            f"<b>{safe_title}</b>\n"
            f"<a href=\"{article['link']}\">Source: {safe_source}</a>\n\n"
            f"{safe_summary}"
        )
        send_to_telegram(message)

    print("Done.")


if __name__ == "__main__":
    main()
