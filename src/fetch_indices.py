"""Fetch index quotes via yfinance. Numeric data only — never touched by the LLM."""
import logging

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


def _fetch_one(symbol: str) -> dict:
    """Return {'price': float, 'change_pct': float} for a single ticker, or raise."""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="5d")
    if hist.empty or len(hist) < 2:
        raise ValueError(f"insufficient history for {symbol}")
    prev_close = hist["Close"].iloc[-2]
    last_close = hist["Close"].iloc[-1]
    change_pct = (last_close - prev_close) / prev_close * 100
    return {"price": round(float(last_close), 2), "change_pct": round(float(change_pct), 2)}


def fetch_gift_nifty() -> dict:
    """GIFT Nifty has no reliable yfinance ticker; try a couple of fallbacks."""
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
