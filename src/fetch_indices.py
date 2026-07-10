"""Fetch index quotes via yfinance. Numeric data only — never touched by the LLM."""
import json
import logging
import math
import re

import requests
import yfinance as yf

logger = logging.getLogger(__name__)

TICKERS = {
    "nifty": "^NSEI",
    "gift_nifty": "^NSEI",  # placeholder, overridden by fetch_gift_nifty
    "dow": "^DJI",
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "ftse": "^FTSE",
    "dax": "^GDAXI",
    "nikkei": "^N225",
    "hsi": "^HSI",
    "kospi": "^KS11",
}


# A genuine single-day move beyond this for a major index (Nikkei/HSI/Kospi/
# Dow/etc.) is extraordinarily rare — more likely a stale/misaligned data
# point (e.g. diffed across a holiday gap) than reality. Flag it as unusable
# rather than silently displaying a bogus swing.
MAX_PLAUSIBLE_CHANGE_PCT = 15.0


def _from_fast_info(ticker: "yf.Ticker") -> dict | None:
    """
    Prefer yfinance's fast_info — Yahoo's own authoritative last-price /
    previous-close pair — over manually diffing two rows of history(), which
    is prone to misalignment (holiday gaps, partial intraday rows).
    Returns None if fast_info doesn't have usable values.
    """
    try:
        info = ticker.fast_info
        last_price = float(info["last_price"])
        prev_close = float(info["previous_close"])
    except (KeyError, TypeError, ValueError):
        return None

    if math.isnan(last_price) or math.isnan(prev_close) or prev_close == 0:
        return None

    change_pct = (last_price - prev_close) / prev_close * 100
    if math.isnan(change_pct):
        return None

    return {"price": round(last_price, 2), "change_pct": round(change_pct, 2)}


def _from_history(symbol: str) -> dict:
    """Fallback: diff the last two daily closes from history()."""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="5d")
    hist = hist.dropna(subset=["Close"])
    if hist.empty or len(hist) < 2:
        raise ValueError(f"insufficient history for {symbol}")
    prev_close = float(hist["Close"].iloc[-2])
    last_close = float(hist["Close"].iloc[-1])
    if math.isnan(prev_close) or math.isnan(last_close) or prev_close == 0:
        raise ValueError(f"invalid close values for {symbol}: prev={prev_close} last={last_close}")
    change_pct = (last_close - prev_close) / prev_close * 100
    if math.isnan(change_pct):
        raise ValueError(f"computed NaN change_pct for {symbol}")
    return {"price": round(last_close, 2), "change_pct": round(change_pct, 2)}


def _fetch_one(symbol: str) -> dict:
    """Return {'price': float, 'change_pct': float} for a single ticker, or raise."""
    ticker = yf.Ticker(symbol)
    result = _from_fast_info(ticker)
    if result is None:
        result = _from_history(symbol)

    if abs(result["change_pct"]) > MAX_PLAUSIBLE_CHANGE_PCT:
        raise ValueError(
            f"implausible change_pct for {symbol}: {result['change_pct']}% "
            f"(price={result['price']}) — treating as bad data"
        )

    return result


GIFT_NIFTY_URL = "https://groww.in/indices/global-indices/sgx-nifty"
GIFT_NIFTY_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}

# Field names Groww's frontend commonly uses for price/change on their
# Next.js-rendered pages. Matched case-insensitively.
PRICE_KEYS = {"ltp", "lastprice", "last_price", "value", "close", "cmp"}
CHANGE_PCT_KEYS = {
    "daychangeperc", "changepercentage", "chgpercent",
    "percentagechange", "change_perc", "pchange", "daychangeperc",
}
IDENTITY_KEYS = {"symbol", "name", "title", "displayname", "shortname"}
IDENTITY_HINTS = ("nifty", "gift", "sgx")


def _looks_like_gift_nifty(node: dict) -> bool:
    """Guard against grabbing a different index's numbers off the same page
    (it lists multiple global indices) — only trust a match if some
    identity-ish field on the same object actually mentions nifty/gift/sgx."""
    for key, value in node.items():
        if key.lower() in IDENTITY_KEYS and isinstance(value, str):
            lowered = value.lower()
            if any(hint in lowered for hint in IDENTITY_HINTS):
                return True
    return False


