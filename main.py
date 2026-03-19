#!/usr/bin/env python3
"""Cyber News Digest - fetches, scores, and prepares cybersecurity headlines."""

import json
import os
import re
import sys
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

# Configuration
SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "news-sources.json"
SEEN_PATH = SCRIPT_DIR / "data" / "seen.json"
SEEN_RETENTION_DAYS = 30
REQUEST_TIMEOUT = 12
SCRAPE_TIMEOUT = 5
VERBOSE = os.environ.get("DIGEST_VERBOSE", "0").lower() in {"1", "true", "yes", "on"}


def _read_bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _proxy_is_configured() -> bool:
    return bool(
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
        or os.environ.get("ALL_PROXY")
        or os.environ.get("all_proxy")
    )


PROXY_CONFIGURED = _proxy_is_configured()
VERIFY_SSL = _read_bool_env("DIGEST_SSL_VERIFY", True)
SSL_FALLBACK = _read_bool_env("DIGEST_SSL_FALLBACK", PROXY_CONFIGURED)
CUSTOM_CA_BUNDLE = (
    os.environ.get("DIGEST_CA_BUNDLE")
    or os.environ.get("REQUESTS_CA_BUNDLE")
    or os.environ.get("SSL_CERT_FILE")
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

REGION_KEYWORDS = ["europe", "eu", "scandinavia", "nordic", "sweden", "norway", "finland", "denmark", "baltic", "lithuania", "latvia", "estonia"]
REGION_SCORE = 8
FOCUS_SCORE = 5


def log(message: str) -> None:
    if VERBOSE:
        print(message, file=sys.stderr)


def request_get(url: str, timeout: int) -> requests.Response:
    verify_setting = VERIFY_SSL
    if CUSTOM_CA_BUNDLE:
        verify_setting = CUSTOM_CA_BUNDLE

    try:
        return requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            verify=verify_setting,
        )
    except requests.exceptions.SSLError as error:
        print(f"SSL error while requesting {url}: {error}", file=sys.stderr)
        if SSL_FALLBACK and VERIFY_SSL:
            if PROXY_CONFIGURED:
                log("Corporate proxy detected; retrying request with SSL verification disabled.")
            else:
                log("Retrying request with SSL verification disabled.")
            return requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, verify=False)
        raise


def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_seen() -> set[str]:
    try:
        with open(SEEN_PATH, encoding="utf-8") as f:
            data = json.load(f)
            cutoff = datetime.now().date() - timedelta(days=SEEN_RETENTION_DAYS)
            entries = (data.get("entries") or []) if isinstance(data, dict) else []
            return {
                item.get("link")
                for item in entries
                if isinstance(item, dict)
                and item.get("shownAt")
                and datetime.fromisoformat(item["shownAt"]).date() >= cutoff
            }
    except Exception:
        return set()


