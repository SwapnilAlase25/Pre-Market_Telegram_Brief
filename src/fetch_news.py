"""Fetch recent market/global-news headlines. Returns headline text only.

Primary source is live RSS feeds (no publish-delay embargo, no API key
needed). NewsAPI is kept as a fallback for when RSS feeds are unreachable.
"""
import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import requests

logger = logging.getLogger(__name__)

LOOKBACK_HOURS = 20
MAX_HEADLINES = 5
FETCH_COUNT = 12
REQUEST_TIMEOUT = 10
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PreMarketBrief/1.0)"}

# Markets (India-focused) + global/geopolitical wires — war, sanctions, and
# similar events move oil/currency/equity markets even without a "Sensex"
# mention in the headline itself.
RSS_FEEDS = [
    ("Moneycontrol Markets", "https://www.moneycontrol.com/rss/marketreports.xml"),
    ("Moneycontrol Business", "https://www.moneycontrol.com/rss/business.xml"),
    ("Economic Times Markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Business Standard Markets", "https://www.business-standard.com/rss/markets-106.rss"),
    ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
]

# NewsAPI fallback config (used only if all RSS feeds fail/return nothing).
NEWS_API_URL = "https://newsapi.org/v2/everything"
NEWS_API_KEYWORDS = [
    '"Nifty"', '"Sensex"', '"RBI"', '"Federal Reserve"', '"crude oil"',
    '"USD INR"', '"rupee"', '"Indian stock market"', '"war"', '"ceasefire"',
    '"sanctions"', '"Israel"', '"Iran"', '"Ukraine"', '"Russia"',
]
NEWS_API_DOMAINS = ",".join(
    [
        "moneycontrol.com", "economictimes.indiatimes.com", "livemint.com",
        "business-standard.com", "reuters.com", "cnbctv18.com",
        "bloombergquint.com", "ndtv.com", "bbc.com", "aljazeera.com",
    ]
)
# NewsAPI's free "Developer" plan embargoes very recent articles (roughly
# the last 24h don't show up yet), so a short lookback window can return
# zero/stale results even when the key and query are fine.
NEWS_API_LOOKBACK_HOURS = 48

# Title must contain one of these before we treat it as brief-worthy —
# covers both markets/finance and geopolitical/war terms that move markets
# (oil, currency, risk sentiment) even without an explicit finance word.
TITLE_SIGNAL_TERMS = [
    # markets / finance
    "nifty", "sensex", "rbi", "fed", "rupee", "crude", "oil",
    "market", "stock", "equit", "ipo", "gdp", "inflation",
    "earnings", "rally", "selloff", "sell-off", "correction",
    "bond", "yield", "fii", "dii", "q1", "q2", "q3", "q4", "tariff",
    "trade deal", "trade war",
    # geopolitical / war — routinely move oil, currencies, and risk sentiment
    "war", "ceasefire", "conflict", "sanction", "strike", "attack",
    "missile", "troops", "military", "geopolit", "nato",
    "israel", "iran", "gaza", "ukraine", "russia", "china", "taiwan",
    "opec", "border",
]


def _title_is_relevant(title: str) -> bool:
    lowered = title.lower()
    return any(term in lowered for term in TITLE_SIGNAL_TERMS)


def _parse_pubdate(raw: str | None):
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (TypeError, ValueError):
        return None


def _fetch_rss_feed(name: str, url: str) -> list[dict]:
    items = []
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        for item in root.iter("item"):
            title_el = item.find("title")
            if title_el is None or not (title_el.text or "").strip():
                continue
            pubdate_el = item.find("pubDate")
            items.append(
                {
                    "title": title_el.text.strip(),
                    "source": name,
                    "published": _parse_pubdate(pubdate_el.text if pubdate_el is not None else None),
                }
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("RSS fetch failed for %s: %s", name, exc)
    return items


def fetch_news_rss() -> list[dict]:
    """Pull recent, relevant headlines from live RSS feeds — no API key, no
    publish-delay embargo. Returns [] if every feed fails."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    raw_items = []
    for name, url in RSS_FEEDS:
        raw_items.extend(_fetch_rss_feed(name, url))

    relevant = [
        item for item in raw_items
        if (item["published"] is None or item["published"] >= cutoff)
        and _title_is_relevant(item["title"])
    ]
    relevant.sort(
        key=lambda item: item["published"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    headlines = []
    seen_titles = set()
    for item in relevant:
        if item["title"] in seen_titles:
            continue
        seen_titles.add(item["title"])
        headlines.append({"title": item["title"], "source": item["source"]})
        if len(headlines) >= MAX_HEADLINES:
            break

    return headlines


def fetch_news_newsapi(api_key: str | None = None) -> list[dict]:
    """Fallback source: NewsAPI /everything. Returns [] on any failure."""
    api_key = api_key or os.environ.get("NEWS_API_KEY")
    if not api_key:
        logger.warning("NEWS_API_KEY not set; skipping NewsAPI fallback")
        return []

    since = (
        datetime.now(timezone.utc) - timedelta(hours=NEWS_API_LOOKBACK_HOURS)
    ).strftime("%Y-%m-%dT%H:%M:%S")
    query = " OR ".join(NEWS_API_KEYWORDS)

    try:
        resp = requests.get(
            NEWS_API_URL,
            params={
                "q": query,
                "domains": NEWS_API_DOMAINS,
                "from": since,
                "sortBy": "publishedAt",
                "language": "en",
                "pageSize": FETCH_COUNT,
                "apiKey": api_key,
            },
            timeout=15,
        )
        if not resp.ok:
            logger.warning("NewsAPI returned %s: %s", resp.status_code, resp.text[:500])
            return []
        body = resp.json()
        articles = body.get("articles", [])
        if not articles:
            logger.info(
                "NewsAPI succeeded but returned 0 articles (status=%s totalResults=%s)",
                body.get("status"), body.get("totalResults"),
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("NewsAPI fetch failed: %s", exc)
        return []

    headlines = []
    for article in articles:
        title = article.get("title")
        source = (article.get("source") or {}).get("name", "unknown")
        if title and _title_is_relevant(title):
            headlines.append({"title": title, "source": source})
        if len(headlines) >= MAX_HEADLINES:
            break

    return headlines


def fetch_news(api_key: str | None = None) -> list[dict]:
    """
    Fetch relevant, recent headlines. Tries live RSS feeds first (real-time,
    no embargo); falls back to NewsAPI if every RSS feed fails or returns
    nothing relevant. Returns [] only if both sources come up empty —
    callers must treat that as "no news available", not fatal.
    """
    headlines = fetch_news_rss()
    if headlines:
        return headlines

    logger.info("RSS feeds returned no relevant headlines; falling back to NewsAPI")
    return fetch_news_newsapi(api_key)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for h in fetch_news():
        print(f"[{h['source']}] {h['title']}")
