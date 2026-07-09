"""Fetch recent market-relevant headlines via NewsAPI. Returns headline text only."""
import logging
import os
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

NEWS_API_URL = "https://newsapi.org/v2/everything"
KEYWORDS = ["Nifty", "Sensex", "RBI", "Fed", "crude oil", "USD INR", "Indian markets"]
LOOKBACK_HOURS = 16
MAX_HEADLINES = 8


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
                "from": since,
                "sortBy": "publishedAt",
                "language": "en",
                "pageSize": MAX_HEADLINES,
                "apiKey": api_key,
            },
            timeout=15,
        )
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
    except Exception as exc:  # noqa: BLE001
        logger.warning("News fetch failed: %s", exc)
        return []

    headlines = []
    for article in articles[:MAX_HEADLINES]:
        title = article.get("title")
        source = (article.get("source") or {}).get("name", "unknown")
        if title:
            headlines.append({"title": title, "source": source})

    return headlines


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for h in fetch_news():
        print(f"[{h['source']}] {h['title']}")
