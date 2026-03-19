import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';
import Parser from 'rss-parser';
import fetch from 'node-fetch';
import * as cheerio from 'cheerio';

// No URLs, no API calls. Fetches RSS, scores, outputs raw content for the AI (Cursor, etc.) to summarize.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CONFIG_PATH = path.join(__dirname, 'news-sources.json');
const SEEN_PATH = path.join(__dirname, 'data', 'seen.json');
const SEEN_RETENTION_DAYS = 30;

const parser = new Parser({
    headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    },
    customFields: {
        item: ['content:encoded', 'description']
    }
});

async function loadConfig() {
    const data = await fs.readFile(CONFIG_PATH, 'utf8');
    return JSON.parse(data);
}

async function loadSeen() {
    try {
        const data = await fs.readFile(SEEN_PATH, 'utf8');
        const json = JSON.parse(data);
        const cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - SEEN_RETENTION_DAYS);
        const cutoffStr = cutoff.toISOString().slice(0, 10);
        const entries = (json.entries || []).filter(e => (e.shownAt || '') >= cutoffStr);
        return new Set(entries.map(e => e.link));
    } catch {
        return new Set();
    }
}

async function saveSeen(newLinks) {
    const today = new Date().toISOString().slice(0, 10);
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - SEEN_RETENTION_DAYS);
    const cutoffStr = cutoff.toISOString().slice(0, 10);

    let entries = [];
    try {
        const data = await fs.readFile(SEEN_PATH, 'utf8');
        entries = JSON.parse(data).entries || [];
    } catch {
        // File doesn't exist or is invalid
    }

    for (const link of newLinks) {
        entries.push({ link, shownAt: today });
    }
    entries = entries.filter(e => (e.shownAt || '') >= cutoffStr);

    await fs.mkdir(path.dirname(SEEN_PATH), { recursive: true });
    await fs.writeFile(SEEN_PATH, JSON.stringify({ entries, lastUpdated: today }, null, 2), 'utf8');
}

async function fetchFeed(source) {
    try {
        console.error(`Fetching ${source.name}...`);
        const feed = await parser.parseURL(source.url);
        return feed.items.map(item => ({
            title: item.title,
            link: item.link,
            content: item['content:encoded'] || item.content || item.description || '',
            pubDate: item.pubDate ? new Date(item.pubDate) : new Date(),
            source: source.name,
            region: source.region
        }));
    } catch (error) {
        console.error(`Error fetching ${source.name}: ${error.message}`);
        return [];
    }
}

// Europe/Scandinavia get higher weight than other keywords
const REGION_KEYWORDS = ['europe', 'eu', 'scandinavia', 'nordic', 'sweden', 'norway', 'finland', 'denmark', 'baltic', 'lithuania', 'latvia', 'estonia'];
const REGION_SCORE = 8;
const FOCUS_SCORE = 5;

function scoreArticle(article, keywords) {
    let score = 0;
    const text = (article.title + ' ' + article.content).toLowerCase();

    keywords.forEach(kw => {
        const lower = kw.toLowerCase();
        if (REGION_KEYWORDS.includes(lower)) {
            if (text.includes(lower)) score += REGION_SCORE;
        } else if (text.includes(lower)) {
            score += FOCUS_SCORE;
        }
    });

    if (text.includes('zero-day') || text.includes('0-day')) score += 3;
    if (text.includes('critical') || text.includes('vulnerability') || text.includes('cve-')) score += 2;
    if (text.includes('breach') || text.includes('hack') || text.includes('ransomware')) score += 1;

    const today = new Date();
    if (article.pubDate.toDateString() === today.toDateString()) score += 2;

    return score;
}