def save_seen(new_links: set[str]) -> None:
    today = datetime.now().date().isoformat()
    cutoff = datetime.now().date() - timedelta(days=SEEN_RETENTION_DAYS)

    entries: list[dict[str, str]] = []
    if SEEN_PATH.exists():
        try:
            with open(SEEN_PATH, encoding="utf-8") as f:
                data = json.load(f)
                existing = data.get("entries") if isinstance(data, dict) else None
                if isinstance(existing, list):
                    entries = existing
        except Exception:
            entries = []

    existing = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        shown_at = item.get("shownAt")
        try:
            if shown_at and datetime.fromisoformat(shown_at).date() >= cutoff:
                existing.append(item)
        except Exception:
            continue

    for link in sorted(new_links):
        existing.append({"link": link, "shownAt": today})

    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump({"entries": existing, "lastUpdated": today}, f, indent=2, ensure_ascii=False)


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
        log(f"Fetching {source['name']}...")
        response = request_get(source["url"], timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        root = ET.fromstring(response.text)
        candidates: list[ET.Element] = [*root.findall(".//item"), *root.findall(".//entry")]
        if not candidates:
            candidates = [node for node in root.iter() if _local_name(node.tag).lower() in {"item", "entry"}]

        items: list[dict] = []
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
        print(f"Error fetching {source['name']}: {e}", file=sys.stderr)
        return []


def score_article(article: dict, keywords: list[str]) -> int:
    score = 0
    text = (article["title"] + " " + article["content"]).lower()

    for keyword in keywords:
        lower = keyword.lower()
        if lower in REGION_KEYWORDS:
            if lower in text:
                score += REGION_SCORE
        elif lower in text:
            score += FOCUS_SCORE

    if "zero-day" in text or "0-day" in text:
        score += 3
    if any(tag in text for tag in ["critical", "vulnerability", "cve-"]):
        score += 2
    if any(tag in text for tag in ["breach", "hack", "ransomware"]):
        score += 1

    if article["pubDate"].date() == datetime.now().date():
        score += 2

    return score


def scrape_content(url: str) -> str:
    try:
        response = request_get(url, timeout=SCRAPE_TIMEOUT)
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


def print_for_ai(overview: list[dict], full_articles: list[dict]) -> str:
    sep = "─" * 60
    date_str = datetime.now().strftime("%B %d, %Y").replace(" 0", " ")

    lines = [
        "",
        sep,
        f"Daily Security News Briefing — {date_str}",
        sep,
        "",
        "## Instructions for Overview",
        "",
        "Produce an Overview first, structured as follows. Use the headlines and article content below to populate each section. Place items where they fit best. Use \"───\" as section dividers.",
        "",
        "**🌍 Global Headlines (Last 24 Hours)**",
        "2–4 major worldwide incidents: ransomware, breaches, zero-days, critical vulnerabilities. One paragraph per item.",
        "",
        "**🇪🇺 European & Nordic Developments**",
        "EU/Nordic-specific news: nation-state activity, regional partnerships, elections, critical infrastructure. One paragraph per item.",
        "",
        "**📜 Regulatory & Compliance Updates**",
        "GDPR, NIS2, new legislation, enforcement actions. ",
        "",
        "**⚠️ Threat Landscape Summary**",
        "Bullet summary of: ransomware trends, notable threat actors, and key vulnerabilities/CVEs to patch (with severity where known).",
        "",
        f"Then provide detailed summaries of the {len(full_articles)} full articles below.",
        "",
        sep,
        "## Overview",
    ]

    for idx, headline in enumerate(overview, start=1):
        excerpt = re.sub(r"\s+", " ", (headline["content"] or "").strip())[:400]
        lines.append(f"{idx}. {headline['title']} ({headline['source']})")
        lines.append(f"   Link: {headline['link']}")
        lines.append(f"   Region: {headline['region']}")
        if excerpt:
            lines.append(f"   Excerpt: {excerpt}...")
        lines.append(f"   Score: {headline['score']}")
        lines.append("")

    lines.append(sep)
    lines.append("")
    lines.append(f"## Full Articles ({len(full_articles)}) — Summarize each in detail")
    lines.append(sep)
    lines.append("")

    for article in full_articles:
        lines.append(f"## Article: {article['title']}")
        lines.append(f"Source: {article['source']}")
        lines.append(f"Link: {article['link']}")
        lines.append("")
        lines.append("--- Content to summarize ---")
        lines.append(article["content"])
        lines.append("")
        lines.append("--- End ---")
        lines.append("")

    lines.append(sep)
    return "\n".join(lines).strip()


def main() -> None:
    log(f"[{datetime.now().isoformat()}] Fetching cyber news...")
    config = load_config()
    keywords = config.get("focusKeywords", [])
    seen_links = load_seen()

    all_articles = []
    for source in config["sources"]:
        all_articles.extend(fetch_feed(source))

    if not all_articles:
        print("No articles fetched.", file=sys.stderr)
        return

    unique_articles = []
    seen_titles = set()
    for article in all_articles:
        normalized = article["title"].lower().strip()
        if normalized not in seen_titles:
            seen_titles.add(normalized)
            unique_articles.append(article)

    new_articles = [article for article in unique_articles if article["link"] not in seen_links]
    if not new_articles:
        print("No new articles since the last run.", file=sys.stderr)
        return

    for article in new_articles:
        article["score"] = score_article(article, keywords)

    new_articles.sort(key=lambda item: item["score"], reverse=True)

    overview_pool = min(config.get("overviewPool", 25), len(new_articles), 5)
    max_full = min(config.get("maxArticles", 5), 5)
    headlines = new_articles[:overview_pool]
    top_articles = new_articles[:max_full]

    if not top_articles:
        print("No articles found after filtering.", file=sys.stderr)
        return

    log(f"Enriching {len(top_articles)} full articles (scraping where needed)...")
    for article in top_articles:
        if len(article["content"]) < 500:
            scraped = scrape_content(article["link"])
            if len(scraped) > len(article["content"]):
                article["content"] = scraped
        if len(article["content"]) > 6000:
            article["content"] = article["content"][:6000] + "\n[... truncated]"

    print(print_for_ai(headlines, top_articles))

    links_to_save = {
        *[h["link"] for h in headlines if h.get("link")],
        *[a["link"] for a in top_articles if a.get("link")],
    }
    save_seen(links_to_save)
    log("Done. Summarize the overview and articles above.")


if __name__ == "__main__":
    main()
