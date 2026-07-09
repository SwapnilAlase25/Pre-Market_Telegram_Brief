"""Fetch recent market-relevant headlines via NewsAPI. Returns headline text only."""
import logging
import os
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

NEWS_API_URL = "https://newsapi.org/v2/everything"
# Quoted phrases so NewsAPI matches them exactly rather than any word in
# isolation — a bare "Fed" or "crude oil" (unquoted) matches unrelated
# articles that merely contain "fed" as a verb or "oil" in any context.
KEYWORDS = [
    '"Nifty"',
    '"Sensex"',
    '"RBI"',
    '"Federal Reserve"',
    '"crude oil"',
    '"USD INR"',
    '"rupee"',
    '"Indian stock market"',
    '"Indian equities"',
    '"Indian economy"',
]
# Restrict to financial/business news sources — cuts out crypto blogs, sports,
# and generic wire noise that would otherwise match loosely on a keyword.
DOMAINS = ",".join(
    [
        "moneycontrol.com",
        "economictimes.indiatimes.com",
        "livemint.com",
        "business-standard.com",
        "reuters.com",
        "cnbctv18.com",
        "bloombergquint.com",
        "ndtv.com",
    ]
)
# NewsAPI's free "Developer" plan embargoes very recent articles (roughly the
# last 24h don't show up yet), so a short lookback window can return zero
# results even when the key and query are fine. 48h gives a visible band.
LOOKBACK_HOURS = 48
FETCH_COUNT = 12
MAX_HEADLINES = 5

# NewsAPI's /everything matches keywords anywhere in the article body, so a
# domain-restricted query can still surface generic personal-finance pieces
# (e.g. "Starting a SIP?") that happen to mention "Sensex" once in passing.
# Require the *title itself* to contain a market-moving signal before we
# treat it as brief-worthy.
TITLE_SIGNAL_TERMS = [
    "nifty", "sensex", "rbi", "fed", "rupee", "crude", "oil",
    "market", "stock", "equit", "ipo", "gdp", "inflation",
    "earnings", "rally", "selloff", "sell-off", "correction",
    "bond", "yield", "fii", "dii", "q1", "q2", "q3", "q4",
]


def _title_is_relevant(title: str) -> bool:
    lowered = title.lower()
    return any(term in lowered for term in TITLE_SIGNAL_TERMS)


def fetch_news(api_key: str | None = None) -> list[dict]:
    """
    Fetch top headlines from the last ~16 hours matching market keywords.
    Returns a list of {"title": str, "source": str} dicts. Returns [] on any failure
    — callers must treat an empty list as "no news available", not fatal.
    """
    api_key = api_key or os.environ.get("NEWS_API_KEY")
    if not api_key:
        logger.warning("NEWS_API_KEY not set; skipping news fetch")
        return []

    since = (datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )
    query = " OR ".join(KEYWORDS)

    try:
        resp = requests.get(
            NEWS_API_URL,
            params={
                "q": query,
                "domains": DOMAINS,
                "from": since,
                "sortBy": "publishedAt",
                "language": "en",
                "pageSize": FETCH_COUNT,
                "apiKey": api_key,
            },
            timeout=15,
        )
        if not resp.ok:
            logger.warning("News fetch returned %s: %s", resp.status_code, resp.text[:500])
            return []
        body = resp.json()
        articles = body.get("articles", [])
        if not articles:
            logger.info("News fetch succeeded but returned 0 articles (status=%s totalResults=%s)",
                        body.get("status"), body.get("totalResults"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("News fetch failed: %s", exc)
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for h in fetch_news():
        print(f"[{h['source']}] {h['title']}")