async function scrapeContent(url) {
    try {
        const res = await fetch(url, {
            timeout: 5000,
            headers: {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        });
        const html = await res.text();
        const $ = cheerio.load(html);

        $('script, style, nav, footer, header, .ads, .comments').remove();

        let text = $('article').text() || $('main').text() || $('body').text();
        return text.replace(/\s+/g, ' ').trim();
    } catch (e) {
        return "";
    }
}

function printForAI(headlines, fullArticles) {
    const sep = '─'.repeat(60);
    const dateStr = new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });

    console.log(`\n${sep}`);
    console.log(`Daily Security News Briefing — ${dateStr}`);
    console.log(sep);
    console.log(`
## Instructions for Overview

Produce an Overview first, structured as follows. Use the headlines and article content below to populate each section. Place items where they fit best. Use "───" as section dividers.

**🌍 Global Headlines (Last 24 Hours)**
2–4 major worldwide incidents: ransomware, breaches, zero-days, critical vulnerabilities. One paragraph per item.

**🇪🇺 European & Nordic Developments**
EU/Nordic-specific news: nation-state activity, regional partnerships, elections, critical infrastructure. One paragraph per item.

**📜 Regulatory & Compliance Updates**
GDPR, NIS2, new legislation, enforcement actions. One paragraph per item.

**⚠️ Threat Landscape Summary**
Bullet summary of: ransomware trends, notable threat actors, and key vulnerabilities/CVEs to patch (with severity where known).

Then provide detailed summaries of the ${fullArticles.length} full articles below.
`);
    console.log(`${sep}\n`);
    console.log(`## Headlines (for Overview)\n`);
    for (const h of headlines) {
        const excerpt = (h.content || '').replace(/\s+/g, ' ').trim().substring(0, 400);
        console.log(`• **${h.title}** (${h.source})`);
        console.log(`  ${h.link}`);
        if (excerpt) console.log(`  ${excerpt}...`);
        console.log('');
    }
    console.log(`${sep}`);
    console.log(`\n## Full Articles (${fullArticles.length}) — Summarize each in detail\n`);
    console.log(sep);

    for (const article of fullArticles) {
        console.log(`\n## Article: ${article.title}`);
        console.log(`Source: ${article.source}`);
        console.log(`Link: ${article.link}`);
        console.log(`\n--- Content to summarize ---\n`);
        console.log(article.content);
        console.log(`\n--- End ---\n`);
    }
    console.log(sep);
}

async function main() {
    console.error(`[${new Date().toISOString()}] Fetching cyber news...`);
    const config = await loadConfig();
    const keywords = config.focusKeywords || [];
    const seenLinks = await loadSeen();

    let allArticles = [];
    for (const source of config.sources) {
        const items = await fetchFeed(source);
        allArticles = allArticles.concat(items);
    }

    if (allArticles.length === 0) {
        console.error("No articles fetched.");
        return;
    }

    const uniqueArticles = [];
    const seenTitles = new Set();
    for (const art of allArticles) {
        const normTitle = art.title.toLowerCase().trim();
        if (!seenTitles.has(normTitle)) {
            seenTitles.add(normTitle);
            uniqueArticles.push(art);
        }
    }

    // Filter out articles already shown (by link)
    const newArticles = uniqueArticles.filter(a => !seenLinks.has(a.link));
    if (newArticles.length === 0) {
        console.log("No new articles since the last run.");
        return;
    }

    newArticles.forEach(a => a.score = scoreArticle(a, keywords));
    newArticles.sort((a, b) => b.score - a.score);

    const overviewPool = Math.min(config.overviewPool || 25, newArticles.length);
    const maxFull = config.maxArticles || 5;
    const headlines = newArticles.slice(0, overviewPool);
    const topArticles = newArticles.slice(0, maxFull);

    console.error(`Enriching ${topArticles.length} full articles (scraping where needed)...`);

    for (const article of topArticles) {
        if (article.content.length < 500) {
            const scraped = await scrapeContent(article.link);
            if (scraped.length > article.content.length) {
                article.content = scraped;
            }
        }
        if (article.content.length > 6000) {
            article.content = article.content.substring(0, 6000) + "\n[... truncated]";
        }
    }

    printForAI(headlines, topArticles);

    const linksToSave = [...new Set([...headlines.map(h => h.link), ...topArticles.map(a => a.link)])];
    await saveSeen(linksToSave);
    console.error("Done. Summarize the overview and articles above.");
}

main().catch(err => {
    console.error(err);
    process.exit(1);
});
