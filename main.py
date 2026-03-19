#!/usr/bin/env python3
"""Cyber News Digest - Fetches, filters, and prepares cybersecurity news."""

import json
import os
import re
from email.utils import parsedate_to_datetime
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

# Configuration
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "news-sources.json"
OUTPUT_MODE = os.environ.get("DIGEST_OUTPUT", "json").lower()
REQUEST_TIMEOUT = 12

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
SCRAPE_TIMEOUT = 5


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _child_text(node: ET.Element, names: set[str]) -> str:
    wanted = {name.lower() for name in names}
    for child in list(node):
        child_name = _local_name(child.tag).lower()
        if child_name in wanted:
            if child.text and child.text.strip():
                return child.text.strip()
            for attr in ("href", "url", "src"):
                if child.attrib.get(attr):
                    return child.attrib[attr].strip()

        for subchild in list(child):
            sub_name = _local_name(subchild.tag).lower()
            if sub_name in wanted:
                if subchild.text and subchild.text.strip():
                    return subchild.text.strip()
            if sub_name in {"encoded", "content", "description", "summary"}:
                if subchild.text and subchild.text.strip():
                    return subchild.text.strip()
    return ""


def _parse_pub_date(raw: str) -> datetime:
    if not raw:
        return datetime.now()

    try:
        parsed = parsedate_to_datetime(raw)
        return parsed.replace(tzinfo=None)
    except Exception:
        pass

    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except Exception:
            continue
    return datetime.now()


def fetch_feed(source: dict) -> list[dict]:
    try:
        print(f"Fetching {source['name']}...")
        response = requests.get(
            source["url"],
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        root = ET.fromstring(response.text)
        items: list[dict] = []
        candidates: list[ET.Element] = [*root.findall(".//item"), *root.findall(".//entry")]

        if not candidates:
            candidates = [
                node for node in root.iter()
                if _local_name(node.tag).lower() in {"item", "entry"}
            ]

        for node in candidates:
            title = _child_text(node, {"title"}) or node.findtext("title", default="").strip()
            link = (
                _child_text(node, {"link"})
                or node.attrib.get("href", "").strip()
                or ""
            )
            content = (
                _child_text(node, {"description", "content", "summary", "encoded"})
                or node.findtext("description", default="").strip()
                or ""
            )
            pub_raw = (
                _child_text(node, {"pubdate", "published", "updated"})
                or node.findtext("pubDate", default="")
                or node.findtext("published", default="")
                or node.findtext("updated", default="")
            )

            items.append({
                "title": title,
                "link": link,
                "content": content,
                "pubDate": _parse_pub_date(pub_raw),
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


def summarize_text_for_agent(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return "No article text available."
    if len(cleaned) > 6000:
        return cleaned[:6000] + "\n[... truncated]"
    return cleaned


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
        lines.append(f"Text for summary: {item['summary']}")
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
        print(f"Preparing article for Agent summary: {article['title']}")
        text_to_summarize = article["content"]
        if len(text_to_summarize) < 500:
            scraped = scrape_content(article["link"])
            if len(scraped) > len(text_to_summarize):
                text_to_summarize = scraped

        summary = summarize_text_for_agent(text_to_summarize)

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