def _walk_json_for_gift_nifty_quote(node) -> tuple[float, float] | None:
    """Recursively search parsed page JSON for a dict that looks like the
    GIFT Nifty quote (has both a price-like and change%-like field, and an
    identity field confirming it's actually GIFT/SGX Nifty, not some other
    index on the same page)."""
    if isinstance(node, dict):
        lower_keys = {k.lower(): k for k in node.keys()}
        price_key = next((lower_keys[k] for k in lower_keys if k in PRICE_KEYS), None)
        change_key = next((lower_keys[k] for k in lower_keys if k in CHANGE_PCT_KEYS), None)
        if price_key and change_key and _looks_like_gift_nifty(node):
            try:
                return float(node[price_key]), float(node[change_key])
            except (TypeError, ValueError):
                pass
        for value in node.values():
            result = _walk_json_for_gift_nifty_quote(value)
            if result:
                return result
    elif isinstance(node, list):
        for item in node:
            result = _walk_json_for_gift_nifty_quote(item)
            if result:
                return result
    return None


def fetch_gift_nifty_scrape() -> dict:
    """
    Best-effort scrape of Groww's GIFT/SGX Nifty page. Groww is a Next.js
    site that embeds its initial data as JSON in a <script id="__NEXT_DATA__">
    tag server-side, so a plain HTTP GET (no JS execution) can often read it.
    Deliberately conservative: only trusts a match if it's tagged with an
    identity field mentioning nifty/gift/sgx, to avoid misattributing some
    other index's numbers as GIFT Nifty.
    """
    resp = requests.get(GIFT_NIFTY_URL, headers=GIFT_NIFTY_HEADERS, timeout=15)
    resp.raise_for_status()

    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL
    )
    if not match:
        raise ValueError("__NEXT_DATA__ block not found on Groww GIFT Nifty page")

    data = json.loads(match.group(1))
    result = _walk_json_for_gift_nifty_quote(data)
    if not result:
        raise ValueError("could not locate an identifiable GIFT Nifty quote in page data")

    price, change_pct = result
    logger.info("GIFT Nifty scrape matched: price=%s change_pct=%s", price, change_pct)

    if abs(change_pct) > MAX_PLAUSIBLE_CHANGE_PCT:
        raise ValueError(f"implausible GIFT Nifty change_pct: {change_pct}%")

    return {"price": round(price, 2), "change_pct": round(change_pct, 2)}


def fetch_gift_nifty() -> dict:
    """GIFT Nifty has no reliable yfinance ticker or broker-API coverage;
    try a page scrape first, then a couple of speculative yfinance tickers."""
    try:
        return fetch_gift_nifty_scrape()
    except Exception as exc:  # noqa: BLE001
        logger.warning("gift_nifty scrape failed: %s", exc)

    for symbol in ("NIFTY_F1.NS", "GIFTNIFTY.NS"):
        try:
            return _fetch_one(symbol)
        except Exception as exc:  # noqa: BLE001
            logger.warning("gift_nifty fallback %s failed: %s", symbol, exc)
    raise ValueError("GIFT Nifty data unavailable from all sources")


def fetch_indices() -> tuple[dict, list[str]]:
    """
    Fetch all index quotes. Never raises — each ticker is isolated.
    Returns (results, failed_keys).
    """
    results: dict = {}
    failed: list[str] = []

    for key, symbol in TICKERS.items():
        if key == "gift_nifty":
            continue
        try:
            results[key] = _fetch_one(symbol)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to fetch %s (%s): %s", key, symbol, exc)
            failed.append(key)

    try:
        results["gift_nifty"] = fetch_gift_nifty()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to fetch gift_nifty: %s", exc)
        failed.append("gift_nifty")

    return results, failed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data, failures = fetch_indices()
    for k, v in data.items():
        print(f"{k}: {v}")
    if failures:
        print("Failed:", failures)
